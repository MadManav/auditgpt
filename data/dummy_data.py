"""
dummy_data.py — Fallback/Test Data (Person 1)
Provides hardcoded sample financial data for development and demos.
Data intentionally includes some suspicious patterns to trigger fraud signals.
"""


def get_dummy_data(ticker: str = "TEST") -> dict:
    """
    Returns hardcoded sample financial data (10 years) for testing.
    Data is structured as dict of lists, each list = 10 years of values.
    Index 0 = oldest year, Index 9 = most recent year.
    
    Returns:
        dict with keys: years, revenue, net_income, operating_cash_flow,
        total_debt, receivables, total_assets, total_liabilities,
        current_assets, current_liabilities, cost_of_goods, depreciation,
        sga, gross_profit, inventory, working_capital, capex,
        other_income, tax_expense, ebit, interest_expense
    """
    data = {
        "ticker": ticker,
        "company_name": f"Test Company ({ticker})",
        "sector": "IT",
        "years": [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],

        # Revenue growing steadily, but with suspicious acceleration in later years
        "revenue": [
            10000, 11500, 13200, 15000, 16800, 19500, 24000, 31000, 42000, 55000
        ],

        # Net income growing but with some inconsistencies vs cash flow
        "net_income": [
            1500, 1800, 2100, 2400, 2600, 3200, 4200, 5800, 8500, 12000
        ],

        # Cash flow NOT keeping up with net income (red flag)
        "operating_cash_flow": [
            1400, 1700, 2000, 2200, 2100, 2800, 3000, 3200, 4000, 4500
        ],

        # Debt growing faster than revenue (red flag)
        "total_debt": [
            5000, 5500, 6000, 7000, 8500, 11000, 15000, 22000, 32000, 45000
        ],

        # Receivables growing faster than revenue (red flag)
        "receivables": [
            1200, 1500, 1800, 2200, 2800, 3800, 5500, 8000, 12000, 18000
        ],

        "total_assets": [
            20000, 23000, 26000, 30000, 35000, 42000, 52000, 68000, 90000, 120000
        ],

        "total_liabilities": [
            8000, 9500, 11000, 13000, 16000, 20000, 27000, 38000, 52000, 72000
        ],

        "current_assets": [
            6000, 7000, 8000, 9000, 10000, 12000, 14000, 17000, 21000, 26000
        ],

        "current_liabilities": [
            3000, 3500, 4000, 4800, 5800, 7200, 9500, 13000, 18000, 24000
        ],

        "cost_of_goods": [
            6000, 6800, 7800, 8800, 10000, 11500, 14500, 19000, 26000, 34000
        ],

        # Depreciation declining as % of assets (suspicious)
        "depreciation": [
            800, 900, 1000, 1050, 1050, 1100, 1100, 1150, 1200, 1200
        ],

        # SGA expenses
        "sga": [
            1500, 1700, 1900, 2100, 2300, 2700, 3200, 3800, 4500, 5500
        ],

        "gross_profit": [
            4000, 4700, 5400, 6200, 6800, 8000, 9500, 12000, 16000, 21000
        ],

        # Inventory building up (red flag for non-service companies)
        "inventory": [
            800, 900, 1100, 1400, 1800, 2500, 3500, 5200, 7800, 11000
        ],

        "working_capital": [
            3000, 3500, 4000, 4200, 4200, 4800, 4500, 4000, 3000, 2000
        ],

        # Capex declining while revenue grows (red flag)
        "capex": [
            2000, 2200, 2500, 2400, 2000, 1800, 1600, 1500, 1400, 1300
        ],

        # Other income spiking in recent years (red flag)
        "other_income": [
            100, 120, 130, 150, 200, 400, 800, 1500, 2500, 4000
        ],

        "tax_expense": [
            500, 600, 700, 800, 860, 1050, 1400, 1900, 2800, 3900
        ],

        "ebit": [
            2000, 2400, 2800, 3200, 3500, 4300, 5600, 7700, 11300, 15900
        ],

        "interest_expense": [
            400, 440, 480, 560, 680, 880, 1200, 1760, 2560, 3600
        ],
    }

    return data


def get_clean_dummy_data(ticker: str = "CLEAN") -> dict:
    """
    Returns clean/healthy financial data with no suspicious patterns.
    Useful for testing that signals DON'T fire on healthy companies.
    """
    data = {
        "ticker": ticker,
        "company_name": f"Clean Company ({ticker})",
        "sector": "IT",
        "years": [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025],

        "revenue": [
            10000, 11000, 12100, 13300, 14600, 16000, 17600, 19400, 21300, 23400
        ],
        "net_income": [
            1500, 1650, 1815, 2000, 2200, 2400, 2640, 2900, 3200, 3500
        ],
        "operating_cash_flow": [
            1600, 1760, 1940, 2130, 2340, 2570, 2830, 3110, 3420, 3760
        ],
        "total_debt": [
            3000, 3100, 3200, 3300, 3400, 3500, 3600, 3700, 3800, 3900
        ],
        "receivables": [
            1200, 1320, 1450, 1590, 1750, 1920, 2110, 2320, 2550, 2800
        ],
        "total_assets": [
            20000, 22000, 24200, 26600, 29300, 32200, 35400, 38900, 42800, 47100
        ],
        "total_liabilities": [
            6000, 6300, 6600, 6900, 7200, 7500, 7800, 8100, 8400, 8700
        ],
        "current_assets": [
            6000, 6600, 7260, 7980, 8780, 9660, 10620, 11680, 12850, 14130
        ],
        "current_liabilities": [
            3000, 3150, 3310, 3470, 3650, 3830, 4020, 4220, 4430, 4650
        ],
        "cost_of_goods": [
            6000, 6600, 7260, 7980, 8770, 9600, 10560, 11620, 12780, 14040
        ],
        "depreciation": [
            800, 880, 968, 1065, 1170, 1290, 1420, 1560, 1716, 1888
        ],
        "sga": [
            1500, 1650, 1815, 2000, 2190, 2400, 2640, 2900, 3190, 3510
        ],
        "gross_profit": [
            4000, 4400, 4840, 5320, 5830, 6400, 7040, 7780, 8520, 9360
        ],
        "inventory": [
            800, 880, 968, 1065, 1170, 1290, 1420, 1560, 1716, 1888
        ],
        "working_capital": [
            3000, 3450, 3950, 4510, 5130, 5830, 6600, 7460, 8420, 9480
        ],
        "capex": [
            2000, 2200, 2420, 2660, 2930, 3220, 3540, 3900, 4290, 4720
        ],
        "other_income": [
            100, 110, 121, 133, 146, 161, 177, 195, 214, 236
        ],
        "tax_expense": [
            500, 550, 605, 665, 730, 800, 880, 970, 1065, 1170
        ],
        "ebit": [
            2000, 2200, 2420, 2660, 2930, 3220, 3540, 3900, 4290, 4720
        ],
        "interest_expense": [
            240, 248, 256, 264, 272, 280, 288, 296, 304, 312
        ],
    }

    return data
