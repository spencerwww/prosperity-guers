"""
Run with:  python tests/test_visualise_backtest.py
Asserts on pure data functions in visualise_backtest.
"""
import os
import sys
import glob as glob_module

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
