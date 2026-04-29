from datamodel import OrderDepth, TradingState, Order
import json
import numpy as np
import math
from statistics import NormalDist

_N = NormalDist()

####### GENERAL ####### GENERAL ####### GENERAL ####### GENERAL ####### GENERAL ####### GENERAL ####### GENERAL ####### GENERAL  

GALAXY_SYMBOLS = [
    'GALAXY_SOUNDS_DARK_MATTER',
    'GALAXY_SOUNDS_BLACK_HOLES',
    'GALAXY_SOUNDS_PLANETARY_RINGS',
    'GALAXY_SOUNDS_SOLAR_WINDS',
    'GALAXY_SOUNDS_SOLAR_FLAMES',
]

SLEEP_POD_SYMBOLS = [
    'SLEEP_POD_SUEDE',
    'SLEEP_POD_LAMB_WOOL',
    'SLEEP_POD_POLYESTER',
    'SLEEP_POD_NYLON',
    'SLEEP_POD_COTTON',
]

MICROCHIP_SYMBOLS = [
    'MICROCHIP_CIRCLE',
    'MICROCHIP_OVAL',
    'MICROCHIP_SQUARE',
    'MICROCHIP_RECTANGLE',
    'MICROCHIP_TRIANGLE',
]

PEBBLES_SYMBOLS = [
    'PEBBLES_XS',
    'PEBBLES_S',
    'PEBBLES_M',
    'PEBBLES_L',
    'PEBBLES_XL',
]

ROBOT_SYMBOLS = [
    'ROBOT_VACUUMING',
    'ROBOT_MOPPING',
    'ROBOT_DISHES',
    'ROBOT_LAUNDRY',
    'ROBOT_IRONING',
]

UV_VISOR_SYMBOLS = [
    'UV_VISOR_YELLOW',
    'UV_VISOR_AMBER',
    'UV_VISOR_ORANGE',
    'UV_VISOR_RED',
    'UV_VISOR_MAGENTA',
]

TRANSLATOR_SYMBOLS = [
    'TRANSLATOR_SPACE_GRAY',
    'TRANSLATOR_ASTRO_BLACK',
    'TRANSLATOR_ECLIPSE_CHARCOAL',
    'TRANSLATOR_GRAPHITE_MIST',
    'TRANSLATOR_VOID_BLUE',
]

PANEL_SYMBOLS = [
    'PANEL_1X2',
    'PANEL_2X2',
    'PANEL_1X4',
    'PANEL_2X4',
    'PANEL_4X4',
]

OXYGEN_SHAKE_SYMBOLS = [
    'OXYGEN_SHAKE_MORNING_BREATH',
    'OXYGEN_SHAKE_EVENING_BREATH',
    'OXYGEN_SHAKE_MINT',
    'OXYGEN_SHAKE_CHOCOLATE',
    'OXYGEN_SHAKE_GARLIC',
]

SNACKPACK_SYMBOLS = [
    'SNACKPACK_CHOCOLATE',
    'SNACKPACK_VANILLA',
    'SNACKPACK_PISTACHIO',
    'SNACKPACK_STRAWBERRY',
    'SNACKPACK_RASPBERRY',
]

SNACKPACK_PSR_SYMBOLS = [
    'SNACKPACK_PISTACHIO',
    'SNACKPACK_STRAWBERRY',
    'SNACKPACK_RASPBERRY',
]

SNACKPACK_VC_SYMBOLS = [
    'SNACKPACK_VANILLA',
    'SNACKPACK_CHOCOLATE',
]

POS_LIMIT = 10

LONG, NEUTRAL, SHORT = 1, 0, -1

############### PSR ############### 

PSR_ALPHA = 11.513697565779395
PSR_BETA = -0.25385583527783534
PSR_SPREAD_STD = 0.01767577401357323
PSR_THRESHOLD = 1.8

############### VC ############### 

VC_ALPHA = 16.556141389751517
VC_BETA = -0.7979115826032864
VC_SPREAD_STD = 0.006755144417558233
VC_THRESHOLD = 1.0

############### PEBBLE ###############

PEBBLES_BETA = [26.28024559,  2.94634034, 32.19080164, 19.19052495, 27.36364919]
PEBBLES_SPREAD_MEAN = 994.1706388773875
PEBBLES_SPREAD_STD = 1.001673170987763
PEBBLES_THRESHOLD = 3.0

############### TRANSLATOR ###############

TRANSLATOR_BETA = [16.25250433, -25.06013879,   2.63142257,  13.14531716, 28.91675378]
TRANSLATOR_SPREAD_MEAN = 331.526249336317
TRANSLATOR_SPREAD_STD = 1.0034714623065943
TRANSLATOR_THRESHOLD = 2

############### MICROCHIP ###############

MICROCHIP_BETA = [16.34572941, -13.59596011, -31.82337302]
MICROCHIP_SPREAD_MEAN = -268.3509747533391
MICROCHIP_SPREAD_STD = 1.0003801297138426
MICROCHIP_THRESHOLD = 1.5

# This is the base ProductTrader class that has all the commonly used utility attributes and methods already implemented for individual traders
class ProductTrader:

    def __init__(self, name, state, prints, new_trader_data, product_group=None):

        self.orders = []

        self.name = name
        self.state = state
        self.prints = prints
        self.new_trader_data = new_trader_data
        self.product_group = name if product_group is None else product_group

        self.last_traderData = self.get_last_traderData()

        self.position_limit = POS_LIMIT
        self.initial_position = self.state.position.get(self.name, 0) # position at beginning of round

        self.expected_position = self.initial_position # update this if you expect a certain change in position e.g. to already hedge


        self.mkt_buy_orders, self.mkt_sell_orders = self.get_order_depth()
        self.bid_wall, self.wall_mid, self.ask_wall = self.get_walls()
        self.best_bid, self.best_ask = self.get_best_bid_ask()

        self.max_allowed_buy_volume, self.max_allowed_sell_volume = self.get_max_allowed_volume() # gets updated when order created
        self.total_mkt_buy_volume, self.total_mkt_sell_volume = self.get_total_market_buy_sell_volume()

    def get_last_traderData(self):
                        
        last_traderData = {}
        try:
            if self.state.traderData != '':
                last_traderData = json.loads(self.state.traderData)
        except: self.log("ERROR", 'td')

        return last_traderData


    def get_best_bid_ask(self):

        best_bid = best_ask = None

        try:
            if len(self.mkt_buy_orders) > 0:
                best_bid = max(self.mkt_buy_orders.keys())
            if len(self.mkt_sell_orders) > 0:
                best_ask = min(self.mkt_sell_orders.keys())
        except: pass

        return best_bid, best_ask


    def get_walls(self):

        bid_wall = wall_mid = ask_wall = None

        try: bid_wall = min([x for x,_ in self.mkt_buy_orders.items()])
        except: pass
        
        try: ask_wall = max([x for x,_ in self.mkt_sell_orders.items()])
        except: pass

        try: wall_mid = (bid_wall + ask_wall) / 2
        except: pass

        return bid_wall, wall_mid, ask_wall
    
    def get_total_market_buy_sell_volume(self):

        market_bid_volume = market_ask_volume = 0

        try:
            market_bid_volume = sum([v for p, v in self.mkt_buy_orders.items()])
            market_ask_volume = sum([v for p, v in self.mkt_sell_orders.items()])
        except: pass

        return market_bid_volume, market_ask_volume
    

    def get_max_allowed_volume(self):
        max_allowed_buy_volume = self.position_limit - self.initial_position
        max_allowed_sell_volume = self.position_limit + self.initial_position
        return max_allowed_buy_volume, max_allowed_sell_volume

    def get_order_depth(self):

        order_depth, buy_orders, sell_orders = {}, {}, {}

        try: order_depth: OrderDepth = self.state.order_depths[self.name]
        except: pass
        try: buy_orders = {bp: abs(bv) for bp, bv in sorted(order_depth.buy_orders.items(), key=lambda x: x[0], reverse=True)}
        except: pass
        try: sell_orders = {sp: abs(sv) for sp, sv in sorted(order_depth.sell_orders.items(), key=lambda x: x[0])}
        except: pass

        return buy_orders, sell_orders
    

    def bid(self, price, volume, logging=True):
        abs_volume = min(abs(int(volume)), self.max_allowed_buy_volume)
        order = Order(self.name, int(price), abs_volume)
        if logging: self.log("BUYO", {"p":price, "s":self.name, "v":int(volume)}, product_group='ORDERS')
        self.max_allowed_buy_volume -= abs_volume
        self.orders.append(order)

    def ask(self, price, volume, logging=True):
        abs_volume = min(abs(int(volume)), self.max_allowed_sell_volume)
        order = Order(self.name, int(price), -abs_volume)
        if logging: self.log("SELLO", {"p":price, "s":self.name, "v":int(volume)}, product_group='ORDERS')
        self.max_allowed_sell_volume -= abs_volume
        self.orders.append(order)

    def log(self, kind, message, product_group=None):
        if product_group is None: product_group = self.product_group

        if product_group == 'ORDERS':
            group = self.prints.get(product_group, [])
            group.append({kind: message})
        else:
            group = self.prints.get(product_group, {})
            group[kind] = message

        self.prints[product_group] = group

    def get_orders(self):
        # overwrite this in each trader
        return {}
    
class PSRTrader:
    def __init__(self, state, prints, new_trader_data):
        self.pistachio = ProductTrader("SNACKPACK_PISTACHIO", state, prints, new_trader_data)
        self.strawberry = ProductTrader("SNACKPACK_STRAWBERRY", state, prints, new_trader_data)
        self.raspberry = ProductTrader("SNACKPACK_RASPBERRY", state, prints, new_trader_data)

        self.state = state
        self.new_trader_data = new_trader_data

        self.z_spread = self.calculate_z_spread()

    def calculate_z_spread(self):
        pistachio_pred = PSR_ALPHA + PSR_BETA * np.log(self.strawberry.wall_mid)
        raw_spread = np.log(self.pistachio.wall_mid) - pistachio_pred
        z_spread = raw_spread / PSR_SPREAD_STD
        return z_spread
    
    def get_orders(self):
        p = self.pistachio
        s = self.strawberry
        r = self.raspberry

        orders = {}

        if self.z_spread > PSR_THRESHOLD and p.max_allowed_sell_volume > 0:
            p.ask(p.bid_wall, p.max_allowed_sell_volume)
            s.ask(s.bid_wall, s.max_allowed_sell_volume)
            r.bid(r.ask_wall, r.max_allowed_buy_volume)
        elif self.z_spread < -PSR_THRESHOLD and p.max_allowed_buy_volume > 0:
            p.bid(p.ask_wall, p.max_allowed_buy_volume)
            s.bid(s.ask_wall, s.max_allowed_buy_volume)
            r.ask(r.bid_wall, r.max_allowed_sell_volume)

        orders.update({p.name: p.orders, s.name: s.orders, r.name: r.orders})

        return orders
    
class VCTrader:
    def __init__(self, state, prints, new_trader_data):
        self.vanilla = ProductTrader("SNACKPACK_VANILLA", state, prints, new_trader_data)
        self.chocolate = ProductTrader("SNACKPACK_CHOCOLATE", state, prints, new_trader_data)
        
        self.state = state
        self.new_trader_data = new_trader_data

        self.z_spread = self.calculate_z_spread()

    def calculate_z_spread(self):
        vanilla_pred = VC_ALPHA + VC_BETA * np.log(self.chocolate.wall_mid)
        raw_spread = np.log(self.vanilla.wall_mid) - vanilla_pred
        z_spread = raw_spread / VC_SPREAD_STD
        return z_spread
    
    def get_orders(self):
        v = self.vanilla
        c = self.chocolate

        orders = {}

        if self.z_spread > VC_THRESHOLD and v.max_allowed_sell_volume > 0:
            v.ask(v.bid_wall, v.max_allowed_sell_volume)
            c.bid(c.ask_wall, c.max_allowed_buy_volume)
            
        elif self.z_spread < -VC_THRESHOLD and v.max_allowed_buy_volume > 0:
            v.bid(v.ask_wall, v.max_allowed_buy_volume)
            c.ask(c.bid_wall, c.max_allowed_sell_volume)

        orders.update({v.name: v.orders, c.name: c.orders})

        return orders
    
class BasketTrader:
    """
    Generic linear-basket mean-reversion trader.

    legs: list of dicts with keys
        symbol: product symbol
        side:   +1 / 0 / -1
                When z > +threshold we trade `side`: +1 → ask, -1 → bid, 0 → skip.
                When z < -threshold the directions flip.
        vol:    'self' (default) or float scale.
                'self'  -> use this leg's own max_allowed_{buy,sell}_volume.
                float k -> use k * lead's volume in the entry direction.

    The lead leg is the first leg with side != 0 and vol == 'self'; its
    volume gates entry and serves as the base for scaled legs.

    flatten: if True, when no entry fires and the lead carries a position
             whose sign disagrees with z, close every traded leg at its
             own |initial_position|.
    """

    def __init__(self, state, prints, new_trader_data, *, legs,
                 beta, spread_mean, spread_std, threshold, flatten=False):
        self.legs = []
        for leg in legs:
            pt = ProductTrader(leg['symbol'], state, prints, new_trader_data)
            self.legs.append({'pt': pt, 'side': leg['side'], 'vol': leg.get('vol', 'self')})

        self.beta = np.asarray(beta)
        self.spread_mean = spread_mean
        self.spread_std = spread_std
        self.threshold = threshold
        self.flatten = flatten

        self.lead = next(l for l in self.legs if l['side'] != 0 and l['vol'] == 'self')

        self.z_spread = self.calculate_z_spread()

    def calculate_z_spread(self):
        y = np.array([l['pt'].wall_mid for l in self.legs])
        raw_spread = y @ self.beta
        return (raw_spread - self.spread_mean) / self.spread_std

    @staticmethod
    def _do_ask(sign, side):
        return (sign * side) > 0

    def _lead_entry_vol(self, sign):
        lead_pt = self.lead['pt']
        if self._do_ask(sign, self.lead['side']):
            return lead_pt.max_allowed_sell_volume
        return lead_pt.max_allowed_buy_volume

    def _trade(self, sign, use_initial_position=False):
        lead_base = (abs(self.lead['pt'].initial_position)
                     if use_initial_position else self._lead_entry_vol(sign))

        for leg in self.legs:
            if leg['side'] == 0:
                continue
            pt = leg['pt']
            do_ask = self._do_ask(sign, leg['side'])
            if leg['vol'] == 'self':
                if use_initial_position:
                    vol = abs(pt.initial_position)
                else:
                    vol = pt.max_allowed_sell_volume if do_ask else pt.max_allowed_buy_volume
            else:
                vol = int(leg['vol'] * lead_base)
            if do_ask:
                pt.ask(pt.bid_wall, vol)
            else:
                pt.bid(pt.ask_wall, vol)

    def get_orders(self):
        z = self.z_spread

        if z > self.threshold and self._lead_entry_vol(+1) > 0:
            self._trade(+1)
        elif z < -self.threshold and self._lead_entry_vol(-1) > 0:
            self._trade(-1)
        elif self.flatten:
            lead_pos = self.lead['pt'].initial_position
            lead_side = self.lead['side']
            # Closing trades the lead opposite to entry. Lead asks ⇔ sign*lead_side>0.
            # lead_pos>0 was acquired by bidding → close by asking → close_sign = lead_side.
            if lead_pos > 0 and z < 0:
                self._trade(lead_side, use_initial_position=True)
            elif lead_pos < 0 and z > 0:
                self._trade(-lead_side, use_initial_position=True)

        return {l['pt'].name: l['pt'].orders for l in self.legs if l['side'] != 0}


class PebblesTrader(BasketTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'PEBBLES_XS', 'side': +1},
                {'symbol': 'PEBBLES_S',  'side': +1},
                {'symbol': 'PEBBLES_M',  'side':  0},
                {'symbol': 'PEBBLES_L',  'side':  0},
                {'symbol': 'PEBBLES_XL', 'side': -1},
            ],
            beta=PEBBLES_BETA,
            spread_mean=PEBBLES_SPREAD_MEAN,
            spread_std=PEBBLES_SPREAD_STD,
            threshold=PEBBLES_THRESHOLD,
        )


class TranslatorTrader(BasketTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'TRANSLATOR_ASTRO_BLACK',       'side': +1},
                {'symbol': 'TRANSLATOR_ECLIPSE_CHARCOAL',  'side': -1},
                {'symbol': 'TRANSLATOR_GRAPHITE_MIST',     'side': +1},
                {'symbol': 'TRANSLATOR_SPACE_GRAY',        'side': +1},
                {'symbol': 'TRANSLATOR_VOID_BLUE',         'side': +1},
            ],
            beta=TRANSLATOR_BETA,
            spread_mean=TRANSLATOR_SPREAD_MEAN,
            spread_std=TRANSLATOR_SPREAD_STD,
            threshold=TRANSLATOR_THRESHOLD,
        )


class MicrochipTrader(BasketTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(state, prints, new_trader_data,
            legs=[
                {'symbol': 'MICROCHIP_OVAL',      'side': +1, 'vol': 0.5},
                {'symbol': 'MICROCHIP_RECTANGLE', 'side': +1, 'vol': 0.4},
                {'symbol': 'MICROCHIP_TRIANGLE',  'side': -1},
            ],
            beta=MICROCHIP_BETA,
            spread_mean=MICROCHIP_SPREAD_MEAN,
            spread_std=MICROCHIP_SPREAD_STD,
            threshold=MICROCHIP_THRESHOLD,
            flatten=True,
        )


class MarketMakingTrader:
    """
    Single-product market maker following the take → flatten → make pattern.

    Fair value = midpoint of the largest-volume bid and ask in the book
    (the "walls"), matching the original tomatoes strategy. This differs
    from ProductTrader.wall_mid, which uses the outermost prices.

    Phases:
      1. Take    - cross any bid above fair / ask below fair
      2. Flatten - dump residual position at the fair price
      3. Make    - post one tick inside top-of-book on each side, only when
                   the resulting quote stays on the right side of fair
    """

    SYMBOL = None  # override in subclass

    def __init__(self, state, prints, new_trader_data):
        if self.SYMBOL is None:
            raise ValueError(f"{type(self).__name__} must set SYMBOL")
        self.pt = ProductTrader(self.SYMBOL, state, prints, new_trader_data)

    def _fair_value(self):
        pt = self.pt
        if not pt.mkt_buy_orders or not pt.mkt_sell_orders:
            return None
        wall_bid = max(pt.mkt_buy_orders, key=pt.mkt_buy_orders.get)
        wall_ask = max(pt.mkt_sell_orders, key=pt.mkt_sell_orders.get)
        return int((wall_bid + wall_ask) / 2)

    def get_orders(self):
        pt = self.pt
        fair = self._fair_value()
        if fair is None or pt.best_bid is None or pt.best_ask is None:
            return {pt.name: pt.orders}

        limit = pt.position_limit
        cur_pos = pt.initial_position

        # # Taking
        # for price, qty in pt.mkt_buy_orders.items():
        #     if int(price) > fair:
        #         sell_qty = min(qty, limit + cur_pos)
        #         if sell_qty > 0:
        #             pt.ask(price, sell_qty)
        #             cur_pos -= sell_qty

        # for price, qty in pt.mkt_sell_orders.items():
        #     if int(price) < fair:
        #         buy_qty = min(qty, limit - cur_pos)
        #         if buy_qty > 0:
        #             pt.bid(price, buy_qty)
        #             cur_pos += buy_qty

        # # Flattening at fair value
        # if cur_pos > 0 and fair in pt.mkt_buy_orders:
        #     sell_qty = min(pt.mkt_buy_orders[fair], cur_pos)
        #     if sell_qty > 0:
        #         pt.ask(fair, sell_qty)
        #         cur_pos -= sell_qty
        # if cur_pos < 0 and fair in pt.mkt_sell_orders:
        #     buy_qty = min(pt.mkt_sell_orders[fair], -cur_pos)
        #     if buy_qty > 0:
        #         pt.bid(fair, buy_qty)
        #         cur_pos += buy_qty

        # Making one tick inside top-of-book
        my_bid = pt.best_bid + 1
        my_ask = pt.best_ask - 1

        if my_bid < fair:
            remaining_buy = limit - cur_pos
            if remaining_buy > 0:
                pt.bid(my_bid, remaining_buy)
        if my_ask > fair:
            remaining_sell = limit + cur_pos
            if remaining_sell > 0:
                pt.ask(my_ask, remaining_sell)

        return {pt.name: pt.orders}


class MicrochipCircleMM(MarketMakingTrader):
    SYMBOL = "MICROCHIP_CIRCLE"


class Trader:

    def run(self, state: TradingState):
        result:dict[str,list[Order]] = {}
        new_trader_data = {}
        prints = {
            "GENERAL": {
                "TIMESTAMP": state.timestamp,
                "POSITIONS": state.position
            },
        }

        def export(prints):
            try: print(json.dumps(prints))
            except: pass


        product_traders = {
            # SNACKPACK_PSR_SYMBOLS[0]: PSRTrader,
            # SNACKPACK_VC_SYMBOLS[0]: VCTrader,
            # PEBBLES_SYMBOLS[0]: PebblesTrader,
            # TRANSLATOR_SYMBOLS[0]: TranslatorTrader,
            MicrochipCircleMM.SYMBOL: MicrochipCircleMM
        }

        result, conversions = {}, 0
        for symbol, product_trader in product_traders.items():
            if symbol in state.order_depths:

                try:
                    trader = product_trader(state, prints, new_trader_data)
                    result.update(trader.get_orders())
                except: pass


        try: final_trader_data = json.dumps(new_trader_data)
        except: final_trader_data = ''


        export(prints)
        return result, conversions, final_trader_data