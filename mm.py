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


class AbstractTradingAPI(abc.ABC):
    @abc.abstractmethod
    def get_price(self) -> float:
        pass

    @abc.abstractmethod
    def place_order(self, side: str, price: float, quantity: int, expiration_ts: int = None) -> int:
        pass

    @abc.abstractmethod
    def cancel_order(self, order_id: int) -> bool:
        pass

    @abc.abstractmethod
    def get_position(self) -> int:
        pass

    @abc.abstractmethod
    def get_orders(self) -> List[Dict]:
        pass


class KalshiTradingAPI:
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

    def place_order(self, side: str, price: float, quantity: int, expiration_ts: int = None) -> int:
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
        return order_id

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


class MarketMaker:
    def __init__(
        self,
        logger: logging.Logger,
        api: KalshiTradingAPI,
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple Market Making Algorithm")
    parser.add_argument(
        "--dt", type=float, default=1.0, help="Trading frequency in seconds"
    )
    parser.add_argument(
        "--market-ticker", type=str, required=True, help="Market ticker"
    )
    parser.add_argument(
        "--trade-side",
        type=str,
        choices=["yes", "no"],
        required=True,
        help="Side to trade (yes or no)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level",
    )
    parser.add_argument(
        "--spread",
        type=float,
        default=0.01,
        help="Spread for market making (in dollars)",
    )
    parser.add_argument(
        "--max-position",
        type=int,
        default=10,
        help="Maximum position size (absolute value)",
    )
    parser.add_argument(
        "--order-expiration",
        type=int,
        default=60,
        help="Order expiration time in seconds (default: 60)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level)
    logger = logging.getLogger(__name__)

    # Load environment variables from .env file
    load_dotenv()

    # Kalshi API configuration
    BASE_URL = os.getenv("KALSHI_BASE_URL")
    EMAIL = os.getenv("KALSHI_EMAIL")
    PASSWORD = os.getenv("KALSHI_PASSWORD")

    api = KalshiTradingAPI(
        email=EMAIL,
        password=PASSWORD,
        market_ticker=args.market_ticker,
        trade_side=args.trade_side,
        base_url=BASE_URL,
        logger=logger,
    )

    market_maker = MarketMaker(
        logger=logger,
        api=api,
        spread=args.spread,
        max_position=args.max_position,
        order_expiration=args.order_expiration
    )
    market_maker.run(args.dt)