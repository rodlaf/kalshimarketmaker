import abc
import argparse
import time
from typing import Dict, List
import requests
from datetime import datetime
import logging
from dotenv import load_dotenv
import os
import uuid
import math
import random
import yaml


class AbstractTradingAPI(abc.ABC):
    @abc.abstractmethod
    def get_price(self) -> float:
        pass

    @abc.abstractmethod
    def place_order(self, side: str, price: float, quantity: int, expiration_ts: int = None) -> str:
        pass

    @abc.abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass

    @abc.abstractmethod
    def get_position(self) -> int:
        pass

    @abc.abstractmethod
    def get_orders(self) -> List[Dict]:
        pass

class KalshiTradingAPI(AbstractTradingAPI):
    def __init__(
        self,
        email: str,
        password: str,
        market_ticker: str,
        trade_side: str,
        base_url: str,
        logger: logging.Logger,
    ):
        self.email = email
        self.password = password
        self.market_ticker = market_ticker
        self.trade_side = trade_side  # 'yes' or 'no'
        self.token = None
        self.member_id = None
        self.logger = logger
        self.base_url = base_url
        self.login()

    def login(self):
        url = f"{self.base_url}/login"
        data = {"email": self.email, "password": self.password}
        response = requests.post(url, json=data)
        response.raise_for_status()
        result = response.json()
        self.token = result["token"]
        self.member_id = result.get("member_id")
        self.logger.info("Successfully logged in")

    def logout(self):
        if self.token:
            url = f"{self.base_url}/logout"
            headers = self.get_headers()
            response = requests.post(url, headers=headers)
            response.raise_for_status()
            self.token = None
            self.member_id = None
            self.logger.info("Successfully logged out")

    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def make_request(
        self, method: str, path: str, params: Dict = None, data: Dict = None
    ):
        url = f"{self.base_url}{path}"
        headers = self.get_headers()

        try:
            response = requests.request(
                method, url, headers=headers, params=params, json=data
            )
            self.logger.debug(f"Request URL: {response.url}")
            self.logger.debug(f"Request headers: {response.request.headers}")
            self.logger.debug(f"Request params: {params}")
            self.logger.debug(f"Request data: {data}")
            self.logger.debug(f"Response status code: {response.status_code}")
            self.logger.debug(f"Response content: {response.text}")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            if hasattr(e, "response") and e.response is not None:
                self.logger.error(f"Response content: {e.response.text}")
            raise

    def get_position(self) -> int:
        self.logger.info("Retrieving position...")
        path = "/portfolio/positions"
        params = {"ticker": self.market_ticker, "settlement_status": "unsettled"}
        response = self.make_request("GET", path, params=params)
        positions = response.get("market_positions", [])

        total_position = 0
        for position in positions:
            if position["ticker"] == self.market_ticker:
                total_position += position["position"]

        self.logger.info(f"Current position: {total_position}")
        return total_position if self.trade_side == "yes" else -total_position

    def get_price(self) -> float:
        self.logger.info("Retrieving market data...")
        path = f"/markets/{self.market_ticker}"
        data = self.make_request("GET", path)

        if self.trade_side == "yes":
            bid = float(data["market"]["yes_bid"]) / 100
            ask = float(data["market"]["yes_ask"]) / 100
        else:  # "no" side
            bid = float(data["market"]["no_bid"]) / 100
            ask = float(data["market"]["no_ask"]) / 100
        
        mid_price = round((bid + ask) / 2, 2)

        self.logger.info(f"Current {self.trade_side} mid-market price: ${mid_price:.2f}")
        return mid_price

    def place_order(self, side: str, price: float, quantity: int, expiration_ts: int = None) -> str:
        self.logger.info(
            f"Placing {side} order at price ${price:.2f} with quantity {quantity}..."
        )
        path = "/portfolio/orders"
        data = {
            "ticker": self.market_ticker,
            "action": side.lower(),  # 'buy' or 'sell'
            "type": "limit",
            "side": self.trade_side,
            "count": quantity,
            "client_order_id": str(uuid.uuid4()),
            f"{self.trade_side}_price": int(price * 100),  # Convert dollars to cents
        }

        if expiration_ts is not None:
            data["expiration_ts"] = expiration_ts

        response = self.make_request("POST", path, data=data)
        order_id = response["order"]["order_id"]
        self.logger.info(
            f"Placed {side} order at price ${price:.2f} with quantity {quantity}, order ID: {order_id}"
        )
        return str(order_id)

    def cancel_order(self, order_id: int) -> bool:
        self.logger.info(f"Canceling order with ID {order_id}...")
        path = f"/portfolio/orders/{order_id}"
        response = self.make_request("DELETE", path)
        success = response["reduced_by"] > 0
        self.logger.info(f"Canceled order with ID {order_id}, success: {success}")
        return success

    def get_orders(self) -> List[Dict]:
        self.logger.info("Retrieving orders...")
        path = "/portfolio/orders"
        params = {"ticker": self.market_ticker, "status": "resting"}
        response = self.make_request("GET", path, params=params)
        orders = response.get("orders", [])
        self.logger.info(
            f"Retrieved orders {[order['order_id'] for order in orders]}"
        )
        return orders

    def __del__(self):
        self.logout()

class SimulatedKalshiTradingApi(AbstractTradingAPI):
    def __init__(self, initial_price: float = 0.5, volatility: float = 0.0001, logger: logging.Logger = None):
        self.current_price = initial_price
        self.volatility = volatility
        self.position = 0
        self.orders = {}
        self.order_book = {'bids': {}, 'asks': {}}
        self.last_update = time.time()
        self.logger = logger or logging.getLogger(__name__)

    def _update_price(self):
        current_time = time.time()
        dt = current_time - self.last_update
        self.last_update = current_time
        
        # Brownian motion price update
        price_change = random.gauss(0, self.volatility * (dt ** 0.5))
        self.current_price = max(0, min(1, self.current_price + price_change))
        self.logger.debug(f"Updated price to {self.current_price:.4f}")

    def _execute_orders(self):
        best_bid = max(self.order_book['bids'].keys()) if self.order_book['bids'] else 0
        best_ask = min(self.order_book['asks'].keys()) if self.order_book['asks'] else 1

        if best_bid >= best_ask:
            execution_price = (best_bid + best_ask) / 2
            bid_order = self.order_book['bids'][best_bid].pop(0)
            ask_order = self.order_book['asks'][best_ask].pop(0)

            self.position += bid_order['quantity']
            self.position -= ask_order['quantity']

            del self.orders[bid_order['order_id']]
            del self.orders[ask_order['order_id']]

            if not self.order_book['bids'][best_bid]:
                del self.order_book['bids'][best_bid]
            if not self.order_book['asks'][best_ask]:
                del self.order_book['asks'][best_ask]

            self.logger.info(f"Executed orders at price {execution_price:.4f}")

    def get_price(self) -> float:
        self._update_price()
        self._execute_orders()
        self.logger.info(f"Current price: {self.current_price:.4f}")
        return self.current_price

    def place_order(self, side: str, price: float, quantity: int, expiration_ts: int = None) -> str:
        order_id = str(uuid.uuid4())
        order = {
            'order_id': order_id,
            'side': side,
            'price': price,
            'quantity': quantity,
            'expiration_ts': expiration_ts
        }
        self.orders[order_id] = order

        book_side = 'bids' if side == 'BUY' else 'asks'
        if price not in self.order_book[book_side]:
            self.order_book[book_side][price] = []
        self.order_book[book_side][price].append(order)

        self.logger.info(f"Placed {side} order: ID {order_id}, Price {price:.4f}, Quantity {quantity}")
        return order_id

    def cancel_order(self, order_id: str) -> bool:
        if order_id not in self.orders:
            self.logger.warning(f"Attempted to cancel non-existent order: {order_id}")
            return False

        order = self.orders[order_id]
        book_side = 'bids' if order['side'] == 'BUY' else 'asks'
        self.order_book[book_side][order['price']].remove(order)
        if not self.order_book[book_side][order['price']]:
            del self.order_book[book_side][order['price']]
        del self.orders[order_id]

        self.logger.info(f"Canceled order: {order_id}")
        return True

    def get_position(self) -> int:
        self.logger.info(f"Current position: {self.position}")
        return self.position

    def get_orders(self) -> List[Dict]:
        current_time = time.time()
        active_orders = [
            order for order in self.orders.values()
            if order['expiration_ts'] is None or order['expiration_ts'] > current_time
        ]
        self.logger.info(f"Retrieved {len(active_orders)} active orders")
        return active_orders

class SimpleMarketMaker:
    def __init__(
        self,
        logger: logging.Logger,
        api: AbstractTradingAPI,  # Change to AbstractTradingAPI
        spread: float = 0.01,
        max_position: int = 100,
        order_expiration: int = 60,
    ):
        self.api = api
        self.spread = spread
        self.max_position = max_position
        self.current_orders = []
        self.logger = logger
        self.order_expiration = order_expiration

    def run(self, dt: float):
        while True:
            self.logger.info(f"Running market maker at {datetime.now()}...")

            market_price = self.api.get_price()
            position = self.api.get_position()
            self.current_orders = [order["order_id"] for order in self.api.get_orders()]

            # Cancel existing orders
            for order_id in self.current_orders:
                self.api.cancel_order(order_id)
            self.current_orders.clear()

            # Calculate new bid and ask prices
            mid_price = market_price
            if position > 0:
                mid_price -= 0.001 * position
            elif position < 0:
                mid_price += 0.001 * abs(position)

            bid_price = mid_price - self.spread / 2
            ask_price = mid_price + self.spread / 2

            # Place new orders, only if they do not exceed bounds and are within valid price range
            if abs(position) < self.max_position:
                expiration_ts = int(time.time()) + self.order_expiration
                if 0 < bid_price < 1:
                    bid_id = self.api.place_order("BUY", bid_price, 1, expiration_ts)
                    self.current_orders.append(bid_id)
                else:
                    self.logger.info(f"Skipping BUY order: Price ${bid_price:.2f} is out of valid range (0, 1)")

                if 0 < ask_price < 1:
                    ask_id = self.api.place_order("SELL", ask_price, 1, expiration_ts)
                    self.current_orders.append(ask_id)
                else:
                    self.logger.info(f"Skipping SELL order: Price ${ask_price:.2f} is out of valid range (0, 1)")

            time.sleep(dt)

class AvellanedaMarketMaker:
    def __init__(
        self,
        logger: logging.Logger,
        api: AbstractTradingAPI,
        gamma: float = 0.0001,
        k: float = 1.5,
        sigma: float = 0.00001,
        T: float = 3600,  # Time horizon in seconds (e.g., 1 hour)
        max_position: int = 100,
        order_expiration: int = 60,
    ):
        self.api = api
        self.logger = logger
        self.gamma = gamma
        self.k = k
        self.sigma = sigma
        self.T = T
        self.max_position = max_position
        self.current_orders = []
        self.order_expiration = order_expiration

    def calculate_reservation_price(self, mid_price: float, inventory: int, t: float) -> float:
        normalized_t = t / self.T  # Normalize time to [0, 1]
        reservation_price = mid_price - inventory * self.gamma * (self.sigma**2) * (1 - normalized_t)
        self.logger.info(f"Calculated reservation price: {reservation_price:.4f}")
        return reservation_price

    def calculate_optimal_spread(self, t: float) -> float:
        normalized_t = t / self.T  # Normalize time to [0, 1]
        spread = (self.gamma * (self.sigma**2) * (1 - normalized_t) + 
                  (2 / self.gamma) * math.log(1 + (self.gamma / self.k)))
        scaled_spread = spread * 0.01  # Scale to penny level
        self.logger.info(f"Calculated optimal spread: {scaled_spread:.4f}")
        return scaled_spread

    def calculate_optimal_quotes(self, mid_price: float, inventory: int, t: float) -> tuple:
        reservation_price = self.calculate_reservation_price(mid_price, inventory, t)
        spread = self.calculate_optimal_spread(t)
        
        bid_price = max(0, min(mid_price, reservation_price - spread / 2))
        ask_price = min(1, max(mid_price, reservation_price + spread / 2))
        
        self.logger.info(f"Optimal quotes - Bid: {bid_price:.4f}, Ask: {ask_price:.4f}")
        return bid_price, ask_price

    def run(self, dt: float):
        start_time = time.time()
        while time.time() - start_time < self.T:
            current_time = time.time() - start_time
            self.logger.info(f"Running Avellaneda market maker at {current_time:.2f}")

            mid_price = self.api.get_price()
            inventory = self.api.get_position()
            self.logger.info(f"Current mid price: {mid_price:.4f}, Inventory: {inventory}")
            self.current_orders = [order["order_id"] for order in self.api.get_orders()]

            # Cancel existing orders
            for order_id in self.current_orders:
                self.api.cancel_order(order_id)
            self.current_orders.clear()

            # Calculate new bid and ask prices
            bid_price, ask_price = self.calculate_optimal_quotes(mid_price, inventory, current_time)

            # Place new orders, only if they do not exceed bounds and are within valid price range
            if abs(inventory) < self.max_position:
                expiration_ts = int(time.time()) + self.order_expiration
                if 0 < bid_price < mid_price:
                    bid_id = self.api.place_order("BUY", bid_price, 1, expiration_ts)
                    self.current_orders.append(bid_id)
                else:
                    self.logger.info(f"Skipping BUY order: Price {bid_price:.4f} is out of valid range (0, {mid_price:.4f})")

                if mid_price < ask_price < 1:
                    ask_id = self.api.place_order("SELL", ask_price, 1, expiration_ts)
                    self.current_orders.append(ask_id)
                else:
                    self.logger.info(f"Skipping SELL order: Price {ask_price:.4f} is out of valid range ({mid_price:.4f}, 1)")

            time.sleep(dt)

        self.logger.info("Avellaneda market maker finished running")


def load_config(config_file, config_name):
    with open(config_file, 'r') as f:
        configs = yaml.safe_load(f)
    return configs.get(config_name, {})

def create_api(api_config, logger):
    if api_config['type'] == 'real':
        return KalshiTradingAPI(
            email=os.getenv("KALSHI_EMAIL"),
            password=os.getenv("KALSHI_PASSWORD"),
            market_ticker=api_config['market_ticker'],
            trade_side=api_config['trade_side'],
            base_url=os.getenv("KALSHI_BASE_URL"),
            logger=logger,
        )
    elif api_config['type'] == 'simulated':
        return SimulatedKalshiTradingApi(
            initial_price=api_config.get('initial_price', 0.5),
            volatility=api_config.get('volatility', 0.00001),
            logger=logger,
        )
    else:
        raise ValueError(f"Unknown API type: {api_config['type']}")

def create_market_maker(mm_config, api, logger):
    if mm_config['type'] == 'simple':
        return SimpleMarketMaker(
            logger=logger,
            api=api,
            spread=mm_config.get('spread'),
            max_position=mm_config.get('max_position'),
            order_expiration=mm_config.get('order_expiration'),
        )
    elif mm_config['type'] == 'avellaneda':
        return AvellanedaMarketMaker(
            logger=logger,
            api=api,
            gamma=mm_config.get('gamma', 0.7),
            k=mm_config.get('k', 1.5),
            sigma=mm_config.get('sigma', 0.00001),
            T=mm_config.get('T', 3600),
            max_position=mm_config.get('max_position'),
            order_expiration=mm_config.get('order_expiration'),
        )
    else:
        raise ValueError(f"Unknown market maker type: {mm_config['type']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Market Making Algorithm")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config file")
    parser.add_argument("--config-name", type=str, required=True, help="Name of the configuration to use")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Logging level")
    args, unknown = parser.parse_known_args()

    # Load configuration
    config = load_config(args.config, args.config_name)

    # Setup logging
    logging.basicConfig(level=args.log_level or config.get('log_level', 'INFO'))
    logger = logging.getLogger(__name__)

    # Load environment variables
    load_dotenv()

    # Create API
    api = create_api(config['api'], logger)

    # Create market maker
    market_maker = create_market_maker(config['market_maker'], api, logger)

    # Run market maker
    market_maker.run(config.get('dt', 1.0))