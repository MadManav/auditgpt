"""
pdf_parser.py — Local Annual Report PDF Parsing (NO Gemini API needed)
Uses pdfplumber to extract text locally, then keyword-matches for:
  - Auditor name, opinion type, key audit matters, page references
  - Going concern, related party flags
Falls back to Gemini-from-memory for years without local PDFs.
"""

import os
import glob
import re
import pdfplumber

# ── Ticker → Folder Mapping ──
TICKER_FOLDER_MAP = {
    "MARUTI.NS": "Automobile (Maruti Suzuki)",
    "MARUTI": "Automobile (Maruti Suzuki)",
    "ITC.NS": "Fast moving goods (ITC)/Fast moving goods (ITC)",
    "ITC": "Fast moving goods (ITC)/Fast moving goods (ITC)",
    "SUNPHARMA.NS": "HealthCare (Sun pharmaceutical)/HealthCare (Sun pharmaceutical)",
    "SUNPHARMA": "HealthCare (Sun pharmaceutical)/HealthCare (Sun pharmaceutical)",
    "INFY.NS": "IT  (Infosys)",
    "INFY": "IT  (Infosys)",
    "ONGC.NS": "Oil, Gas &Energy (ONGC)",
    "ONGC": "Oil, Gas &Energy (ONGC)",
    "HDFCBANK.NS": "banking sector (HDFC)",
    "HDFCBANK": "banking sector (HDFC)",
    "HDFC.NS": "banking sector (HDFC)",
    "HDFC": "banking sector (HDFC)",
    "LT.NS": "infra (L&T)",
    "LT": "infra (L&T)",
}

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Nse company reports")

# ── Known Big-4 and major audit firms ──
AUDIT_FIRMS = [
    "Deloitte Haskins & Sells",
    "Deloitte Haskins and Sells",
    "Price Waterhouse",
    "PricewaterhouseCoopers",
    "KPMG",
    "Ernst & Young",
    "Ernst and Young",
    "S R Batliboi",
    "S.R. Batliboi",
    "B S R & Co",
    "B S R and Co",
    "BSR & Co",
    "Walker Chandiok",
    "Sharp & Tannan",
    "Brahmayya & Co",
    "Sundaram & Srinivasan",
    "M S K A & Associates",
    "MSKA & Associates",
    "Khimji Kunverji",
    "Lodha & Co",
    "G M Kapadia",
    "Kalyaniwalla & Mistry",
    "S R B C & CO",
    "SRBC & CO",
]

# ── Keyword patterns ──
OPINION_PATTERNS = {
    "ADVERSE": [r"adverse\s+opinion", r"we\s+do\s+not\s+express\s+an?\s+opinion"],
    "DISCLAIMER": [r"disclaimer\s+of\s+opinion"],
    "QUALIFIED": [r"qualified\s+opinion", r"except\s+for\s+the\s+(?:effects?|matters?)"],
    "EMPHASIS_OF_MATTER": [r"emphasis\s+of\s+matter", r"material\s+uncertainty"],
    "UNQUALIFIED": [r"true\s+and\s+fair\s+view", r"present\s+fairly.*in\s+all\s+material\s+respects"],
}

GOING_CONCERN_PATTERNS = [
    r"going\s+concern",
    r"material\s+uncertainty.*(?:ability|continue)",
    r"ability.*continue\s+as\s+a?\s*going\s+concern",
]

RELATED_PARTY_PATTERNS = [
    r"related\s+party\s+transaction",
    r"related\s+party\s+disclosure",
]

KAM_PATTERNS = [
    r"key\s+audit\s+matter",
    r"significant\s+audit\s+matter",
]


def find_pdf_for_ticker(ticker, year=None):
    """Find available PDF annual reports for a ticker."""
    folder_name = TICKER_FOLDER_MAP.get(ticker.upper())
    if not folder_name:
        clean_ticker = ticker.upper().replace(".NS", "")
        folder_name = TICKER_FOLDER_MAP.get(clean_ticker)

    if not folder_name:
        return []

    folder_path = os.path.join(REPORTS_DIR, folder_name)
    if not os.path.isdir(folder_path):
        return []

    pdfs = []
    for f in glob.glob(os.path.join(folder_path, "*.pdf")):
        basename = os.path.splitext(os.path.basename(f))[0]
        try:
            pdf_year = int(basename)
            if year is None or pdf_year == year:
                pdfs.append((pdf_year, f))
        except ValueError:
            continue

    pdfs.sort(key=lambda x: x[0])
    return pdfs


def _extract_text_with_pages(pdf_path):
    """Extract text from PDF, returning list of (page_number, text) tuples."""
    pages = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                pages.append((i + 1, text))  # 1-indexed pages
    except Exception as e:
        print(f"[pdf_parser] Error reading PDF {pdf_path}: {e}")
    return pages


def _find_auditor_name(full_text):
    """Find the auditor firm name from the report text."""
    for firm in AUDIT_FIRMS:
        if firm.lower() in full_text.lower():
            return firm
    # Try to find "Chartered Accountants" pattern
    match = re.search(r'(?:For\s+)?([A-Z][A-Za-z\s&.]+?)(?:\s*,?\s*(?:LLP)?)\s*\n?\s*Chartered\s+Accountants', full_text)
    if match:
        return match.group(1).strip()
    return "Not identified"


def _find_opinion_type(audit_section_text):
    """Determine the audit opinion type from the auditor report section."""
    text_lower = audit_section_text.lower()
    # Check in order of severity (most severe first)
    for opinion_type in ["ADVERSE", "DISCLAIMER", "QUALIFIED", "EMPHASIS_OF_MATTER", "UNQUALIFIED"]:
        for pattern in OPINION_PATTERNS[opinion_type]:
            if re.search(pattern, text_lower):
                return opinion_type
    return "UNQUALIFIED"  # Default if "true and fair view" not explicitly found


def _find_pages_for_pattern(pages_text, patterns):
    """Find page numbers where any of the patterns appear."""
    found_pages = []
    for page_num, text in pages_text:
        text_lower = text.lower()
        for pattern in patterns:
            if re.search(pattern, text_lower):
                found_pages.append(page_num)
                break
    return found_pages


def _extract_key_issues(pages_text, audit_pages):
    """Extract key audit matters / issues from the report."""
    issues = []
    kam_pages = _find_pages_for_pattern(pages_text, KAM_PATTERNS)

    if kam_pages:
        # Extract text from KAM pages
        for page_num, text in pages_text:
            if page_num in kam_pages:
                # Find bullet points or numbered items
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    # Look for KAM titles (usually bold/capitalized or numbered)
                    if len(line) > 20 and len(line) < 200:
                        if any(kw in line.lower() for kw in [
                            'revenue', 'loan', 'provision', 'impairment', 'goodwill',
                            'tax', 'investment', 'valuation', 'allowance', 'fair value',
                            'asset', 'liability', 'compliance', 'fraud', 'risk',
                            'classification', 'it system', 'information technology',
                            'npa', 'non-performing', 'deposit', 'capital adequacy',
                        ]):
                            clean_line = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
                            if clean_line and clean_line not in issues:
                                issues.append(clean_line)

    return issues[:5]  # Top 5 issues


def _compute_sentiment_score(opinion_type, has_going_concern, has_emphasis, num_kam_issues):
    """Compute a sentiment score (0-100) based on extracted facts."""
    score = 85  # Base score for clean report

    if opinion_type == "ADVERSE":
        score = 15
    elif opinion_type == "DISCLAIMER":
        score = 25
    elif opinion_type == "QUALIFIED":
        score = 45
    elif opinion_type == "EMPHASIS_OF_MATTER":
        score = 65

    if has_going_concern:
        score -= 20
    if num_kam_issues > 3:
        score -= 5

    return max(0, min(100, score))


def parse_annual_report_pdf(pdf_path, ticker, company_name, year):
    """
    Parse a single annual report PDF using LOCAL text extraction.
    No API calls needed — uses pdfplumber + keyword matching.
    """
    print(f"[pdf_parser] 📄 Parsing locally: {os.path.basename(pdf_path)} for {company_name} FY{year}")

    pages_text = _extract_text_with_pages(pdf_path)
    if not pages_text:
        print(f"[pdf_parser] ❌ Could not extract text from {pdf_path}")
        return None

    full_text = "\n".join(text for _, text in pages_text)
    total_pages = len(pages_text)

    # 1. Find auditor name
    auditor_name = _find_auditor_name(full_text)

    # 2. Find audit report pages
    audit_report_pages = _find_pages_for_pattern(pages_text, [
        r"independent\s+auditor", r"independent\s+audit", r"auditor.?s?\s+report"
    ])

    # 3. Get audit section text for opinion detection
    audit_text = ""
    if audit_report_pages:
        for page_num, text in pages_text:
            if page_num in audit_report_pages:
                audit_text += text + "\n"
    else:
        # Use first 20% of document as fallback
        cutoff = max(1, total_pages // 5)
        for page_num, text in pages_text[:cutoff]:
            audit_text += text + "\n"

    # 4. Determine opinion type
    opinion_type = _find_opinion_type(audit_text)

    # 5. Check for emphasis of matter (can coexist with unqualified)
    has_emphasis = bool(re.search(r"emphasis\s+of\s+matter", full_text.lower()))
    if has_emphasis and opinion_type == "UNQUALIFIED":
        opinion_type = "EMPHASIS_OF_MATTER"

    # 6. Going concern check
    gc_pages = _find_pages_for_pattern(pages_text, GOING_CONCERN_PATTERNS)
    has_going_concern = len(gc_pages) > 0

    # 7. Related party check
    rp_pages = _find_pages_for_pattern(pages_text, RELATED_PARTY_PATTERNS)
    has_related_party = len(rp_pages) > 0

    # 8. KAM pages
    kam_pages = _find_pages_for_pattern(pages_text, KAM_PATTERNS)

    # 9. Notes to accounts pages
    notes_pages = _find_pages_for_pattern(pages_text, [r"notes\s+to\s+(?:the\s+)?(?:financial|standalone|consolidated)\s+statement"])

    # 10. Extract key issues
    key_issues = _extract_key_issues(pages_text, audit_report_pages)

    # 11. Determine tone
    cautious_words = len(re.findall(r'(?:uncertain|concern|risk|significant|material|adverse)', full_text.lower()))
    if cautious_words > 50:
        tone = "ALARMED"
    elif cautious_words > 30:
        tone = "CAUTIOUS"
    elif cautious_words > 15:
        tone = "HEDGED"
    else:
        tone = "CLEAN"

    # 12. Compute score
    sentiment_score = _compute_sentiment_score(opinion_type, has_going_concern, has_emphasis, len(key_issues))

    # Format page references
    def fmt_pages(pg_list):
        if not pg_list:
            return "Not found"
        if len(pg_list) <= 3:
            return ", ".join(str(p) for p in pg_list)
        return f"{pg_list[0]}-{pg_list[-1]}"

    result = {
        "year": year,
        "auditor_name": auditor_name,
        "auditor_changed": False,
        "opinion_type": opinion_type,
        "key_issues": key_issues if key_issues else [f"Report parsed — {opinion_type.replace('_', ' ').title()} opinion on p.{fmt_pages(audit_report_pages)}"],
        "going_concern": has_going_concern,
        "related_party_flag": has_related_party,
        "language_tone": tone,
        "sentiment_score": sentiment_score,
        "confidence": "HIGH",
        "source": "PDF",
        "pdf_file": os.path.basename(pdf_path),
        "page_references": {
            "auditor_report": fmt_pages(audit_report_pages),
            "key_audit_matters": fmt_pages(kam_pages),
            "notes_to_accounts": fmt_pages(notes_pages),
            "related_party": fmt_pages(rp_pages),
        },
        "notable_findings": [],
    }

    # Build notable findings
    if has_going_concern:
        result["notable_findings"].append(f"⚠️ Going concern mentioned on p.{fmt_pages(gc_pages)}")
    if has_related_party:
        result["notable_findings"].append(f"📋 Related party disclosures on p.{fmt_pages(rp_pages)}")
    if kam_pages:
        result["notable_findings"].append(f"🔍 Key Audit Matters on p.{fmt_pages(kam_pages)}")
    if opinion_type != "UNQUALIFIED":
        result["notable_findings"].append(f"🚩 Opinion: {opinion_type.replace('_', ' ')} — see p.{fmt_pages(audit_report_pages)}")

    print(f"[pdf_parser] ✅ FY{year}: {opinion_type} | Auditor: {auditor_name} | Score: {sentiment_score}")
    return result


def analyze_with_pdfs(ticker, company_name, years):
    """
    Hybrid analysis: Use local PDF parsing where available,
    fall back to Gemini-from-memory for remaining years.
    """
    available_pdfs = find_pdf_for_ticker(ticker)
    pdf_years = {y: path for y, path in available_pdfs}
    has_pdfs = len(pdf_years) > 0

    print(f"[pdf_parser] Found {len(pdf_years)} PDFs for {ticker}: {list(pdf_years.keys())}")

    year_data = []
    pdf_parsed_count = 0
    memory_years = []

    # Parse ALL available PDFs locally (no API quota concern!)
    for year in years:
        yr = int(str(year)[:4]) if year else None
        if yr and yr in pdf_years:
            result = parse_annual_report_pdf(pdf_years[yr], ticker, company_name, yr)
            if result:
                year_data.append(result)
                pdf_parsed_count += 1
                continue
        # Track years needing memory-based analysis
        if yr:
            memory_years.append(yr)

    # Detect auditor changes across parsed years
    auditor_names = [(d["year"], d["auditor_name"]) for d in year_data if d.get("auditor_name")]
    auditor_names.sort()
    for i in range(1, len(auditor_names)):
        if auditor_names[i][1] != auditor_names[i-1][1]:
            for d in year_data:
                if d["year"] == auditor_names[i][0]:
                    d["auditor_changed"] = True

    # For remaining years, use Gemini from memory (batch)
    if memory_years:
        try:
            from analysis.auditor_sentiment import analyze_auditor_sentiment
            memory_result = analyze_auditor_sentiment(ticker, company_name, memory_years)
            memory_year_data = memory_result.get("years", [])

            if memory_year_data:
                for y_data in memory_year_data:
                    y_data["source"] = "AI_MEMORY"
                    y_data["confidence"] = y_data.get("confidence", "MEDIUM")
                    year_data.append(y_data)
            else:
                raise ValueError(memory_result.get("summary", "No data returned"))

        except Exception as e:
            print(f"[pdf_parser] Memory fallback failed: {e}")
            for yr in memory_years:
                year_data.append({
                    "year": yr,
                    "source": "UNAVAILABLE",
                    "sentiment_score": 50,
                    "opinion_type": "UNKNOWN",
                    "auditor_name": "Data unavailable (API error)",
                    "auditor_changed": False,
                    "going_concern": False,
                    "related_party_flag": False,
                    "language_tone": "UNKNOWN",
                    "key_issues": ["No PDF available — AI memory unavailable"],
                    "confidence": "NONE",
                })

    # Sort by year
    year_data.sort(key=lambda x: x.get("year", 0))

    # Compute aggregates
    scores = [y.get("sentiment_score") for y in year_data if y.get("sentiment_score") is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else None
    going_concern_count = sum(1 for y in year_data if y.get("going_concern"))
    related_party_count = sum(1 for y in year_data if y.get("related_party_flag"))
    auditor_changes = sum(1 for y in year_data if y.get("auditor_changed"))
    qualified_count = sum(1 for y in year_data if y.get("opinion_type") not in ["UNQUALIFIED", "EMPHASIS_OF_MATTER", "UNKNOWN", None])

    source_summary = f"{pdf_parsed_count} from PDF, {len(memory_years)} from AI memory"

    return {
        "years": year_data,
        "summary": f"Analyzed {len(year_data)} years ({source_summary})",
        "avg_score": avg_score,
        "going_concern_count": going_concern_count,
        "related_party_count": related_party_count,
        "auditor_changes": auditor_changes,
        "qualified_count": qualified_count,
        "total_years": len(year_data),
        "has_pdfs": has_pdfs,
        "pdf_count": pdf_parsed_count,
        "source_summary": source_summary,
    }
