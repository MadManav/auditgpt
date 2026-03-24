"""
signals.py — Fraud Signal Detection (Person 2)
Runs 20+ fraud signals on financial data.
Each signal returns: { name, triggered, severity, explanation, year }
"""


def _safe_divide(a, b):
    if b is None or b == 0 or a is None:
        return None
    return a / b


def _growth_rate(values, idx):
    """Calculate year-over-year growth rate."""
    if idx < 1:
        return None
    if values[idx] is None or values[idx - 1] is None:
        return None
    return _safe_divide(values[idx] - values[idx - 1], abs(values[idx - 1]))


def _make_signal(name, triggered, severity, explanation, year=None):
    return {
        "name": name,
        "triggered": triggered,
        "severity": severity,  # "high", "medium", "low"
        "explanation": explanation,
        "year": year,
    }


# ──────────────────────────────────────────────
# Individual signal checks
# ──────────────────────────────────────────────

def _check_revenue_vs_cashflow(financials, idx):
    """Revenue growing but operating cash flow declining or flat."""
    rev_growth = _growth_rate(financials["revenue"], idx)
    ocf_growth = _growth_rate(financials["operating_cash_flow"], idx)
    if rev_growth is None or ocf_growth is None:
        return None

    triggered = rev_growth > 0.10 and ocf_growth < 0.05
    return _make_signal(
        "Revenue-Cash Flow Divergence",
        triggered,
        "high" if triggered else "low",
        f"Revenue grew {rev_growth:.1%} but operating cash flow grew only {ocf_growth:.1%}. "
        "Healthy companies should see cash flow track revenue growth."
        if triggered else "Revenue and cash flow are growing in sync.",
        financials["years"][idx],
    )


def _check_receivables_vs_revenue(financials, idx):
    """Receivables growing faster than revenue — potential revenue manipulation."""
    recv_growth = _growth_rate(financials["receivables"], idx)
    rev_growth = _growth_rate(financials["revenue"], idx)
    if recv_growth is None or rev_growth is None:
        return None

    triggered = recv_growth > rev_growth * 1.5 and recv_growth > 0.15
    return _make_signal(
        "Receivables Outpacing Revenue",
        triggered,
        "high" if triggered else "low",
        f"Receivables grew {recv_growth:.1%} vs revenue growth of {rev_growth:.1%}. "
        "This could indicate channel stuffing or fictitious revenue."
        if triggered else "Receivables growth is proportional to revenue.",
        financials["years"][idx],
    )


def _check_debt_vs_revenue(financials, idx):
    """Debt growing faster than revenue."""
    debt_growth = _growth_rate(financials["total_debt"], idx)
    rev_growth = _growth_rate(financials["revenue"], idx)
    if debt_growth is None or rev_growth is None:
        return None

    triggered = debt_growth > rev_growth * 1.5 and debt_growth > 0.15
    return _make_signal(
        "Debt Growing Faster Than Revenue",
        triggered,
        "high" if triggered else "low",
        f"Debt grew {debt_growth:.1%} vs revenue growth of {rev_growth:.1%}. "
        "Company may be funding operations/growth through unsustainable borrowing."
        if triggered else "Debt growth is manageable relative to revenue.",
        financials["years"][idx],
    )


def _check_declining_cashflow(financials, idx):
    """Operating cash flow declining year-over-year."""
    ocf_growth = _growth_rate(financials["operating_cash_flow"], idx)
    if ocf_growth is None:
        return None

    triggered = ocf_growth < -0.05
    return _make_signal(
        "Declining Operating Cash Flow",
        triggered,
        "high" if triggered else "low",
        f"Operating cash flow declined by {abs(ocf_growth):.1%}. "
        "Persistent cash flow decline is a major red flag."
        if triggered else "Operating cash flow is stable or growing.",
        financials["years"][idx],
    )


def _check_other_income_spike(financials, idx):
    """Unusual spike in other income relative to revenue."""
    if idx < 1:
        return None
    oi_ratio_curr = _safe_divide(financials["other_income"][idx], financials["revenue"][idx])
    oi_ratio_prev = _safe_divide(financials["other_income"][idx - 1], financials["revenue"][idx - 1])
    if oi_ratio_curr is None or oi_ratio_prev is None:
        return None

    triggered = oi_ratio_curr > 0.05 and oi_ratio_curr > oi_ratio_prev * 1.5
    return _make_signal(
        "Unusual Other Income Spike",
        triggered,
        "medium" if triggered else "low",
        f"Other income is {oi_ratio_curr:.1%} of revenue (was {oi_ratio_prev:.1%}). "
        "Companies sometimes use other income to mask declining core profitability."
        if triggered else "Other income is at normal levels.",
        financials["years"][idx],
    )


def _check_profit_vs_cashflow(financials, idx):
    """Net income significantly exceeding operating cash flow (accrual red flag)."""
    ni = financials["net_income"][idx]
    ocf = financials["operating_cash_flow"][idx]
    if ni is None or ocf is None or ocf == 0:
        return None

    ratio = _safe_divide(ni, ocf)
    triggered = ratio > 1.5 and ni > ocf + 1000
    return _make_signal(
        "Profit Exceeding Cash Flow",
        triggered,
        "high" if triggered else "low",
        f"Net income is {ratio:.1f}x operating cash flow. "
        "Earnings not backed by cash suggest aggressive accounting."
        if triggered else "Net income and cash flow are reasonably aligned.",
        financials["years"][idx],
    )


def _check_inventory_buildup(financials, idx):
    """Inventory growing faster than cost of goods sold."""
    inv_growth = _growth_rate(financials["inventory"], idx)
    cogs_growth = _growth_rate(financials["cost_of_goods"], idx)
    if inv_growth is None or cogs_growth is None:
        return None

    triggered = inv_growth > cogs_growth * 1.5 and inv_growth > 0.15
    return _make_signal(
        "Inventory Buildup",
        triggered,
        "medium" if triggered else "low",
        f"Inventory grew {inv_growth:.1%} vs COGS growth of {cogs_growth:.1%}. "
        "Excess inventory may indicate demand weakness or obsolescence risk."
        if triggered else "Inventory levels are consistent with sales.",
        financials["years"][idx],
    )


def _check_depreciation_slowdown(financials, idx):
    """Depreciation declining as % of total assets — inflating earnings."""
    if idx < 1:
        return None
    dep_ratio_curr = _safe_divide(financials["depreciation"][idx], financials["total_assets"][idx])
    dep_ratio_prev = _safe_divide(financials["depreciation"][idx - 1], financials["total_assets"][idx - 1])
    if dep_ratio_curr is None or dep_ratio_prev is None:
        return None

    triggered = dep_ratio_curr < dep_ratio_prev * 0.85
    return _make_signal(
        "Depreciation Slowdown",
        triggered,
        "medium" if triggered else "low",
        f"Depreciation/Assets ratio dropped from {dep_ratio_prev:.2%} to {dep_ratio_curr:.2%}. "
        "Reducing depreciation artificially inflates reported earnings."
        if triggered else "Depreciation rates are consistent.",
        financials["years"][idx],
    )


def _check_working_capital_decline(financials, idx):
    """Negative working capital trend."""
    if idx < 1:
        return None
    wc_curr = financials["working_capital"][idx]
    wc_prev = financials["working_capital"][idx - 1]
    if wc_curr is None or wc_prev is None:
        return None

    triggered = (wc_curr < wc_prev and wc_curr < 0) or (wc_prev > 0 and wc_curr < wc_prev * 0.7)
    return _make_signal(
        "Working Capital Deterioration",
        triggered,
        "medium" if triggered else "low",
        f"Working capital dropped from {wc_prev:,.0f} to {wc_curr:,.0f}. "
        "Deteriorating working capital signals potential liquidity issues."
        if triggered else "Working capital is stable.",
        financials["years"][idx],
    )


def _check_altman_z_score(financials, idx):
    """Altman Z-Score: Z < 1.81 = distress zone."""
    ta = financials["total_assets"][idx]
    tl_val = financials["total_liabilities"][idx]
    if ta is None or ta == 0 or tl_val is None:
        return None

    wc = financials["working_capital"][idx]
    re = financials["net_income"][idx]  # Retained earnings proxy
    ebit = financials["ebit"][idx]
    equity = ta - tl_val
    tl = tl_val
    rev = financials["revenue"][idx]

    if any(v is None for v in [wc, re, ebit, rev]):
        return None

    A = _safe_divide(wc, ta)
    B = _safe_divide(re, ta)
    C = _safe_divide(ebit, ta)
    D = _safe_divide(equity, tl)
    E = _safe_divide(rev, ta)

    if any(v is None for v in [A, B, C, D, E]):
        return None

    z_score = 1.2 * A + 1.4 * B + 3.3 * C + 0.6 * D + 1.0 * E

    if z_score < 1.81:
        triggered = True
        severity = "high"
        explanation = f"Altman Z-Score = {z_score:.2f} (< 1.81). Company is in the DISTRESS ZONE — high bankruptcy risk."
    elif z_score < 2.99:
        triggered = True
        severity = "medium"
        explanation = f"Altman Z-Score = {z_score:.2f} (grey zone 1.81-2.99). Company shows some financial stress."
    else:
        triggered = False
        severity = "low"
        explanation = f"Altman Z-Score = {z_score:.2f} (> 2.99). Company is in the SAFE ZONE."

    return _make_signal("Altman Z-Score", triggered, severity, explanation, financials["years"][idx])


def _check_capex_cuts(financials, idx):
    """Capex declining while revenue grows — underinvestment risk."""
    capex_growth = _growth_rate(financials["capex"], idx)
    rev_growth = _growth_rate(financials["revenue"], idx)
    if capex_growth is None or rev_growth is None:
        return None

    triggered = rev_growth > 0.10 and capex_growth < -0.05
    return _make_signal(
        "Capex Cuts During Growth",
        triggered,
        "medium" if triggered else "low",
        f"Revenue grew {rev_growth:.1%} but capex declined {capex_growth:.1%}. "
        "Cutting investment during growth may inflate short-term profits unsustainably."
        if triggered else "Capex is aligned with revenue growth.",
        financials["years"][idx],
    )


def _check_tax_anomaly(financials, idx):
    """Effective tax rate significantly below expected rate."""
    ebit_val = financials["ebit"][idx]
    int_val = financials["interest_expense"][idx]
    tax = financials["tax_expense"][idx]
    if ebit_val is None or int_val is None or tax is None:
        return None
    ebt = ebit_val - int_val
    if ebt <= 0:
        return None

    effective_rate = _safe_divide(tax, ebt)
    if effective_rate is None:
        return None

    triggered = effective_rate < 0.15 or effective_rate > 0.40
    return _make_signal(
        "Tax Rate Anomaly",
        triggered,
        "medium" if triggered else "low",
        f"Effective tax rate is {effective_rate:.1%}. "
        "Abnormal tax rates may indicate aggressive tax planning or earnings manipulation."
        if triggered else f"Effective tax rate of {effective_rate:.1%} appears normal.",
        financials["years"][idx],
    )


def _check_leverage_spike(financials, idx):
    """Debt-to-equity ratio spiking."""
    if idx < 1:
        return None
    ta_c, tl_c = financials["total_assets"][idx], financials["total_liabilities"][idx]
    ta_p, tl_p = financials["total_assets"][idx - 1], financials["total_liabilities"][idx - 1]
    if any(v is None for v in [ta_c, tl_c, ta_p, tl_p]):
        return None
    equity_curr = ta_c - tl_c
    equity_prev = ta_p - tl_p

    de_curr = _safe_divide(financials["total_debt"][idx], equity_curr)
    de_prev = _safe_divide(financials["total_debt"][idx - 1], equity_prev)
    if de_curr is None or de_prev is None:
        return None

    triggered = de_curr > de_prev * 1.3 and de_curr > 1.0
    return _make_signal(
        "Leverage Spike",
        triggered,
        "high" if triggered else "low",
        f"Debt-to-equity jumped from {de_prev:.2f} to {de_curr:.2f}. "
        "Rapid leverage increase signals financial stress."
        if triggered else f"Debt-to-equity ratio of {de_curr:.2f} is stable.",
        financials["years"][idx],
    )


def _check_interest_coverage(financials, idx):
    """Interest coverage ratio declining below safe levels."""
    ebit = financials["ebit"][idx]
    interest = financials["interest_expense"][idx]
    if ebit is None or interest is None or interest == 0:
        return None

    coverage = _safe_divide(ebit, interest)
    if coverage is None:
        return None
    triggered = coverage < 2.0
    return _make_signal(
        "Weak Interest Coverage",
        triggered,
        "high" if triggered else "low",
        f"Interest coverage ratio = {coverage:.1f}x. "
        "Below 2x means the company may struggle to service its debt."
        if triggered else f"Interest coverage of {coverage:.1f}x is adequate.",
        financials["years"][idx],
    )


def _check_margin_compression(financials, idx):
    """Gross margin declining over time."""
    if idx < 2:
        return None
    margin_curr = _safe_divide(financials["gross_profit"][idx], financials["revenue"][idx])
    margin_2yr_ago = _safe_divide(financials["gross_profit"][idx - 2], financials["revenue"][idx - 2])
    if margin_curr is None or margin_2yr_ago is None:
        return None

    triggered = margin_curr < margin_2yr_ago * 0.90
    return _make_signal(
        "Gross Margin Compression",
        triggered,
        "medium" if triggered else "low",
        f"Gross margin dropped from {margin_2yr_ago:.1%} to {margin_curr:.1%} over 2 years. "
        "Sustained margin compression indicates pricing pressure or cost issues."
        if triggered else "Gross margins are stable.",
        financials["years"][idx],
    )


def _check_cash_conversion(financials, idx):
    """Cash conversion ratio (OCF / Net Income) deteriorating."""
    ni = financials["net_income"][idx]
    ocf = financials["operating_cash_flow"][idx]
    if ni is None or ni <= 0:
        return None

    ratio = _safe_divide(ocf, ni)
    triggered = ratio < 0.5
    return _make_signal(
        "Poor Cash Conversion",
        triggered,
        "high" if triggered else "low",
        f"Cash conversion ratio = {ratio:.1%} (OCF/Net Income). "
        "Healthy companies convert >80% of profit to cash."
        if triggered else f"Cash conversion of {ratio:.1%} is healthy.",
        financials["years"][idx],
    )


def _check_revenue_quality(financials, idx):
    """Revenue quality: ratio of OCF to Revenue declining."""
    if idx < 1:
        return None
    rq_curr = _safe_divide(financials["operating_cash_flow"][idx], financials["revenue"][idx])
    rq_prev = _safe_divide(financials["operating_cash_flow"][idx - 1], financials["revenue"][idx - 1])
    if rq_curr is None or rq_prev is None:
        return None

    triggered = rq_curr < rq_prev * 0.75 and rq_curr < 0.10
    return _make_signal(
        "Declining Revenue Quality",
        triggered,
        "high" if triggered else "low",
        f"Revenue quality (OCF/Revenue) dropped from {rq_prev:.1%} to {rq_curr:.1%}. "
        "Revenue not backed by cash inflows may be fictitious or unsustainable."
        if triggered else "Revenue quality is acceptable.",
        financials["years"][idx],
    )


def _check_sga_anomaly(financials, idx):
    """SGA expenses not scaling with revenue — possible cost hiding."""
    if idx < 1:
        return None
    sga_ratio_curr = _safe_divide(financials["sga"][idx], financials["revenue"][idx])
    sga_ratio_prev = _safe_divide(financials["sga"][idx - 1], financials["revenue"][idx - 1])
    if sga_ratio_curr is None or sga_ratio_prev is None:
        return None

    # SGA dropping too fast could mean cost capitalization
    triggered = sga_ratio_curr < sga_ratio_prev * 0.80
    return _make_signal(
        "SGA Expense Anomaly",
        triggered,
        "medium" if triggered else "low",
        f"SGA/Revenue dropped from {sga_ratio_prev:.1%} to {sga_ratio_curr:.1%}. "
        "Sharp SGA decline may indicate improper expense capitalization."
        if triggered else "SGA expenses are proportional to revenue.",
        financials["years"][idx],
    )


def _check_asset_turnover_decline(financials, idx):
    """Asset turnover declining — assets growing but not generating revenue."""
    if idx < 1:
        return None
    at_curr = _safe_divide(financials["revenue"][idx], financials["total_assets"][idx])
    at_prev = _safe_divide(financials["revenue"][idx - 1], financials["total_assets"][idx - 1])
    if at_curr is None or at_prev is None:
        return None

    triggered = at_curr < at_prev * 0.90
    return _make_signal(
        "Asset Turnover Decline",
        triggered,
        "medium" if triggered else "low",
        f"Asset turnover fell from {at_prev:.2f} to {at_curr:.2f}. "
        "Assets growing faster than revenue may indicate impaired/fictitious assets."
        if triggered else "Asset turnover is stable.",
        financials["years"][idx],
    )


# ──────────────────────────────────────────────
# Main detection function
# ──────────────────────────────────────────────

ALL_CHECKS = [
    _check_revenue_vs_cashflow,
    _check_receivables_vs_revenue,
    _check_debt_vs_revenue,
    _check_declining_cashflow,
    _check_other_income_spike,
    _check_profit_vs_cashflow,
    _check_inventory_buildup,
    _check_depreciation_slowdown,
    _check_working_capital_decline,
    _check_altman_z_score,
    _check_capex_cuts,
    _check_tax_anomaly,
    _check_leverage_spike,
    _check_interest_coverage,
    _check_margin_compression,
    _check_cash_conversion,
    _check_revenue_quality,
    _check_sga_anomaly,
    _check_asset_turnover_decline,
]


def detect_fraud_signals(financials: dict) -> list:
    """
    Run all fraud signal checks across all years.

    Returns:
        list of signal dicts, each with: name, triggered, severity, explanation, year
        Only includes signals that were triggered (red flags).
    """
    all_signals = []
    n_years = len(financials["years"])

    for check_fn in ALL_CHECKS:
        for idx in range(1, n_years):
            result = check_fn(financials, idx)
            if result and result["triggered"]:
                all_signals.append(result)

    # Sort by year (most recent first), then by severity
    severity_order = {"high": 0, "medium": 1, "low": 2}
    all_signals.sort(key=lambda s: (-(s["year"] or 0), severity_order.get(s["severity"], 3)))

    return all_signals


def get_signal_summary(signals: list) -> dict:
    """
    Get a summary of detected signals.

    Returns:
        dict with: total, high_count, medium_count, low_count, by_year, by_type
    """
    summary = {
        "total": len(signals),
        "high_count": sum(1 for s in signals if s["severity"] == "high"),
        "medium_count": sum(1 for s in signals if s["severity"] == "medium"),
        "low_count": sum(1 for s in signals if s["severity"] == "low"),
        "by_year": {},
        "by_type": {},
    }

    for s in signals:
        year = s["year"]
        if year not in summary["by_year"]:
            summary["by_year"][year] = []
        summary["by_year"][year].append(s["name"])

        name = s["name"]
        if name not in summary["by_type"]:
            summary["by_type"][name] = 0
        summary["by_type"][name] += 1

    return summary
