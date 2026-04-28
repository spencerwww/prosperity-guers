"""
Backtest log visualiser.

Reads a Prosperity backtest .log file and renders an interactive Plotly chart
with one (price, position) row pair per product:

    - Mid price over time, with our buy/sell fills overlaid as markers
    - Our net position over time (step plot)

Usage:
    python visualise_backtest.py <path_to_log_file>
    python visualise_backtest.py          # prompts for a file from backtests/
"""

import sys
import os
import re
import io
import glob
import json
import webbrowser
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _read_section(log_path: str, header: str, next_headers: list[str]) -> str:
    """Return raw text between `header` and the next of `next_headers` (or EOF)."""
    out, in_section = [], False
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip("\n")
            if stripped == header:
                in_section = True
                continue
            if in_section and stripped in next_headers:
                break
            if in_section:
                out.append(stripped)
    return "\n".join(out)


def parse_activities_log(log_path: str) -> pd.DataFrame:
    """CSV block giving mid_price + book + PnL per (timestamp, product)."""
    text = _read_section(log_path, "Activities log:", ["Trade History:"])
    # Trade history starts with '[' — strip anything after the CSV ends.
    text = re.split(r"^\[", text, maxsplit=1, flags=re.MULTILINE)[0]
    if not text.strip():
        raise ValueError(f"No 'Activities log:' section found in {log_path}")
    df = pd.read_csv(io.StringIO(text), sep=";", dtype={"day": str})
    df.columns = df.columns.str.strip()
    return df


def parse_trade_history(log_path: str) -> pd.DataFrame:
    """JSON list of every fill in the sim. The JSON has trailing commas, so
    strip them before parsing."""
    text = _read_section(log_path, "Trade History:", []).strip()
    if not text:
        return pd.DataFrame(columns=["timestamp", "symbol", "price", "quantity", "buyer", "seller"])
    # Remove trailing commas before } or ]
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    trades = json.loads(text)
    return pd.DataFrame(trades)


def derive_our_trades(trades: pd.DataFrame) -> pd.DataFrame:
    """Filter to fills involving our submission and tag side / signed qty."""
    if trades.empty:
        return trades.assign(side=pd.Series(dtype=str), signed_qty=pd.Series(dtype=int))
    mask = (trades["buyer"] == "SUBMISSION") | (trades["seller"] == "SUBMISSION")
    ours = trades.loc[mask].copy()
    ours["side"] = ours["buyer"].eq("SUBMISSION").map({True: "BUY", False: "SELL"})
    ours["signed_qty"] = ours["quantity"] * ours["side"].map({"BUY": 1, "SELL": -1})
    return ours.sort_values("timestamp").reset_index(drop=True)


def build_position_series(our_trades: pd.DataFrame, timestamps: pd.Series) -> dict[str, pd.DataFrame]:
    """For each product, return a DataFrame indexed by timestamp with the
    running net position evaluated at every market tick."""
    out: dict[str, pd.DataFrame] = {}
    grid = pd.Index(sorted(timestamps.unique()), name="timestamp")
    for product, grp in our_trades.groupby("symbol"):
        per_ts = grp.groupby("timestamp")["signed_qty"].sum()
        pos = per_ts.reindex(grid, fill_value=0).cumsum()
        out[product] = pos.reset_index(name="position")
    return out


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

BUY_COLOUR = "#1f9d55"
SELL_COLOUR = "#c0392b"


def build_figure(
    activities: pd.DataFrame,
    our_trades: pd.DataFrame,
    positions: dict[str, pd.DataFrame],
    title: str,
) -> go.Figure:
    products = sorted(activities["product"].unique())
    n = len(products)

    # 2 rows per product: price (taller) + position
    row_heights = []
    for _ in products:
        row_heights += [0.7, 0.3]
    row_heights = [h / sum(row_heights) for h in row_heights]

    titles = []
    for p in products:
        titles += [f"{p} — mid price & our fills", f"{p} — position"]

    fig = make_subplots(
        rows=2 * n,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=row_heights,
        subplot_titles=titles,
    )

    for i, product in enumerate(products):
        price_row = 2 * i + 1
        pos_row = 2 * i + 2

        # --- price -------------------------------------------------------
        prod_df = activities[activities["product"] == product].sort_values("timestamp")
        fig.add_trace(
            go.Scatter(
                x=prod_df["timestamp"],
                y=prod_df["mid_price"],
                mode="lines",
                name=f"{product} mid",
                line=dict(color="#888", width=1),
                legendgroup=product,
                showlegend=(i == 0),
                hovertemplate="t=%{x}<br>mid=%{y}<extra></extra>",
            ),
            row=price_row,
            col=1,
        )

        # --- our fills ---------------------------------------------------
        prod_trades = our_trades[our_trades["symbol"] == product]
        for side, colour, symbol in [("BUY", BUY_COLOUR, "triangle-up"),
                                      ("SELL", SELL_COLOUR, "triangle-down")]:
            sub = prod_trades[prod_trades["side"] == side]
            if sub.empty:
                continue
            fig.add_trace(
                go.Scatter(
                    x=sub["timestamp"],
                    y=sub["price"],
                    mode="markers",
                    marker=dict(color=colour, symbol=symbol, size=9,
                                line=dict(color="black", width=0.5)),
                    name=f"{side}",
                    legendgroup=side,
                    showlegend=(i == 0),
                    customdata=sub[["quantity"]].values,
                    hovertemplate=(
                        f"{side} {{customdata[0]}} @ %{{y}}<br>t=%{{x}}<extra></extra>"
                    ).replace("{customdata[0]}", "%{customdata[0]}"),
                ),
                row=price_row,
                col=1,
            )

        # --- position ---------------------------------------------------
        pos_df = positions.get(product)
        if pos_df is not None and not pos_df.empty:
            fig.add_trace(
                go.Scatter(
                    x=pos_df["timestamp"],
                    y=pos_df["position"],
                    mode="lines",
                    line=dict(color="#2c5282", width=1, shape="hv"),
                    name=f"{product} position",
                    legendgroup=f"{product}-pos",
                    showlegend=False,
                    hovertemplate="t=%{x}<br>pos=%{y}<extra></extra>",
                ),
                row=pos_row,
                col=1,
            )
            fig.add_hline(y=0, line=dict(color="#aaa", width=0.5, dash="dot"),
                          row=pos_row, col=1)

        fig.update_yaxes(title_text="price", row=price_row, col=1)
        fig.update_yaxes(title_text="position", row=pos_row, col=1)

    fig.update_xaxes(title_text="timestamp", row=2 * n, col=1)
    fig.update_layout(
        title=title,
        height=320 * n + 80,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=20, t=80, b=40),
    )
    return fig


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def pick_log_file() -> str:
    logs = sorted(glob.glob("backtests/*.log"))
    if not logs:
        raise FileNotFoundError("No .log files found in backtests/")
    print("Available backtest logs:")
    for i, path in enumerate(logs):
        print(f"  [{i}] {os.path.basename(path)}")
    choice = input("Enter number (default = most recent): ").strip()
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
    activities = parse_activities_log(log_path)
    trades = parse_trade_history(log_path)
    our_trades = derive_our_trades(trades)
    positions = build_position_series(our_trades, activities["timestamp"])

    print(f"  products       : {sorted(activities['product'].unique())}")
    print(f"  ticks          : {activities['timestamp'].nunique()}")
    print(f"  total fills    : {len(trades)}")
    print(f"  our fills      : {len(our_trades)}")

    fig = build_figure(activities, our_trades, positions,
                       title=f"Backtest: {os.path.basename(log_path)}")

    out_path = os.path.splitext(log_path)[0] + ".html"
    fig.write_html(out_path, include_plotlyjs="cdn")
    print(f"\nWrote {out_path}")
    webbrowser.open("file://" + os.path.abspath(out_path))


if __name__ == "__main__":
    main()
