from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import numpy as np
import string

from emeralds import emeralds
from tomatoes import tomatoes

from logger import Logger
logger = Logger()
    
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