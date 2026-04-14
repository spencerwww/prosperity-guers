from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
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
    best_ask, best_ask_amount = list(order_depth.sell_orders.items())[0]
    best_bid, best_bid_amount = list(order_depth.buy_orders.items())[0]

    if len(order_depth.sell_orders) != 0:  
        if best_ask < mid_price:
            orders.append(Order(product, best_ask, best_ask_amount))
        if best_ask >= mid_price + 2:
            orders.append(Order(product, best_ask - 1, -max_pos - position))


    if len(order_depth.buy_orders) != 0:
        if best_bid > mid_price:
            orders.append(Order(product, best_bid, -best_bid_amount))
        if best_bid <= mid_price - 2:
            orders.append(Order(product, best_bid + 1, max_pos - position))

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
                    result[product] = []
    
        traderData = ""  # No state needed - we check position directly
        conversions = 0

        # logger.flush(state, result, conversions, traderData)
        return result, conversions, traderData