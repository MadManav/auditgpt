"""
fetcher.py — Data Collection Module (Person 1)
Uses yfinance to pull up to 10 years of financial data for any company.
Returns a normalized dict matching the format expected by analysis modules.
"""

import yfinance as yf
import pandas as pd


def _safe_get(df, row_labels, col_idx=None):
    """
    Safely extract a value from a DataFrame by trying multiple row label names.
    Returns None if not found.
    """
    if df is None or df.empty:
        return None
    for label in row_labels:
        if label in df.index:
            if col_idx is not None:
                try:
                    val = df.loc[label].iloc[col_idx]
                    return float(val) if pd.notna(val) else None
                except (IndexError, KeyError):
                    return None
            else:
                return df.loc[label]
    return None


def _extract_yearly_values(df, row_labels):
    """
    Extract a full row of yearly values from a financial statement DataFrame.
    Tries multiple possible label names. Returns list (oldest → newest).
    """
    if df is None or df.empty:
        return []
    for label in row_labels:
        if label in df.index:
            row = df.loc[label]
            # Reverse so oldest is first (yfinance returns newest first)
            values = [float(v) if pd.notna(v) else None for v in row.values]
            values.reverse()
            return values
    return []


def _pad_or_trim(values, target_len, fill=None):
    """Pad list to target length with fill value, or trim from the start."""
    if len(values) >= target_len:
        return values[-target_len:]
    return [fill] * (target_len - len(values)) + values


def fetch_financials(ticker: str, years: int = 10) -> dict:
    """
    Fetch financial statements from yfinance and normalize into
    the dict format expected by analysis modules.

    Args:
        ticker: Stock ticker (e.g., 'TCS.NS', 'RELIANCE.NS')
        years: Number of years of data to fetch (max ~4 from yfinance annual)

    Returns:
        dict with yearly financial data lists (index 0 = oldest)
        or None if the ticker is invalid / data unavailable
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        # Pull financial statements (yfinance gives up to ~4 years annual)
        income_stmt = stock.income_stmt  # columns = dates, rows = items
        balance_sheet = stock.balance_sheet
        cashflow = stock.cashflow

        if income_stmt is None or income_stmt.empty:
            return None

        # Get the year labels from income statement columns
        year_columns = income_stmt.columns
        year_labels = [col.year for col in year_columns]
        year_labels.reverse()  # oldest first
        n_years = len(year_labels)

        # ── Income Statement ──
        revenue = _extract_yearly_values(income_stmt, [
            "Total Revenue", "Operating Revenue", "Revenue"
        ])
        net_income = _extract_yearly_values(income_stmt, [
            "Net Income", "Net Income Common Stockholders"
        ])
        gross_profit = _extract_yearly_values(income_stmt, [
            "Gross Profit"
        ])
        cost_of_goods = _extract_yearly_values(income_stmt, [
            "Cost Of Revenue", "Cost of Goods Sold", "Cost Of Goods Sold"
        ])
        sga = _extract_yearly_values(income_stmt, [
            "Selling General And Administration", "Selling And Marketing Expense",
            "General And Administrative Expense"
        ])
        depreciation = _extract_yearly_values(income_stmt, [
            "Reconciled Depreciation", "Depreciation And Amortization In Income Statement",
            "Depreciation Amortization Depletion"
        ])
        ebit = _extract_yearly_values(income_stmt, [
            "EBIT", "Operating Income"
        ])
        interest_expense = _extract_yearly_values(income_stmt, [
            "Interest Expense", "Interest Expense Non Operating",
            "Net Interest Income"
        ])
        tax_expense = _extract_yearly_values(income_stmt, [
            "Tax Provision", "Income Tax Expense", "Tax Effect Of Unusual Items"
        ])
        other_income = _extract_yearly_values(income_stmt, [
            "Other Income Expense", "Other Non Operating Income Expenses",
            "Special Income Charges"
        ])

        # ── Balance Sheet ──
        total_assets = _extract_yearly_values(balance_sheet, [
            "Total Assets"
        ])
        total_liabilities = _extract_yearly_values(balance_sheet, [
            "Total Liabilities Net Minority Interest", "Total Liabilities"
        ])
        current_assets = _extract_yearly_values(balance_sheet, [
            "Current Assets"
        ])
        current_liabilities = _extract_yearly_values(balance_sheet, [
            "Current Liabilities"
        ])
        total_debt = _extract_yearly_values(balance_sheet, [
            "Total Debt", "Long Term Debt And Capital Lease Obligation",
            "Long Term Debt"
        ])
        receivables = _extract_yearly_values(balance_sheet, [
            "Receivables", "Accounts Receivable", "Net Receivables"
        ])
        inventory = _extract_yearly_values(balance_sheet, [
            "Inventory", "Raw Materials", "Finished Goods"
        ])

        # ── Cash Flow Statement ──
        operating_cash_flow = _extract_yearly_values(cashflow, [
            "Operating Cash Flow", "Cash Flow From Continuing Operating Activities",
            "Free Cash Flow"
        ])
        capex = _extract_yearly_values(cashflow, [
            "Capital Expenditure", "Purchase Of PPE",
            "Net PPE Purchase And Sale"
        ])

        # ── Compute derived fields ──
        working_capital = []
        for i in range(n_years):
            ca = current_assets[i] if i < len(current_assets) else None
            cl = current_liabilities[i] if i < len(current_liabilities) else None
            if ca is not None and cl is not None:
                working_capital.append(ca - cl)
            else:
                working_capital.append(None)

        # Make capex positive (yfinance reports it as negative)
        capex = [abs(v) if v is not None else None for v in capex]

        # Make interest_expense positive
        interest_expense = [abs(v) if v is not None else None for v in interest_expense]

        # Handle missing SGA — fill with zeros if not available
        if not sga:
            sga = [0] * n_years

        # Handle missing other_income
        if not other_income:
            other_income = [0] * n_years

        # Pad all lists to same length
        all_fields = {
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
        }

        # Pad each list to n_years
        for key in all_fields:
            all_fields[key] = _pad_or_trim(all_fields[key], n_years, fill=None)

        # Replace any remaining None in critical fields with 0
        for key in ["sga", "other_income", "depreciation", "inventory"]:
            all_fields[key] = [v if v is not None else 0 for v in all_fields[key]]

        result = {
            "ticker": ticker,
            "company_name": info.get("longName", info.get("shortName", ticker)),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "years": year_labels,
            **all_fields,
        }

        return result

    except Exception as e:
        print(f"[fetcher] Error fetching data for {ticker}: {e}")
        return None


def get_company_info(ticker: str) -> dict:
    """
    Fetch basic company info: name, sector, industry, market cap.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        return {
            "ticker": ticker,
            "name": info.get("longName", info.get("shortName", ticker)),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "market_cap": info.get("marketCap", None),
            "country": info.get("country", "Unknown"),
            "website": info.get("website", ""),
            "description": info.get("longBusinessSummary", ""),
        }
    except Exception as e:
        print(f"[fetcher] Error fetching info for {ticker}: {e}")
        return {"ticker": ticker, "name": ticker, "sector": "Unknown", "industry": "Unknown"}


if __name__ == "__main__":
    # Quick test
    import json
    ticker = "TCS.NS"
    print(f"Fetching data for {ticker}...")
    data = fetch_financials(ticker)
    if data:
        print(f"Company: {data['company_name']}")
        print(f"Sector: {data['sector']}")
        print(f"Years: {data['years']}")
        print(f"Revenue: {data['revenue']}")
        print(f"Net Income: {data['net_income']}")
        print(f"OCF: {data['operating_cash_flow']}")
        print(f"Total Debt: {data['total_debt']}")
        print(f"Receivables: {data['receivables']}")
    else:
        print("Failed to fetch data!")
