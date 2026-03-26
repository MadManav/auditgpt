"""
app.py — Flask Routes & Blueprint (Person 3)
Handles web routes and orchestrates the full analysis pipeline.
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, make_response, session
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import traceback
import json
import csv
import os
import threading
import uuid

bp = Blueprint('main', __name__)



# Background job store: { job_id: { 'status': 'running'|'done'|'error', 'result': ..., 'error': ... } }
_jobs = {}

# ── Load NSE ticker list at startup ──
_TICKER_MAP = {}  # { "SYMBOL": "Company Name", ... }
_NAME_MAP = {}    # { "company name lower": "SYMBOL", ... }

def _load_ticker_list():
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "EQUITY_L.csv")
    if not os.path.exists(csv_path):
        return
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row.get("SYMBOL", "").strip()
            name = row.get("NAME OF COMPANY", "").strip()
            if symbol and name:
                _TICKER_MAP[symbol.upper()] = name
                _NAME_MAP[name.lower()] = symbol.upper()

_load_ticker_list()


def _resolve_ticker(user_input: str) -> str:
    """
    Resolve user input to an NSE ticker.
    1. If it's already a valid symbol → use it
    2. If it matches a company name (fuzzy) → return the symbol
    3. Otherwise → return input as-is
    """
    clean = user_input.strip().upper().replace(" ", "")

    # Direct ticker match (e.g. "TCS", "RELIANCE")
    if clean in _TICKER_MAP:
        return clean

    # Fuzzy match against company names
    query = user_input.strip().lower()
    
    # Exact name match
    if query in _NAME_MAP:
        return _NAME_MAP[query]

    # Partial match — find best match
    best_match = None
    best_score = 0
    for name_lower, symbol in _NAME_MAP.items():
        query_words = query.split()
        matches = sum(1 for w in query_words if w in name_lower)
        score = matches / len(query_words) if query_words else 0
        
        if score > best_score and score >= 0.5:
            best_score = score
            best_match = symbol

    if best_match:
        return best_match

    # Fallback: return cleaned input
    return clean


def _run_pipeline(ticker):
    """
    Run the full forensic analysis pipeline.
    Returns dict with all results or raises an exception.
    """
    from data.fetcher import fetch_financials, get_company_info
    from analysis.beneish import calculate_beneish_mscore, calculate_beneish_trend
    from analysis.signals import detect_fraud_signals, get_signal_summary
    from analysis.scorer import score_company, benchmark_against_peers

    # Step 1 — Fetch financial data
    financials = fetch_financials(ticker)
    if financials is None:
        raise ValueError(
            f"Could not fetch financial data for '{ticker}'. "
            f"Possible reasons: invalid ticker, company delisted/suspended, "
            f"insufficient historical data, or data source temporarily unavailable."
        )

    company_info = get_company_info(ticker)

    # Step 2 — Beneish M-Score
    beneish = calculate_beneish_mscore(financials)
    beneish_trend = calculate_beneish_trend(financials)

    # Step 3 — Fraud signal detection
    signals = detect_fraud_signals(financials)
    signal_summary = get_signal_summary(signals)

    # Step 5 — Risk scoring (needed before Step 8, so run before parallel block)
    score = score_company(financials, signals, beneish)

    # Step 6 — Peer benchmarking
    peer_comparison = benchmark_against_peers(ticker, financials)

    # ── Shared inputs for Gemini calls ──────────────────────────
    company_name = company_info.get("name", ticker) if company_info else ticker
    # Cap at 8 most recent years to reduce token count and speed up Gemini
    audit_years = [int(str(y)[:4]) for y in financials.get("years", [])][-8:]

    # ── Steps 4, 4b, 7, 8 — run in parallel ────────────────────
    from analysis.auditor_sentiment import analyze_auditor_sentiment
    from analysis.mda_sentiment import analyze_mda_sentiment, compute_mismatch
    from analysis.promoter_tracker import analyze_promoter_behaviour
    from ui.llm import generate_forensic_report

    def _get_auditor():
        return analyze_auditor_sentiment(ticker, company_name, audit_years)

    def _get_mda():
        return analyze_mda_sentiment(ticker, company_name, audit_years)

    def _get_promoter():
        return analyze_promoter_behaviour(ticker)

    def _get_report():
        return generate_forensic_report(
            ticker, company_info, financials, beneish,
            signals, signal_summary, score, peer_comparison
        )

    auditor_sentiment = None
    mda_sentiment     = None
    promoter_data     = None
    ai_report_json    = None

    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {
            ex.submit(_get_auditor):  "auditor",
            ex.submit(_get_mda):      "mda",
            ex.submit(_get_promoter): "promoter",
            ex.submit(_get_report):   "report",
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                result = future.result()
                if key == "auditor":
                    auditor_sentiment = result
                elif key == "mda":
                    mda_sentiment = result
                elif key == "promoter":
                    promoter_data = result
                elif key == "report":
                    ai_report_json = result
            except Exception as e:
                print(f"[app] Parallel task '{key}' failed: {e}")

    # ── Post-process auditor result ──────────────────────────────
    if auditor_sentiment is not None:
        auditor_sentiment["has_pdfs"] = False
        if not auditor_sentiment.get("years"):
            print("[app] Auditor analysis returned empty — creating placeholders")
            auditor_sentiment["years"] = [
                {
                    "year": yr, "source": "UNAVAILABLE", "sentiment_score": 50,
                    "opinion_type": "UNKNOWN", "auditor_name": "Data unavailable",
                    "auditor_changed": False, "going_concern": False,
                    "related_party_flag": False, "language_tone": "UNKNOWN",
                    "key_issues": ["API error — retry later"], "confidence": "NONE",
                } for yr in audit_years[-5:]
            ]
            auditor_sentiment["total_years"] = len(auditor_sentiment["years"])
            auditor_sentiment["avg_score"] = 50
        else:
            for y in auditor_sentiment["years"]:
                y["source"] = y.get("source", "AI_MEMORY")

    # ── Tone mismatch (needs both auditor + mda results) ─────────
    tone_mismatch = None
    if mda_sentiment and auditor_sentiment:
        try:
            tone_mismatch = compute_mismatch(auditor_sentiment, mda_sentiment)
        except Exception as e:
            print(f"[app] Tone mismatch failed: {e}")

    # Pre-serialize chart data to avoid Jinja2 Undefined→tojson crashes
    years = financials.get("years", []) if financials else []
    revenue = financials.get("revenue", []) if financials else []
    net_income = financials.get("net_income", []) if financials else []
    total_debt = financials.get("total_debt", []) if financials else []
    receivables = financials.get("receivables", []) if financials else []
    ocf = financials.get("operating_cash_flow", []) if financials else []

    # Compute YoY growth rates for anomaly deviation map
    def _yoy(values):
        result = [None]
        for i in range(1, len(values)):
            if values[i] is not None and values[i-1] is not None and values[i-1] != 0:
                result.append(round((values[i] - values[i-1]) / abs(values[i-1]) * 100, 1))
            else:
                result.append(None)
        return result

    # Compute red flag counts per year by severity
    _rf_counts = {}  # { year: {high: N, medium: N, low: N} }
    if signals:
        for sig in signals:
            yr = sig.get("year")
            sev = sig.get("severity", "low")
            if yr not in _rf_counts:
                _rf_counts[yr] = {"high": 0, "medium": 0, "low": 0}
            _rf_counts[yr][sev] = _rf_counts[yr].get(sev, 0) + 1
    _rf_sorted_years = sorted(_rf_counts.keys()) if _rf_counts else []

    chart_data = {
        "years": years,
        "revenue": revenue,
        "cashflow": ocf,
        "debt": total_debt,
        "mscoreYears": [item.get("year") for item in (beneish_trend or [])],
        "mscoreVals": [item.get("m_score") for item in (beneish_trend or [])],
        "sentYears": [],
        "sentScores": [],
        "peerMetrics": peer_comparison.get("company_metrics", {}) if peer_comparison else {},
        "peerAvgs": peer_comparison.get("peer_averages", {}) if peer_comparison else {},
        # Anomaly deviation map
        "anomalyYears": years[1:] if len(years) > 1 else [],
        "anomalyRevenue": _yoy(revenue)[1:] if len(revenue) > 1 else [],
        "anomalyDebt": _yoy(total_debt)[1:] if len(total_debt) > 1 else [],
        "anomalyReceivables": _yoy(receivables)[1:] if len(receivables) > 1 else [],
        "anomalyNetIncome": _yoy(net_income)[1:] if len(net_income) > 1 else [],
        # Red flag timeline chart
        "redFlagYears": _rf_sorted_years,
        "redFlagHigh": [_rf_counts[y]["high"] for y in _rf_sorted_years],
        "redFlagMedium": [_rf_counts[y]["medium"] for y in _rf_sorted_years],
        "redFlagLow": [_rf_counts[y]["low"] for y in _rf_sorted_years],
    }
    if auditor_sentiment and auditor_sentiment.get("years"):
        chart_data["sentYears"] = [y.get("year") for y in auditor_sentiment["years"]]
        chart_data["sentScores"] = [y.get("sentiment_score", 0) for y in auditor_sentiment["years"]]

    # MD&A vs Auditor mismatch chart data
    if tone_mismatch and tone_mismatch.get("years"):
        chart_data["mismatchYears"] = [y["year"] for y in tone_mismatch["years"]]
        chart_data["mismatchAuditor"] = [y["auditor_score"] for y in tone_mismatch["years"]]
        chart_data["mismatchMgmt"] = [y["mgmt_score"] for y in tone_mismatch["years"]]
        chart_data["mismatchGaps"] = [y["gap"] for y in tone_mismatch["years"]]
    else:
        chart_data["mismatchYears"] = []
        chart_data["mismatchAuditor"] = []
        chart_data["mismatchMgmt"] = []
        chart_data["mismatchGaps"] = []

    show_beneish = score.get("sector_used") not in {"Banking", "Financial Services", "Insurance"}

    results = {
        "ticker": ticker,
        "company_info": company_info,
        "financials": financials,
        "beneish": beneish if show_beneish else None,
        "beneish_trend": beneish_trend if show_beneish else None,
        "show_beneish": show_beneish,
        "signals": signals,
        "signal_summary": signal_summary,
        "auditor_sentiment": auditor_sentiment,
        "mda_sentiment": mda_sentiment,
        "tone_mismatch": tone_mismatch,
        "score": score,
        "peer_comparison": peer_comparison,
        "ai_report_json": ai_report_json,
        "promoter_data": promoter_data,
        "chart_data_json": json.dumps(chart_data),
    }

    return results


@bp.route('/')
def index():
    """Landing page with ticker search bar."""
    return render_template('index.html')


@bp.route('/analyze', methods=['POST'])
def analyze():
    """
    Immediately returns loading.html, kicks off pipeline in background thread.
    """
    raw_input = request.form.get('ticker', '').strip()
    if not raw_input:
        return render_template('index.html', error="Please enter a stock ticker or company name.")

    ticker = _resolve_ticker(raw_input)
    if '.' not in ticker:
        ticker = ticker + '.NS'

    # Quick validity check (takes 1-2 sec) before moving to loading screen
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        if stock.history(period="1d").empty:
            return render_template('index.html', error=f"Could not find valid data for '{ticker}'. It may be delisted, suspended, or invalid.")
    except Exception as e:
        return render_template('index.html', error=f"Error validating ticker '{ticker}'. It may be invalid.")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {'status': 'running', 'result': None, 'error': None}

    def _run():
        try:
            start_time = time.time()
            results = _run_pipeline(ticker)
            results['elapsed_time'] = round(time.time() - start_time, 1)
            _jobs[job_id]['result'] = results
            _jobs[job_id]['status'] = 'done'
        except ValueError as e:
            _jobs[job_id]['status'] = 'error'
            _jobs[job_id]['error'] = str(e)
        except Exception as e:
            traceback.print_exc()
            _jobs[job_id]['status'] = 'error'
            _jobs[job_id]['error'] = f"Analysis failed: {str(e)}"

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return render_template('loading.html', ticker=ticker, job_id=job_id)


@bp.route('/status/<job_id>')
def status(job_id):
    """Polling endpoint — returns JSON with status and redirect URL when done."""
    job = _jobs.get(job_id)
    if not job:
        return jsonify({'status': 'error', 'error': 'Job not found'}), 404
    if job['status'] == 'done':
        return jsonify({'status': 'done', 'redirect': url_for('main.report', job_id=job_id)})
    if job['status'] == 'error':
        return jsonify({'status': 'error', 'error': job['error']})
    return jsonify({'status': 'running'})


@bp.route('/report/<job_id>')
def report(job_id):
    """Render the final report once the job is done."""
    job = _jobs.get(job_id)
    if not job or job['status'] != 'done':
        return redirect(url_for('main.index'))
    results = job['result']
    return render_template('report.html', **results)