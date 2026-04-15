from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import numpy as np
import string

from ipr import ipr
from bnh_ipr import bnh_ipr
from aco import aco

# from logger import Logger
# logger = Logger()
    
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
                    result[product] = []
    
        traderData = ""  # No state needed - we check position directly
        conversions = 0

        # logger.flush(state, result, conversions, traderData)
        return result, conversions, traderData