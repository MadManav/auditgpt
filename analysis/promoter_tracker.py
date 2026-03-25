"""
promoter_tracker.py — Promoter / Insider Behaviour Analysis
Tracks promoter holding %, insider transactions, and flags suspicious activity.

"When the insider runs, you run." 🎯
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


def analyze_promoter_behaviour(ticker: str) -> dict:
    """
    Analyze promoter/insider behaviour for a given ticker.

    Returns:
        dict with:
        - promoter_holding_pct: current promoter/insider holding %
        - insider_transactions: list of recent transactions
        - flags: list of red-flag dicts {name, severity, detail}
        - risk_level: "LOW" / "MEDIUM" / "HIGH" / "CRITICAL"
    """
    result = {
        "promoter_holding_pct": None,
        "insider_transactions": [],
        "net_insider_activity": "neutral",
        "total_sold_value": 0,
        "total_bought_value": 0,
        "flags": [],
        "risk_level": "LOW",
        "available": False,
    }

    try:
        stock = yf.Ticker(ticker)

        # ── 1. Promoter / Insider Holding % ─────────────────────
        holders = stock.major_holders
        if holders is not None and not holders.empty:
            # yfinance major_holders has index like 'insidersPercentHeld'
            # and a single column 'Value'
            if "insidersPercentHeld" in holders.index:
                val = holders.loc["insidersPercentHeld", "Value"]
                result["promoter_holding_pct"] = round(float(val) * 100, 2)
                result["available"] = True

        # ── 2. Insider Transactions ─────────────────────────────
        txns = stock.insider_transactions
        if txns is not None and not txns.empty:
            result["available"] = True
            total_sold = 0
            total_bought = 0
            sell_count = 0
            buy_count = 0
            recent_txns = []

            for _, row in txns.iterrows():
                text = str(row.get("Text", "")).lower()
                shares = abs(int(row.get("Shares", 0)))
                value = abs(int(row.get("Value", 0)))
                insider = str(row.get("Insider", "Unknown"))
                date = row.get("Start Date", "")

                # Determine if buy or sell
                is_sale = "sale" in text or "sell" in text or "disposition" in text
                is_buy = "purchase" in text or "buy" in text or "acquisition" in text

                if is_sale:
                    total_sold += value
                    sell_count += 1
                    txn_type = "SELL"
                elif is_buy:
                    total_bought += value
                    buy_count += 1
                    txn_type = "BUY"
                else:
                    txn_type = "OTHER"

                recent_txns.append({
                    "insider": insider[:30],  # Truncate long names
                    "type": txn_type,
                    "shares": shares,
                    "value": value,
                    "date": str(date)[:10] if date else "",
                })

            result["insider_transactions"] = recent_txns[:10]  # Top 10
            result["total_sold_value"] = total_sold
            result["total_bought_value"] = total_bought

            # Net activity
            if total_sold > total_bought * 2:
                result["net_insider_activity"] = "heavy_selling"
            elif total_sold > total_bought:
                result["net_insider_activity"] = "net_selling"
            elif total_bought > total_sold * 2:
                result["net_insider_activity"] = "heavy_buying"
            elif total_bought > total_sold:
                result["net_insider_activity"] = "net_buying"
            else:
                result["net_insider_activity"] = "neutral"

        # ── 3. Generate Red Flags ───────────────────────────────
        flags = []
        holding = result["promoter_holding_pct"]

        # Flag: Very low promoter holding
        if holding is not None:
            if holding < 20:
                flags.append({
                    "name": "Very Low Promoter Holding",
                    "severity": "high",
                    "detail": f"Promoter holds only {holding}% — below 20% is a major red flag"
                })
            elif holding < 35:
                flags.append({
                    "name": "Low Promoter Holding",
                    "severity": "medium",
                    "detail": f"Promoter holds {holding}% — below 35% indicates weak promoter confidence"
                })

        # Flag: Heavy insider selling
        activity = result["net_insider_activity"]
        sold = result["total_sold_value"]
        bought = result["total_bought_value"]

        if activity == "heavy_selling":
            flags.append({
                "name": "Heavy Insider Selling",
                "severity": "high",
                "detail": f"Insiders sold ₹{_fmt_value(sold)} vs bought ₹{_fmt_value(bought)} — insiders dumping shares"
            })
        elif activity == "net_selling":
            flags.append({
                "name": "Net Insider Selling",
                "severity": "medium",
                "detail": f"Insiders sold ₹{_fmt_value(sold)} vs bought ₹{_fmt_value(bought)}"
            })
        elif activity == "heavy_buying":
            # Positive signal — not a flag but noteworthy
            flags.append({
                "name": "Strong Insider Buying",
                "severity": "low",
                "detail": f"Insiders bought ₹{_fmt_value(bought)} vs sold ₹{_fmt_value(sold)} — confidence signal ✅"
            })

        result["flags"] = flags

        # ── 4. Overall Promoter Risk Level ──────────────────────
        high_count = sum(1 for f in flags if f["severity"] == "high")
        med_count = sum(1 for f in flags if f["severity"] == "medium")

        if high_count >= 2:
            result["risk_level"] = "CRITICAL"
        elif high_count >= 1:
            result["risk_level"] = "HIGH"
        elif med_count >= 1:
            result["risk_level"] = "MEDIUM"
        else:
            result["risk_level"] = "LOW"

    except Exception as e:
        result["error"] = str(e)

    return result


def _fmt_value(val: int) -> str:
    """Format large numbers in Cr/Lakh for readability."""
    if val >= 1_00_00_000:  # 1 Crore
        return f"{val / 1_00_00_000:.1f} Cr"
    elif val >= 1_00_000:  # 1 Lakh
        return f"{val / 1_00_000:.1f} L"
    elif val >= 1000:
        return f"{val / 1000:.1f}K"
    return str(val)
