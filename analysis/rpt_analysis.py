"""
rpt_analysis.py — Related Party Transaction (RPT) Analysis (Gemini-powered)
Fetches RPT data using Gemini AI and flags unusual year-over-year jumps.
"""

import os
import json
import re
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv(override=True)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def _clean_json(raw: str) -> str:
    """Robustly clean Gemini's response to get valid JSON."""
    raw = re.sub(r'^```json\s*', '', raw.strip())
    raw = re.sub(r'^```\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    raw = re.sub(r',\s*}', '}', raw)
    raw = re.sub(r',\s*]', ']', raw)
    raw = raw.replace('\u2018', "'").replace('\u2019', "'")
    raw = raw.replace('\u201c', '"').replace('\u201d', '"')
    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw)
    raw = re.sub(r"(?<=\w)'(?=\w)", '', raw)
    return raw.strip()


def analyze_rpt(ticker: str, company_name: str, years: list) -> dict:
    """
    Call Gemini to analyze Related Party Transactions for a company.

    Returns dict with:
        - years: list of year-wise RPT data
        - top_parties: list of major related parties
        - flags: list of years with unusual jumps
        - summary: overall assessment
    """
    years_str = ", ".join([f"FY{y}" for y in years])

    prompt = f"""You are a forensic accounting expert analyzing Indian listed company filings.

Analyze Related Party Transactions (RPT) for: {company_name} (NSE: {ticker})
Years: {years_str}

For each fiscal year, use your knowledge of this companys public annual reports, SEBI disclosures, and audit filings.

Return ONLY valid JSON with this structure:
{{
  "summary": "one line overall RPT assessment",
  "top_parties": [
    {{
      "name": "Related Entity Name",
      "relationship": "Subsidiary / Promoter Group / Key Management / Associate",
      "latest_amount_cr": 500.0
    }}
  ],
  "years": [
    {{
      "year": 2022,
      "rpt_total_cr": 1200.0,
      "transaction_count": 15,
      "largest_party": "Entity Name",
      "largest_amount_cr": 400.0,
      "yoy_growth_pct": 12.5,
      "flag": false,
      "flag_reason": ""
    }}
  ]
}}

Rules:
- rpt_total_cr: total value of all related party transactions in Crores
- yoy_growth_pct: year-over-year growth percentage (null for first year)
- flag: true if yoy_growth_pct > 30 or there is a suspicious pattern
- flag_reason: explain why its flagged (empty string if not flagged)
- top_parties: list the top 3-5 related parties by transaction value (latest year)
- No apostrophes in string values
- Include all {len(years)} years
- Use realistic data based on public filings
"""

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=4096,
                response_mime_type="application/json",
            )
        )

        MAX_RETRIES = 2
        data = None
        for attempt in range(MAX_RETRIES):
            try:
                response = model.generate_content(prompt)
                cleaned = _clean_json(response.text)
                data = json.loads(cleaned)
                break
            except json.JSONDecodeError as je:
                print(f"[rpt_analysis] JSON parse error (attempt {attempt + 1}/{MAX_RETRIES}): {je}")
                if attempt >= MAX_RETRIES - 1:
                    raise

        if data is None:
            raise ValueError("Failed to parse Gemini RPT response after retries")

        # Process year data
        year_data = data.get("years", [])
        top_parties = data.get("top_parties", [])
        summary = data.get("summary", "")

        # Sort by year
        year_data.sort(key=lambda x: x.get("year", 0))

        # Recompute YoY growth and flags to be safe
        for i, yr in enumerate(year_data):
            if i == 0:
                yr["yoy_growth_pct"] = None
            else:
                prev = year_data[i - 1].get("rpt_total_cr")
                curr = yr.get("rpt_total_cr")
                if prev and curr and prev > 0:
                    growth = round(((curr - prev) / prev) * 100, 1)
                    yr["yoy_growth_pct"] = growth
                    if abs(growth) > 30:
                        yr["flag"] = True
                        if not yr.get("flag_reason"):
                            yr["flag_reason"] = f"RPT jumped {growth}% YoY"
                else:
                    yr["yoy_growth_pct"] = None

        # Collect flagged years
        flags = [yr for yr in year_data if yr.get("flag")]

        return {
            "years": year_data,
            "top_parties": top_parties,
            "flags": flags,
            "summary": summary,
            "total_years": len(year_data),
            "flag_count": len(flags),
        }

    except Exception as e:
        print(f"[rpt_analysis] Error: {e}")
        return {
            "years": [],
            "top_parties": [],
            "flags": [],
            "summary": f"Could not analyze RPT data: {str(e)}",
            "total_years": 0,
            "flag_count": 0,
            "error": str(e),
        }
