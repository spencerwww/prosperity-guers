from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import numpy as np

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