"""
Round 4 trade-over-price visualiser.

Reads ROUND_4/prices_round_4_day_{1,2,3}.csv and trades_round_4_day_{1,2,3}.csv,
concatenates the days into one timeline, and renders an interactive Plotly chart:

    - Mid price line per product
    - Every trade overlaid as a marker, coloured by trader ID
    - Hover shows price, quantity, buyer, seller
    - Dropdown selector switches between products

Round 4 trade rows include trader IDs (e.g. "Mark 22") in the buyer/seller fields.

Usage:
    python visualise_round4.py
"""

import os
import webbrowser
import pandas as pd
import plotly.graph_objects as go


ROUND_DIR = "ROUND_4"
OUTPUT_HTML = os.path.join(ROUND_DIR, "visualisation.html")
DAY_LENGTH = 1_000_000  # one day of timestamps in Prosperity

# 7 distinct colors for the 7 known trader IDs (Mark 01/14/22/38/49/55/67).
# Falls back to a cycler if new trader IDs appear.
TRADER_PALETTE = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231",
    "#911eb4", "#42d4f4", "#f032e6", "#9a6324",
    "#808000", "#000075",
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_prices() -> pd.DataFrame:
    frames = []
    for day in (1, 2, 3):
        path = os.path.join(ROUND_DIR, f"prices_round_4_day_{day}.csv")
        df = pd.read_csv(path, sep=";")
        df["abs_timestamp"] = df["timestamp"] + (day - 1) * DAY_LENGTH
        df["day"] = day
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_trades() -> pd.DataFrame:
    frames = []
    for day in (1, 2, 3):
        path = os.path.join(ROUND_DIR, f"trades_round_4_day_{day}.csv")
        df = pd.read_csv(path, sep=";")
        df["abs_timestamp"] = df["timestamp"] + (day - 1) * DAY_LENGTH
        df["day"] = day
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Plot construction
# ---------------------------------------------------------------------------

def quantity_to_size(qty: pd.Series) -> pd.Series:
    """Clip quantity to a reasonable range and map to marker size in pixels."""
    return 6 + qty.clip(lower=1, upper=25) * 0.5


def build_figure(prices: pd.DataFrame, trades: pd.DataFrame) -> go.Figure:
    products = sorted(prices["product"].unique())
    traders = sorted(pd.concat([trades["buyer"], trades["seller"]]).unique())
    trader_color = {t: TRADER_PALETTE[i % len(TRADER_PALETTE)] for i, t in enumerate(traders)}

    fig = go.Figure()

    # We track which traces belong to which product so the dropdown can
    # toggle visibility cleanly.
    trace_product: list[str] = []

    for product in products:
        prod_prices = (
            prices[prices["product"] == product]
            .dropna(subset=["mid_price"])
            .sort_values("abs_timestamp")
        )
        fig.add_trace(go.Scatter(
            x=prod_prices["abs_timestamp"],
            y=prod_prices["mid_price"],
            mode="lines",
            name="mid price",
            line=dict(color="#888", width=1),
            legendgroup="mid",
            showlegend=True,
            hovertemplate="t=%{x}<br>mid=%{y}<extra></extra>",
        ))
        trace_product.append(product)

        prod_trades = trades[trades["symbol"] == product]
        for trader in traders:
            # Each trade is plotted in BOTH the buyer's and the seller's trace
            # so that toggling a trader's legend hides all of their activity,
            # not just the side they happened to be on.
            sub = prod_trades[(prod_trades["buyer"] == trader) | (prod_trades["seller"] == trader)]
            if sub.empty:
                # Add an empty trace to keep visibility-mask alignment simple
                # and so the legend still shows the trader.
                fig.add_trace(go.Scatter(
                    x=[], y=[],
                    mode="markers",
                    name=trader,
                    legendgroup=trader,
                    marker=dict(color=trader_color[trader], size=8,
                                line=dict(color="black", width=0.4)),
                    showlegend=True,
                ))
                trace_product.append(product)
                continue

            customdata = sub[["quantity", "buyer", "seller", "symbol"]].values
            fig.add_trace(go.Scatter(
                x=sub["abs_timestamp"],
                y=sub["price"],
                mode="markers",
                name=trader,
                legendgroup=trader,
                marker=dict(
                    color=trader_color[trader],
                    size=quantity_to_size(sub["quantity"]),
                    line=dict(color="black", width=0.4),
                    opacity=0.85,
                ),
                customdata=customdata,
                hovertemplate=(
                    "t=%{x}<br>"
                    "%{customdata[3]}<br>"
                    "qty=%{customdata[0]} @ %{y}<br>"
                    "buyer: %{customdata[1]}<br>"
                    "seller: %{customdata[2]}"
                    "<extra></extra>"
                ),
            ))
            trace_product.append(product)

    # ----- dropdown ---------------------------------------------------------
    n_traces = len(fig.data)
    buttons = []
    default_product = products[0]
    for product in products:
        visible = [trace_product[i] == product for i in range(n_traces)]
        buttons.append(dict(
            label=product,
            method="update",
            args=[
                {"visible": visible},
                {"title": f"Round 4 — {product} (days 1–3)"},
            ],
        ))

    # Set initial visibility to first product
    initial_visible = [trace_product[i] == default_product for i in range(n_traces)]
    for trace, vis in zip(fig.data, initial_visible):
        trace.visible = vis

    # ----- day boundaries ---------------------------------------------------
    for day in (1, 2):
        fig.add_vline(
            x=day * DAY_LENGTH,
            line=dict(color="#aaa", width=1, dash="dot"),
        )
    for day in (1, 2, 3):
        fig.add_annotation(
            x=(day - 1) * DAY_LENGTH + DAY_LENGTH / 2,
            y=1.02, xref="x", yref="paper",
            text=f"day {day}",
            showarrow=False,
            font=dict(size=11, color="#666"),
        )

    fig.update_layout(
        title=f"Round 4 — {default_product} (days 1–3)",
        xaxis_title="timestamp (day-offset)",
        yaxis_title="price",
        height=720,
        hovermode="closest",
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
        margin=dict(l=60, r=160, t=90, b=50),
        updatemenus=[dict(
            type="dropdown",
            buttons=buttons,
            x=0, xanchor="left",
            y=1.12, yanchor="top",
            showactive=True,
        )],
    )
    return fig


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    print("Loading prices ...")
    prices = load_prices()
    print(f"  {len(prices):,} price rows across {prices['product'].nunique()} products")

    print("Loading trades ...")
    trades = load_trades()
    print(f"  {len(trades):,} trades, {trades['buyer'].nunique() + trades['seller'].nunique() - len(set(trades['buyer']) & set(trades['seller']))} unique trader IDs")
    print(f"  traders: {sorted(set(trades['buyer']) | set(trades['seller']))}")

    print("Building figure ...")
    fig = build_figure(prices, trades)

    fig.write_html(OUTPUT_HTML, include_plotlyjs="cdn")
    print(f"\nWrote {OUTPUT_HTML}")
    webbrowser.open("file://" + os.path.abspath(OUTPUT_HTML))


if __name__ == "__main__":
    main()
