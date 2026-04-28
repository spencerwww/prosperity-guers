from datamodel import OrderDepth, UserId, TradingState, Order, Symbol, Trade, Listing, Observation, ProsperityEncoder
from typing import List, Any
import json
import numpy as np
import string

from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState

class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                ]
            )
        )

        # We truncate state.traderData, trader_data, and self.logs to the same max. length to fit the log limit
        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        compressed = []
        for listing in listings.values():
            compressed.append([listing.symbol, listing.product, listing.denomination])

        return compressed

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [order_depth.buy_orders, order_depth.sell_orders]

        return compressed

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append(
                    [
                        trade.symbol,
                        trade.price,
                        trade.quantity,
                        trade.buyer,
                        trade.seller,
                        trade.timestamp,
                    ]
                )

        return compressed

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice,
                observation.askPrice,
                observation.transportFees,
                observation.exportTariff,
                observation.importTariff,
                observation.sugarPrice,
                observation.sunlightIndex,
            ]

        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])

        return compressed

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        lo, hi = 0, min(len(value), max_length)
        out = ""

        while lo <= hi:
            mid = (lo + hi) // 2

            candidate = value[:mid]
            if len(candidate) < len(value):
                candidate += "..."

            encoded_candidate = json.dumps(candidate)

            if len(encoded_candidate) <= max_length:
                out = candidate
                lo = mid + 1
            else:
                hi = mid - 1

        return out

logger = Logger()

MEAN_REVERTING_MU = 9990.806866666666
MEAN_REVERTING_STD = 31.93521376335991
MEAN_REVERTING_N_STD = 1.6
MEAN_REVERTING_UPPER_BAND = MEAN_REVERTING_MU + MEAN_REVERTING_N_STD * MEAN_REVERTING_STD
MEAN_REVERTING_LOWER_BAND = MEAN_REVERTING_MU - MEAN_REVERTING_N_STD * MEAN_REVERTING_STD

VEV_MU = 5250.0981
VEV_STD = 15.630415436563267
VEV_N_STD = 1.4
VEV_UPPER_BAND = VEV_MU + VEV_N_STD * VEV_STD
VEV_LOWER_BAND = VEV_MU - VEV_N_STD * VEV_STD

VEV_4000_MU = 1250.1098
VEV_4000_STD = 15.647242733684596

VEV_4500_MU = 750.1096
VEV_4500_STD = 15.6399

VEV_5000_MU = 255.0224
VEV_5000_STD = 14.3756

VEV_5100_MU = 166.8055
VEV_5100_STD = 12.7426

VEV_5200_MU = 95.5488
VEV_5200_STD = 9.6642

VEV_5300_MU = 46.7599
VEV_5300_STD = 6.2281

VEV_5400_MU = 15.9519
VEV_5400_STD = 3.4292

VEV_5500_MU = 6.6414
VEV_5500_STD = 1.7388

def informed(product, trader_name, state: TradingState):
    max_pos = 200

    position = state.position.get(product, 0)
    order_depth: OrderDepth = state.order_depths[product]
    orders: List[Order] = []
    market_trades = state.market_trades.get(product, [])
    bids = list(order_depth.buy_orders.items())
    asks = list(order_depth.sell_orders.items())

    wall_bid, wall_bid_qty = max(bids, key=lambda x: x[1])
    wall_ask, wall_ask_qty = max(asks, key=lambda x: x[1])

    wall_mid = int((wall_bid + wall_ask) / 2)

    for trade in market_trades:
        if trade.buyer == trader_name:
            for bp, bv in bids:
                orders.append(Order(product, bp, -bv))
                break
            
            
        if trade.seller == trader_name:
            for sp, sv in asks:
                orders.append(Order(product, sp, -sv))
                break
            

    return orders

def underlying(product, mean, std, n_std, state: TradingState):
    upper_band = mean + n_std * std
    lower_band = mean - n_std * std
    max_pos = 200

    position = state.position.get(product, 0)
    order_depth: OrderDepth = state.order_depths[product]
    orders: List[Order] = []
    bids = list(order_depth.buy_orders.items())
    asks = list(order_depth.sell_orders.items())

    wall_bid, wall_bid_qty = max(bids, key=lambda x: x[1])
    wall_ask, wall_ask_qty = max(asks, key=lambda x: x[1])

    wall_mid = int((wall_bid + wall_ask) / 2)


    if wall_mid is not None:

        if position > 0:
            if wall_mid > 9985 and wall_mid < 9995:
                for bp, bv in bids:
                    orders.append(Order(product, bp, -bv))
                    break

        if position < 0:
            if wall_mid > 9985 and wall_mid < 9995:
                for sp, sv in asks:
                    orders.append(Order(product, sp, -sv))
                    break
                
            ##########################################################
            ####### 1. TAKING
            ##########################################################
        for sp, sv in asks:
            if wall_mid <= lower_band:
                orders.append(Order(product, sp, -sv))
                break

        for bp, bv in bids:
            if wall_mid >= upper_band:
                orders.append(Order(product, bp, -bv))
                break

    return orders


    
class Trader:
    
    def run(self, state: TradingState):
        """Only method required. It takes all buy and sell orders for all
        symbols as an input, and outputs a list of orders to be sent."""

        print("traderData: " + state.traderData)
        print("Observations: " + str(state.observations))

        result = {}
        for product in state.order_depths:
            match product:
                case "HYDROGEL_PACK":
                    result[product] = informed(product, "Mark 14", state)
                case "VELVETFRUIT_EXTRACT":
                    result[product] = informed(product, "Mark 14", state)
                case "VEV_4000":
                    result[product] = informed(product, "Mark 14", state)
                # case "VEV_4500":
                #     result[product] = underlying(product, VEV_4500_MU, VEV_4500_STD, VEV_N_STD, state)
                # case "VEV_5000":
                #     result[product] = underlying(product, VEV_5000_MU, VEV_5000_STD, VEV_N_STD, state)
                # case "VEV_5100":
                #     result[product] = underlying(product, VEV_5100_MU, VEV_5100_STD, VEV_N_STD, state)
                # case "VEV_5200":
                #     result[product] = underlying(product, VEV_5200_MU, VEV_5200_STD, VEV_N_STD, state)
                # case "VEV_5300":
                #     result[product] = underlying(product, VEV_5300_MU, VEV_5300_STD, VEV_N_STD, state)
                # case "VEV_5400":
                #     result[product] = underlying(product, VEV_5400_MU, VEV_5400_STD, VEV_N_STD, state)
                # case "VEV_5500":
                #     result[product] = underlying(product, VEV_5500_MU, VEV_5500_STD, VEV_N_STD, state)
        traderData = ""  # No state needed - we check position directly
        conversions = 0

        logger.flush(state, result, conversions, traderData)
        return result, conversions, traderData