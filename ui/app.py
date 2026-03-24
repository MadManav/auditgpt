"""
app.py — Flask Routes & Blueprint (Person 3)
Handles web routes and orchestrates the full analysis pipeline.
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
import time
import traceback
import json
import csv
import os

bp = Blueprint('main', __name__)

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
        # Check if all query words appear in the company name
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

    # Step 4 — Auditor sentiment analysis (Gemini memory-based)
    try:
        from analysis.auditor_sentiment import analyze_auditor_sentiment
        company_name = company_info.get("name", ticker) if company_info else ticker
        audit_years = [int(str(y)[:4]) for y in financials.get("years", [])]
        auditor_sentiment = analyze_auditor_sentiment(ticker, company_name, audit_years)
        auditor_sentiment["has_pdfs"] = False
        # If returned empty years (API error), create placeholders
        if not auditor_sentiment.get("years"):
            print(f"[app] Auditor analysis returned empty — creating placeholders")
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
    except Exception as e:
        print(f"[app] Auditor sentiment failed: {e}")
        auditor_sentiment = None

    # Step 4b — MD&A (Management) tone analysis
    mda_sentiment = None
    tone_mismatch = None
    try:
        from analysis.mda_sentiment import analyze_mda_sentiment, compute_mismatch
        company_name = company_info.get("name", ticker) if company_info else ticker
        audit_years = [int(str(y)[:4]) for y in financials.get("years", [])]
        mda_sentiment = analyze_mda_sentiment(ticker, company_name, audit_years)
        if mda_sentiment and auditor_sentiment:
            tone_mismatch = compute_mismatch(auditor_sentiment, mda_sentiment)
    except Exception as e:
        print(f"[app] MD&A sentiment failed: {e}")

    # Step 5 — Risk scoring
    score = score_company(financials, signals, beneish)

    # Step 6 — Peer benchmarking
    peer_comparison = benchmark_against_peers(ticker, financials)

    # Step 7 — LLM forensic report (Gemini)
    try:
        from ui.llm import generate_forensic_report
        ai_report = generate_forensic_report(
            ticker, company_info, financials, beneish,
            signals, signal_summary, score, peer_comparison
        )
    except Exception:
        ai_report = None

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

    # RPT data — presence score per year (0 = no flag, 1 = flagged)
    rpt_years = []
    rpt_scores = []
    if auditor_sentiment and auditor_sentiment.get("years"):
        for y in auditor_sentiment["years"]:
            rpt_years.append(y.get("year"))
            rpt_scores.append(1 if y.get("related_party_flag") else 0)

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
        # RPT chart
        "rptYears": rpt_years,
        "rptScores": rpt_scores,
        # Anomaly deviation map
        "anomalyYears": years[1:] if len(years) > 1 else [],
        "anomalyRevenue": _yoy(revenue)[1:] if len(revenue) > 1 else [],
        "anomalyDebt": _yoy(total_debt)[1:] if len(total_debt) > 1 else [],
        "anomalyReceivables": _yoy(receivables)[1:] if len(receivables) > 1 else [],
        "anomalyNetIncome": _yoy(net_income)[1:] if len(net_income) > 1 else [],
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

    return {
        "ticker": ticker,
        "company_info": company_info,
        "financials": financials,
        "beneish": beneish,
        "beneish_trend": beneish_trend,
        "signals": signals,
        "signal_summary": signal_summary,
        "auditor_sentiment": auditor_sentiment,
        "mda_sentiment": mda_sentiment,
        "tone_mismatch": tone_mismatch,
        "score": score,
        "peer_comparison": peer_comparison,
        "ai_report": ai_report,
        "chart_data_json": json.dumps(chart_data),
    }


@bp.route('/')
def index():
    """Landing page with ticker search bar."""
    return render_template('index.html')


@bp.route('/analyze', methods=['POST'])
def analyze():
    """
    Run the full 5-step forensic analysis pipeline and render report.
    """
    raw_input = request.form.get('ticker', '').strip()
    if not raw_input:
        return render_template('index.html', error="Please enter a stock ticker or company name.")

    # Resolve company name to ticker symbol
    ticker = _resolve_ticker(raw_input)

    # Add .NS suffix if not present (assume NSE)
    if '.' not in ticker:
        ticker = ticker + '.NS'

    try:
        start_time = time.time()
        results = _run_pipeline(ticker)
        elapsed = round(time.time() - start_time, 1)
        results['elapsed_time'] = elapsed

        return render_template('report.html', **results)

    except ValueError as e:
        return render_template('index.html', error=str(e))
    except Exception as e:
        traceback.print_exc()
        return render_template('index.html', error=f"Analysis failed: {str(e)}")
