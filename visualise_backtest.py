"""
Backtest log visualiser.

Reads a Prosperity backtest log (JSON with `activitiesLog` + `tradeHistory`)
and writes a single self-contained HTML next to the log with one tab per
product family plus a summary tab.

Usage:
    python visualise_backtest.py backtests/2026-04-29_12-49-55.log
    python visualise_backtest.py             # picks from backtests/ interactively
"""

import sys
import os
import io
import json
import glob
import webbrowser
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


DAY_LENGTH = 1_000_000

GROUP_ORDER = [
    "GALAXY_SOUNDS", "SLEEP_POD", "MICROCHIP", "PEBBLES", "ROBOT",
    "UV_VISOR", "TRANSLATOR", "PANEL", "OXYGEN_SHAKE", "SNACKPACK",
]

GROUP_COLOURS = {
    "GALAXY_SOUNDS":  "#e6194b",
    "SLEEP_POD":      "#3cb44b",
    "MICROCHIP":      "#4363d8",
    "PEBBLES":        "#f58231",
    "ROBOT":          "#911eb4",
    "UV_VISOR":       "#42d4f4",
    "TRANSLATOR":     "#f032e6",
    "PANEL":          "#9a6324",
    "OXYGEN_SHAKE":   "#808000",
    "SNACKPACK":      "#000075",
    "OTHER":          "#888888",
}

BUY_COLOUR = "#1f9d55"
SELL_COLOUR = "#c0392b"
MARKET_COLOUR = "rgba(120,120,120,0.35)"


def bucket_symbol(symbol: str) -> str:
    """Return the family group for a product symbol, or 'OTHER' if no prefix matches.

    Uses longest-prefix-match against GROUP_ORDER so that, e.g., 'SLEEP_POD'
    wins over any accidental shorter match.
    """
    matches = [g for g in GROUP_ORDER if symbol.startswith(g + "_") or symbol == g]
    if not matches:
        return "OTHER"
    return max(matches, key=len)


def bucket_products(products: list[str]) -> dict[str, list[str]]:
    """Group products by family, preserving GROUP_ORDER and putting OTHER last.

    Empty groups are omitted. Products inside each group are sorted alphabetically.
    """
    grouped: dict[str, list[str]] = {}
    for p in products:
        g = bucket_symbol(p)
        grouped.setdefault(g, []).append(p)
    for g in grouped:
        grouped[g].sort()

    ordered: dict[str, list[str]] = {}
    for g in GROUP_ORDER:
        if g in grouped:
            ordered[g] = grouped[g]
    if "OTHER" in grouped:
        ordered["OTHER"] = grouped["OTHER"]
    return ordered


def load_log(path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse a Prosperity backtest log into (activities_df, trades_df).

    activities_df gets an extra `abs_timestamp` column = timestamp + day-offset
    so multi-day backtests fit on a single timeline. Same for trades_df, using
    the first activities day as the reference offset.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    activities = pd.read_csv(io.StringIO(data["activitiesLog"]), sep=";")
    activities.columns = activities.columns.str.strip()

    trade_records = data.get("tradeHistory", []) or []
    if trade_records:
        trades = pd.DataFrame(trade_records)
    else:
        trades = pd.DataFrame(columns=["timestamp", "buyer", "seller", "symbol",
                                       "currency", "price", "quantity"])

    if "day" in activities.columns:
        day_min = activities["day"].min()
        activities["abs_timestamp"] = (
            activities["timestamp"] + (activities["day"] - day_min) * DAY_LENGTH
        )
        # Trades have no explicit `day` field. Backtest logs emit trade timestamps
        # already aligned with activities; match by (timestamp, symbol) where
        # possible. The simplest and correct approach: map each trade timestamp
        # to the activities row sharing it, then carry that day's offset.
        if not trades.empty:
            ts_to_day = (
                activities.drop_duplicates("timestamp")
                          .set_index("timestamp")["day"]
            )
            trades["day"] = trades["timestamp"].map(ts_to_day).fillna(day_min).astype(int)
            trades["abs_timestamp"] = (
                trades["timestamp"] + (trades["day"] - day_min) * DAY_LENGTH
            )
        else:
            trades["abs_timestamp"] = trades["timestamp"]
    else:
        activities["abs_timestamp"] = activities["timestamp"]
        trades["abs_timestamp"] = trades["timestamp"]

    return activities, trades


def derive_sides(trades: pd.DataFrame) -> pd.DataFrame:
    """Tag each trade as our BUY, our SELL, or MARKET (no SUBMISSION involved).

    Adds three columns: `side`, `counterparty`, `signed_qty`.
    """
    out = trades.copy()
    if out.empty:
        out["side"] = pd.Series(dtype=str)
        out["counterparty"] = pd.Series(dtype=str)
        out["signed_qty"] = pd.Series(dtype="int64")
        return out

    sides, cps = [], []
    for buyer, seller in zip(out["buyer"], out["seller"]):
        if buyer == "SUBMISSION":
            sides.append("BUY")
            cps.append(seller)
        elif seller == "SUBMISSION":
            sides.append("SELL")
            cps.append(buyer)
        else:
            sides.append("MARKET")
            cps.append(f"{buyer} ↔ {seller}")
    out["side"] = sides
    out["counterparty"] = cps
    sign_map = {"BUY": 1, "SELL": -1, "MARKET": 0}
    out["signed_qty"] = out["quantity"] * out["side"].map(sign_map).fillna(0)
    out["signed_qty"] = out["signed_qty"].astype("int64")
    return out


def build_position_per_product(
    trades: pd.DataFrame, ts_grid: pd.Index
) -> dict[str, pd.DataFrame]:
    """Cumulative net position per product, evaluated on the activities tick grid.

    Returns a dict keyed by symbol; each value is a 2-column DataFrame
    `[abs_timestamp, position]`.
    """
    out: dict[str, pd.DataFrame] = {}
    if trades.empty:
        return out
    ours = trades[trades["side"].isin(["BUY", "SELL"])]
    for product, grp in ours.groupby("symbol"):
        per_ts = grp.groupby("abs_timestamp")["signed_qty"].sum()
        pos = per_ts.reindex(ts_grid, fill_value=0).cumsum()
        pos.name = "position"
        out[product] = pos.reset_index()
    return out


def main():
    print("visualise_backtest: skeleton only")


if __name__ == "__main__":
    main()
