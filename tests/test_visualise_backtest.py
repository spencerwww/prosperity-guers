"""
Run with:  python tests/test_visualise_backtest.py
Asserts on pure data functions in visualise_backtest.
"""
import os
import sys
import glob as glob_module
import tempfile
import plotly.graph_objects as go

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


def test_downsample_caps_at_max_points():
    from visualise_backtest import _downsample, MAX_POINTS_PER_LINE
    # Below the cap: passes through unchanged.
    small = pd.DataFrame({"x": range(100)})
    assert len(_downsample(small)) == 100

    # Above the cap: stride-sampled to <= max_points.
    big = pd.DataFrame({"x": range(MAX_POINTS_PER_LINE * 10)})
    out = _downsample(big)
    assert len(out) <= MAX_POINTS_PER_LINE
    # First and last x values are preserved roughly (first exact, last close).
    assert out["x"].iloc[0] == 0

    # Series path also works.
    s = pd.Series(range(MAX_POINTS_PER_LINE * 5))
    assert len(_downsample(s)) <= MAX_POINTS_PER_LINE


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
