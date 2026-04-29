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


def _quantity_to_size(qty: pd.Series, base: float = 7, scale: float = 0.6) -> pd.Series:
    return base + qty.clip(lower=1, upper=25) * scale


def build_group_figure(
    group: str,
    products: list[str],
    activities: pd.DataFrame,
    trades: pd.DataFrame,
    positions: dict[str, pd.DataFrame],
    day_boundaries: list[int],
) -> go.Figure:
    """Build the Nx3 grid for one group: [price+fills, position, equity] per product."""
    n = len(products)
    titles = []
    for p in products:
        titles.extend([f"<b>{p}</b> — price + fills", "position", "equity"])

    fig = make_subplots(
        rows=n, cols=3,
        shared_xaxes=True,
        column_widths=[0.5, 0.25, 0.25],
        vertical_spacing=0.04,
        horizontal_spacing=0.05,
        subplot_titles=titles,
    )

    for i, product in enumerate(products, start=1):
        prod_act = (
            activities[activities["product"] == product]
            .dropna(subset=["mid_price"])
            .sort_values("abs_timestamp")
        )
        prod_trades = trades[trades["symbol"] == product] if not trades.empty else trades
        ours = prod_trades[prod_trades["side"].isin(["BUY", "SELL"])] if not prod_trades.empty else prod_trades
        market = prod_trades[prod_trades["side"] == "MARKET"] if not prod_trades.empty else prod_trades

        # ----- col 1: price + market fills + our fills -----
        fig.add_trace(go.Scatter(
            x=prod_act["abs_timestamp"], y=prod_act["mid_price"],
            mode="lines", name="mid",
            line=dict(color="#888", width=1),
            showlegend=False,
            hovertemplate="t=%{x}<br>mid=%{y}<extra></extra>",
        ), row=i, col=1)

        if not market.empty:
            fig.add_trace(go.Scatter(
                x=market["abs_timestamp"], y=market["price"],
                mode="markers", name="market",
                marker=dict(color=MARKET_COLOUR,
                            size=_quantity_to_size(market["quantity"], base=5, scale=0.4),
                            line=dict(color="rgba(0,0,0,0.2)", width=0.3)),
                customdata=market[["quantity", "buyer", "seller"]].values,
                hovertemplate=(
                    "t=%{x}<br>qty=%{customdata[0]} @ %{y}<br>"
                    "%{customdata[1]} → %{customdata[2]}<extra></extra>"
                ),
                showlegend=False,
            ), row=i, col=1)

        if not ours.empty:
            buys = ours[ours["side"] == "BUY"]
            sells = ours[ours["side"] == "SELL"]
            if not buys.empty:
                fig.add_trace(go.Scatter(
                    x=buys["abs_timestamp"], y=buys["price"],
                    mode="markers", name="our BUY",
                    marker=dict(color=BUY_COLOUR, symbol="triangle-up",
                                size=_quantity_to_size(buys["quantity"]),
                                line=dict(color="black", width=0.6)),
                    customdata=buys[["quantity", "counterparty"]].values,
                    hovertemplate=(
                        "BUY %{customdata[0]} @ %{y}<br>"
                        "t=%{x}<br>from: %{customdata[1]}<extra></extra>"
                    ),
                    showlegend=False,
                ), row=i, col=1)
            if not sells.empty:
                fig.add_trace(go.Scatter(
                    x=sells["abs_timestamp"], y=sells["price"],
                    mode="markers", name="our SELL",
                    marker=dict(color=SELL_COLOUR, symbol="triangle-down",
                                size=_quantity_to_size(sells["quantity"]),
                                line=dict(color="black", width=0.6)),
                    customdata=sells[["quantity", "counterparty"]].values,
                    hovertemplate=(
                        "SELL %{customdata[0]} @ %{y}<br>"
                        "t=%{x}<br>to: %{customdata[1]}<extra></extra>"
                    ),
                    showlegend=False,
                ), row=i, col=1)

        # ----- col 2: position step plot -----
        pos_df = positions.get(product)
        if pos_df is not None and not pos_df.empty:
            fig.add_trace(go.Scatter(
                x=pos_df["abs_timestamp"], y=pos_df["position"],
                mode="lines", name="position",
                line=dict(color="#2c5282", width=1, shape="hv"),
                showlegend=False,
                hovertemplate="t=%{x}<br>pos=%{y}<extra></extra>",
            ), row=i, col=2)
        else:
            fig.add_trace(go.Scatter(x=[], y=[], mode="lines", showlegend=False),
                          row=i, col=2)
        fig.add_hline(y=0, line=dict(color="#aaa", width=0.5, dash="dot"),
                      row=i, col=2)

        # ----- col 3: per-product equity -----
        fig.add_trace(go.Scatter(
            x=prod_act["abs_timestamp"], y=prod_act["profit_and_loss"],
            mode="lines", name="equity",
            line=dict(color="#805ad5", width=1.2),
            showlegend=False,
            hovertemplate="t=%{x}<br>pnl=%{y:.1f}<extra></extra>",
        ), row=i, col=3)
        fig.add_hline(y=0, line=dict(color="#aaa", width=0.5, dash="dot"),
                      row=i, col=3)

    # Day boundary lines apply to every subplot.
    for bx in day_boundaries:
        fig.add_vline(x=bx, line=dict(color="#aaa", width=0.5, dash="dot"))

    fig.update_layout(
        title=f"Group: {group}",
        height=max(360, 220 * n),
        hovermode="x unified",
        margin=dict(l=60, r=30, t=80, b=40),
    )
    return fig


def build_summary_figure(
    activities: pd.DataFrame,
    products_by_group: dict[str, list[str]],
    day_boundaries: list[int],
) -> go.Figure:
    """Two-panel summary: total cumulative equity on top, per-product overlay below."""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.4, 0.6],
        vertical_spacing=0.06,
        subplot_titles=("Total cumulative equity (sum across all products)",
                        "Per-product equity (coloured by group)"),
    )

    # ----- top: total cumulative equity -----
    total = (
        activities.groupby("abs_timestamp")["profit_and_loss"]
        .sum()
        .sort_index()
    )
    fig.add_trace(go.Scatter(
        x=total.index, y=total.values,
        mode="lines", name="total",
        line=dict(color="#000000", width=2.5),
        hovertemplate="t=%{x}<br>total pnl=%{y:.1f}<extra></extra>",
    ), row=1, col=1)
    fig.add_hline(y=0, line=dict(color="#aaa", width=0.5, dash="dot"),
                  row=1, col=1)

    # ----- bottom: per-product overlay coloured by group -----
    for group, products in products_by_group.items():
        colour = GROUP_COLOURS.get(group, "#888888")
        for product in products:
            prod_act = (
                activities[activities["product"] == product]
                .sort_values("abs_timestamp")
            )
            fig.add_trace(go.Scatter(
                x=prod_act["abs_timestamp"], y=prod_act["profit_and_loss"],
                mode="lines", name=product,
                legendgroup=group,
                legendgrouptitle_text=group,
                line=dict(color=colour, width=1),
                hovertemplate=(
                    f"<b>{product}</b><br>"
                    "t=%{x}<br>pnl=%{y:.1f}<extra></extra>"
                ),
            ), row=2, col=1)
    fig.add_hline(y=0, line=dict(color="#aaa", width=0.5, dash="dot"),
                  row=2, col=1)

    for bx in day_boundaries:
        fig.add_vline(x=bx, line=dict(color="#aaa", width=0.5, dash="dot"))

    fig.update_layout(
        title="Summary",
        height=720,
        hovermode="x unified",
        legend=dict(groupclick="toggleitem"),
        margin=dict(l=60, r=200, t=80, b=40),
    )
    fig.update_yaxes(title_text="total PnL", row=1, col=1)
    fig.update_yaxes(title_text="product PnL", row=2, col=1)
    fig.update_xaxes(title_text="timestamp", row=2, col=1)
    return fig


def write_tabbed_html(
    figures: dict[str, go.Figure],
    output_path: str,
    title: str,
) -> None:
    """Write one HTML file with a top tab strip; clicking a tab swaps which
    Plotly figure div is visible. Plotly.js is loaded once via CDN.
    """
    tab_buttons = []
    tab_pages = []
    for i, (label, fig) in enumerate(figures.items()):
        active = " active" if i == 0 else ""
        display = "block" if i == 0 else "none"
        tab_buttons.append(
            f'<button class="tab-button{active}" data-tab="tab-{i}" '
            f'onclick="showTab({i})">{label}</button>'
        )
        # include_plotlyjs=False so the script is loaded once at the top.
        fig_div = fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            div_id=f"plot-{i}",
        )
        tab_pages.append(
            f'<div class="tab-page" id="tab-{i}" style="display:{display};">'
            f'{fig_div}</div>'
        )

    css = """
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           margin: 0; padding: 0; background: #fafafa; color: #222; }
    .tab-strip { display: flex; gap: 4px; padding: 8px 12px; background: #fff;
                 border-bottom: 1px solid #ddd; flex-wrap: wrap; position: sticky;
                 top: 0; z-index: 10; }
    .tab-button { padding: 6px 14px; border: 1px solid #ccc; border-radius: 4px;
                  background: #f5f5f5; cursor: pointer; font-size: 13px; }
    .tab-button.active { background: #2c5282; color: white; border-color: #2c5282; }
    .tab-button:hover:not(.active) { background: #e6e6e6; }
    .tab-page { padding: 8px 12px; }
    h1.page-title { margin: 12px; font-size: 16px; color: #555; font-weight: 500; }
    """

    js = """
    function showTab(idx) {
      document.querySelectorAll('.tab-page').forEach(function(el, i) {
        el.style.display = (i === idx) ? 'block' : 'none';
      });
      document.querySelectorAll('.tab-button').forEach(function(el, i) {
        el.classList.toggle('active', i === idx);
      });
      // Plotly figures need a resize when un-hidden so axes pick up the
      // container width that was zero while display:none.
      var page = document.querySelectorAll('.tab-page')[idx];
      if (page) {
        page.querySelectorAll('.js-plotly-plot').forEach(function(p) {
          if (window.Plotly) { window.Plotly.Plots.resize(p); }
        });
      }
    }
    """

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>{css}</style>
</head>
<body>
<h1 class="page-title">{title}</h1>
<div class="tab-strip">{''.join(tab_buttons)}</div>
{''.join(tab_pages)}
<script>{js}</script>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    print("visualise_backtest: skeleton only")


if __name__ == "__main__":
    main()
