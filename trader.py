from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import numpy as np
import string

from logger import Logger
logger = Logger()

def emeralds(state: TradingState):
    product = "EMERALDS"
    max_pos = 80
    mid_price = 10000

    position = state.position.get(product, 0)
    order_depth: OrderDepth = state.order_depths[product]
    orders: List[Order] = []
    bids = list(order_depth.buy_orders.items())
    asks = list(order_depth.sell_orders.items())

    cur_pos = position

    # Taking
    if bids:
        for bid, qty in bids:
            if int(bid) > mid_price:
                sell_qty = min(qty, max_pos + cur_pos)
                if sell_qty > 0:
                    orders.append(Order(product, bid, -sell_qty))
                    cur_pos -= sell_qty

    if asks:
        for ask, qty in asks:
            if int(ask) < mid_price:
                buy_qty = min(-qty, max_pos - cur_pos)
                if buy_qty > 0:
                    orders.append(Order(product, ask, buy_qty))
                    cur_pos += buy_qty

    # Flatten
    if bids and cur_pos > 0:
        for bid, qty in bids:
            if int(bid) == mid_price:
                sell_qty = min(qty, cur_pos)
                if sell_qty > 0:
                    orders.append(Order(product, bid, -sell_qty))
                    cur_pos -= sell_qty

    if asks and cur_pos < 0:
        for ask, qty in asks:
            if int(ask) == mid_price:
                buy_qty = min(-qty, -cur_pos)
                if buy_qty > 0:
                    orders.append(Order(product, ask, buy_qty))
                    cur_pos += buy_qty

    # Making
    if len(order_depth.sell_orders) != 0 and len(order_depth.buy_orders) != 0:
        best_ask = list(order_depth.sell_orders.keys())[0]
        best_bid = list(order_depth.buy_orders.keys())[0]

        my_ask = best_ask - 1
        my_bid = best_bid + 1

        remaining_bid_capacity = max_pos - cur_pos
        remaining_ask_capacity = max_pos + cur_pos

        if my_ask > mid_price and remaining_ask_capacity > 0:
            orders.append(Order(product, my_ask, -remaining_ask_capacity))

        if my_bid < mid_price and remaining_bid_capacity > 0:
            orders.append(Order(product, my_bid, remaining_bid_capacity))

    return orders

def tomatoes(state: TradingState):
    product = "TOMATOES"
    max_pos = 80

    position = state.position.get(product, 0)
    order_depth: OrderDepth = state.order_depths[product]
    orders: List[Order] = []
    bids = list(order_depth.buy_orders.items())
    asks = list(order_depth.sell_orders.items())

    wall_bid, wall_bid_qty = max(bids, key=lambda x: x[1])
    wall_ask, wall_ask_qty = min(asks, key=lambda x: x[1])

    wall_mid = int((wall_bid + wall_ask) / 2)

    cur_pos = position

    # Taking
    if bids:
        for bid, qty in bids:
            if int(bid) > wall_mid:
                sell_qty = min(qty, max_pos + cur_pos)
                if sell_qty > 0:
                    orders.append(Order(product, bid, -sell_qty))
                    cur_pos -= sell_qty

    if asks:
        for ask, qty in asks:
            if int(ask) < wall_mid:
                buy_qty = min(-qty, max_pos - cur_pos)
                if buy_qty > 0:
                    orders.append(Order(product, ask, buy_qty))
                    cur_pos += buy_qty

    # Flatten
    if bids and cur_pos > 0:
        for bid, qty in bids:
            if int(bid) == wall_mid:
                sell_qty = min(qty, cur_pos)
                if sell_qty > 0:
                    orders.append(Order(product, bid, -sell_qty))
                    cur_pos -= sell_qty

    if asks and cur_pos < 0:
        for ask, qty in asks:
            if int(ask) == wall_mid:
                buy_qty = min(-qty, -cur_pos)
                if buy_qty > 0:
                    orders.append(Order(product, ask, buy_qty))
                    cur_pos += buy_qty
    
    # Making
    if bids and asks:
        best_bid = list(order_depth.buy_orders.keys())[0]
        best_ask = list(order_depth.sell_orders.keys())[0]
        
        my_bid = best_bid + 1
        my_ask = best_ask - 1

        remaining_bid_capacity = max_pos - cur_pos
        remaining_ask_capacity = max_pos + cur_pos

        if my_bid < wall_mid and remaining_bid_capacity > 0:
            orders.append(Order(product, my_bid, remaining_bid_capacity))

        if my_ask > wall_mid and remaining_ask_capacity > 0:
            orders.append(Order(product, my_ask, -remaining_ask_capacity))

    return orders
    
class Trader:

    def bid(self):
        return 15
    
    def run(self, state: TradingState):
        """Only method required. It takes all buy and sell orders for all
        symbols as an input, and outputs a list of orders to be sent."""

        print("traderData: " + state.traderData)
        print("Observations: " + str(state.observations))

        # Orders to be placed on exchange matching engine
        result = {}
        for product in state.order_depths:
            match product:
                case "EMERALDS":
                    result[product] = emeralds(state)
                case "TOMATOES":
                    result[product] = tomatoes(state)
    
        traderData = ""  # No state needed - we check position directly
        conversions = 0

        logger.flush(state, result, conversions, traderData)
        return result, conversions, traderData