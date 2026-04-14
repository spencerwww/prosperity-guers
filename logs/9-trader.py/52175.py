from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import numpy as np
import string

# from logger import Logger
# logger = Logger()

def emeralds(state: TradingState):
    product = "EMERALDS"
    max_pos = 80
    mid_price = 10000

    position = state.position.get(product, 0)
    order_depth: OrderDepth = state.order_depths[product]
    orders: List[Order] = []

    buy_submitted = 0
    sell_submitted = 0

    if abs(position) >= 60:
        orders.append(Order(product, mid_price, -position))
        return orders
    

    if len(order_depth.sell_orders) != 0:
        for ask, qty in list(order_depth.sell_orders.items()):
            if int(ask) < mid_price:
                buy_qty = min(-qty, max_pos - position - buy_submitted)
                if buy_qty > 0:
                    orders.append(Order(product, ask, buy_qty))
                    buy_submitted += buy_qty

    if len(order_depth.buy_orders) != 0:
        for bid, qty in list(order_depth.buy_orders.items()):
            if int(bid) > mid_price:
                sell_qty = min(qty, max_pos + position - sell_submitted)
                if sell_qty > 0:
                    orders.append(Order(product, bid, -sell_qty))
                    sell_submitted += sell_qty

    if position > 53:
        unwind = min(position, max_pos + position - sell_submitted)
        if unwind > 0:
            orders.append(Order(product, mid_price, -unwind))
            sell_submitted += unwind
    elif position < 10:
        unwind = min(-position, max_pos - position - buy_submitted)
        if unwind > 0:
            orders.append(Order(product, mid_price, unwind))
            buy_submitted += unwind

    if len(order_depth.sell_orders) != 0 and len(order_depth.buy_orders) != 0:
        best_ask = list(order_depth.sell_orders.keys())[0]
        best_bid = list(order_depth.buy_orders.keys())[0]

        my_ask = best_ask - 1
        my_bid = best_bid + 1

        remaining_bid_capacity = max_pos - position - buy_submitted
        remaining_ask_capacity = max_pos + position - sell_submitted

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

    best_ask = list(order_depth.sell_orders.keys())[0]
    best_bid = list(order_depth.buy_orders.keys())[0]

    mid_price = int((best_ask + best_bid) / 2)

    buy_submitted = 0
    sell_submitted = 0

    if abs(position) >= 60:
        orders.append(Order(product, mid_price, -position))
        return orders
    

    if len(order_depth.sell_orders) != 0:
        for ask, qty in list(order_depth.sell_orders.items()):
            if int(ask) < mid_price:
                buy_qty = min(-qty, max_pos - position - buy_submitted)
                if buy_qty > 0:
                    orders.append(Order(product, ask, buy_qty))
                    buy_submitted += buy_qty

    if len(order_depth.buy_orders) != 0:
        for bid, qty in list(order_depth.buy_orders.items()):
            if int(bid) > mid_price:
                sell_qty = min(qty, max_pos + position - sell_submitted)
                if sell_qty > 0:
                    orders.append(Order(product, bid, -sell_qty))
                    sell_submitted += sell_qty

    if position > 53:
        unwind = min(position, max_pos + position - sell_submitted)
        if unwind > 0:
            orders.append(Order(product, mid_price, -unwind))
            sell_submitted += unwind
    elif position < -53:
        unwind = min(-position, max_pos - position - buy_submitted)
        if unwind > 0:
            orders.append(Order(product, mid_price, unwind))
            buy_submitted += unwind

    if len(order_depth.sell_orders) != 0 and len(order_depth.buy_orders) != 0:
        best_ask = list(order_depth.sell_orders.keys())[0]
        best_bid = list(order_depth.buy_orders.keys())[0]

        my_ask = best_ask - 1
        my_bid = best_bid + 1

        remaining_bid_capacity = max_pos - position - buy_submitted
        remaining_ask_capacity = max_pos + position - sell_submitted

        if my_ask > mid_price and remaining_ask_capacity > 0:
            orders.append(Order(product, my_ask, -remaining_ask_capacity))

        if my_bid < mid_price and remaining_bid_capacity > 0:
            orders.append(Order(product, my_bid, remaining_bid_capacity))

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

        # logger.flush(state, result, conversions, traderData)
        return result, conversions, traderData