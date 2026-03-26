"""
llm.py — LLM-Powered Forensic Report Generation
Uses Google Gemini to generate structured JSON forensic audit reports.
"""

import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def _build_prompt(ticker, company_info, financials, beneish, signals, signal_summary, score, peer_comparison):
    """Build the forensic analysis prompt for the LLM."""

    company_name = company_info.get("name", ticker) if company_info else ticker
    sector = company_info.get("sector", "Unknown") if company_info else "Unknown"

    years = financials.get("years", [])
    revenue = financials.get("revenue", [])
    net_income = financials.get("net_income", [])
    ocf = financials.get("operating_cash_flow", [])
    debt = financials.get("total_debt", [])

    fin_table = "Year | Revenue (Cr) | Net Income (Cr) | OCF (Cr) | Debt (Cr)\n"
    for i, yr in enumerate(years):
        r = f"{revenue[i]/1e7:,.0f}" if i < len(revenue) and revenue[i] else "N/A"
        n = f"{net_income[i]/1e7:,.0f}" if i < len(net_income) and net_income[i] else "N/A"
        o = f"{ocf[i]/1e7:,.0f}" if i < len(ocf) and ocf[i] else "N/A"
        d = f"{debt[i]/1e7:,.0f}" if i < len(debt) and debt[i] else "N/A"
        fin_table += f"{yr} | Rs.{r} | Rs.{n} | Rs.{o} | Rs.{d}\n"

    top_signals = ""
    for s in signals[:10]:
        top_signals += f"- [{s['severity'].upper()}] {s['year']} - {s['name']}: {s['explanation']}\n"

    m_score_info = f"M-Score: {beneish.get('m_score', 'N/A')}"
    if beneish.get('is_likely_manipulator'):
        m_score_info += " (LIKELY MANIPULATOR)"
    else:
        m_score_info += " (Unlikely manipulator)"

    peer_metrics = ""
    if peer_comparison and peer_comparison.get("company_metrics"):
        for k, v in peer_comparison["company_metrics"].items():
            peer_metrics += f"- {k.replace('_', ' ').title()}: {v}\n"

    prompt = f"""You are a senior forensic accountant. Analyze {company_name} ({ticker}).

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

OUTPUT FORMAT: Return ONLY a valid JSON object with this exact structure:
{{
  "summary_paragraph": "<A single comprehensive paragraph following the template below>",
  "pointwise_report": [
    {{ "title": "<Finding Title>", "description": "<Detailed explanation>", "evidence": "<Specific data point or number>" }},
    ... (5-8 findings)
  ]
}}

TEMPLATE FOR summary_paragraph:
"The company exhibits a [Low / Moderate / High] fraud risk with an overall score of {score['overall_score']}/100. [2-3 sentences about key findings: what the M-Score says, major red flags or positive signals detected, and how financials trend over the years]. [1 sentence on the overall recommendation - whether the company appears clean or warrants further scrutiny]."

Rules:
- Be specific - cite actual numbers from the data
- Use plain English, no jargon
- Be balanced - mention both risks AND positives
- The summary_paragraph should be exactly 1 paragraph, 4-6 sentences
- Include 5-8 pointwise findings covering: executive summary, key concerns, positive indicators, and recommendation
- Do NOT mention the AI model or system used to generate this report
- Do NOT use any Unicode special characters like emojis, Rupee signs, or fancy dashes - use plain ASCII only
"""
    return prompt


def _is_quota_error(e: Exception) -> bool:
    msg = str(e).lower()
    return any(k in msg for k in ("quota", "resource_exhausted", "resourceexhausted", "429", "rate limit", "per day"))


def generate_forensic_report(ticker, company_info, financials, beneish, signals, signal_summary, score, peer_comparison):
    """
    Generate a structured JSON forensic audit report using Gemini.
    Returns fallback immediately on quota errors.
    """
    risk_level = score.get("risk_level", "Unknown") if score else "Unknown"
    overall = score.get("overall_score", "N/A") if score else "N/A"
    m_score = beneish.get("m_score", "N/A") if beneish else "N/A"
    total_flags = signal_summary.get("total", 0) if signal_summary else 0

    def _fallback(reason=""):
        print(f"[llm] Returning fallback ({reason})")
        return {
            "summary_paragraph": (
                f"The company exhibits a {risk_level} fraud risk with an overall score of {overall}/100. "
                f"The Beneish M-Score is {m_score}. A total of {total_flags} forensic red flags were detected. "
                f"Please refer to the detailed charts and signal analysis for more information."
            ),
            "pointwise_report": [
                {
                    "title": "AI Report Unavailable",
                    "description": f"Could not generate detailed AI analysis: {reason or 'API error'}",
                    "evidence": "Fallback data used - re-run analysis to retry"
                }
            ]
        }

    try:
        prompt = _build_prompt(
            ticker, company_info, financials, beneish,
            signals, signal_summary, score, peer_comparison
        )

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
        except Exception as api_err:
            if _is_quota_error(api_err):
                print("[llm] Quota exceeded — skipping AI report, continuing pipeline.")
                return _fallback("Gemini free-tier daily quota exceeded (20 req/day)")
            raise

        result = json.loads(response.text)

        if "summary_paragraph" not in result:
            result["summary_paragraph"] = "Analysis complete. Please review the pointwise findings below."
        if "pointwise_report" not in result or not isinstance(result["pointwise_report"], list):
            result["pointwise_report"] = []

        return result

    except Exception as e:
        print(f"[llm] Error generating report: {e}")
        return _fallback(str(e))