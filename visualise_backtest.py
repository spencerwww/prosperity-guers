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
