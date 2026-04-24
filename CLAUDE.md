# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **IMC Prosperity algorithmic trading competition** project. You write a `Trader` class with a `run()` method that the competition platform calls each timestep. The platform provides market state and expects back a dict of orders.

## Key Commands

Analyze a backtest log file:
```bash
python analyse_backtest.py backtests/<file>.log
# Or interactively pick from backtests/ directory:
python analyse_backtest.py
```

## Architecture

### Competition Interface

**`trader.py`** — the only file submitted to the competition. Contains the `Trader` class with a single required method:
```python
def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
```
It routes each product to a strategy function and returns `(orders, conversions, traderData)`.

**`datamodel.py`** — competition-provided data structures (do not modify):
- `TradingState`: full market snapshot per timestep — contains `order_depths`, `position`, `own_trades`, `market_trades`, `observations`, `traderData`
- `OrderDepth`: `buy_orders` and `sell_orders` as `{price: quantity}` dicts (sell quantities are negative)
- `Order(symbol, price, quantity)`: positive qty = buy, negative = sell

**`logger.py`** — competition-provided logger. Always call `logger.flush(state, result, conversions, traderData)` at the end of `run()`.

### Strategy Library

**`phase_1.py`** — all current strategy implementations as standalone functions:
- `bnh_ipr(state)` — buy-and-hold for INTARIAN_PEPPER_ROOT (accumulates max long)
- `mm_aco(state)` — market-making for ASH_COATED_OSMIUM with fixed fair value 10000
- `ou_aco(state)` — unused Ornstein-Uhlenbeck mean reversion (mu=10000, std=5.35)
- `aco(state)` — unused Bollinger band strategy for ACO
- `vwap(bids, asks)` — helper to compute volume-weighted average price

**`emeralds.py`** — market-making for EMERALDS (fixed mid=10000)

**`tomatoes.py`** — market-making for TOMATOES (fair value from largest bid/ask wall)

### Strategy Pattern

All strategies follow the same three-phase structure:
1. **Taking** — aggressively trade when price deviates from fair value
2. **Flattening** — close position at fair value price
3. **Making** — provide liquidity with limit orders on both sides

Position limit is **80 units** per product. Always track `cur_pos` through the order loop since multiple orders in one timestep stack.

### Analysis Infrastructure

**`analyse_backtest.py`** — parses `.log` files from backtests and prints Sharpe, Sortino, Calmar ratios, max drawdown, total PnL, and per-product breakdown.

**`ROUND_X/`** directories — Jupyter notebooks for exploratory data analysis of each round's price/trade CSVs (`prices_round_X_day_Y.csv`, `trades_round_X_day_Y.csv`).

## Adding a New Product Strategy

1. Write a function `my_strategy(state: TradingState) -> list[Order]` in `phase_1.py` (or a new module)
2. Add a `case "PRODUCT_NAME": result[product] = my_strategy(state)` in `trader.py`
3. Import the function in `trader.py` if it lives in a separate file
