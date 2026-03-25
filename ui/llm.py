"""
llm.py — LLM-Powered Forensic Report Generation
Uses Google Gemini to generate plain-English forensic audit reports.
"""

import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def _build_prompt(ticker, company_info, financials, beneish, signals, signal_summary, score, peer_comparison):
    """Build the forensic analysis prompt for the LLM."""

    company_name = company_info.get("name", ticker) if company_info else ticker
    sector = company_info.get("sector", "Unknown") if company_info else "Unknown"

    # Format financial data
    years = financials.get("years", [])
    revenue = financials.get("revenue", [])
    net_income = financials.get("net_income", [])
    ocf = financials.get("operating_cash_flow", [])
    debt = financials.get("total_debt", [])

    fin_table = "Year | Revenue (Cr) | Net Income (Cr) | OCF (Cr) | Debt (Cr)\n"
    for i, yr in enumerate(years):
        r = f"{revenue[i]/1e7:,.0f}" if revenue[i] else "N/A"
        n = f"{net_income[i]/1e7:,.0f}" if net_income[i] else "N/A"
        o = f"{ocf[i]/1e7:,.0f}" if ocf[i] else "N/A"
        d = f"{debt[i]/1e7:,.0f}" if debt[i] else "N/A"
        fin_table += f"{yr} | ₹{r} | ₹{n} | ₹{o} | ₹{d}\n"

    # Format signals
    top_signals = ""
    for s in signals[:10]:
        top_signals += f"- [{s['severity'].upper()}] {s['year']} - {s['name']}: {s['explanation']}\n"

    # Beneish info
    m_score_info = f"M-Score: {beneish.get('m_score', 'N/A')}"
    if beneish.get('is_likely_manipulator'):
        m_score_info += " (LIKELY MANIPULATOR)"
    else:
        m_score_info += " (Unlikely manipulator)"

    # Peer metrics
    peer_metrics = ""
    if peer_comparison and peer_comparison.get("company_metrics"):
        for k, v in peer_comparison["company_metrics"].items():
            peer_metrics += f"- {k.replace('_', ' ').title()}: {v}\n"

    prompt = f"""You are a forensic financial auditor AI. Analyze the following company data and generate a professional forensic audit report.

COMPANY: {company_name} ({ticker})
SECTOR: {sector}
RISK SCORE: {score['overall_score']}/100 ({score['risk_level']})

FINANCIAL DATA:
{fin_table}

BENEISH M-SCORE ANALYSIS:
{m_score_info}
{beneish.get('interpretation', '')}

FRAUD SIGNALS DETECTED ({signal_summary['total']} total - {signal_summary['high_count']} High, {signal_summary['medium_count']} Medium):
{top_signals if top_signals else "No significant red flags detected."}

KEY RATIOS:
{peer_metrics}

Generate a forensic audit report with these sections (use ## markdown headings exactly as shown):
## Executive Summary
(2-3 lines — overall verdict)
## Key Findings
(bullet points — what stands out, both positive and negative)
## Risk Areas
(specific concerns with data backing)
## Positive Indicators
(what looks healthy)
## Recommendation
(1-2 lines — what an investor/auditor should do next)

Rules:
- Use ## headings exactly as shown above — do NOT use numbered sections
- Be specific — cite actual numbers from the data
- Use plain English, no jargon
- Be balanced — mention both risks AND positives
- Keep it under 300 words
- Format in markdown with bullet points using - dashes
- Do NOT mention the AI model or system used to generate this report
"""
    return prompt


def generate_forensic_report(ticker, company_info, financials, beneish, signals, signal_summary, score, peer_comparison):
    """
    Generate a plain-English forensic audit report using Gemini.

    Returns:
        str — the generated report in markdown, or error message
    """
    try:
        prompt = _build_prompt(
            ticker, company_info, financials, beneish,
            signals, signal_summary, score, peer_comparison
        )

        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)

        return response.text

    except Exception as e:
        return f"⚠️ Could not generate AI report: {str(e)}"
