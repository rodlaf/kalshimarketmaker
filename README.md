# Market Making System

## Overview

This project implements a flexible market making system that can operate with both real and simulated trading APIs. It supports two market making strategies: a simple strategy and an Avellaneda-Stoikov strategy. The system is designed to be easily configurable and can be run with different parameters without modifying the main script.

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/market-making-system.git
   cd market-making-system
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Configuration

The system uses a YAML configuration file (`config.yaml`) to manage different setups. The file contains configurations for both real and simulated trading scenarios, as well as for both simple and Avellaneda market making strategies.

### YAML Configuration File Structure

```yaml
config_name:
  api:
    type: [real|simulated]
    # API-specific parameters
  market_maker:
    type: [simple|avellaneda]
    # Market maker-specific parameters
  log_level: [DEBUG|INFO|WARNING|ERROR|CRITICAL]
  dt: float  # Trading frequency in seconds
```

### API Configuration

#### Real API
- `type: real`
- `market_ticker`: The market ticker to trade
- `trade_side`: The side to trade (yes or no)

#### Simulated API
- `type: simulated`
- `initial_price`: Initial price for the simulation
- `volatility`: Volatility parameter for price simulation

### Market Maker Configuration

#### Simple Market Maker
- `type: simple`
- `spread`: Spread for market making (in dollars)
- `max_position`: Maximum position size (absolute value)
- `order_expiration`: Order expiration time in seconds

#### Avellaneda Market Maker
- `type: avellaneda`
- `max_position`: Maximum position size (absolute value)
- `order_expiration`: Order expiration time in seconds
- `gamma`: Risk aversion parameter
- `k`: Order arrival intensity parameter
- `sigma`: Volatility parameter
- `T`: Time horizon in seconds

## Usage

To run the market making system, use the following command:

```
python mm.py --config-name <configuration_name> [--log-level <log_level>]
```

- `<configuration_name>`: The name of the configuration in the YAML file you want to use.
- `<log_level>`: (Optional) Override the log level specified in the configuration file.

### Examples

1. Run with the real API and simple market maker:
   ```
   python mm.py --config-name real_simple
   ```

2. Run with the simulated API and Avellaneda market maker:
   ```
   python mm.py --config-name simulated_avellaneda
   ```

3. Run with a specific configuration and override the log level:
   ```
   python mm.py --config-name real_avellaneda --log-level DEBUG
   ```

## Components

### Main Script (mm.py)

This is the entry point of the system. It parses command-line arguments, loads the configuration, sets up logging, creates the appropriate API and market maker instances, and runs the market making strategy.

### Configuration Loader

The `load_config` function in the main script loads the YAML configuration file and returns the specified configuration.

### API Factory

The `create_api` function creates either a real or simulated API instance based on the configuration.

### Market Maker Factory

The `create_market_maker` function creates either a simple or Avellaneda market maker instance based on the configuration.

### Trading APIs

#### KalshiTradingAPI

This class implements the interface for trading on the real Kalshi platform. It handles authentication, order placement, and market data retrieval.

#### SimulatedKalshiTradingApi

This class provides a simulated trading environment for testing strategies. It simulates price movements and order execution.

### Market Making Strategies

#### SimpleMarketMaker

This class implements a basic market making strategy that sets bid and ask prices around a mid-price, adjusting for the current inventory position.

#### AvellanedaMarketMaker

This class implements the Avellaneda-Stoikov market making model, which calculates optimal bid and ask quotes based on the current inventory, time horizon, and market parameters.

## Environment Variables

The system uses the following environment variables for the real Kalshi API:

- `KALSHI_BASE_URL`: The base URL for the Kalshi API
- `KALSHI_EMAIL`: Your Kalshi account email
- `KALSHI_PASSWORD`: Your Kalshi account password

These should be set in a `.env` file in the project root directory.

## Troubleshooting

1. If you encounter authentication errors with the real Kalshi API, check your `.env` file and ensure your credentials are correct.

2. If the simulated API is not behaving as expected, check the `initial_price` and `volatility` parameters in your configuration.

3. For issues with the Avellaneda market maker, try adjusting the `gamma`, `k`, `sigma`, and `T` parameters in the configuration file.

4. If you're not seeing any logs, make sure the `log_level` in your configuration is set appropriately (e.g., "INFO" or "DEBUG").

5. If the script fails to start, ensure all required packages are installed by running `pip install -r requirements.txt`.

For any other issues, please check the logs and consult the error messages. If the problem persists, feel free to open an issue on the project's GitHub repository.