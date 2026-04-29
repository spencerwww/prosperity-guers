# Backtest Visualiser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `visualise_backtest.py`, a CLI tool that turns a `backtests/*.log` JSON file into a single self-contained tabbed HTML visualisation: one tab per product family showing each product's price+fills+position+equity, plus a summary tab with total cumulative equity and per-product overlay.

**Architecture:** Pure-function pipeline `log → DataFrames → per-tab Plotly figures → tabbed HTML`. Reuses loading and trade-tagging patterns from the existing `visualise_live_log.py`. Tabbed page emission is a thin custom HTML/JS wrapper around `fig.to_html(full_html=False)` outputs. Tests live in `tests/test_visualise_backtest.py` and are runnable directly via `python tests/test_visualise_backtest.py` (no pytest dependency added — matches the project's script-based style).

**Tech Stack:** Python 3, `pandas`, `plotly`. No new dependencies.

---

## File Structure

- Create: `visualise_backtest.py` — the CLI tool, all logic.
- Create: `tests/test_visualise_backtest.py` — assert-based test runner for pure functions.
- No edits to existing files.

Module layout inside `visualise_backtest.py` (top → bottom):

1. Imports and constants (group prefix list, colour palette, day length, marker colours).
2. `bucket_symbol(symbol) -> str` — longest-prefix match, returns group name or `"OTHER"`.
3. `bucket_products(products) -> dict[str, list[str]]` — groups → sorted product list. Group order is fixed.
4. `load_log(path) -> tuple[DataFrame, DataFrame]` — JSON load + activities/trades parsing + abs_timestamp.
5. `derive_sides(trades) -> DataFrame` — adds `side`, `counterparty`, `signed_qty`.
6. `build_position_per_product(trades, ts_grid) -> dict[str, DataFrame]` — cumulative position per symbol on the activities tick grid.
7. `build_group_figure(group, products, activities, trades, positions, day_boundaries) -> go.Figure` — Nx3 subplot grid for one group.
8. `build_summary_figure(activities, products_by_group, day_boundaries) -> go.Figure` — two-panel summary.
9. `write_tabbed_html(figures, output_path, title) -> None` — wraps each figure's div in a tab page; emits one HTML file with a JS tab switcher.
10. `pick_log() -> str` — interactive picker scanning `backtests/*.log`.
11. `main()` and `if __name__ == "__main__"`.

Group order constant:

```python
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
```

---

## Task 1: Skeleton + first commit

**Files:**
- Create: `visualise_backtest.py`

- [ ] **Step 1: Create the file with module docstring and imports**

```python
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


def main():
    print("visualise_backtest: skeleton only")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the skeleton runs**

Run: `python visualise_backtest.py`
Expected output: `visualise_backtest: skeleton only`

- [ ] **Step 3: Commit**

```bash
git add visualise_backtest.py
git commit -m "Add visualise_backtest skeleton with constants"
```

---

## Task 2: Group bucketing (TDD)

**Files:**
- Create: `tests/test_visualise_backtest.py`
- Modify: `visualise_backtest.py` — add `bucket_symbol` and `bucket_products`.

- [ ] **Step 1: Write the failing test file**

```python
"""
Run with:  python tests/test_visualise_backtest.py
Asserts on pure data functions in visualise_backtest.
"""
import os
import sys

# Make project root importable when run from repo root or tests/ dir
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd
from visualise_backtest import bucket_symbol, bucket_products


def test_bucket_symbol_galaxy():
    assert bucket_symbol("GALAXY_SOUNDS_DARK_MATTER") == "GALAXY_SOUNDS"


def test_bucket_symbol_longest_prefix_wins_over_subprefix():
    # SLEEP_POD must beat any shorter accidental match.
    assert bucket_symbol("SLEEP_POD_LAMB_WOOL") == "SLEEP_POD"


def test_bucket_symbol_unmatched_goes_to_other():
    assert bucket_symbol("INTARIAN_PEPPER_ROOT") == "OTHER"


def test_bucket_products_orders_by_group_order_and_sorts_within():
    products = [
        "SNACKPACK_VANILLA",
        "GALAXY_SOUNDS_BLACK_HOLES",
        "GALAXY_SOUNDS_DARK_MATTER",
        "INTARIAN_PEPPER_ROOT",
        "SNACKPACK_CHOCOLATE",
    ]
    out = bucket_products(products)
    keys = list(out.keys())
    # GALAXY_SOUNDS comes before SNACKPACK in GROUP_ORDER; OTHER comes last.
    assert keys.index("GALAXY_SOUNDS") < keys.index("SNACKPACK")
    assert keys[-1] == "OTHER"
    # Products are sorted alphabetically within each group.
    assert out["GALAXY_SOUNDS"] == [
        "GALAXY_SOUNDS_BLACK_HOLES", "GALAXY_SOUNDS_DARK_MATTER"
    ]
    assert out["SNACKPACK"] == ["SNACKPACK_CHOCOLATE", "SNACKPACK_VANILLA"]
    assert out["OTHER"] == ["INTARIAN_PEPPER_ROOT"]


def test_bucket_products_skips_empty_groups():
    products = ["SNACKPACK_VANILLA"]
    out = bucket_products(products)
    assert "GALAXY_SOUNDS" not in out
    assert out["SNACKPACK"] == ["SNACKPACK_VANILLA"]


def run_all():
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except AssertionError as e:
                failed += 1
                print(f"  FAIL  {name}: {e}")
            except Exception as e:
                failed += 1
                print(f"  ERR   {name}: {type(e).__name__}: {e}")
    if failed:
        print(f"\n{failed} test(s) failed")
        sys.exit(1)
    print("\nAll tests passed.")


if __name__ == "__main__":
    run_all()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python tests/test_visualise_backtest.py`
Expected: `ImportError` because `bucket_symbol` and `bucket_products` don't exist yet.

- [ ] **Step 3: Implement `bucket_symbol` and `bucket_products`**

Add these functions to `visualise_backtest.py` after the constants block:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python tests/test_visualise_backtest.py`
Expected: `All tests passed.` with 5 PASS lines.

- [ ] **Step 5: Commit**

```bash
git add visualise_backtest.py tests/test_visualise_backtest.py
git commit -m "Add bucket_symbol/bucket_products with tests"
```

---

## Task 3: Log loader

**Files:**
- Modify: `visualise_backtest.py` — add `load_log`.
- Modify: `tests/test_visualise_backtest.py` — add a smoke test against the latest backtest log.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_visualise_backtest.py` before `run_all()`:

```python
def _latest_backtest_log():
    paths = sorted(glob_module.glob(os.path.join(ROOT, "backtests", "*.log")))
    assert paths, "No backtest logs found in backtests/"
    return paths[-1]


def test_load_log_returns_two_dataframes_with_expected_columns():
    from visualise_backtest import load_log
    activities, trades = load_log(_latest_backtest_log())

    assert isinstance(activities, pd.DataFrame)
    assert isinstance(trades, pd.DataFrame)

    for col in ["day", "timestamp", "product", "mid_price", "profit_and_loss",
                "abs_timestamp"]:
        assert col in activities.columns, f"missing activities column {col}"

    # tradeHistory may be empty in some logs but the DataFrame still has the schema.
    for col in ["timestamp", "buyer", "seller", "symbol", "price", "quantity",
                "abs_timestamp"]:
        assert col in trades.columns, f"missing trades column {col}"

    # abs_timestamp matches timestamp when single-day; otherwise differs.
    if activities["day"].nunique() == 1:
        assert (activities["abs_timestamp"] == activities["timestamp"]).all()
```

Also add `import glob as glob_module` at the top of the test file.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python tests/test_visualise_backtest.py`
Expected: `ImportError: cannot import name 'load_log'`.

- [ ] **Step 3: Implement `load_log`**

Add after `bucket_products`:

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `python tests/test_visualise_backtest.py`
Expected: `All tests passed.` (now 6 PASS lines).

- [ ] **Step 5: Commit**

```bash
git add visualise_backtest.py tests/test_visualise_backtest.py
git commit -m "Add load_log with multi-day abs_timestamp handling"
```

---

## Task 4: Trade tagging + position derivation

**Files:**
- Modify: `visualise_backtest.py` — add `derive_sides`, `build_position_per_product`.
- Modify: `tests/test_visualise_backtest.py` — add unit tests with synthetic DataFrames.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_visualise_backtest.py` before `run_all()`:

```python
def test_derive_sides_tags_buy_sell_market():
    from visualise_backtest import derive_sides
    df = pd.DataFrame([
        {"timestamp": 0, "buyer": "SUBMISSION", "seller": "Mark 14",
         "symbol": "X", "price": 100, "quantity": 3, "abs_timestamp": 0},
        {"timestamp": 1, "buyer": "Mark 22", "seller": "SUBMISSION",
         "symbol": "X", "price": 101, "quantity": 5, "abs_timestamp": 1},
        {"timestamp": 2, "buyer": "Mark 14", "seller": "Mark 22",
         "symbol": "X", "price": 102, "quantity": 7, "abs_timestamp": 2},
    ])
    out = derive_sides(df)
    assert list(out["side"]) == ["BUY", "SELL", "MARKET"]
    assert list(out["counterparty"]) == ["Mark 14", "Mark 22", "Mark 14 ↔ Mark 22"]
    assert list(out["signed_qty"]) == [3, -5, 0]


def test_derive_sides_handles_empty_input():
    from visualise_backtest import derive_sides
    df = pd.DataFrame(columns=["timestamp", "buyer", "seller", "symbol",
                               "price", "quantity", "abs_timestamp"])
    out = derive_sides(df)
    assert list(out.columns) == list(df.columns) + ["side", "counterparty", "signed_qty"]
    assert len(out) == 0


def test_build_position_cumulates_signed_qty_on_tick_grid():
    from visualise_backtest import derive_sides, build_position_per_product
    trades = pd.DataFrame([
        {"timestamp": 100, "buyer": "SUBMISSION", "seller": "M",
         "symbol": "X", "price": 1, "quantity": 4, "abs_timestamp": 100},
        {"timestamp": 200, "buyer": "M", "seller": "SUBMISSION",
         "symbol": "X", "price": 1, "quantity": 1, "abs_timestamp": 200},
        {"timestamp": 300, "buyer": "SUBMISSION", "seller": "M",
         "symbol": "X", "price": 1, "quantity": 2, "abs_timestamp": 300},
    ])
    trades = derive_sides(trades)
    ts_grid = pd.Index([0, 100, 150, 200, 250, 300, 400], name="abs_timestamp")
    pos = build_position_per_product(trades, ts_grid)
    assert "X" in pos
    series = pos["X"].set_index("abs_timestamp")["position"]
    assert series.tolist() == [0, 4, 4, 3, 3, 5, 5]
```

- [ ] **Step 2: Run to verify they fail**

Run: `python tests/test_visualise_backtest.py`
Expected: `ImportError: cannot import name 'derive_sides'`.

- [ ] **Step 3: Implement both functions**

Add after `load_log`:

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `python tests/test_visualise_backtest.py`
Expected: `All tests passed.` (now 9 PASS lines).

- [ ] **Step 5: Commit**

```bash
git add visualise_backtest.py tests/test_visualise_backtest.py
git commit -m "Add derive_sides and build_position_per_product"
```

---

## Task 5: Group page figure

**Files:**
- Modify: `visualise_backtest.py` — add `_quantity_to_size`, `build_group_figure`.
- Modify: `tests/test_visualise_backtest.py` — shape-check on the figure.

- [ ] **Step 1: Write the shape-check test**

Append before `run_all()`:

```python
def test_build_group_figure_has_expected_subplot_grid():
    from visualise_backtest import (
        load_log, derive_sides, build_position_per_product, build_group_figure
    )
    activities, trades = load_log(_latest_backtest_log())
    trades = derive_sides(trades)
    products = sorted(activities["product"].unique())[:3]  # any 3 products
    ts_grid = pd.Index(sorted(activities["abs_timestamp"].unique()),
                       name="abs_timestamp")
    positions = build_position_per_product(trades, ts_grid)

    fig = build_group_figure("TEST", products, activities, trades, positions,
                              day_boundaries=[])
    # 3 rows x 3 cols = 9 subplots; Plotly stores axes as xaxis, xaxis2 ... xaxis9.
    xaxes = [k for k in fig.layout if k.startswith("xaxis")]
    yaxes = [k for k in fig.layout if k.startswith("yaxis")]
    assert len(xaxes) == 9, f"expected 9 x-axes, got {len(xaxes)}"
    assert len(yaxes) == 9, f"expected 9 y-axes, got {len(yaxes)}"
    # At least one trace per row * col should be present.
    assert len(fig.data) >= 9
```

- [ ] **Step 2: Run to verify it fails**

Run: `python tests/test_visualise_backtest.py`
Expected: `ImportError: cannot import name 'build_group_figure'`.

- [ ] **Step 3: Implement `build_group_figure` and the size helper**

Add after `build_position_per_product`:

```python
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
            # Empty trace so axis exists.
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
```

- [ ] **Step 4: Run the tests**

Run: `python tests/test_visualise_backtest.py`
Expected: `All tests passed.` (now 10 PASS lines).

- [ ] **Step 5: Commit**

```bash
git add visualise_backtest.py tests/test_visualise_backtest.py
git commit -m "Add build_group_figure with Nx3 subplot grid"
```

---

## Task 6: Summary page figure

**Files:**
- Modify: `visualise_backtest.py` — add `build_summary_figure`.
- Modify: `tests/test_visualise_backtest.py` — shape and trace-count check.

- [ ] **Step 1: Write the test**

Append before `run_all()`:

```python
def test_build_summary_figure_has_top_total_and_per_product_overlay():
    from visualise_backtest import (
        load_log, build_summary_figure, bucket_products,
    )
    activities, _ = load_log(_latest_backtest_log())
    products = sorted(activities["product"].unique())
    by_group = bucket_products(products)

    fig = build_summary_figure(activities, by_group, day_boundaries=[])
    # Two subplots = 2 x-axes / 2 y-axes
    xaxes = [k for k in fig.layout if k.startswith("xaxis")]
    yaxes = [k for k in fig.layout if k.startswith("yaxis")]
    assert len(xaxes) == 2
    assert len(yaxes) == 2

    # Trace count: 1 (top: total) + N products (bottom)
    assert len(fig.data) == 1 + len(products)
    # The first trace should be the total cumulative.
    assert fig.data[0].name == "total"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python tests/test_visualise_backtest.py`
Expected: `ImportError: cannot import name 'build_summary_figure'`.

- [ ] **Step 3: Implement `build_summary_figure`**

Add after `build_group_figure`:

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `python tests/test_visualise_backtest.py`
Expected: `All tests passed.` (now 11 PASS lines).

- [ ] **Step 5: Commit**

```bash
git add visualise_backtest.py tests/test_visualise_backtest.py
git commit -m "Add build_summary_figure with total + per-product overlay"
```

---

## Task 7: Tabbed HTML emitter

**Files:**
- Modify: `visualise_backtest.py` — add `write_tabbed_html`.
- Modify: `tests/test_visualise_backtest.py` — assert HTML written and contains expected tab markup.

- [ ] **Step 1: Write the test**

Append before `run_all()`:

```python
import tempfile

def test_write_tabbed_html_produces_one_div_per_tab():
    from visualise_backtest import write_tabbed_html
    figs = {
        "Summary": go.Figure(go.Scatter(x=[0, 1], y=[0, 1])),
        "GROUP_A":  go.Figure(go.Scatter(x=[0, 1], y=[1, 2])),
    }
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tf:
        path = tf.name
    try:
        write_tabbed_html(figs, path, title="Test")
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        # One tab button per figure (count by data-tab attribute, which is
        # unique per button regardless of whether the .active class is set).
        assert html.count('data-tab="tab-') == 2
        # One page div per figure
        assert html.count('class="tab-page"') == 2
        # Plotly is loaded once via CDN
        assert "cdn.plot.ly" in html or "cdn.plotly.com" in html
        # Both labels appear in the nav
        assert ">Summary<" in html
        assert ">GROUP_A<" in html
    finally:
        os.remove(path)
```

Add `import tempfile` near the top of the test file (after existing imports).
Add `import plotly.graph_objects as go` to the test file's imports.

- [ ] **Step 2: Run to verify it fails**

Run: `python tests/test_visualise_backtest.py`
Expected: `ImportError: cannot import name 'write_tabbed_html'`.

- [ ] **Step 3: Implement `write_tabbed_html`**

Add after `build_summary_figure`:

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `python tests/test_visualise_backtest.py`
Expected: `All tests passed.` (now 12 PASS lines).

- [ ] **Step 5: Commit**

```bash
git add visualise_backtest.py tests/test_visualise_backtest.py
git commit -m "Add write_tabbed_html with tab-strip JS"
```

---

## Task 8: CLI wiring (file picker + main)

**Files:**
- Modify: `visualise_backtest.py` — add `pick_log` and replace `main` with the real wiring.

- [ ] **Step 1: Replace the placeholder `main` and add `pick_log`**

In `visualise_backtest.py`, replace the existing `main()` function and add `pick_log` just above it:

```python
def pick_log() -> str:
    candidates = sorted(glob.glob(os.path.join("backtests", "*.log")))
    if not candidates:
        raise FileNotFoundError("No backtests/*.log files found")
    print("Available backtest logs:")
    for i, p in enumerate(candidates):
        print(f"  [{i}] {p}")
    choice = input("Enter number (default = most recent): ").strip()
    idx = int(choice) if choice else len(candidates) - 1
    return candidates[idx]


def _day_boundaries(activities: pd.DataFrame) -> list[int]:
    """Return abs_timestamp positions where each new day starts (excluding the first)."""
    if "day" not in activities.columns or activities["day"].nunique() <= 1:
        return []
    day_min = activities["day"].min()
    days = sorted(d for d in activities["day"].unique() if d != day_min)
    return [(d - day_min) * DAY_LENGTH for d in days]


def main():
    log_path = sys.argv[1] if len(sys.argv) >= 2 else pick_log()
    if not os.path.isfile(log_path):
        print(f"Error: file not found: {log_path}")
        sys.exit(1)

    print(f"Loading {log_path} ...")
    activities, trades = load_log(log_path)
    trades = derive_sides(trades)

    products = sorted(activities["product"].unique())
    by_group = bucket_products(products)

    n_ours = int((trades["side"].isin(["BUY", "SELL"])).sum()) if not trades.empty else 0
    n_market = int((trades["side"] == "MARKET").sum()) if not trades.empty else 0
    final_pnl = activities.groupby("product")["profit_and_loss"].last().sum()

    print(f"  products       : {len(products)} across {len(by_group)} groups")
    print(f"  ticks          : {activities['abs_timestamp'].nunique()}")
    print(f"  our fills      : {n_ours}")
    print(f"  market fills   : {n_market}")
    print(f"  final P&L sum  : {final_pnl:+,.2f}")

    ts_grid = pd.Index(sorted(activities["abs_timestamp"].unique()),
                       name="abs_timestamp")
    positions = build_position_per_product(trades, ts_grid)
    boundaries = _day_boundaries(activities)

    print("Building figures ...")
    figures: dict[str, go.Figure] = {}
    figures["Summary"] = build_summary_figure(activities, by_group, boundaries)
    for group, group_products in by_group.items():
        figures[group] = build_group_figure(
            group, group_products, activities, trades, positions, boundaries,
        )

    out_path = os.path.splitext(log_path)[0] + "_visualisation.html"
    title = f"backtest {os.path.basename(log_path)}  (final P&L: {final_pnl:+,.1f})"
    write_tabbed_html(figures, out_path, title=title)
    print(f"\nWrote {out_path}")
    webbrowser.open("file://" + os.path.abspath(out_path))
```

- [ ] **Step 2: Run on the latest backtest log**

Run: `python visualise_backtest.py backtests/2026-04-29_12-49-55.log`
Expected:
- Console prints the summary block (products / ticks / fills / final P&L).
- Final line: `Wrote backtests/2026-04-29_12-49-55_visualisation.html`.
- Browser opens that file.

- [ ] **Step 3: Manual verification in the browser**

In the browser, confirm:

1. The tab strip is visible at the top with `Summary` first followed by group names.
2. Clicking `Summary` shows two panels: a thick black total cumulative equity line on top, per-product overlay below with multiple coloured lines.
3. Clicking a group tab (e.g. `MICROCHIP`) shows N rows of `[price+fills, position, equity]`.
4. Hovering on a price chart shows mid + any market trades + our fills.
5. If the backtest spans multiple days, faint vertical dotted lines appear at the day boundaries on every panel.

If any of those fail, fix and re-run before continuing.

- [ ] **Step 4: Run the test suite again to make sure nothing regressed**

Run: `python tests/test_visualise_backtest.py`
Expected: `All tests passed.` with 12 PASS lines.

- [ ] **Step 5: Commit**

```bash
git add visualise_backtest.py
git commit -m "Wire up CLI: pick_log, day boundaries, end-to-end main"
```

---

## Task 9: No-arg interactive run + error edge cases

**Files:**
- No code changes unless edge cases surface.

- [ ] **Step 1: Run with no argument and pick the most recent**

Run: `python visualise_backtest.py`
At the prompt, press Enter (default = most recent).
Expected:
- Numbered list of `backtests/*.log` files printed.
- Most recent log loads, summary prints, HTML opens.

- [ ] **Step 2: Run with a bad path**

Run: `python visualise_backtest.py /does/not/exist.log`
Expected:
- Prints `Error: file not found: /does/not/exist.log`
- Exits with non-zero status.

- [ ] **Step 3: Run with an older backtest log**

Pick a log from earlier than the recent ones (e.g. `backtests/2026-04-25_07-31-15.log`):

Run: `python visualise_backtest.py backtests/2026-04-25_07-31-15.log`
Expected:
- Loads and renders without errors.
- HTML written next to that log.
- Tabs adapt to whatever products that log contained.

- [ ] **Step 4: Final test sweep**

Run: `python tests/test_visualise_backtest.py`
Expected: `All tests passed.` with 12 PASS lines.

- [ ] **Step 5: Commit (only if anything changed)**

If the previous steps surfaced edge cases requiring code changes, commit them now. Otherwise skip this step.

```bash
git status
# If clean, no commit needed.
```

---

## Self-review notes (for the implementer)

- The plan does NOT add pytest. Tests are run with `python tests/test_visualise_backtest.py` to match the project's existing script-based style.
- Group bucketing uses **longest-prefix match** so `SLEEP_POD_LAMB_WOOL` correctly bucketed as `SLEEP_POD` even if `SLEEP` appeared somewhere in `GROUP_ORDER` (it doesn't — but the longest-match guard makes the function robust to future additions).
- The `_day_boundaries` helper returns `abs_timestamp` positions of every day except the first, matching how `visualise_live_log.py` annotates day breaks.
- `write_tabbed_html` calls `Plotly.Plots.resize` when a hidden tab becomes visible because Plotly figures rendered inside `display:none` containers have zero-width axes until they get a resize signal.
- Trades have no `day` field in the JSON; `load_log` infers `day` per trade by joining on `timestamp` against the activities table. This is correct because backtest trades always happen at activities timestamps.
