# Backtest Visualiser — Design

**Date:** 2026-04-29
**Topic:** New tool to visualise IMC Prosperity backtest log files (`backtests/*.log`)
**Status:** Approved by user

## Goal

Render a single self-contained HTML page that lets the trader inspect, post-hoc, what a backtest run did across all products. Specifically:

- A page per product family (group) showing each product's mid price with our buy/sell fills, our net position over time, and the per-product equity curve.
- A summary page showing total cumulative equity plus a per-product equity overlay coloured by group.

This is a static post-mortem visualiser, not a live tool.

## Output

- One self-contained HTML file written next to the source log: `backtests/<logname>_visualisation.html` (matches the existing convention used by `visualise_live_log.py`).
- Page navigation via a small JS tab strip at the top. Each tab maps to one Plotly `<div>`; clicking a tab toggles `display` on the divs. No bundler, no framework.
- Tab order: `Summary` first, then one tab per group in a fixed order, then `OTHER` if any unmatched products exist.

## Group detection

Hardcode the 10 family prefixes in the visualiser:

```
GALAXY_SOUNDS, SLEEP_POD, MICROCHIP, PEBBLES, ROBOT,
UV_VISOR, TRANSLATOR, PANEL, OXYGEN_SHAKE, SNACKPACK
```

For each product symbol observed in the log, bucket it under the **longest** matching prefix. Symbols that match no prefix go into a catch-all `OTHER` group.

Rationale: keeps the visualiser independent of `R5_trader.py`, so it doesn't break if that file is renamed or its constants change. The list is small and stable enough to duplicate.

## Data loading

Reuse the pattern from `visualise_live_log.py:42-66`:

1. `json.load(<logfile>)` → `{submissionId, activitiesLog, tradeHistory}`.
2. Parse `activitiesLog` (CSV-as-string, `;` separator) into a DataFrame. Columns include `day, timestamp, product, bid_price_*, bid_volume_*, ask_price_*, ask_volume_*, mid_price, profit_and_loss`.
3. Parse `tradeHistory` (list of dicts) into a DataFrame. Columns: `timestamp, buyer, seller, symbol, currency, price, quantity`.

If `day` is present and spans multiple values, compute an absolute timestamp: `abs_timestamp = timestamp + (day - day.min()) * 1_000_000`. Otherwise use raw `timestamp`. Add faint vertical day-boundary lines on every chart when there are multiple days.

## Trade tagging

Reuse `derive_sides` (`visualise_live_log.py:69-90`):

- `buyer == "SUBMISSION"` → side = `BUY`, counterparty = seller.
- `seller == "SUBMISSION"` → side = `SELL`, counterparty = buyer.
- otherwise → side = `MARKET` (other-trader fills shown as faint context dots).
- `signed_qty = quantity * {BUY: +1, SELL: -1, MARKET: 0}`.

## Position derivation

For each product, group `BUY`/`SELL` trades by `abs_timestamp`, sum `signed_qty`, reindex onto the activities tick grid filling 0, then `cumsum`. Same shape as `build_position_per_product` in `visualise_live_log.py:93-102`.

## Equity curve

Trust the `profit_and_loss` column emitted by the platform inside `activitiesLog`. Per-product equity = that column. Cumulative equity at each timestamp = sum across products of `profit_and_loss` at that timestamp. Do not recompute from trades.

## Group page layout

For a group with N products (typically up to 5), build `make_subplots(rows=N, cols=3, shared_xaxes=True)`:

| Col | Content |
|-----|---------|
| 1 | Mid price line (grey), our BUYs (green ▲), our SELLs (red ▽), market fills (faint grey dots). Lifted from `visualise_live_log.py:144-222`. |
| 2 | Step plot of net position (`shape="hv"`). Zero line dotted. |
| 3 | Cumulative `profit_and_loss` for that product (per-product equity curve). Zero line dotted. |

Each row is labelled with the product symbol via a left-anchored paper-coordinate annotation (Plotly subplots have no native left-row titles). Row height ~180px; a 5-product group is ~900px tall — one scroll. Figure-level `hovermode="x unified"` so hovering shows all three columns' values at that timestamp.

## Summary page

Two stacked subplots, shared x-axis:

- **Top** — single thick line: total cumulative equity = sum across all products of `profit_and_loss` at each timestamp. Height ~280px.
- **Bottom** — one line per product (~50), coloured by group family using a 10-colour palette. Legend toggleable; click a legend entry to hide that product. Height ~440px.

`hovermode="x unified"` so a single hover shows all visible products' values at that tick.

## CLI

Mirror `visualise_live_log.py:303-345`:

```
python visualise_backtest.py [<logfile>]
```

No argument → scan `backtests/*.log`, print numbered list, prompt for choice (default = most recent). Print a one-line summary on load (products, ticks, our fills, final summed PnL). Write `<logfile>_visualisation.html`. Open it in the default browser.

## Out of scope (explicitly not built)

- Order-book depth view — `visualiser.py` already covers this.
- Multi-backtest comparison — one log at a time.
- Streamlit — single self-contained HTML chosen instead.
- PnL recomputation from trades — platform's `profit_and_loss` is treated as authoritative.
- Per-trade strategy attribution / log-line correlation.

## File structure

One new file: `visualise_backtest.py` at the project root, alongside the existing `visualise_*.py` siblings. No edits to other files.

## Dependencies

`pandas`, `plotly` — both already used elsewhere in the project. No new dependencies.
