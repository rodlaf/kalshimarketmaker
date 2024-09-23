# Kalshi Market Making Algorithm

This project implements a market making algorithm for Kalshi markets.

## Local Setup

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file with your Kalshi credentials:
   ```
   KALSHI_EMAIL=your_email
   KALSHI_PASSWORD=your_password
   KALSHI_BASE_URL=https://trading-api.kalshi.com/trade-api/v2
   ```
4. Create a `config.yaml` file with your market making configuration.
5. Run the script:
   ```
   python mm.py --config config.yaml --config-name your_config_name --log-level INFO --trade-side yes
   ```

## Deploying on fly.io

1. Install the flyctl CLI: https://fly.io/docs/hands-on/install-flyctl/
2. Login to fly.io:
   ```
   flyctl auth login
   ```
3. Navigate to your project directory and initialize your fly.io app:
   ```
   flyctl launch
   ```
   Follow the prompts, but don't deploy yet.
4. Set your Kalshi credentials and base URL as secrets:
   ```
   flyctl secrets set KALSHI_EMAIL=your_email
   flyctl secrets set KALSHI_PASSWORD=your_password
   flyctl secrets set KALSHI_BASE_URL=https://trading-api.kalshi.com/trade-api/v2
   ```
5. Deploy the app:
   ```
   flyctl deploy
   ```

Note: Make sure your `config.yaml` file is in the same directory as `mm.py` before deploying.

For more detailed instructions, refer to the fly.io documentation.