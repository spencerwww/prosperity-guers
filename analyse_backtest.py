"""
Backtest log analyser.

Reads a Prosperity backtest .log file, extracts the Activities log section,
builds a time-series DataFrame of total PnL, and prints key performance metrics.

Usage:
    python analyse_backtest.py <path_to_log_file>
    python analyse_backtest.py          # prompts for a file from backtests/
"""

import sys
import os
import re
import io
import glob
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_activities_log(log_path: str) -> pd.DataFrame:
    """
    Extract the 'Activities log:' CSV block from a .log file and return it
    as a DataFrame with columns:
        day, timestamp, product, bid_price_1..ask_volume_3, mid_price, profit_and_loss
    """
    in_activities = False
    lines = []

    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip("\n")
            if stripped == "Activities log:":
                in_activities = True
                continue
            if in_activities:
                # The trade-history JSON array starts with '[' on its own line
                if stripped.startswith("["):
                    break
                lines.append(stripped)

    if not lines:
        raise ValueError(f"No 'Activities log:' section found in {log_path}")

    df = pd.read_csv(io.StringIO("\n".join(lines)), sep=";", dtype={"day": str})
    df.columns = df.columns.str.strip()
    return df


def build_pnl_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate per-product PnL into a single total-PnL time series.

    The activities log records one row per (timestamp, product).  We sum
    profit_and_loss across all products at each timestamp to get total PnL,
    then compute the per-step return (delta PnL).
    """
    total = (
        df.groupby("timestamp")["profit_and_loss"]
        .sum()
        .reset_index()
        .rename(columns={"profit_and_loss": "total_pnl"})
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    total["pnl_delta"] = total["total_pnl"].diff().fillna(total["total_pnl"].iloc[0])
    return total


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(ts: pd.DataFrame) -> dict:
    """
    Compute performance metrics from a time-series DataFrame that has
    'total_pnl' and 'pnl_delta' columns.
    """
    returns = ts["pnl_delta"]
    pnl = ts["total_pnl"]

    mean_return = returns.mean()
    std_return = returns.std(ddof=1)

    # Sharpe ratio (risk-free rate = 0, returns are already in PnL units)
    sharpe = mean_return / std_return if std_return != 0 else np.nan

    # Sortino ratio (downside deviation)
    downside = returns[returns < 0]
    downside_std = downside.std(ddof=1) if len(downside) > 1 else np.nan
    sortino = mean_return / downside_std if (downside_std and downside_std != 0) else np.nan

    # Max drawdown
    running_max = pnl.cummax()
    drawdown = pnl - running_max
    max_drawdown = drawdown.min()

    # Calmar ratio  (annualisation not meaningful for tick-level sim; use raw)
    calmar = mean_return / abs(max_drawdown) if max_drawdown != 0 else np.nan

    # Capital invested: peak capital deployed, estimated as max absolute PnL swing
    # (For this sim the "capital" is the cumulative mark-to-market at its peak exposure)
    capital_invested = pnl.abs().max()

    total_pnl = pnl.iloc[-1]

    return {
        "Mean step return":    mean_return,
        "Std step return":     std_return,
        "Sharpe ratio":        sharpe,
        "Sortino ratio":       sortino,
        "Calmar ratio":        calmar,
        "Max drawdown":        max_drawdown,
        "Total PnL":           total_pnl,
        "Capital invested":    capital_invested,
    }


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_metrics(metrics: dict, log_path: str) -> None:
    label_width = max(len(k) for k in metrics) + 2
    print(f"\n{'='*55}")
    print(f"  Backtest: {os.path.basename(log_path)}")
    print(f"{'='*55}")
    for key, val in metrics.items():
        if isinstance(val, float):
            print(f"  {key:<{label_width}} {val:>12.4f}")
        else:
            print(f"  {key:<{label_width}} {val!r:>12}")
    print(f"{'='*55}\n")


def print_per_product_summary(df: pd.DataFrame) -> None:
    """Print final PnL per product."""
    final = df.sort_values("timestamp").groupby("product").last()["profit_and_loss"]
    print("  Per-product final PnL:")
    for product, val in final.items():
        print(f"    {product:<20} {val:>12.2f}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def pick_log_file() -> str:
    """If no argument given, list available logs and let the user pick."""
    logs = sorted(glob.glob("backtests/*.log"))
    if not logs:
        raise FileNotFoundError("No .log files found in backtests/")
    print("Available backtest logs:")
    for i, path in enumerate(logs):
        print(f"  [{i}] {os.path.basename(path)}")
    choice = input("Enter number (default 0, most-recent = last): ").strip()
    idx = int(choice) if choice else len(logs) - 1
    return logs[idx]


def main():
    if len(sys.argv) >= 2:
        log_path = sys.argv[1]
    else:
        log_path = pick_log_file()

    if not os.path.isfile(log_path):
        print(f"Error: file not found: {log_path}")
        sys.exit(1)

    print(f"\nParsing {log_path} ...")
    df = parse_activities_log(log_path)
    ts = build_pnl_timeseries(df)

    metrics = compute_metrics(ts)
    print_metrics(metrics, log_path)
    print_per_product_summary(df)

    # Optionally return the DataFrame for interactive / notebook use
    return ts, df, metrics


if __name__ == "__main__":
    main()
