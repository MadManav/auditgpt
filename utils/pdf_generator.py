"""
pdf_generator.py — PDF Report Generator for AuditGPT
Generates a professional forensic audit PDF from analysis results.
Uses fpdf2 for PDF creation.
"""

from fpdf import FPDF
import datetime


def clean_text(text):
    """
    Replace Unicode characters that cause issues with latin-1 encoding.
    FPDF's default fonts only support latin-1, so we sanitize here.
    """
    if not text:
        return ""
    replacements = {
        "\u2014": "-",       # em-dash
        "\u2013": "-",       # en-dash
        "\u2018": "'",       # left single quote
        "\u2019": "'",       # right single quote
        "\u201c": '"',       # left double quote
        "\u201d": '"',       # right double quote
        "\u20b9": "Rs. ",    # Rupee sign
        "\u2022": "-",       # bullet
        "\u2026": "...",     # ellipsis
        "\u00d7": "x",       # multiplication sign
        "\u2265": ">=",      # >=
        "\u2264": "<=",      # <=
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Encode to latin-1, replacing any remaining problematic chars
    return text.encode('latin-1', 'replace').decode('latin-1')


def _reset_x(pdf):
    """Reset X to left margin to prevent horizontal space errors."""
    pdf.set_x(pdf.l_margin)


def _safe_page_check(pdf, needed_height=30):
    """Force a page break if not enough vertical space, and reset X."""
    if pdf.get_y() + needed_height > pdf.h - pdf.b_margin:
        pdf.add_page()
    _reset_x(pdf)


def generate_audit_pdf(data):
    """
    Generate a professional forensic audit PDF report.

    Args:
        data: dict containing full analysis results from _run_pipeline()

    Returns:
        bytes — the PDF file content
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    ticker = data.get("ticker", "UNKNOWN")
    company_info = data.get("company_info") or {}
    company_name = company_info.get("name", ticker)
    sector = company_info.get("sector", "Unknown")
    industry = company_info.get("industry", "Unknown")
    score = data.get("score", {})
    overall_score = score.get("overall_score", "N/A")
    risk_level = score.get("risk_level", "UNKNOWN")
    beneish = data.get("beneish", {})
    signal_summary = data.get("signal_summary", {})
    ai_report_json = data.get("ai_report_json") or {}
    financials = data.get("financials") or {}

    # Usable width (page width minus both margins)
    usable_w = pdf.w - pdf.l_margin - pdf.r_margin

    # ── Title Banner ──
    pdf.set_fill_color(4, 22, 39)  # primary dark
    pdf.rect(0, 0, 210, 38, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 20)
    pdf.set_y(8)
    _reset_x(pdf)
    pdf.cell(usable_w, 10, clean_text("AuditGPT - Forensic Audit Report"), ln=True, align="C")
    pdf.set_font("helvetica", "", 10)
    _reset_x(pdf)
    pdf.cell(usable_w, 6, clean_text(f"{company_name} ({ticker})  |  {sector} - {industry}"), ln=True, align="C")

    # Reset text color
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(44)
    _reset_x(pdf)

    # ── Report Metadata ──
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    now = datetime.datetime.now().strftime("%d %B %Y, %I:%M %p")
    pdf.cell(usable_w, 5, clean_text(f"Generated on: {now}"), ln=True)
    pdf.ln(4)
    _reset_x(pdf)

    # ── Risk Score Section (simple text instead of rect to avoid X offset issues) ──
    _safe_page_check(pdf, 25)
    pdf.set_fill_color(248, 249, 250)
    pdf.set_draw_color(200, 200, 200)

    # Draw background rect at current position
    box_y = pdf.get_y()
    pdf.rect(pdf.l_margin, box_y, usable_w, 20, 'DF')

    # Risk score label
    pdf.set_xy(pdf.l_margin + 5, box_y + 3)
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(4, 22, 39)
    pdf.cell(80, 8, clean_text(f"Risk Score: {overall_score}/100"))

    # Risk level label (right-aligned)
    pdf.set_font("helvetica", "B", 12)
    if overall_score != "N/A" and overall_score >= 70:
        pdf.set_text_color(186, 26, 26)
    elif overall_score != "N/A" and overall_score >= 50:
        pdf.set_text_color(217, 119, 6)
    elif overall_score != "N/A" and overall_score >= 30:
        pdf.set_text_color(202, 138, 4)
    else:
        pdf.set_text_color(22, 163, 74)
    pdf.set_xy(pdf.l_margin + 5, box_y + 3)
    pdf.cell(usable_w - 10, 8, clean_text(f"{risk_level} RISK"), align="R")

    # M-score / flags subline
    pdf.set_xy(pdf.l_margin + 5, box_y + 12)
    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(100, 100, 100)
    m_score = beneish.get("m_score", "N/A")
    m_label = "LIKELY MANIPULATOR" if beneish.get("is_likely_manipulator") else "Unlikely Manipulator"
    total_flags = signal_summary.get("total", 0)
    high_flags = signal_summary.get("high_count", 0)
    pdf.cell(usable_w - 10, 5, clean_text(f"Beneish M-Score: {m_score} ({m_label})  |  Total Flags: {total_flags} (High: {high_flags})"))

    # Move past the box
    pdf.set_y(box_y + 24)
    _reset_x(pdf)

    # ── Executive Summary ──
    summary_text = ai_report_json.get("summary_paragraph", "")
    if summary_text:
        _safe_page_check(pdf, 30)
        pdf.set_font("helvetica", "B", 13)
        pdf.set_text_color(4, 22, 39)
        pdf.cell(usable_w, 8, "Executive Summary", ln=True)
        pdf.set_draw_color(4, 83, 205)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 65, pdf.get_y())
        pdf.ln(3)
        _reset_x(pdf)
        pdf.set_font("helvetica", "", 10)
        pdf.set_text_color(50, 50, 50)
        pdf.multi_cell(usable_w, 5.5, clean_text(summary_text))
        pdf.ln(5)
        _reset_x(pdf)

    # ── Pointwise Findings ──
    findings = ai_report_json.get("pointwise_report", [])
    if findings:
        _safe_page_check(pdf, 20)
        pdf.set_font("helvetica", "B", 13)
        pdf.set_text_color(4, 22, 39)
        pdf.cell(usable_w, 8, "Key Findings", ln=True)
        pdf.set_draw_color(124, 58, 237)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 55, pdf.get_y())
        pdf.ln(3)
        _reset_x(pdf)

        for i, finding in enumerate(findings, 1):
            title = finding.get("title", f"Finding {i}")
            desc = finding.get("description", "")
            evidence = finding.get("evidence", "")

            _safe_page_check(pdf, 18)

            # Finding title
            pdf.set_font("helvetica", "B", 10)
            pdf.set_text_color(4, 22, 39)
            pdf.cell(usable_w, 6, clean_text(f"{i}. {title}"), ln=True)
            _reset_x(pdf)

            # Description
            if desc:
                pdf.set_font("helvetica", "", 9)
                pdf.set_text_color(68, 71, 76)
                pdf.multi_cell(usable_w, 5, clean_text(f"   {desc}"))
                _reset_x(pdf)

            # Evidence
            if evidence:
                pdf.set_font("helvetica", "I", 8)
                pdf.set_text_color(100, 100, 100)
                pdf.multi_cell(usable_w, 4.5, clean_text(f"   Evidence: {evidence}"))
                _reset_x(pdf)

            pdf.ln(2)

    # ── Score Breakdown Table ──
    breakdown = score.get("breakdown", {})
    if breakdown:
        _safe_page_check(pdf, 40)
        pdf.ln(3)
        pdf.set_font("helvetica", "B", 13)
        pdf.set_text_color(4, 22, 39)
        pdf.cell(usable_w, 8, "Score Breakdown", ln=True)
        pdf.set_draw_color(217, 119, 6)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 60, pdf.get_y())
        pdf.ln(3)
        _reset_x(pdf)

        # Column widths that fit within usable_w
        c1 = usable_w * 0.35
        c2 = usable_w * 0.20
        c3 = usable_w * 0.20
        c4 = usable_w * 0.25

        # Table header
        pdf.set_fill_color(4, 22, 39)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("helvetica", "B", 9)
        pdf.cell(c1, 7, "Component", border=1, fill=True, align="C")
        pdf.cell(c2, 7, "Score", border=1, fill=True, align="C")
        pdf.cell(c3, 7, "Max", border=1, fill=True, align="C")
        pdf.cell(c4, 7, "Percentage", border=1, fill=True, align="C")
        pdf.ln()
        _reset_x(pdf)

        # Table rows
        pdf.set_text_color(50, 50, 50)
        pdf.set_font("helvetica", "", 9)

        score_pairs = [
            ("Signal Analysis", "signal_score", "signal_max"),
            ("Beneish M-Score", "beneish_score", "beneish_max"),
            ("Trend Analysis", "trend_score", "trend_max"),
        ]

        fill = False
        for label, score_key, max_key in score_pairs:
            s = breakdown.get(score_key, 0)
            m = breakdown.get(max_key, 1)
            pct = round(s / m * 100) if m > 0 else 0

            if fill:
                pdf.set_fill_color(245, 245, 245)
            else:
                pdf.set_fill_color(255, 255, 255)

            pdf.cell(c1, 7, clean_text(label), border=1, fill=True)
            pdf.cell(c2, 7, str(s), border=1, fill=True, align="C")
            pdf.cell(c3, 7, str(m), border=1, fill=True, align="C")
            pdf.cell(c4, 7, f"{pct}%", border=1, fill=True, align="C")
            pdf.ln()
            _reset_x(pdf)
            fill = not fill

    # ── Financial Snapshot ──
    years = financials.get("years", [])
    if years:
        _safe_page_check(pdf, 50)
        pdf.ln(5)
        pdf.set_font("helvetica", "B", 13)
        pdf.set_text_color(4, 22, 39)
        pdf.cell(usable_w, 8, "Financial Snapshot (in Cr)", ln=True)
        pdf.set_draw_color(4, 83, 205)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + 75, pdf.get_y())
        pdf.ln(3)
        _reset_x(pdf)

        # Use only last 5 years to fit the page
        display_years = years[-5:]
        start_idx = len(years) - len(display_years)

        metrics = [
            ("Revenue", "revenue"),
            ("Net Income", "net_income"),
            ("Operating CF", "operating_cash_flow"),
            ("Total Debt", "total_debt"),
        ]

        # Calculate column widths proportionally
        label_w = usable_w * 0.18
        num_years = max(len(display_years), 1)
        col_w = (usable_w - label_w) / num_years

        # Header
        pdf.set_fill_color(4, 22, 39)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(label_w, 6, "Metric", border=1, fill=True, align="C")
        for yr in display_years:
            pdf.cell(col_w, 6, str(yr), border=1, fill=True, align="C")
        pdf.ln()
        _reset_x(pdf)

        # Rows
        pdf.set_text_color(50, 50, 50)
        pdf.set_font("helvetica", "", 8)
        fill = False
        for label, key in metrics:
            values = financials.get(key, [])
            if fill:
                pdf.set_fill_color(245, 245, 245)
            else:
                pdf.set_fill_color(255, 255, 255)

            pdf.cell(label_w, 6, clean_text(label), border=1, fill=True)
            for i, yr in enumerate(display_years):
                idx = start_idx + i
                v = values[idx] if idx < len(values) and values[idx] is not None else None
                display = f"{int(v / 1e7):,}" if v is not None else "-"
                pdf.cell(col_w, 6, display, border=1, fill=True, align="C")
            pdf.ln()
            _reset_x(pdf)
            fill = not fill

    # ── Disclaimer Footer ──
    _safe_page_check(pdf, 25)
    pdf.ln(10)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(3)
    _reset_x(pdf)
    pdf.set_font("helvetica", "I", 7)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(usable_w, 4, clean_text(
        "DISCLAIMER: This report is generated by AuditGPT for educational and research purposes only. "
        "It does not constitute financial or investment advice. The analysis is based on publicly "
        "available data and AI-generated insights which may contain inaccuracies. Always consult "
        "a qualified financial advisor before making investment decisions."
    ))

    return pdf.output()
