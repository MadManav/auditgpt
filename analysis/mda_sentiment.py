"""
mda_sentiment.py — Management Discussion & Analysis Tone Analyser (Gemini-powered)

Asks Gemini to rate management's MD&A tone for each year, then compares
it with the auditor sentiment to detect mismatches (optimistic mgmt +
cautious auditor = red flag).
"""

import os
import json
import re
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def _clean_json(raw: str) -> str:
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


def analyze_mda_sentiment(ticker: str, company_name: str, years: list) -> dict:
    """
    Ask Gemini to assess management tone from MD&A sections.

    Returns dict with:
        - years: [{year, tone, optimism_score, key_claims, red_flags}]
        - summary: overall management trajectory
    """
    years_str = ", ".join([f"FY{y}" for y in years])

    prompt = f"""You are a forensic accounting expert specializing in analyzing Management Discussion and Analysis (MD&A) sections of Indian listed companies.

Analyze the management tone for: {company_name} (NSE: {ticker})
Years: {years_str}

For each fiscal year, assess how management characterized the companys performance, outlook, and risks in their MD&A section.

Return ONLY valid JSON with this structure:
{{
  "summary": "one line overall management tone trajectory",
  "years": [
    {{
      "year": 2022,
      "tone": "OPTIMISTIC",
      "optimism_score": 75,
      "key_claims": ["revenue guidance raised", "expansion planned"],
      "red_flags": ["no mention of debt concerns"],
      "forward_guidance": "POSITIVE",
      "risk_acknowledgment": "LOW"
    }}
  ]
}}

Rules:
- tone: VERY_OPTIMISTIC | OPTIMISTIC | BALANCED | CAUTIOUS | DEFENSIVE | EVASIVE
- optimism_score: 0 (extremely defensive/evasive) to 100 (extremely optimistic/bullish)
- forward_guidance: POSITIVE | NEUTRAL | NEGATIVE | MISSING
- risk_acknowledgment: HIGH | MEDIUM | LOW | NONE
- No apostrophes in string values
- Include all {len(years)} years
- Focus on how management FRAMED performance, not actual results
- Flag years where management was overly optimistic despite known problems
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
                from google.api_core.retry import Retry
                response = model.generate_content(
                    prompt, 
                    request_options={"retry": None, "timeout": 10}
                )
                cleaned = _clean_json(response.text)
                data = json.loads(cleaned)
                break
            except json.JSONDecodeError as je:
                print(f"[mda_sentiment] JSON parse error (attempt {attempt + 1}): {je}")
                if attempt >= MAX_RETRIES - 1:
                    raise
            except Exception as api_err:
                msg = str(api_err).lower()
                if any(k in msg for k in ("quota", "resource_exhausted", "resourceexhausted", "429", "rate limit", "per day")):
                    print(f"[mda_sentiment] Quota exceeded — skipping Gemini call.")
                    raise
                raise

        if data is None:
            raise ValueError("Failed to parse Gemini response after retries")

        year_data = data.get("years", [])
        summary = data.get("summary", "")

        scores = [y.get("optimism_score") for y in year_data if y.get("optimism_score") is not None]
        avg_score = round(sum(scores) / len(scores), 1) if scores else None

        year_data.sort(key=lambda x: x.get("year", 0))

        return {
            "years": year_data,
            "summary": summary,
            "avg_score": avg_score,
            "total_years": len(year_data),
        }

    except Exception as e:
        print(f"[mda_sentiment] Error: {e}")
        return {
            "years": [],
            "summary": f"Could not analyze MD&A sentiment: {str(e)}",
            "avg_score": None,
            "total_years": 0,
            "error": str(e),
        }


def compute_mismatch(auditor_data: dict, mda_data: dict) -> dict:
    """
    Compare auditor sentiment vs management tone year-by-year.
    A mismatch = management optimistic but auditor cautious (or vice versa).

    Returns:
        - years: [{year, auditor_score, mgmt_score, gap, mismatch_level}]
        - mismatch_count: number of years with significant mismatch
        - avg_gap: average gap across years
    """
    auditor_by_year = {}
    if auditor_data and auditor_data.get("years"):
        for y in auditor_data["years"]:
            auditor_by_year[y.get("year")] = y.get("sentiment_score", 50)

    mda_by_year = {}
    if mda_data and mda_data.get("years"):
        for y in mda_data["years"]:
            mda_by_year[y.get("year")] = y.get("optimism_score", 50)

    # Build comparison for years present in both
    all_years = sorted(set(auditor_by_year.keys()) & set(mda_by_year.keys()))

    result_years = []
    mismatches = 0
    gaps = []

    for yr in all_years:
        a_score = auditor_by_year[yr]
        m_score = mda_by_year[yr]
        gap = m_score - a_score  # Positive = mgmt more optimistic than auditor

        if gap >= 30:
            level = "CRITICAL"
            mismatches += 1
        elif gap >= 15:
            level = "HIGH"
            mismatches += 1
        elif gap >= 5:
            level = "MODERATE"
        elif gap <= -15:
            level = "INVERSE"  # Auditor more positive than management (unusual)
        else:
            level = "ALIGNED"

        gaps.append(abs(gap))
        result_years.append({
            "year": yr,
            "auditor_score": a_score,
            "mgmt_score": m_score,
            "gap": gap,
            "mismatch_level": level,
        })

    avg_gap = round(sum(gaps) / len(gaps), 1) if gaps else 0

    return {
        "years": result_years,
        "mismatch_count": mismatches,
        "avg_gap": avg_gap,
        "total_years": len(result_years),
    }
