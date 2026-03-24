"""
screener.py — Screener.in Scraper for 10-Year Financial Data
Scrapes consolidated financial statements from screener.in.
Returns data in the SAME format as fetcher.py for seamless integration.
"""

import requests
from bs4 import BeautifulSoup
import re


def _parse_number(text: str):
    """Convert Screener.in number string to float. Returns None if invalid."""
    if not text or text.strip() in ('', '-', 'N/A'):
        return None
    # Remove commas and percentage signs
    clean = text.strip().replace(',', '').replace('%', '')
    try:
        return float(clean)
    except ValueError:
        return None


def _scrape_table(soup, section_id: str) -> dict:
    """
    Scrape a financial table from Screener.in.
    Returns: { "row_label": [val_oldest, ..., val_newest], ... }
    """
    section = soup.find('section', id=section_id)
    if not section:
        return {}

    table = section.find('table')
    if not table:
        return {}

    rows = table.find_all('tr')
    if not rows:
        return {}

    # First row is the header with year labels
    header_cells = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
    # Extract year labels (skip first empty cell), filter only "Mar YYYY" etc
    year_labels = []
    for h in header_cells[1:]:
        match = re.search(r'(\d{4})', h)
        if match:
            year_labels.append(int(match.group(1)))

    n_years = len(year_labels)
    result = {}

    for row in rows[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all(['th', 'td'])]
        if not cells or len(cells) < 2:
            continue

        label = cells[0].rstrip('+').strip()
        # Get values — Screener shows oldest to newest (left to right)
        values = []
        for cell_text in cells[1:n_years + 1]:
            values.append(_parse_number(cell_text))

        result[label] = values

    return result


def _get_row(data: dict, *labels, default_len: int = 0):
    """Get a row by trying multiple label names. Returns list or empty list."""
    for label in labels:
        if label in data:
            return data[label]
    return [None] * default_len if default_len else []


def _to_crores_to_raw(values: list) -> list:
    """
    Screener shows values in Crores. Convert to raw numbers (multiply by 1e7)
    to match yfinance format.
    """
    return [v * 1e7 if v is not None else None for v in values]


def fetch_from_screener(company_slug: str) -> dict:
    """
    Fetch 10-year financial data from Screener.in.

    Args:
        company_slug: Screener.in company slug (e.g., 'TCS', 'RELIANCE', 'YESBANK')

    Returns:
        dict in the SAME format as fetcher.fetch_financials(), or None on failure.
    """
    url = f"https://www.screener.in/company/{company_slug}/consolidated/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            # Try standalone (non-consolidated) version
            url = f"https://www.screener.in/company/{company_slug}/"
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code != 200:
                print(f"[screener] HTTP {r.status_code} for {company_slug}")
                return None

        soup = BeautifulSoup(r.text, 'html.parser')

        # ── Scrape all three tables ──
        pl = _scrape_table(soup, 'profit-loss')
        bs = _scrape_table(soup, 'balance-sheet')
        cf = _scrape_table(soup, 'cash-flow')

        if not pl:
            print(f"[screener] No P&L data for {company_slug}")
            return None

        # Determine year count from the first P&L row
        first_key = next(iter(pl))
        n_years = len(pl[first_key])

        # Extract year labels from header
        section = soup.find('section', id='profit-loss')
        header_cells = [th.get_text(strip=True) for th in section.find('tr').find_all(['th', 'td'])]
        year_labels = []
        for h in header_cells[1:]:
            match = re.search(r'(\d{4})', h)
            if match:
                year_labels.append(int(match.group(1)))
        year_labels = year_labels[:n_years]

        # ── Map Screener rows to our format ──
        # P&L (Screener shows in Cr)
        # Banks use 'Revenue'/'Interest Earned' instead of 'Sales'
        revenue = _to_crores_to_raw(_get_row(pl, 'Sales', 'Revenue', 'Interest Earned', 'Revenue from Operations', default_len=n_years))
        net_income = _to_crores_to_raw(_get_row(pl, 'Net Profit', 'Financing Profit', default_len=n_years))
        operating_profit = _to_crores_to_raw(_get_row(pl, 'Operating Profit', 'Financing Profit', default_len=n_years))
        depreciation = _to_crores_to_raw(_get_row(pl, 'Depreciation', default_len=n_years))
        interest_expense = _to_crores_to_raw(_get_row(pl, 'Interest', 'Interest Expended', default_len=n_years))
        other_income = _to_crores_to_raw(_get_row(pl, 'Other Income', default_len=n_years))
        expenses = _to_crores_to_raw(_get_row(pl, 'Expenses', default_len=n_years))
        tax_pct = _get_row(pl, 'Tax %', 'Tax', default_len=n_years)

        # IMPORTANT: Do NOT approximate COGS, Gross Profit, SGA from Screener data.
        # Screener's "Expenses" = ALL operating expenses, not just COGS.
        # Using it for Beneish M-Score gives FALSE fraud flags.
        # These fields will be filled by accurate yfinance data in fetcher.py merge.
        cost_of_goods = [None] * n_years
        gross_profit = [None] * n_years

        # Compute tax expense from tax % and profit before tax
        pbt = _to_crores_to_raw(_get_row(pl, 'Profit before tax', default_len=n_years))
        tax_expense = []
        for i in range(n_years):
            pbt_val = pbt[i] if i < len(pbt) else None
            tp = tax_pct[i] if i < len(tax_pct) else None
            if pbt_val is not None and tp is not None:
                tax_expense.append(pbt_val * tp / 100)
            else:
                tax_expense.append(None)

        # Balance Sheet (in Cr)
        total_assets = _to_crores_to_raw(_get_row(bs, 'Total Assets', default_len=n_years))
        # NOTE: Screener's "Total Liabilities" = Total Assets (includes equity!)
        # Real liabilities = Borrowings + Deposits + Other Liabilities
        borrowings = _to_crores_to_raw(_get_row(bs, 'Borrowings', default_len=n_years))
        deposits = _to_crores_to_raw(_get_row(bs, 'Deposits', default_len=n_years))
        other_liabilities = _to_crores_to_raw(_get_row(bs, 'Other Liabilities', default_len=n_years))
        other_assets = _to_crores_to_raw(_get_row(bs, 'Other Assets', default_len=n_years))
        investments = _to_crores_to_raw(_get_row(bs, 'Investments', default_len=n_years))
        fixed_assets = _to_crores_to_raw(_get_row(bs, 'Fixed Assets', default_len=n_years))
        reserves = _to_crores_to_raw(_get_row(bs, 'Reserves', default_len=n_years))
        equity_capital = _to_crores_to_raw(_get_row(bs, 'Equity Capital', default_len=n_years))

        # total_debt = Borrowings + Deposits (for banks, deposits are the main liability)
        total_debt = []
        for i in range(n_years):
            borrow_val = borrowings[i] if i < len(borrowings) else 0
            deposit_val = deposits[i] if i < len(deposits) else 0
            total_debt.append((borrow_val or 0) + (deposit_val or 0))

        # Compute REAL total liabilities (without equity)
        total_liabilities = []
        for i in range(n_years):
            debt_val = total_debt[i] if i < len(total_debt) else 0
            other_val = other_liabilities[i] if i < len(other_liabilities) else 0
            total_liabilities.append((debt_val or 0) + (other_val or 0))

        # Screener doesn't have separate Current Assets/Liabilities
        # Approximate: Current Assets ≈ Other Assets, Current Liabilities ≈ Other Liabilities
        current_assets = other_assets if other_assets else [None] * n_years
        current_liabilities = other_liabilities if other_liabilities else [None] * n_years

        # These fields are NOT available on Screener — leave as None.
        # yfinance will fill in accurate values for the years it covers.
        receivables = [None] * n_years
        inventory = [None] * n_years
        sga = [None] * n_years

        # Cash Flow (in Cr)
        operating_cash_flow = _to_crores_to_raw(_get_row(cf, 'Cash from Operating Activity', default_len=n_years))
        investing_cf = _to_crores_to_raw(_get_row(cf, 'Cash from Investing Activity', default_len=n_years))

        # Capex ≈ abs(investing cash flow) (rough approximation)
        capex = [abs(v) if v is not None else None for v in investing_cf]

        # Working capital
        working_capital = []
        for i in range(n_years):
            ca = current_assets[i] if i < len(current_assets) else None
            cl = current_liabilities[i] if i < len(current_liabilities) else None
            if ca is not None and cl is not None:
                working_capital.append(ca - cl)
            else:
                working_capital.append(None)

        # Make interest_expense positive
        interest_expense = [abs(v) if v is not None else None for v in interest_expense]

        # EBIT = Operating Profit
        ebit = operating_profit

        result = {
            "ticker": company_slug,
            "company_name": company_slug,  # Will be overridden by yfinance info
            "sector": "Unknown",  # Will be overridden by yfinance info
            "industry": "Unknown",
            "years": year_labels,
            "revenue": revenue,
            "net_income": net_income,
            "operating_cash_flow": operating_cash_flow,
            "total_debt": total_debt,
            "receivables": receivables,
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "current_assets": current_assets,
            "current_liabilities": current_liabilities,
            "cost_of_goods": cost_of_goods,
            "depreciation": depreciation,
            "sga": sga,
            "gross_profit": gross_profit,
            "inventory": inventory,
            "working_capital": working_capital,
            "capex": capex,
            "other_income": other_income,
            "tax_expense": tax_expense,
            "ebit": ebit,
            "interest_expense": interest_expense,
            "data_source": "screener.in",
        }

        print(f"[screener] Fetched {n_years} years for {company_slug}")
        return result

    except Exception as e:
        print(f"[screener] Error: {e}")
        return None


def ticker_to_slug(ticker: str) -> str:
    """Convert yfinance ticker to Screener.in slug. E.g., 'TCS.NS' → 'TCS'"""
    return ticker.replace('.NS', '').replace('.BO', '').strip()


if __name__ == "__main__":
    data = fetch_from_screener("TCS")
    if data:
        print(f"Years: {data['years']}")
        print(f"Revenue (Cr): {[round(v/1e7) if v else None for v in data['revenue']]}")
        print(f"Net Income (Cr): {[round(v/1e7) if v else None for v in data['net_income']]}")
        print(f"Total years: {len(data['years'])}")
    else:
        print("Failed!")
