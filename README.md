# Prosperity 4

My codebase for the **IMC Prosperity 4** algorithmic trading competition.

## About the Competition

[IMC Prosperity](https://prosperity.imc.com/) is a 15-day algorithmic trading challenge run by IMC. Teams write a Python `Trader` class that the platform calls each timestep on a simulated exchange. The simulation spans **five rounds**, each unlocking new tradable products and market mechanics (market-making fundamentals, ETF/basket arbitrage, options and implied volatility, foreign-exchange conversions, observation-driven signals, etc.).

Each round consists of:
- An **algorithmic challenge** — your `Trader` runs against bot counterparties on historical-style data, ranked by total PnL.
- A **manual challenge** — a one-off puzzle (auction, game-theory problem, expected-value question).

Across rounds new products carry over, so the trader grows into a multi-product engine by Round 5.

## Competition Interface

The platform invokes one method per timestep:

```python
def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
```

Returning `(orders_by_symbol, conversions, traderData)`. Position limits are enforced per product; orders that breach the limit are rejected.

Two files are platform-provided and unmodifiable:
- `datamodel.py` — `TradingState`, `OrderDepth`, `Order`, `Trade`, `Observation`.
- `logger.py` — competition logger used by the visualiser.

## Repository Layout

### Round entrypoints

- **`R5_trader.py`** — current submission. Defines per-product trader classes (`TranslatorTrader`, `GSTrader`, `UVTrader`, `OSTrader`, `MicrochipTrader`, `RobotTrader`, `PSRTrader`, `VCTrader`, `XLSTrader`, `SPPSTrader`, `PanelPairTrader`, ...) plus a top-level `Trader.run()` that dispatches each product to its trader class.
- **`R4_trader.py`** — Round 4 submission, kept for reference.
- **`archive/`** — earlier rounds (`phase_1.py`, `emeralds.py`, `tomatoes.py`) and experimental strategies.

### Architecture inside `R5_trader.py`

1. **Symbol groups** (top of file): every product is grouped into a family (`GALAXY_SYMBOLS`, `MICROCHIP_SYMBOLS`, `PANEL_SYMBOLS`, etc.). Cross-product strategies (pair trades, basket arb, sector rotation) index into these lists.
2. **Per-product trader classes**: each class is constructed per timestep with `(state, prints, trader_data)` and exposes `get_orders() -> dict[Symbol, list[Order]]`. Strategies generally follow the **take / flatten / make** pattern:
   - **Take** — cross the spread when price diverges from fair value.
   - **Flatten** — unwind inventory at fair value.
   - **Make** — quote limit orders on both sides.
3. **`Trader.run()`**: deserialises `state.traderData`, iterates the `product_traders` dispatch dict, swallows per-product exceptions so one broken strategy can't kill the rest, then re-serialises `traderData` and emits a JSON `prints` blob the visualiser parses.

### Analysis & visualisation

- **`visualiser.py`** — backtest log → interactive HTML (PnL curves, position/inventory traces, order-book heatmaps).
- **`visualise_backtest.py`**, **`visualise_round4.py`**, **`visualise_live_log.py`** — entry scripts for various log formats.
- **`backtests/`** — saved `.log` files plus generated `_visualisation.html` companions.

### Per-round research

- **`ROUND_1/` … `ROUND_5/`** — raw competition data (`prices_round_X_day_Y.csv`, `trades_round_X_day_Y.csv`) and Jupyter notebooks for EDA, model fitting, and strategy prototyping (e.g. `R5/PSR.ipynb`, `R5/translators.ipynb`, `R4/vev.ipynb`, `R3/iv.ipynb`).
- **`Resources/`** — course material and reference implementations (backtester scaffolds, statistics solutions) used while studying.

### Misc

- **`informed_trader.py`**, **`sma_trader.py`** — standalone strategy experiments.
- **`logs/`** — historical submissions paired with the trader source that produced them.
- **`docs/`** — design notes and implementation plans.

## Running a Backtest

The competition provides its own backtester; locally the workflow is:

1. Run a backtest using the official tool, dumping a `.log` into `backtests/`.
2. Generate the HTML visualisation:
   ```bash
   python visualise_backtest.py backtests/<file>.log
   ```
3. Open the produced `<file>_visualisation.html`.

## Adding a New Product

1. Add the product's symbols to a constant list at the top of `R5_trader.py`.
2. Write a `FooTrader` class taking `(state, prints, trader_data)` with a `get_orders()` method.
3. Register it in the `product_traders` dict inside `Trader.run()`.
