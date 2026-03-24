"""
scorer.py — Risk Scoring & Industry Benchmarking (Person 2)
Computes overall fraud risk score and Z-score peer comparison.
"""

import os
import csv
import numpy as np


# ──────────────────────────────────────────────
# Fraud Risk Scoring
# ──────────────────────────────────────────────

# Weights for severity levels
SEVERITY_WEIGHTS = {
    "high": 5,
    "medium": 3,
    "low": 1,
}

# Maximum possible score normalization factor
MAX_REASONABLE_RAW_SCORE = 150  # ~30 high-severity signals


def score_company(financials: dict, signals: list, beneish: dict) -> dict:
    """
    Compute weighted fraud risk score (0-100) from all detected signals + Beneish.

    Scoring breakdown:
    - 60% from fraud signals (weighted by severity)
    - 25% from Beneish M-Score
    - 15% from trend consistency

    Returns:
        dict with: overall_score, risk_level, signal_score, beneish_score, breakdown
    """
    # --- Signal-based score (0-60) ---
    raw_signal_score = sum(SEVERITY_WEIGHTS.get(s["severity"], 1) for s in signals)
    signal_score = min(60, (raw_signal_score / MAX_REASONABLE_RAW_SCORE) * 60)

    # --- Beneish-based score (0-25) ---
    beneish_score = 0
    if beneish and beneish.get("m_score") is not None:
        m = beneish["m_score"]
        if m > -1.78:
            beneish_score = 25  # Likely manipulator
        elif m > -2.22:
            beneish_score = 15  # Grey zone
        elif m > -2.50:
            beneish_score = 8   # Slightly concerning
        else:
            beneish_score = 2   # Low risk

    # --- Trend score (0-15) ---
    # Check: are signals getting worse over time?
    trend_score = 0
    if signals:
        recent_years = set()
        older_years = set()
        years = financials.get("years", [])
        if len(years) >= 4:
            mid = len(years) // 2
            recent_year_set = set(years[mid:])
            older_year_set = set(years[:mid])

            recent_count = sum(1 for s in signals if s.get("year") in recent_year_set)
            older_count = sum(1 for s in signals if s.get("year") in older_year_set)

            if older_count > 0:
                trend_ratio = recent_count / older_count
                if trend_ratio > 2.0:
                    trend_score = 15  # Significant worsening
                elif trend_ratio > 1.5:
                    trend_score = 10
                elif trend_ratio > 1.0:
                    trend_score = 5
            elif recent_count > 5:
                trend_score = 12  # Many recent signals, no old ones

    overall_score = round(signal_score + beneish_score + trend_score, 1)
    overall_score = min(100, overall_score)

    # Risk level classification
    if overall_score >= 70:
        risk_level = "CRITICAL"
        risk_color = "red"
    elif overall_score >= 50:
        risk_level = "HIGH"
        risk_color = "orange"
    elif overall_score >= 30:
        risk_level = "MODERATE"
        risk_color = "yellow"
    else:
        risk_level = "LOW"
        risk_color = "green"

    return {
        "overall_score": overall_score,
        "risk_level": risk_level,
        "risk_color": risk_color,
        "breakdown": {
            "signal_score": round(signal_score, 1),
            "signal_max": 60,
            "beneish_score": beneish_score,
            "beneish_max": 25,
            "trend_score": trend_score,
            "trend_max": 15,
        },
        "total_signals_triggered": len(signals),
        "high_severity_count": sum(1 for s in signals if s["severity"] == "high"),
        "medium_severity_count": sum(1 for s in signals if s["severity"] == "medium"),
    }


# ──────────────────────────────────────────────
# Industry Peer Benchmarking (Z-Score Analysis)
# ──────────────────────────────────────────────

def _load_peers(peers_csv_path: str) -> dict:
    """Load peer mappings from CSV."""
    peers = {}
    with open(peers_csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sector = row["sector"].strip()
            tickers = [t.strip() for t in row["peer_tickers"].split(",")]
            peers[sector] = tickers
    return peers


def _calculate_z_scores(values: list, target_value: float) -> dict:
    """Calculate Z-score of target_value against a list of values."""
    if not values or len(values) < 2:
        return {"z_score": None, "mean": None, "std": None}

    arr = np.array(values, dtype=float)
    mean = np.mean(arr)
    std = np.std(arr)

    if std == 0:
        z = 0.0
    else:
        z = (target_value - mean) / std

    return {
        "z_score": round(float(z), 2),
        "mean": round(float(mean), 2),
        "std": round(float(std), 2),
    }


def benchmark_against_peers(ticker: str, financials: dict, peers_csv_path: str = None) -> dict:
    """
    Industry-aware peer benchmarking with sector-specific thresholds.
    
    THE TWIST: A construction company carrying high debt is normal,
    the same debt level in a software company is a critical red flag.
    Every flag is contextualised against what is normal for that industry.
    """
    raw_sector = financials.get("sector", "Unknown")
    raw_industry = financials.get("industry", "Unknown")

    # Fine-grained: map by INDUSTRY first (more specific)
    INDUSTRY_MAP = {
        # Consumer Cyclical sub-sectors
        "Luxury Goods": "Jewelry",
        "Gold": "Jewelry",
        "Jewelry": "Jewelry",
        "Specialty Retail": "Retail",
        "Department Stores": "Retail",
        "Apparel Retail": "Retail",
        "Internet Retail": "Retail",
        "Home Improvement Retail": "Retail",
        "Auto Manufacturers": "Auto",
        "Auto Parts": "Auto",
        "Auto - Manufacturers": "Auto",
        "Auto - Parts": "Auto",
        "Residential Construction": "Realty",
        "Lodging": "Hospitality",
        "Restaurants": "Hospitality",
        "Travel Services": "Hospitality",
        # Other industries
        "Drug Manufacturers": "Pharma",
        "Drug Manufacturers - General": "Pharma",
        "Drug Manufacturers - Specialty & Generic": "Pharma",
        "Biotechnology": "Pharma",
        "Banks - Regional": "Banking",
        "Banks - Diversified": "Banking",
        "Insurance": "Financial Services",
        "Credit Services": "Financial Services",
        "Capital Markets": "Financial Services",
        "Software - Application": "IT",
        "Software - Infrastructure": "IT",
        "Information Technology Services": "IT",
        "Semiconductors": "IT",
        "Cement": "Infra",
        "Building Materials": "Infra",
        "Steel": "Metals",
        "Aluminum": "Metals",
        "Copper": "Metals",
        "Oil & Gas E&P": "Energy",
        "Oil & Gas Integrated": "Energy",
        "Oil & Gas Refining & Marketing": "Energy",
        "Packaged Foods": "FMCG",
        "Household & Personal Products": "FMCG",
        "Beverages - Non-Alcoholic": "FMCG",
        "Tobacco": "FMCG",
        "Telecom Services": "Telecom",
    }

    # Broad fallback: map by SECTOR
    SECTOR_MAP = {
        "Technology": "IT",
        "Information Technology": "IT",
        "Healthcare": "Pharma",
        "Consumer Cyclical": "Auto",
        "Consumer Defensive": "FMCG",
        "Energy": "Energy",
        "Communication Services": "Telecom",
        "Basic Materials": "Metals",
        "Industrials": "Infra",
        "Real Estate": "Realty",
        "Utilities": "Energy",
    }

    # Priority: industry-specific → broad sector → raw value
    sector = INDUSTRY_MAP.get(raw_industry, SECTOR_MAP.get(raw_sector, raw_sector))

    # ── Industry-specific norms ────────────────────────────────────────
    # Format: { sector: { metric: (normal_low, normal_high, description) } }
    INDUSTRY_NORMS = {
        "IT": {
            "debt_to_equity": (0, 0.5, "IT companies are asset-light — D/E above 0.5 is unusual"),
            "profit_margin": (10, 30, "IT margins typically 10-30%"),
            "cash_conversion": (70, 150, "IT should have strong cash conversion"),
            "roa": (10, 40, "IT companies have high asset returns"),
        },
        "Banking": {
            "debt_to_equity": (5, 15, "Banks naturally carry high leverage — this is normal"),
            "profit_margin": (5, 25, "Bank margins depend on interest spread"),
            "cash_conversion": (-200, 200, "Cash flow volatile for banks — not a reliable metric"),
            "roa": (0.5, 2.5, "Bank ROA is naturally low due to large balance sheets"),
        },
        "Financial Services": {
            "debt_to_equity": (1, 8, "NBFCs/financial cos carry high leverage but less than banks"),
            "profit_margin": (10, 40, "Financial services can have high margins from lending spread"),
            "cash_conversion": (-100, 200, "Cash flow volatile for financial companies"),
            "roa": (1, 5, "Large loan books reduce ROA"),
        },
        "Pharma": {
            "debt_to_equity": (0, 1.0, "Pharma companies should have moderate debt"),
            "profit_margin": (8, 25, "Pharma margins vary by generics vs patented"),
            "cash_conversion": (50, 130, "Expect solid cash conversion"),
            "roa": (5, 20, "Moderate asset returns expected"),
        },
        "Auto": {
            "debt_to_equity": (0.3, 2.0, "Auto companies carry moderate debt for capex"),
            "profit_margin": (3, 15, "Auto margins are typically thin"),
            "cash_conversion": (40, 120, "Capital-intensive → moderate conversion"),
            "roa": (3, 15, "Heavy assets → lower ROA is normal"),
        },
        "FMCG": {
            "debt_to_equity": (0, 0.8, "FMCG should be low-debt with strong brands"),
            "profit_margin": (10, 25, "FMCG enjoys pricing power"),
            "cash_conversion": (60, 130, "Strong cash generation expected"),
            "roa": (10, 35, "Asset-light model → high ROA"),
        },
        "Energy": {
            "debt_to_equity": (0.5, 3.0, "Energy companies carry significant capex debt"),
            "profit_margin": (3, 15, "Commodity-linked margins"),
            "cash_conversion": (30, 120, "Cyclical cash flows"),
            "roa": (2, 12, "Heavy asset base"),
        },
        "Telecom": {
            "debt_to_equity": (1.0, 5.0, "Telecom needs heavy infra investment — high debt normal"),
            "profit_margin": (-10, 20, "Many telecom cos are loss-making due to competition"),
            "cash_conversion": (30, 150, "Subscription revenue should convert well"),
            "roa": (0, 8, "Huge tower/spectrum assets"),
        },
        "Metals": {
            "debt_to_equity": (0.5, 2.5, "Capital-intensive → moderate debt expected"),
            "profit_margin": (3, 20, "Highly cyclical margins"),
            "cash_conversion": (30, 120, "Depends on commodity cycle"),
            "roa": (2, 15, "Heavy fixed assets"),
        },
        "Infra": {
            "debt_to_equity": (1.0, 4.0, "Infrastructure projects need heavy borrowing — high D/E is normal"),
            "profit_margin": (3, 12, "Thin margins on large projects"),
            "cash_conversion": (20, 100, "Long project cycles affect cash flow"),
            "roa": (1, 8, "Asset-heavy"),
        },
        "Realty": {
            "debt_to_equity": (0.5, 3.0, "Real estate is debt-funded by nature"),
            "profit_margin": (5, 25, "Location and cycle dependent"),
            "cash_conversion": (10, 100, "Lumpy project completions"),
            "roa": (1, 10, "Large land banks on balance sheet"),
        },
        "Jewelry": {
            "debt_to_equity": (0, 1.5, "Jewelry companies should be moderately leveraged"),
            "profit_margin": (5, 20, "Margins depend on gold/diamond prices and brand"),
            "cash_conversion": (30, 120, "Inventory-heavy — moderate cash conversion"),
            "roa": (3, 15, "Significant inventory on balance sheet"),
        },
        "Retail": {
            "debt_to_equity": (0, 1.5, "Retail should be moderately leveraged"),
            "profit_margin": (2, 12, "Retail margins are thin by nature"),
            "cash_conversion": (40, 130, "Working capital management is key"),
            "roa": (3, 15, "Store assets and inventory on balance sheet"),
        },
        "Hospitality": {
            "debt_to_equity": (0.3, 2.5, "Hotel/travel companies carry property debt"),
            "profit_margin": (5, 20, "Seasonal and cyclical"),
            "cash_conversion": (40, 130, "Operating leverage matters"),
            "roa": (2, 12, "Property-heavy balance sheets"),
        },
    }

    # Default norms for unknown sectors
    DEFAULT_NORMS = {
        "debt_to_equity": (0, 2.0, "General threshold"),
        "profit_margin": (5, 25, "General threshold"),
        "cash_conversion": (50, 130, "General threshold"),
        "roa": (3, 20, "General threshold"),
    }

    norms = INDUSTRY_NORMS.get(sector, DEFAULT_NORMS)

    # Default peers CSV path
    if peers_csv_path is None:
        peers_csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "peers.csv")

    # Load peer tickers
    try:
        peers_map = _load_peers(peers_csv_path)
        peer_tickers = peers_map.get(sector, [])
        # Remove the target company from peers list
        peer_tickers = [p for p in peer_tickers if p != ticker]
    except FileNotFoundError:
        peer_tickers = []

    # Calculate key ratios for the target company
    latest_idx = -1
    rev = financials["revenue"][latest_idx]
    ta = financials["total_assets"][latest_idx]
    tl = financials["total_liabilities"][latest_idx]
    ni = financials["net_income"][latest_idx]
    ocf = financials["operating_cash_flow"][latest_idx]
    debt = financials["total_debt"][latest_idx]
    equity = (ta - tl) if (ta is not None and tl is not None) else None

    company_metrics = {
        "profit_margin": round(ni / rev * 100, 2) if (rev and ni is not None) else None,
        "debt_to_equity": round(debt / equity, 2) if (equity and debt is not None and equity != 0) else None,
        "cash_conversion": round(ocf / ni * 100, 2) if (ni and ocf is not None and ni != 0) else None,
        "asset_turnover": round(rev / ta, 2) if (ta and rev is not None) else None,
        "roa": round(ni / ta * 100, 2) if (ta and ni is not None) else None,
        "roe": round(ni / equity * 100, 2) if (equity and ni is not None and equity != 0) else None,
    }

    # ── Fetch live peer data via yfinance ──────────────────────────────
    peer_data = {}
    peer_metrics_list = []

    if peer_tickers:
        import yfinance as yf
        for p_ticker in peer_tickers[:5]:  # Cap at 5 peers for speed
            try:
                info = yf.Ticker(p_ticker).info
                pm = info.get("profitMargins")
                de = info.get("debtToEquity")
                roa_val = info.get("returnOnAssets")
                roe_val = info.get("returnOnEquity")

                p_metrics = {
                    "profit_margin": round(pm * 100, 2) if pm is not None else None,
                    "debt_to_equity": round(de / 100, 2) if de is not None else None,
                    "roa": round(roa_val * 100, 2) if roa_val is not None else None,
                    "roe": round(roe_val * 100, 2) if roe_val is not None else None,
                }
                peer_data[p_ticker] = p_metrics
                peer_metrics_list.append(p_metrics)
            except Exception:
                pass

    # ── Compute peer averages ─────────────────────────────────────────
    peer_averages = {}
    if peer_metrics_list:
        for key in ["profit_margin", "debt_to_equity", "roa", "roe"]:
            vals = [p[key] for p in peer_metrics_list if p.get(key) is not None]
            if vals:
                peer_averages[key] = round(sum(vals) / len(vals), 2)

    # ── Industry-contextualised flags (now uses peer avg OR hardcoded norms) ──
    flags = []

    for metric_key, (low, high, reason) in norms.items():
        val = company_metrics.get(metric_key)
        if val is None:
            continue

        # If we have live peer data, use peer average to contextualize
        peer_avg = peer_averages.get(metric_key)
        if peer_avg is not None:
            deviation = abs(val - peer_avg) / max(abs(peer_avg), 1) * 100
            if deviation > 50:
                severity = "high"
                flags.append({
                    "metric": metric_key.replace("_", " ").title(),
                    "value": val,
                    "peer_avg": peer_avg,
                    "sector_range": f"{low} – {high}",
                    "concern": f"Deviates {deviation:.0f}% from peer average ({peer_avg}). {reason}",
                    "severity": severity,
                    "direction": "above" if val > peer_avg else "below",
                })
            elif deviation > 25:
                severity = "medium"
                flags.append({
                    "metric": metric_key.replace("_", " ").title(),
                    "value": val,
                    "peer_avg": peer_avg,
                    "sector_range": f"{low} – {high}",
                    "concern": f"Deviates {deviation:.0f}% from peer average ({peer_avg}). {reason}",
                    "severity": severity,
                    "direction": "above" if val > peer_avg else "below",
                })
        else:
            # Fallback to hardcoded norms
            if val > high:
                severity = "high" if val > high * 1.5 else "medium"
                flags.append({
                    "metric": metric_key.replace("_", " ").title(),
                    "value": val,
                    "sector_range": f"{low} – {high}",
                    "concern": f"Above {sector} industry norm ({high}). {reason}",
                    "severity": severity,
                    "direction": "above",
                })
            elif val < low:
                severity = "high" if low > 0 and val < low * 0.5 else "medium"
                flags.append({
                    "metric": metric_key.replace("_", " ").title(),
                    "value": val,
                    "sector_range": f"{low} – {high}",
                    "concern": f"Below {sector} industry norm ({low}). {reason}",
                    "severity": severity,
                    "direction": "below",
                })

    return {
        "ticker": ticker,
        "sector": sector,
        "peer_tickers": list(peer_data.keys()) if peer_data else peer_tickers,
        "company_metrics": company_metrics,
        "peer_data": peer_data,
        "peer_averages": peer_averages,
        "industry_norms": {k: {"low": v[0], "high": v[1], "note": v[2]} for k, v in norms.items()},
        "flags": flags,
        "note": f"Benchmarked against {len(peer_data)} live {sector} peers." if peer_data else f"Benchmarked against {sector} industry norms. {len(peer_tickers)} peers identified.",
    }

