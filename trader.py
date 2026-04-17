from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import numpy as np
import string

from logger import Logger
logger = Logger()

def bnh_ipr(state: TradingState):
  product = "INTARIAN_PEPPER_ROOT"
  order_depth: OrderDepth = state.order_depths[product]
  orders: List[Order] = []
  asks = list(order_depth.sell_orders.items())

  max_pos = 80
  cur_pos = state.position.get(product, 0)

  if asks:
        for ask, qty in asks:
              buy_qty = min(-qty, max_pos - cur_pos)
              if buy_qty > 0:
                  orders.append(Order(product, ask, buy_qty))
                  cur_pos += buy_qty
  
  return orders

def vwap(bids, asks):
    sum_price_volume = 0
    sum_volume = 0

    if bids:
        for bid, qty in bids:
            sum_price_volume += abs(bid * qty)
            sum_volume += abs(qty)
        
    if asks:
        for ask, qty in asks:
            sum_price_volume += abs(ask * qty)
            sum_volume += abs(qty)

    return sum_price_volume / sum_volume

def ou_aco(state: TradingState):
    product = "ASH_COATED_OSMIUM"
    max_pos = 80
    mu = 10000
    std = 5.35
    n_std = 3

    position = state.position.get(product, 0)
    order_depth: OrderDepth = state.order_depths[product]
    orders: List[Order] = []
    bids = list(order_depth.buy_orders.items())
    asks = list(order_depth.sell_orders.items())
    if len(bids) == 0 or len(asks) == 0:
        return orders
    
    best_bid, best_bid_qty = bids[0]
    best_ask, best_ask_qty = asks[0]

    mid_price = best_bid + best_ask / 2

    z_t = (mid_price - mu) / std

    desired_position = -((z_t / n_std) * max_pos)
    desired_position = max(-max_pos, min(max_pos, desired_position))

    if desired_position > position:
        if asks:
            for ask, qty in asks:
                buy_qty = int(min(-qty, desired_position - position))
                if buy_qty > 0:
                    orders.append(Order(product, ask, buy_qty))
                    position += buy_qty

    if desired_position < position:
        if bids:
            for bid, qty in bids:
                sell_qty = int(min(qty, position - desired_position))
                if sell_qty > 0:
                    orders.append(Order(product, bid, -sell_qty))
                    position -= sell_qty
    
    return orders

def bnh_aco(state: TradingState):
    product = "ASH_COATED_OSMIUM"
    order_depth: OrderDepth = state.order_depths[product]
    orders: List[Order] = []
    asks = list(order_depth.sell_orders.items())

    max_pos = 80
    cur_pos = state.position.get(product, 0)

    if asks:
            for ask, qty in asks:
                buy_qty = min(-qty, max_pos - cur_pos)
                if buy_qty > 0:
                    orders.append(Order(product, ask, buy_qty))
                    cur_pos += buy_qty
    
    return orders

def aco(state: TradingState):
    product = "ASH_COATED_OSMIUM"
    max_pos = 80

    position = state.position.get(product, 0)
    order_depth: OrderDepth = state.order_depths[product]
    orders: List[Order] = []
    bids = list(order_depth.buy_orders.items())
    asks = list(order_depth.sell_orders.items())

    true_price = 10000
    std = 5.35
    n_std = 0.6
    upper_band = true_price + (n_std * std)
    lower_band = true_price - (n_std * std)

    # Making
    if bids and asks:
        best_bid = list(order_depth.buy_orders.keys())[0]
        best_ask = list(order_depth.sell_orders.keys())[0]
        
        my_bid = best_bid + 1
        my_ask = best_ask - 1

        remaining_bid_capacity = max_pos - position
        remaining_ask_capacity = max_pos + position

        if my_bid < position and remaining_bid_capacity > 0:
            orders.append(Order(product, my_bid, remaining_bid_capacity))

        if my_ask > position and remaining_ask_capacity > 0:
            orders.append(Order(product, my_ask, -remaining_ask_capacity))

    if position > 0:
        for bid, qty in bids:
            if bid >= true_price:
                sell_qty = min(qty, max_pos + position)
                if sell_qty > 0:
                        orders.append(Order(product, bid, -sell_qty))
                        position -= sell_qty
    if position < 0:
        for ask, qty in asks:
            if ask <= true_price:
                    buy_qty = min(-qty, max_pos - position)
                    if buy_qty > 0:
                        orders.append(Order(product, ask, buy_qty))
                        position += buy_qty

    for bid, qty in bids:
        if bid >= upper_band:
            sell_qty = min(qty, max_pos + position)
            if sell_qty > 0:
                    orders.append(Order(product, bid, -sell_qty))
                    position -= sell_qty

    for ask, qty in asks:
        if ask <= lower_band:
                buy_qty = min(-qty, max_pos - position)
                if buy_qty > 0:
                    orders.append(Order(product, ask, buy_qty))
                    position += buy_qty

    return orders

def mm_aco(state: TradingState):
    product = "ASH_COATED_OSMIUM"
    max_pos = 80

    position = state.position.get(product, 0)
    order_depth: OrderDepth = state.order_depths[product]
    orders: List[Order] = []
    bids = list(order_depth.buy_orders.items())
    asks = list(order_depth.sell_orders.items())

    wall_mid = 10000

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

def bnh_tomatoes(state: TradingState):
    product = "TOMATOES"
    order_depth: OrderDepth = state.order_depths[product]
    orders: List[Order] = []
    asks = list(order_depth.sell_orders.items())

    max_pos = 80
    cur_pos = state.position.get(product, 0)

    if asks:
            for ask, qty in asks:
                buy_qty = min(-qty, max_pos - cur_pos)
                if buy_qty > 0:
                    orders.append(Order(product, ask, buy_qty))
                    cur_pos += buy_qty
    
    return orders

def bnh_emeralds(state: TradingState):
    product = "EMERALDS"
    order_depth: OrderDepth = state.order_depths[product]
    orders: List[Order] = []
    asks = list(order_depth.sell_orders.items())

    max_pos = 80
    cur_pos = state.position.get(product, 0)

    if asks:
            for ask, qty in asks:
                buy_qty = min(-qty, max_pos - cur_pos)
                if buy_qty > 0:
                    orders.append(Order(product, ask, buy_qty))
                    cur_pos += buy_qty
    
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
                case "INTARIAN_PEPPER_ROOT":
                    result[product] = bnh_ipr(state)
                case "ASH_COATED_OSMIUM":
                    result[product] = mm_aco(state)
    
        traderData = ""  # No state needed - we check position directly
        conversions = 0

        logger.flush(state, result, conversions, traderData)
        return result, conversions, traderData