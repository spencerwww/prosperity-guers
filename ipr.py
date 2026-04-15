from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import numpy as np

def ipr(state: TradingState):
    product = "INTARIAN_PEPPER_ROOT"
    max_pos = 80
    timestamp = state.timestamp
    mid_price = 0.001 * timestamp + 10000

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