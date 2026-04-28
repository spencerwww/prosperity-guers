"""
Live submission log visualiser.

Reads a Prosperity live-result log (JSON with `activitiesLog` + `tradeHistory`)
and renders an interactive Plotly chart for debugging losing strategies.

Per product (selectable via dropdown):
    - Mid price line
    - Our buy fills (green ^) and sell fills (red v) — sized by quantity
    - Other-trader fills shown as faint grey dots for context (which Mark
      traded around us)
    - Net position step plot
    - Cumulative realised+unrealised PnL (from the activitiesLog `profit_and_loss`
      column)

Usage:
    python visualise_live_log.py logs/506433/506433.log
    python visualise_live_log.py             # picks logs/<latest>/<file>.log
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


BUY_COLOUR = "#1f9d55"
SELL_COLOUR = "#c0392b"
MARKET_COLOUR = "rgba(120,120,120,0.35)"
DAY_LENGTH = 1_000_000


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_log(path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    activities = pd.read_csv(io.StringIO(data["activitiesLog"]), sep=";")
    activities.columns = activities.columns.str.strip()

    trades = pd.DataFrame(data["tradeHistory"])
    if trades.empty:
        trades = pd.DataFrame(columns=["timestamp", "buyer", "seller", "symbol",
                                       "currency", "price", "quantity"])

    # Normalise timestamps onto a single timeline if multiple days are present.
    if "day" in activities.columns:
        activities["abs_timestamp"] = activities["timestamp"] + (activities["day"] - activities["day"].min()) * DAY_LENGTH
        # tradeHistory has no `day` field, but its timestamps are already absolute
        # within a single submission run (one day for live results). Keep them as-is
        # but align with activities by joining on the day's offset.
        day_offset = (activities["day"].min() - activities["day"].min()) * DAY_LENGTH
        trades["abs_timestamp"] = trades["timestamp"] + day_offset
    else:
        activities["abs_timestamp"] = activities["timestamp"]
        trades["abs_timestamp"] = trades["timestamp"]

    return activities, trades


def derive_sides(trades: pd.DataFrame) -> pd.DataFrame:
    """Tag each trade as our BUY, our SELL, or MARKET (no SUBMISSION involved)."""
    if trades.empty:
        return trades.assign(side="", counterparty="", signed_qty=0)

    out = trades.copy()
    side = []
    counterparty = []
    for buyer, seller in zip(out["buyer"], out["seller"]):
        if buyer == "SUBMISSION":
            side.append("BUY")
            counterparty.append(seller)
        elif seller == "SUBMISSION":
            side.append("SELL")
            counterparty.append(buyer)
        else:
            side.append("MARKET")
            counterparty.append(f"{buyer} ↔ {seller}")
    out["side"] = side
    out["counterparty"] = counterparty
    out["signed_qty"] = out["quantity"] * out["side"].map({"BUY": 1, "SELL": -1, "MARKET": 0}).fillna(0)
    return out


def build_position_per_product(trades: pd.DataFrame, ts_grid: pd.Index) -> dict[str, pd.DataFrame]:
    """Running net position for each product, evaluated on the activities tick grid."""
    out: dict[str, pd.DataFrame] = {}
    ours = trades[trades["side"].isin(["BUY", "SELL"])]
    for product, grp in ours.groupby("symbol"):
        per_ts = grp.groupby("abs_timestamp")["signed_qty"].sum()
        pos = per_ts.reindex(ts_grid, fill_value=0).cumsum()
        pos.name = "position"
        out[product] = pos.reset_index()
    return out


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def quantity_to_size(qty: pd.Series, base: float = 7, scale: float = 0.6) -> pd.Series:
    return base + qty.clip(lower=1, upper=25) * scale


def build_figure(activities: pd.DataFrame, trades: pd.DataFrame, title: str) -> go.Figure:
    products = sorted(activities["product"].unique())
    ts_grid = pd.Index(sorted(activities["abs_timestamp"].unique()), name="abs_timestamp")
    positions = build_position_per_product(trades, ts_grid)

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.55, 0.20, 0.25],
        subplot_titles=("price + our fills (market trades faded)", "position", "P&L"),
    )

    # We track which traces belong to which product so the dropdown can swap them.
    trace_product: list[str] = []

    def add(trace: go.Scatter, row: int, product: str):
        fig.add_trace(trace, row=row, col=1)
        trace_product.append(product)

    for product in products:
        prod_act = (
            activities[activities["product"] == product]
            .dropna(subset=["mid_price"])
            .sort_values("abs_timestamp")
        )
        prod_trades = trades[trades["symbol"] == product]
        ours = prod_trades[prod_trades["side"].isin(["BUY", "SELL"])]
        market = prod_trades[prod_trades["side"] == "MARKET"]

        # ----- mid price -----
        add(go.Scatter(
            x=prod_act["abs_timestamp"],
            y=prod_act["mid_price"],
            mode="lines",
            name="mid",
            line=dict(color="#888", width=1),
            showlegend=True,
            hovertemplate="t=%{x}<br>mid=%{y}<extra></extra>",
        ), row=1, product=product)

        # ----- market trades (faded) -----
        if not market.empty:
            cd = market[["quantity", "buyer", "seller"]].values
            add(go.Scatter(
                x=market["abs_timestamp"],
                y=market["price"],
                mode="markers",
                name="market trade",
                marker=dict(color=MARKET_COLOUR, size=quantity_to_size(market["quantity"], base=5, scale=0.4),
                            line=dict(color="rgba(0,0,0,0.2)", width=0.3)),
                customdata=cd,
                hovertemplate=(
                    "t=%{x}<br>"
                    "qty=%{customdata[0]} @ %{y}<br>"
                    "%{customdata[1]} → %{customdata[2]}"
                    "<extra></extra>"
                ),
            ), row=1, product=product)
        else:
            add(go.Scatter(x=[], y=[], mode="markers", name="market trade",
                           marker=dict(color=MARKET_COLOUR)), row=1, product=product)

        # ----- our buys -----
        buys = ours[ours["side"] == "BUY"]
        if not buys.empty:
            cd = buys[["quantity", "counterparty", "price"]].values
            add(go.Scatter(
                x=buys["abs_timestamp"],
                y=buys["price"],
                mode="markers",
                name="our BUY",
                marker=dict(color=BUY_COLOUR, symbol="triangle-up",
                            size=quantity_to_size(buys["quantity"]),
                            line=dict(color="black", width=0.6)),
                customdata=cd,
                hovertemplate=(
                    "BUY %{customdata[0]} @ %{y}<br>"
                    "t=%{x}<br>"
                    "from: %{customdata[1]}"
                    "<extra></extra>"
                ),
            ), row=1, product=product)
        else:
            add(go.Scatter(x=[], y=[], mode="markers", name="our BUY",
                           marker=dict(color=BUY_COLOUR, symbol="triangle-up")), row=1, product=product)

        # ----- our sells -----
        sells = ours[ours["side"] == "SELL"]
        if not sells.empty:
            cd = sells[["quantity", "counterparty", "price"]].values
            add(go.Scatter(
                x=sells["abs_timestamp"],
                y=sells["price"],
                mode="markers",
                name="our SELL",
                marker=dict(color=SELL_COLOUR, symbol="triangle-down",
                            size=quantity_to_size(sells["quantity"]),
                            line=dict(color="black", width=0.6)),
                customdata=cd,
                hovertemplate=(
                    "SELL %{customdata[0]} @ %{y}<br>"
                    "t=%{x}<br>"
                    "to: %{customdata[1]}"
                    "<extra></extra>"
                ),
            ), row=1, product=product)
        else:
            add(go.Scatter(x=[], y=[], mode="markers", name="our SELL",
                           marker=dict(color=SELL_COLOUR, symbol="triangle-down")), row=1, product=product)

        # ----- position -----
        pos_df = positions.get(product)
        if pos_df is not None and not pos_df.empty:
            add(go.Scatter(
                x=pos_df["abs_timestamp"],
                y=pos_df["position"],
                mode="lines",
                name="position",
                line=dict(color="#2c5282", width=1, shape="hv"),
                showlegend=False,
                hovertemplate="t=%{x}<br>pos=%{y}<extra></extra>",
            ), row=2, product=product)
        else:
            add(go.Scatter(x=[], y=[], mode="lines", name="position",
                           showlegend=False), row=2, product=product)

        # ----- pnl -----
        add(go.Scatter(
            x=prod_act["abs_timestamp"],
            y=prod_act["profit_and_loss"],
            mode="lines",
            name="P&L",
            line=dict(color="#805ad5", width=1.2),
            showlegend=False,
            hovertemplate="t=%{x}<br>pnl=%{y:.1f}<extra></extra>",
        ), row=3, product=product)

    # ----- dropdown -----
    n_traces = len(fig.data)
    default_product = products[0]
    buttons = []
    for product in products:
        visible = [trace_product[i] == product for i in range(n_traces)]
        # Per-product PnL and total PnL printed in subplot titles.
        prod_pnl_final = activities[activities["product"] == product]["profit_and_loss"].iloc[-1]
        buttons.append(dict(
            label=product,
            method="update",
            args=[
                {"visible": visible},
                {"title": f"{title} — {product}  (final P&L: {prod_pnl_final:+,.1f})"},
            ],
        ))

    initial_visible = [trace_product[i] == default_product for i in range(n_traces)]
    for trace, vis in zip(fig.data, initial_visible):
        trace.visible = vis

    initial_pnl = activities[activities["product"] == default_product]["profit_and_loss"].iloc[-1]

    fig.update_yaxes(title_text="price", row=1, col=1)
    fig.update_yaxes(title_text="position", row=2, col=1)
    fig.update_yaxes(title_text="P&L", row=3, col=1)
    fig.update_xaxes(title_text="timestamp", row=3, col=1)

    fig.add_hline(y=0, line=dict(color="#aaa", width=0.5, dash="dot"), row=2, col=1)
    fig.add_hline(y=0, line=dict(color="#aaa", width=0.5, dash="dot"), row=3, col=1)

    fig.update_layout(
        title=f"{title} — {default_product}  (final P&L: {initial_pnl:+,.1f})",
        height=820,
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=70, r=30, t=110, b=50),
        updatemenus=[dict(
            type="dropdown",
            buttons=buttons,
            x=0, xanchor="left",
            y=1.10, yanchor="top",
            showactive=True,
        )],
    )
    return fig


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def pick_log() -> str:
    candidates = sorted(glob.glob("logs/*/*.log"))
    if not candidates:
        raise FileNotFoundError("No logs/*/*.log files found")
    print("Available logs:")
    for i, p in enumerate(candidates):
        print(f"  [{i}] {p}")
    choice = input("Enter number (default = most recent): ").strip()
    idx = int(choice) if choice else len(candidates) - 1
    return candidates[idx]


def main():
    log_path = sys.argv[1] if len(sys.argv) >= 2 else pick_log()
    if not os.path.isfile(log_path):
        print(f"Error: file not found: {log_path}")
        sys.exit(1)

    print(f"Loading {log_path} ...")
    activities, trades = load_log(log_path)
    trades = derive_sides(trades)

    n_ours = (trades["side"].isin(["BUY", "SELL"])).sum()
    n_market = (trades["side"] == "MARKET").sum()
    final_pnl = activities.groupby("product")["profit_and_loss"].last().sum()

    print(f"  products      : {sorted(activities['product'].unique())}")
    print(f"  ticks         : {activities['timestamp'].nunique()}")
    print(f"  our fills     : {n_ours}")
    print(f"  market fills  : {n_market}")
    print(f"  final P&L sum : {final_pnl:+,.2f}")

    title = f"live log {os.path.basename(log_path)}"
    fig = build_figure(activities, trades, title)

    out_path = os.path.splitext(log_path)[0] + "_visualisation.html"
    fig.write_html(out_path, include_plotlyjs="cdn")
    print(f"\nWrote {out_path}")
    webbrowser.open("file://" + os.path.abspath(out_path))


if __name__ == "__main__":
    main()
