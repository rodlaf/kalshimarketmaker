import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from mm import SimulatedKalshiTradingApi, SimpleMarketMaker, AvellanedaMarketMaker, KalshiTradingAPI, load_config, create_api, create_market_maker

# Utility function for creating a mock logger
def create_mock_logger():
    return Mock(debug=Mock(), info=Mock(), warning=Mock(), error=Mock(), critical=Mock())

# Tests for KalshiTradingAPI
class TestKalshiTradingAPI:
    @pytest.fixture
    def mock_requests(self):
        with patch('mm.requests') as mock_requests:
            yield mock_requests

    @pytest.fixture
    def api(self, mock_requests):
        mock_response = MagicMock()
        mock_response.json.return_value = {"token": "test_token", "member_id": "test_member_id"}
        mock_requests.post.return_value = mock_response
        
        return KalshiTradingAPI(
            email="test@example.com",
            password="test_password",
            market_ticker="TEST-MKT",
            trade_side="yes",
            base_url="https://test-api.kalshi.com",
            logger=create_mock_logger()
        )

    def test_login(self, api, mock_requests):
        api.login()
        mock_requests.post.assert_called_once_with(
            "https://test-api.kalshi.com/login",
            json={"email": "test@example.com", "password": "test_password"}
        )
        assert api.token == "test_token"
        assert api.member_id == "test_member_id"

    def test_logout(self, api, mock_requests):
        api.logout()
        mock_requests.post.assert_called_with(
            "https://test-api.kalshi.com/logout",
            headers=api.get_headers()
        )
        assert api.token is None
        assert api.member_id is None

    def test_get_position(self, api, mock_requests):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "market_positions": [{"ticker": "TEST-MKT", "position": 10}]
        }
        mock_requests.request.return_value = mock_response

        position = api.get_position()
        assert position == 10

    def test_get_price(self, api, mock_requests):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "market": {"yes_bid": 4500, "yes_ask": 5500}
        }
        mock_requests.request.return_value = mock_response

        price = api.get_price()
        assert price == 0.5  # (0.45 + 0.55) / 2

    def test_place_order(self, api, mock_requests):
        mock_response = MagicMock()
        mock_response.json.return_value = {"order": {"order_id": "test_order_id"}}
        mock_requests.request.return_value = mock_response

        order_id = api.place_order("buy", 0.5, 10)
        assert order_id == "test_order_id"

    def test_cancel_order(self, api, mock_requests):
        mock_response = MagicMock()
        mock_response.json.return_value = {"reduced_by": 1}
        mock_requests.request.return_value = mock_response

        result = api.cancel_order("test_order_id")
        assert result == True

    def test_get_orders(self, api, mock_requests):
        mock_response = MagicMock()
        mock_response.json.return_value = {"orders": [{"order_id": "test_order_1"}, {"order_id": "test_order_2"}]}
        mock_requests.request.return_value = mock_response

        orders = api.get_orders()
        assert len(orders) == 2
        assert orders[0]["order_id"] == "test_order_1"
        assert orders[1]["order_id"] == "test_order_2"

# Tests for SimulatedKalshiTradingApi
class TestSimulatedKalshiTradingApi:
    @pytest.fixture
    def api(self):
        return SimulatedKalshiTradingApi(initial_price=0.5, volatility=0.01, logger=create_mock_logger())

    def test_get_price(self, api):
        price = api.get_price()
        assert 0 <= price <= 1

    def test_place_order(self, api):
        order_id = api.place_order("BUY", 0.5, 10)
        assert isinstance(order_id, str)
        assert len(api.orders) == 1

    def test_cancel_order(self, api):
        order_id = api.place_order("SELL", 0.6, 5)
        assert api.cancel_order(order_id) == True
        assert len(api.orders) == 0

    def test_get_position(self, api):
        api.position = 100
        assert api.get_position() == 100

    def test_get_orders(self, api):
        api.place_order("BUY", 0.5, 10)
        api.place_order("SELL", 0.6, 5)
        orders = api.get_orders()
        assert len(orders) == 2

# Tests for SimpleMarketMaker
class TestSimpleMarketMaker:
    @pytest.fixture
    def mock_api(self):
        return Mock(get_price=Mock(return_value=0.5),
                    get_position=Mock(return_value=0),
                    get_orders=Mock(return_value=[]),
                    place_order=Mock(return_value="order_id"),
                    cancel_order=Mock(return_value=True))

    @pytest.fixture
    def market_maker(self, mock_api):
        return SimpleMarketMaker(logger=create_mock_logger(), api=mock_api, spread=0.01, max_position=100, order_expiration=60)

    def test_run(self, market_maker):
        with patch('time.sleep', return_value=None):
            market_maker.run(dt=0.1)
            assert market_maker.api.get_price.called
            assert market_maker.api.get_position.called
            assert market_maker.api.get_orders.called
            assert market_maker.api.place_order.call_count == 2  # One for buy, one for sell

# Tests for AvellanedaMarketMaker
class TestAvellanedaMarketMaker:
    @pytest.fixture
    def mock_api(self):
        return Mock(get_price=Mock(return_value=0.5),
                    get_position=Mock(return_value=0),
                    place_order=Mock(return_value="order_id"),
                    cancel_order=Mock(return_value=True))

    @pytest.fixture
    def market_maker(self, mock_api):
        return AvellanedaMarketMaker(logger=create_mock_logger(), api=mock_api, gamma=0.1, k=1.5, sigma=0.1, T=3600, max_position=100, order_expiration=60)

    def test_calculate_dynamic_gamma(self, market_maker):
        assert market_maker.calculate_dynamic_gamma(0) == market_maker.base_gamma
        assert market_maker.calculate_dynamic_gamma(50) < market_maker.base_gamma
        assert market_maker.calculate_dynamic_gamma(-50) < market_maker.base_gamma

    def test_calculate_reservation_price(self, market_maker):
        reservation_price = market_maker.calculate_reservation_price(0.5, 10, 1800)
        assert isinstance(reservation_price, float)

    def test_calculate_optimal_spread(self, market_maker):
        spread = market_maker.calculate_optimal_spread(1800, 10)
        assert isinstance(spread, float)
        assert spread >= market_maker.min_spread

    def test_calculate_asymmetric_quotes(self, market_maker):
        bid_price, ask_price = market_maker.calculate_asymmetric_quotes(0.5, 10, 1800)
        assert 0 <= bid_price < ask_price <= 1

    def test_calculate_order_sizes(self, market_maker):
        buy_size, sell_size = market_maker.calculate_order_sizes(10)
        assert isinstance(buy_size, int)
        assert isinstance(sell_size, int)
        assert buy_size > 0
        assert sell_size > 0

    def test_run(self, market_maker):
        with patch('time.sleep', return_value=None), \
             patch('time.time', side_effect=[0, 1, 2, 3600]):
            market_maker.run(dt=0.1)
            assert market_maker.api.get_price.called
            assert market_maker.api.get_position.called
            assert market_maker.api.place_order.called

# Tests for utility functions
def test_load_config():
    with patch('builtins.open', create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = """
        config1:
            api:
                type: simulated
            market_maker:
                type: simple
        """
        config = load_config('dummy_path', 'config1')
        assert config['api']['type'] == 'simulated'
        assert config['market_maker']['type'] == 'simple'

def test_create_api():
    logger = create_mock_logger()
    
    with patch('os.getenv', return_value='dummy'):
        api_config = {'type': 'real', 'market_ticker': 'DUMMY', 'trade_side': 'yes'}
        api = create_api(api_config, logger)
        assert isinstance(api, KalshiTradingAPI)

    api_config = {'type': 'simulated'}
    api = create_api(api_config, logger)
    assert isinstance(api, SimulatedKalshiTradingApi)

    with pytest.raises(ValueError):
        create_api({'type': 'unknown'}, logger)

def test_create_market_maker():
    logger = create_mock_logger()
    mock_api = Mock()

    mm_config = {'type': 'avellaneda', 'max_position': 100, 'order_expiration': 60}
    mm = create_market_maker(mm_config, mock_api, logger)
    assert isinstance(mm, AvellanedaMarketMaker)

    mm_config = {'type': 'simple', 'spread': 0.01, 'max_position': 100, 'order_expiration': 60}
    mm = create_market_maker(mm_config, mock_api, logger)
    assert isinstance(mm, SimpleMarketMaker)

    with pytest.raises(ValueError):
        create_market_maker({'type': 'unknown'}, mock_api, logger)

if __name__ == "__main__":
    pytest.main()