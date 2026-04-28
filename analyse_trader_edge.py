"""
Quantify the forward-return edge of each named trader.

For every trade in ROUND_4/trades_round_4_day_*.csv, compute the mid-price
return at horizons K = 1, 5, 20, 100 ticks (one tick = 100 timestamps),
bucketed by trader + side (BUY / SELL).

A trader has predictive edge if conditional mean returns differ meaningfully
from zero in the expected direction (BUY → positive forward return,
SELL → negative).

Output:
    1. Per-trader, per-side, per-horizon table for each product.
    2. Cross-trader summary at a fixed horizon (K=20) so you can compare
       Mark 14 to Mark 38, Mark 22, etc.
"""

import os
import numpy as np
import pandas as pd

ROUND_DIR = "ROUND_4"
TICK = 100  # one timestep
HORIZONS = [1, 5, 20, 100]


def load_prices() -> pd.DataFrame:
    frames = []
    for day in (1, 2, 3):
        df = pd.read_csv(os.path.join(ROUND_DIR, f"prices_round_4_day_{day}.csv"), sep=";")
        df["day"] = day
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_trades() -> pd.DataFrame:
    frames = []
    for day in (1, 2, 3):
        df = pd.read_csv(os.path.join(ROUND_DIR, f"trades_round_4_day_{day}.csv"), sep=";")
        df["day"] = day
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def build_mid_lookup(prices: pd.DataFrame) -> pd.Series:
    """Indexed by (day, product, timestamp) → mid_price. Forward-filled within
    each (day, product) so a missing tick reuses the last known mid."""
    p = prices.dropna(subset=["mid_price"]).copy()
    p = p.sort_values(["day", "product", "timestamp"])
    return p.set_index(["day", "product", "timestamp"])["mid_price"]


def forward_returns(trades: pd.DataFrame, mid: pd.Series, horizon_ticks: int) -> pd.Series:
    """For each trade, return mid(t + horizon*TICK) - mid(t). NaN if either
    lookup fails (e.g. horizon walks off the end of the day)."""
    keys_now = list(zip(trades["day"], trades["symbol"], trades["timestamp"]))
    keys_fut = list(zip(trades["day"], trades["symbol"], trades["timestamp"] + horizon_ticks * TICK))
    mid_now = mid.reindex(keys_now).values
    mid_fut = mid.reindex(keys_fut).values
    return pd.Series(mid_fut - mid_now, index=trades.index)


def stats(series: pd.Series) -> dict:
    s = series.dropna()
    n = len(s)
    if n == 0:
        return dict(n=0, mean=np.nan, std=np.nan, t=np.nan)
    mean = s.mean()
    std = s.std(ddof=1) if n > 1 else np.nan
    se = std / np.sqrt(n) if n > 1 else np.nan
    t = mean / se if se and se > 0 else np.nan
    return dict(n=n, mean=mean, std=std, t=t)


def per_product_table(trades: pd.DataFrame, mid: pd.Series, trader: str) -> pd.DataFrame:
    rows = []
    for product, prod_trades in trades.groupby("symbol"):
        for side in ("BUY", "SELL"):
            if side == "BUY":
                sub = prod_trades[prod_trades["buyer"] == trader]
            else:
                sub = prod_trades[prod_trades["seller"] == trader]
            if sub.empty:
                continue
            for k in HORIZONS:
                ret = forward_returns(sub, mid, k)
                # Convention: BUY return is the raw mid-change; SELL return is
                # negated so "edge in the right direction" is always positive.
                signed_ret = ret if side == "BUY" else -ret
                row = dict(product=product, side=side, k=k, **stats(signed_ret))
                rows.append(row)
    return pd.DataFrame(rows)


def cross_trader_table(trades: pd.DataFrame, mid: pd.Series, traders: list[str], k: int) -> pd.DataFrame:
    rows = []
    for trader in traders:
        for product, prod_trades in trades.groupby("symbol"):
            for side in ("BUY", "SELL"):
                if side == "BUY":
                    sub = prod_trades[prod_trades["buyer"] == trader]
                else:
                    sub = prod_trades[prod_trades["seller"] == trader]
                if sub.empty:
                    continue
                ret = forward_returns(sub, mid, k)
                signed_ret = ret if side == "BUY" else -ret
                row = dict(trader=trader, product=product, side=side, **stats(signed_ret))
                rows.append(row)
    return pd.DataFrame(rows)


def fmt_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "  (no data)"
    df = df.copy()
    df["mean"] = df["mean"].map(lambda x: f"{x:+.3f}" if pd.notna(x) else "  nan")
    df["std"] = df["std"].map(lambda x: f"{x:.3f}" if pd.notna(x) else " nan")
    df["t"] = df["t"].map(lambda x: f"{x:+.2f}" if pd.notna(x) else " nan")
    return df.to_string(index=False)


def main():
    print("Loading round 4 data ...")
    prices = load_prices()
    trades = load_trades()
    mid = build_mid_lookup(prices)
    traders = sorted(set(trades["buyer"]) | set(trades["seller"]))
    print(f"  {len(trades):,} trades, traders: {traders}\n")

    # ----------------------------------------------------------------
    # Per-trader deep dive
    # ----------------------------------------------------------------
    for trader in traders:
        print(f"\n{'='*72}")
        print(f"  {trader} — forward-return by product/side/horizon")
        print(f"  (returns sign-flipped on SELL: positive = price moved in trader's favour)")
        print('='*72)
        tbl = per_product_table(trades, mid, trader)
        print(fmt_table(tbl))

    # ----------------------------------------------------------------
    # Cross-trader summary at the horizon you'd most likely trade on
    # ----------------------------------------------------------------
    K_SUMMARY = 20
    print(f"\n\n{'='*72}")
    print(f"  Cross-trader summary at K={K_SUMMARY} ticks ({K_SUMMARY*TICK} timestamp units)")
    print(f"  Sorted by t-statistic — large positive t = strong predictive edge")
    print('='*72)
    summary = cross_trader_table(trades, mid, traders, K_SUMMARY)
    summary = summary.sort_values("t", ascending=False, na_position="last")
    print(fmt_table(summary))

    # ----------------------------------------------------------------
    # Headline number
    # ----------------------------------------------------------------
    print(f"\n\n{'='*72}")
    print("  Best edges (top 5 by t-stat)")
    print('='*72)
    print(fmt_table(summary.head(5)))

    print(f"\n  Worst edges (top 5 — these traders are anti-informed if t is large negative)")
    print(fmt_table(summary.tail(5)))


if __name__ == "__main__":
    main()
