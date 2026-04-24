import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

st.set_page_config(
    layout="wide",
    page_title="Prosperity Visualiser",
    page_icon="📈",
)

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ROUND_3")

PRICE_COLS = [
    ("bid_price_1", "#26a69a", "solid"),
    ("bid_price_2", "#80cbc4", "dash"),
    ("bid_price_3", "#b2dfdb", "dot"),
    ("ask_price_1", "#ef5350", "solid"),
    ("ask_price_2", "#ef9a9a", "dash"),
    ("ask_price_3", "#ffcdd2", "dot"),
    ("mid_price",   "#ffeb3b", "solid"),
]

HOVER_COLS = [
    "bid_price_1", "bid_volume_1",
    "bid_price_2", "bid_volume_2",
    "bid_price_3", "bid_volume_3",
    "ask_price_1", "ask_volume_1",
    "ask_price_2", "ask_volume_2",
    "ask_price_3", "ask_volume_3",
]

HOVER_TMPL = (
    "<b>t = %{x}</b>  price = %{y:.4g}<br>"
    "<br><b>Bids</b><br>"
    "L1 %{customdata[0]} × %{customdata[1]}<br>"
    "L2 %{customdata[2]} × %{customdata[3]}<br>"
    "L3 %{customdata[4]} × %{customdata[5]}<br>"
    "<br><b>Asks</b><br>"
    "L1 %{customdata[6]} × %{customdata[7]}<br>"
    "L2 %{customdata[8]} × %{customdata[9]}<br>"
    "L3 %{customdata[10]} × %{customdata[11]}"
    "<extra></extra>"
)

DARK_BG = "#0e1117"
GRID    = "#2a2d35"


@st.cache_data
def load_prices(day: int) -> pd.DataFrame:
    path = os.path.join(BASE_DIR, f"prices_round_3_day_{day}.csv")
    df = pd.read_csv(path, sep=";")
    df.columns = df.columns.str.strip()
    return df


@st.cache_data
def load_trades(day: int) -> pd.DataFrame:
    path = os.path.join(BASE_DIR, f"trades_round_3_day_{day}.csv")
    df = pd.read_csv(path, sep=";")
    df.columns = df.columns.str.strip()
    return df


# ── Sidebar ──────────────────────────────────────────────────────────────────

st.sidebar.title("📈 Prosperity Visualiser")

day = st.sidebar.selectbox("Day", [0, 1, 2], format_func=lambda d: f"Day {d}")
prices_df = load_prices(day)
trades_df = load_trades(day)

products = sorted(prices_df["product"].unique())
product  = st.sidebar.selectbox("Product", products)

st.sidebar.divider()
st.sidebar.subheader("Price lines")

show: dict[str, bool] = {}
for col, color, _ in PRICE_COLS:
    default = col in ("bid_price_1", "ask_price_1", "mid_price")
    label_html = f'<span style="color:{color};font-weight:600">{col}</span>'
    show[col] = st.sidebar.checkbox(col, value=default, key=col)

# ── Filter ───────────────────────────────────────────────────────────────────

prod_prices = prices_df[prices_df["product"] == product].copy().reset_index(drop=True)
prod_trades = trades_df[trades_df["symbol"] == product].copy().reset_index(drop=True)

# Infer trade direction from price vs mid_price at nearest timestamp
if not prod_trades.empty and not prod_prices.empty:
    mid_lookup = prod_prices.set_index("timestamp")["mid_price"]
    prod_trades["mid_at_ts"] = prod_trades["timestamp"].map(mid_lookup)
    # Forward-fill for timestamps between price snapshots
    if prod_trades["mid_at_ts"].isna().any():
        full_mid = prod_prices.set_index("timestamp")["mid_price"].sort_index()
        prod_trades["mid_at_ts"] = prod_trades["timestamp"].apply(
            lambda t: full_mid.asof(t) if t in full_mid.index or True else np.nan
        )
    prod_trades["direction"] = np.where(
        prod_trades["price"] >= prod_trades["mid_at_ts"], "buy", "sell"
    )

# ── Hover customdata ─────────────────────────────────────────────────────────

customdata = prod_prices[HOVER_COLS].fillna("—").values

# ── Main figure ──────────────────────────────────────────────────────────────

fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    row_heights=[0.72, 0.28],
    vertical_spacing=0.04,
    subplot_titles=[f"{product}  ·  Day {day}  —  Prices", "Orderbook Volume"],
)

# Price lines
any_price_shown = False
for col, color, dash in PRICE_COLS:
    if not show[col]:
        continue
    any_price_shown = True
    fig.add_trace(
        go.Scatter(
            x=prod_prices["timestamp"],
            y=prod_prices[col],
            name=col,
            line=dict(color=color, width=1.5, dash=dash),
            customdata=customdata,
            hovertemplate=HOVER_TMPL,
        ),
        row=1, col=1,
    )

if not any_price_shown:
    st.sidebar.warning("Select at least one price line.")

# Trade markers
for direction, sym, color, label in [
    ("buy",  "triangle-up",   "#00e676", "Buy"),
    ("sell", "triangle-down", "#ff1744", "Sell"),
]:
    if prod_trades.empty:
        break
    mask = prod_trades["direction"] == direction
    t    = prod_trades[mask]
    if t.empty:
        continue
    fig.add_trace(
        go.Scatter(
            x=t["timestamp"],
            y=t["price"],
            mode="markers",
            name=f"{label} trade",
            marker=dict(
                symbol=sym,
                size=10,
                color=color,
                line=dict(width=1, color="white"),
            ),
            customdata=t["quantity"].values,
            hovertemplate=(
                f"<b>{label} trade</b><br>"
                "t = %{x}<br>"
                "price = %{y:.4g}<br>"
                "qty = %{customdata}"
                "<extra></extra>"
            ),
        ),
        row=1, col=1,
    )

# Orderbook volume bars (bid / ask totals per timestamp)
vol_bid = prod_prices[["bid_volume_1", "bid_volume_2", "bid_volume_3"]].fillna(0).sum(axis=1)
vol_ask = prod_prices[["ask_volume_1", "ask_volume_2", "ask_volume_3"]].fillna(0).sum(axis=1)

fig.add_trace(
    go.Bar(
        x=prod_prices["timestamp"], y=vol_bid,
        name="Bid volume", marker_color="#26a69a", opacity=0.75,
        hovertemplate="<b>Bid vol</b>  t=%{x}  vol=%{y}<extra></extra>",
    ),
    row=2, col=1,
)
fig.add_trace(
    go.Bar(
        x=prod_prices["timestamp"], y=vol_ask,
        name="Ask volume", marker_color="#ef5350", opacity=0.75,
        hovertemplate="<b>Ask vol</b>  t=%{x}  vol=%{y}<extra></extra>",
    ),
    row=2, col=1,
)

fig.update_layout(
    height=700,
    template="plotly_dark",
    hovermode="x unified",
    barmode="overlay",
    legend=dict(
        orientation="h", yanchor="bottom", y=1.02,
        xanchor="right", x=1, font=dict(size=11),
    ),
    margin=dict(t=60, b=10, l=60, r=20),
    paper_bgcolor=DARK_BG,
    plot_bgcolor=DARK_BG,
)
fig.update_xaxes(showgrid=True, gridcolor=GRID, zeroline=False)
fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False)

st.plotly_chart(fig, use_container_width=True)

# ── Orderbook snapshot ────────────────────────────────────────────────────────

st.divider()

col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("Orderbook snapshot")
    timestamps = sorted(prod_prices["timestamp"].unique())
    ts_idx = st.slider(
        "Select timestamp",
        min_value=0,
        max_value=len(timestamps) - 1,
        value=0,
        key="ob_slider",
    )
    selected_ts = timestamps[ts_idx]
    st.caption(f"t = {selected_ts}")

    row = prod_prices[prod_prices["timestamp"] == selected_ts].iloc[0]

    bids = [
        (row.get(f"bid_price_{i}"), row.get(f"bid_volume_{i}"))
        for i in range(1, 4)
        if pd.notna(row.get(f"bid_price_{i}")) and pd.notna(row.get(f"bid_volume_{i}"))
    ]
    asks = [
        (row.get(f"ask_price_{i}"), row.get(f"ask_volume_{i}"))
        for i in range(1, 4)
        if pd.notna(row.get(f"ask_price_{i}")) and pd.notna(row.get(f"ask_volume_{i}"))
    ]

    ob_fig = go.Figure()

    if bids:
        ob_fig.add_trace(go.Bar(
            x=[str(b[0]) for b in bids],
            y=[b[1] for b in bids],
            name="Bids",
            marker_color="#26a69a",
            text=[int(b[1]) for b in bids],
            textposition="outside",
            textfont=dict(color="#26a69a"),
        ))
    if asks:
        ob_fig.add_trace(go.Bar(
            x=[str(a[0]) for a in asks],
            y=[a[1] for a in asks],
            name="Asks",
            marker_color="#ef5350",
            text=[int(a[1]) for a in asks],
            textposition="outside",
            textfont=dict(color="#ef5350"),
        ))

    ob_fig.update_layout(
        height=320,
        template="plotly_dark",
        barmode="group",
        xaxis_title="Price level",
        yaxis_title="Volume",
        paper_bgcolor=DARK_BG,
        plot_bgcolor=DARK_BG,
        margin=dict(t=20, b=40, l=50, r=20),
        legend=dict(orientation="h", y=1.1),
    )
    ob_fig.update_xaxes(
        showgrid=True, gridcolor=GRID,
        categoryorder="category ascending",
    )
    ob_fig.update_yaxes(showgrid=True, gridcolor=GRID)

    st.plotly_chart(ob_fig, use_container_width=True)

with col_right:
    st.subheader("Quote table")
    st.caption(f"t = {selected_ts}  ·  mid = {row.get('mid_price', '—'):.4g}")

    table_rows = []
    for i in range(1, 4):
        ap = row.get(f"ask_price_{i}")
        av = row.get(f"ask_volume_{i}")
        bp = row.get(f"bid_price_{i}")
        bv = row.get(f"bid_volume_{i}")
        table_rows.append({
            "Level": f"L{i}",
            "Ask price": f"{ap:.4g}" if pd.notna(ap) else "—",
            "Ask vol":   f"{int(av)}"  if pd.notna(av) else "—",
            "Bid price": f"{bp:.4g}" if pd.notna(bp) else "—",
            "Bid vol":   f"{int(bv)}"  if pd.notna(bv) else "—",
        })

    st.dataframe(
        pd.DataFrame(table_rows).set_index("Level"),
        use_container_width=True,
    )

    if not prod_trades.empty:
        trades_at_ts = prod_trades[prod_trades["timestamp"] == selected_ts]
        if not trades_at_ts.empty:
            st.caption("Trades at this timestamp")
            st.dataframe(
                trades_at_ts[["price", "quantity", "direction"]].reset_index(drop=True),
                use_container_width=True,
            )
