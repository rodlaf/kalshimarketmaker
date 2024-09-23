import abc
import argparse
import time
from typing import Dict, List, Tuple, Optional
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
    def place_order(self, action: str, side: str, price: float, quantity: int, expiration_ts: int = None) -> str:
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
        base_url: str,
        logger: logging.Logger,
    ):
        self.email = email
        self.password = password
        self.market_ticker = market_ticker
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
        return total_position

    def get_price(self) -> Dict[str, float]:
        self.logger.info("Retrieving market data...")
        path = f"/markets/{self.market_ticker}"
        data = self.make_request("GET", path)

        yes_bid = float(data["market"]["yes_bid"]) / 100
        yes_ask = float(data["market"]["yes_ask"]) / 100
        no_bid = float(data["market"]["no_bid"]) / 100
        no_ask = float(data["market"]["no_ask"]) / 100
        
        yes_mid_price = round((yes_bid + yes_ask) / 2, 2)
        no_mid_price = round((no_bid + no_ask) / 2, 2)

        self.logger.info(f"Current yes mid-market price: ${yes_mid_price:.2f}")
        self.logger.info(f"Current no mid-market price: ${no_mid_price:.2f}")
        return {"yes": yes_mid_price, "no": no_mid_price}

    def place_order(self, action: str, side: str, price: float, quantity: int, expiration_ts: int = None) -> str:
        self.logger.info(f"Placing {action} order for {side} side at price ${price:.2f} with quantity {quantity}...")
        path = "/portfolio/orders"
        data = {
            "ticker": self.market_ticker,
            "action": action.lower(),  # 'buy' or 'sell'
            "type": "limit",
            "side": side,  # 'yes' or 'no'
            "count": quantity,
            "client_order_id": str(uuid.uuid4()),
        }
        price_to_send = int(price * 100) # Convert dollars to cents

        if side == "yes":
            data["yes_price"] = price_to_send
        else:
            data["no_price"] = price_to_send

        if expiration_ts is not None:
            data["expiration_ts"] = expiration_ts

        try:
            response = self.make_request("POST", path, data=data)
            order_id = response["order"]["order_id"]
            self.logger.info(f"Placed {action} order for {side} side at price ${price:.2f} with quantity {quantity}, order ID: {order_id}")
            return str(order_id)
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to place order: {e}")
            if hasattr(e, 'response') and e.response is not None:
                self.logger.error(f"Response content: {e.response.text}")
                self.logger.error(f"Request data: {data}")
            raise

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
        self.logger.info(f"Retrieved {len(orders)} orders")
        return orders

class AvellanedaMarketMaker:
    def __init__(
        self,
        logger: logging.Logger,
        api: AbstractTradingAPI,
        gamma: float,
        k: float,
        sigma: float,
        T: float,
        max_position: int,
        order_expiration: int,
        min_spread: float = 0.01,
        position_limit_buffer: float = 0.1,
        inventory_skew_factor: float = 0.01,
        trade_side: str = "yes"
    ):
        self.api = api
        self.logger = logger
        self.base_gamma = gamma
        self.k = k
        self.sigma = sigma
        self.T = T
        self.max_position = max_position
        self.order_expiration = order_expiration
        self.min_spread = min_spread
        self.position_limit_buffer = position_limit_buffer
        self.inventory_skew_factor = inventory_skew_factor
        self.trade_side = trade_side

    def run(self, dt: float):
        start_time = time.time()
        while time.time() - start_time < self.T:
            current_time = time.time() - start_time
            self.logger.info(f"Running Avellaneda market maker at {current_time:.2f}")

            mid_prices = self.api.get_price()
            mid_price = mid_prices[self.trade_side]
            inventory = self.api.get_position()
            self.logger.info(f"Current mid price for {self.trade_side}: {mid_price:.4f}, Inventory: {inventory}")

            reservation_price = self.calculate_reservation_price(mid_price, inventory, current_time)
            bid_price, ask_price = self.calculate_asymmetric_quotes(mid_price, inventory, current_time)
            buy_size, sell_size = self.calculate_order_sizes(inventory)

            self.logger.info(f"Reservation price: {reservation_price:.4f}")
            self.logger.info(f"Computed desired bid: {bid_price:.4f}, ask: {ask_price:.4f}")

            self.manage_orders(bid_price, ask_price, buy_size, sell_size)

            time.sleep(dt)

        self.logger.info("Avellaneda market maker finished running")

    def calculate_asymmetric_quotes(self, mid_price: float, inventory: int, t: float) -> Tuple[float, float]:
        reservation_price = self.calculate_reservation_price(mid_price, inventory, t)
        base_spread = self.calculate_optimal_spread(t, inventory)
        
        position_ratio = inventory / self.max_position
        spread_adjustment = base_spread * abs(position_ratio) * 3
        
        if inventory > 0:
            bid_spread = base_spread / 2 + spread_adjustment
            ask_spread = max(base_spread / 2 - spread_adjustment, self.min_spread / 2)
        else:
            bid_spread = max(base_spread / 2 - spread_adjustment, self.min_spread / 2)
            ask_spread = base_spread / 2 + spread_adjustment
        
        bid_price = max(0, min(mid_price, reservation_price - bid_spread))
        ask_price = min(1, max(mid_price, reservation_price + ask_spread))
        
        return bid_price, ask_price

    def calculate_reservation_price(self, mid_price: float, inventory: int, t: float) -> float:
        dynamic_gamma = self.calculate_dynamic_gamma(inventory)
        inventory_skew = inventory * self.inventory_skew_factor * mid_price
        return mid_price + inventory_skew - inventory * dynamic_gamma * (self.sigma**2) * (1 - t/self.T)

    def calculate_optimal_spread(self, t: float, inventory: int) -> float:
        dynamic_gamma = self.calculate_dynamic_gamma(inventory)
        base_spread = (dynamic_gamma * (self.sigma**2) * (1 - t/self.T) + 
                       (2 / dynamic_gamma) * math.log(1 + (dynamic_gamma / self.k)))
        position_ratio = abs(inventory) / self.max_position
        spread_adjustment = 1 - (position_ratio ** 2)
        return max(base_spread * spread_adjustment * 0.01, self.min_spread)

    def calculate_dynamic_gamma(self, inventory: int) -> float:
        position_ratio = inventory / self.max_position
        return self.base_gamma * math.exp(-abs(position_ratio))

    def calculate_order_sizes(self, inventory: int) -> Tuple[int, int]:
        remaining_capacity = self.max_position - abs(inventory)
        buffer_size = int(self.max_position * self.position_limit_buffer)
        
        if inventory > 0:
            buy_size = max(1, min(buffer_size, remaining_capacity))
            sell_size = max(1, self.max_position)
        else:
            buy_size = max(1, self.max_position)
            sell_size = max(1, min(buffer_size, remaining_capacity))
        
        return buy_size, sell_size

    def manage_orders(self, bid_price: float, ask_price: float, buy_size: int, sell_size: int):
        current_orders = self.api.get_orders()
        self.logger.info(f"Retrieved {len(current_orders)} total orders")

        buy_order = None
        sell_order = None

        for order in current_orders:
            if order['side'] == self.trade_side:
                if order['action'] == 'buy':
                    buy_order = order
                elif order['action'] == 'sell':
                    sell_order = order

        self.logger.info(f"Current buy order: {buy_order}")
        self.logger.info(f"Current sell order: {sell_order}")

        # Handle buy order
        if buy_order:
            current_price = float(buy_order['yes_price']) / 100 if self.trade_side == 'yes' else float(buy_order['no_price']) / 100
            if abs(current_price - bid_price) >= 0.01 or buy_order['remaining_count'] != buy_size:
                self.logger.info(f"Cancelling buy order. ID: {buy_order['order_id']}, Old price: {current_price:.4f}, New price: {bid_price:.4f}")
                self.api.cancel_order(buy_order['order_id'])
                buy_order = None
            else:
                self.logger.info(f"Keeping existing buy order. ID: {buy_order['order_id']}, Price: {current_price:.4f}")
        
        if not buy_order and bid_price < self.api.get_price()[self.trade_side]:
            try:
                order_id = self.api.place_order('buy', self.trade_side, bid_price, buy_size, int(time.time()) + self.order_expiration)
                self.logger.info(f"Placed new buy order. ID: {order_id}, Price: {bid_price:.4f}, Size: {buy_size}")
            except Exception as e:
                self.logger.error(f"Failed to place buy order: {str(e)}")

        # Handle sell order
        if sell_order:
            current_price = float(sell_order['yes_price']) / 100 if self.trade_side == 'yes' else float(sell_order['no_price']) / 100
            if abs(current_price - ask_price) >= 0.01 or sell_order['remaining_count'] != sell_size:
                self.logger.info(f"Cancelling sell order. ID: {sell_order['order_id']}, Old price: {current_price:.4f}, New price: {ask_price:.4f}")
                self.api.cancel_order(sell_order['order_id'])
                sell_order = None
            else:
                self.logger.info(f"Keeping existing sell order. ID: {sell_order['order_id']}, Price: {current_price:.4f}")
        
        if not sell_order and ask_price > self.api.get_price()[self.trade_side]:
            try:
                order_id = self.api.place_order('sell', self.trade_side, ask_price, sell_size, int(time.time()) + self.order_expiration)
                self.logger.info(f"Placed new sell order. ID: {order_id}, Price: {ask_price:.4f}, Size: {sell_size}")
            except Exception as e:
                self.logger.error(f"Failed to place sell order: {str(e)}")
                
def load_config(config_file, config_name):
    with open(config_file, 'r') as f:
        configs = yaml.safe_load(f)
    return configs.get(config_name, {})

def create_api(api_config, logger):
    return KalshiTradingAPI(
        email=os.getenv("KALSHI_EMAIL"),
        password=os.getenv("KALSHI_PASSWORD"),
        market_ticker=api_config['market_ticker'],
        base_url=os.getenv("KALSHI_BASE_URL"),
        logger=logger,
    )

def create_market_maker(mm_config, api, logger):
    return AvellanedaMarketMaker(
        logger=logger,
        api=api,
        gamma=mm_config.get('gamma', 0.1),
        k=mm_config.get('k', 1.5),
        sigma=mm_config.get('sigma', 0.5),
        T=mm_config.get('T', 3600),
        max_position=mm_config.get('max_position', 100),
        order_expiration=mm_config.get('order_expiration', 300),
        min_spread=mm_config.get('min_spread', 0.01),
        position_limit_buffer=mm_config.get('position_limit_buffer', 0.1),
        inventory_skew_factor=mm_config.get('inventory_skew_factor', 0.01),
        trade_side=mm_config.get('trade_side', 'yes')
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kalshi Market Making Algorithm")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config file")
    parser.add_argument("--config-name", type=str, required=True, help="Name of the configuration to use")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Logging level")
    parser.add_argument("--trade-side", type=str, choices=["yes", "no"], default="yes", help="Trade side (yes or no)")
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config, args.config_name)

    # Setup logging
    logging.basicConfig(level=args.log_level or config.get('log_level', 'INFO'))
    logger = logging.getLogger(__name__)

    # Load environment variables
    load_dotenv()

    # Create API
    api = create_api(config['api'], logger)

    # Update trade_side in config
    config['market_maker']['trade_side'] = args.trade_side

    # Create market maker
    market_maker = create_market_maker(config['market_maker'], api, logger)

    try:
        # Run market maker
        market_maker.run(config.get('dt', 1.0))
    except KeyboardInterrupt:
        logger.info("Market maker stopped by user")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
    finally:
        # Ensure logout happens even if an exception occurs
        api.logout()