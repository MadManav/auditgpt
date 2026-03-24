"""
beneish.py — Beneish M-Score Calculator (Person 2)
Computes the 8-variable Beneish M-Score to detect earnings manipulation.
Correctly predicted Enron and Satyam fraud before collapse.

M-Score > -1.78 → Likely manipulator
"""


def _safe_divide(numerator, denominator):
    """Safe division — returns None if denominator is 0 or None."""
    if denominator is None or denominator == 0:
        return None
    if numerator is None:
        return None
    return numerator / denominator


def _calculate_dsri(financials, year_idx):
    """Days Sales in Receivables Index — measures if receivables are growing faster than revenue."""
    if year_idx < 1:
        return None
    recv_curr = financials["receivables"][year_idx]
    rev_curr = financials["revenue"][year_idx]
    recv_prev = financials["receivables"][year_idx - 1]
    rev_prev = financials["revenue"][year_idx - 1]

    ratio_curr = _safe_divide(recv_curr, rev_curr)
    ratio_prev = _safe_divide(recv_prev, rev_prev)
    return _safe_divide(ratio_curr, ratio_prev)


def _calculate_gmi(financials, year_idx):
    """Gross Margin Index — measures if gross margins are deteriorating."""
    if year_idx < 1:
        return None
    gp_prev = financials["gross_profit"][year_idx - 1]
    rev_prev = financials["revenue"][year_idx - 1]
    gp_curr = financials["gross_profit"][year_idx]
    rev_curr = financials["revenue"][year_idx]

    margin_prev = _safe_divide(gp_prev, rev_prev)
    margin_curr = _safe_divide(gp_curr, rev_curr)
    return _safe_divide(margin_prev, margin_curr)


def _calculate_aqi(financials, year_idx):
    """Asset Quality Index — measures if asset quality is declining (more intangibles/other assets)."""
    if year_idx < 1:
        return None

    ca_curr = financials["current_assets"][year_idx]
    ta_curr = financials["total_assets"][year_idx]
    ca_prev = financials["current_assets"][year_idx - 1]
    ta_prev = financials["total_assets"][year_idx - 1]

    if any(v is None for v in [ca_curr, ta_curr, ca_prev, ta_prev]):
        return None

    ppe_curr = ta_curr - ca_curr
    ppe_prev = ta_prev - ca_prev

    aq_curr = _safe_divide(ta_curr - ca_curr - ppe_curr * 0.5, ta_curr)
    aq_prev = _safe_divide(ta_prev - ca_prev - ppe_prev * 0.5, ta_prev)

    if aq_prev is None or aq_prev == 0:
        return 1.0
    return _safe_divide(aq_curr, aq_prev)


def _calculate_sgi(financials, year_idx):
    """Sales Growth Index — measures revenue growth rate."""
    if year_idx < 1:
        return None
    return _safe_divide(financials["revenue"][year_idx], financials["revenue"][year_idx - 1])


def _calculate_depi(financials, year_idx):
    """Depreciation Index — measures if depreciation rate is slowing (inflating earnings)."""
    if year_idx < 1:
        return None

    dep_curr = financials["depreciation"][year_idx]
    dep_prev = financials["depreciation"][year_idx - 1]
    ta_curr = financials["total_assets"][year_idx]
    ca_curr = financials["current_assets"][year_idx]
    ta_prev = financials["total_assets"][year_idx - 1]
    ca_prev = financials["current_assets"][year_idx - 1]

    if any(v is None for v in [dep_curr, dep_prev, ta_curr, ca_curr, ta_prev, ca_prev]):
        return None

    ppe_curr = ta_curr - ca_curr
    ppe_prev = ta_prev - ca_prev

    rate_curr = _safe_divide(dep_curr, dep_curr + ppe_curr)
    rate_prev = _safe_divide(dep_prev, dep_prev + ppe_prev)

    return _safe_divide(rate_prev, rate_curr)


def _calculate_sgai(financials, year_idx):
    """SGA Expense Index — measures change in SGA as % of revenue."""
    if year_idx < 1:
        return None
    sga_curr = _safe_divide(financials["sga"][year_idx], financials["revenue"][year_idx])
    sga_prev = _safe_divide(financials["sga"][year_idx - 1], financials["revenue"][year_idx - 1])
    return _safe_divide(sga_curr, sga_prev)


def _calculate_lvgi(financials, year_idx):
    """Leverage Index — measures change in leverage (debt/assets)."""
    if year_idx < 1:
        return None
    lev_curr = _safe_divide(financials["total_liabilities"][year_idx], financials["total_assets"][year_idx])
    lev_prev = _safe_divide(financials["total_liabilities"][year_idx - 1], financials["total_assets"][year_idx - 1])
    return _safe_divide(lev_curr, lev_prev)


def _calculate_tata(financials, year_idx):
    """Total Accruals to Total Assets — measures how much of earnings are accruals vs cash."""
    ni = financials["net_income"][year_idx]
    ocf = financials["operating_cash_flow"][year_idx]
    ta = financials["total_assets"][year_idx]

    if any(v is None for v in [ni, ocf, ta]):
        return None

    accruals = ni - ocf
    return _safe_divide(accruals, ta)


def calculate_beneish_mscore(financials: dict, year_idx: int = -1) -> dict:
    """
    Calculate the Beneish M-Score from financial data.

    Args:
        financials: dict with financial data lists (from fetcher or dummy_data)
        year_idx: which year to calculate for (default: most recent = -1)

    Returns:
        dict with:
        - m_score: float — the M-Score value
        - components: dict — individual variable values
        - is_likely_manipulator: bool — True if M-Score > -1.78
        - interpretation: str — human-readable interpretation
    """
    # Convert negative index to positive
    n = len(financials["years"])
    if year_idx < 0:
        year_idx = n + year_idx

    if year_idx < 1:
        return {
            "m_score": None,
            "components": {},
            "is_likely_manipulator": None,
            "interpretation": "Insufficient data — need at least 2 years."
        }

    # Calculate all 8 components
    dsri = _calculate_dsri(financials, year_idx)
    gmi = _calculate_gmi(financials, year_idx)
    aqi = _calculate_aqi(financials, year_idx)
    sgi = _calculate_sgi(financials, year_idx)
    depi = _calculate_depi(financials, year_idx)
    sgai = _calculate_sgai(financials, year_idx)
    lvgi = _calculate_lvgi(financials, year_idx)
    tata = _calculate_tata(financials, year_idx)

    components = {
        "DSRI": dsri,
        "GMI": gmi,
        "AQI": aqi,
        "SGI": sgi,
        "DEPI": depi,
        "SGAI": sgai,
        "LVGI": lvgi,
        "TATA": tata,
    }

    # Check if any component is None
    if any(v is None for v in components.values()):
        return {
            "m_score": None,
            "components": components,
            "is_likely_manipulator": None,
            "interpretation": "Some components could not be calculated due to missing data."
        }

    # Beneish M-Score formula
    m_score = (
        -4.84
        + 0.920 * dsri
        + 0.528 * gmi
        + 0.404 * aqi
        + 0.892 * sgi
        + 0.115 * depi
        - 0.172 * sgai
        + 4.679 * tata
        - 0.327 * lvgi
    )

    is_likely = m_score > -1.78

    if m_score > -1.78:
        interpretation = (
            f"M-Score = {m_score:.2f} (> -1.78) — HIGH RISK. "
            "This company shows patterns consistent with earnings manipulation. "
            "The Beneish model would classify this as a LIKELY MANIPULATOR."
        )
    elif m_score > -2.22:
        interpretation = (
            f"M-Score = {m_score:.2f} (between -2.22 and -1.78) — MODERATE RISK. "
            "The company is in the grey zone. Some manipulation patterns detected but not conclusive."
        )
    else:
        interpretation = (
            f"M-Score = {m_score:.2f} (< -2.22) — LOW RISK. "
            "The company's financials appear consistent and unlikely to be manipulated."
        )

    return {
        "m_score": round(m_score, 4),
        "components": {k: round(v, 4) if v else v for k, v in components.items()},
        "is_likely_manipulator": is_likely,
        "interpretation": interpretation,
        "year": financials["years"][year_idx],
    }


def calculate_beneish_trend(financials: dict) -> list:
    """
    Calculate M-Score for all available years to see the trend.

    Returns:
        list of dicts, one per year (from year index 1 onwards)
    """
    results = []
    for i in range(1, len(financials["years"])):
        result = calculate_beneish_mscore(financials, year_idx=i)
        results.append(result)
    return results
