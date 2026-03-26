"""
auditor_sentiment.py — Auditor Note Sentiment Analysis (Gemini-powered)
Analyzes how auditor opinions and language changed over the filing history.
"""

import os
import json
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


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


def analyze_auditor_sentiment(ticker: str, company_name: str, years: list) -> dict:
    """
    Call Gemini to analyze auditor sentiment for a company over multiple years.

    Returns dict with:
        - years: list of year-wise auditor data
        - summary: overall trajectory
        - avg_score: average sentiment score
    """
    years_str = ", ".join([f"FY{y}" for y in years])

    prompt = f"""You are a forensic accounting expert analyzing Indian listed company audit reports.

Analyze auditor sentiment for: {company_name} (NSE: {ticker})
Years: {years_str}

For each fiscal year, use your knowledge of this company's public audit reports filed with BSE/NSE/MCA/SEBI.

Return ONLY valid JSON with this structure:
{{
  "summary": "one line overall trajectory",
  "years": [
    {{
      "year": 2022,
      "auditor_name": "firm name",
      "auditor_changed": false,
      "opinion_type": "UNQUALIFIED",
      "key_issues": ["issue one", "issue two"],
      "going_concern": false,
      "related_party_flag": false,
      "language_tone": "CLEAN",
      "sentiment_score": 85,
      "confidence": "HIGH"
    }}
  ]
}}

Rules:
- opinion_type: UNQUALIFIED | QUALIFIED | ADVERSE | DISCLAIMER | EMPHASIS_OF_MATTER
- language_tone: CLEAN | CAUTIOUS | HEDGED | ALARMED | CRITICAL
- confidence: HIGH | MEDIUM | LOW
- sentiment_score: 0 (collapse) to 100 (perfectly clean)
- No apostrophes in string values
- Include all {len(years)} years
"""

    MAX_RETRIES = 3
    data = None

    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=4096,
                    response_mime_type="application/json",
                ),
            )
            cleaned = _clean_json(response.text)
            data = json.loads(cleaned)
            break  # Success

        except json.JSONDecodeError as je:
            print(f"[auditor_sentiment] JSON parse error (attempt {attempt + 1}/{MAX_RETRIES}): {je}")
            if attempt >= MAX_RETRIES - 1:
                raise

        except Exception as api_err:
            msg = str(api_err).lower()
            if any(k in msg for k in ("quota", "resource_exhausted", "resourceexhausted", "429", "rate limit", "per day")):
                print(f"[auditor_sentiment] Quota exceeded — skipping Gemini call.")
                raise
            if attempt >= MAX_RETRIES - 1:
                raise
            print(f"[auditor_sentiment] Attempt {attempt + 1} failed: {api_err}. Retrying...")

    if data is None:
        raise ValueError("Failed to parse Gemini response after retries")

    year_data = data.get("years", [])
    summary = data.get("summary", "")

    scores = [y.get("sentiment_score") for y in year_data if y.get("sentiment_score") is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else None

    going_concern_count = sum(1 for y in year_data if y.get("going_concern"))
    related_party_count = sum(1 for y in year_data if y.get("related_party_flag"))
    auditor_changes = sum(1 for y in year_data if y.get("auditor_changed"))
    qualified_count = sum(1 for y in year_data if y.get("opinion_type") not in ["UNQUALIFIED", "EMPHASIS_OF_MATTER"])

    year_data.sort(key=lambda x: x.get("year", 0))

    return {
        "years": year_data,
        "summary": summary,
        "avg_score": avg_score,
        "going_concern_count": going_concern_count,
        "related_party_count": related_party_count,
        "auditor_changes": auditor_changes,
        "qualified_count": qualified_count,
        "total_years": len(year_data),
    }

    # Outer exception handler — returns safe fallback
    # (unreachable after successful return above; kept for structure clarity)


def _safe_fallback(e: Exception) -> dict:
    return {
        "years": [],
        "summary": f"Could not analyze auditor sentiment: {str(e)}",
        "avg_score": None,
        "going_concern_count": 0,
        "related_party_count": 0,
        "auditor_changes": 0,
        "qualified_count": 0,
        "total_years": 0,
        "error": str(e),
    }


# Wrap the public function with error handling
_raw_analyze = analyze_auditor_sentiment

def analyze_auditor_sentiment(ticker: str, company_name: str, years: list) -> dict:
    try:
        return _raw_analyze(ticker, company_name, years)
    except Exception as e:
        return _safe_fallback(e)