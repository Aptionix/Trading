# Trading 212 Portfolio Analysis

A comprehensive Python-based framework for analyzing, monitoring, and planning your Trading 212 broker portfolio.

## Features

- **Portfolio Analysis**: View holdings, asset allocation, and performance metrics
- **Risk Assessment**: Measure concentration risk, diversification, and liquidity
- **Price Monitoring**: Set up alerts for price movements
- **Trading Signals**: Generate rebalancing and momentum-based trading signals
- **Historical Tracking**: Monitor portfolio performance over time
- **Interactive Notebooks**: Jupyter notebooks for detailed analysis

## Quick Start

### 1. Clone and Setup

```bash
cd /Users/cristonial/VSCode/Trading
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure API Access

Create a `.env` file in the project root:

```env
TRADING212_API_KEY=your_api_key_here
```

You can get your API key from the Trading 212 website:
1. Log in to your account
2. Go to Settings → API
3. Generate an API key

### 3. Run Analysis

```bash
# Start Jupyter to use interactive notebooks
jupyter notebook notebooks/

# Or run Python analysis scripts directly
python -m src.api_client
```

## Project Structure

```
Trading/
├── src/                          # Python modules
│   ├── api_client.py            # Trading 212 API integration
│   ├── portfolio.py             # Portfolio analysis functions
│   ├── risk_analysis.py         # Risk assessment tools
│   ├── alerts.py                # Price alert system
│   └── trading_signals.py       # Trading signal generation
├── notebooks/                    # Jupyter notebooks
│   └── portfolio_analysis.ipynb # Main analysis notebook
├── data/                         # Local data storage
├── requirements.txt              # Python dependencies
├── .gitignore
└── README.md
```

## Usage Examples

### Basic Portfolio Analysis

```python
from src.api_client import Trading212Client
from src.portfolio import PortfolioAnalyzer

# Initialize API client
client = Trading212Client()
accounts = client.get_accounts()
account_id = accounts[0]["id"]

# Get portfolio data
portfolio = client.get_portfolio(account_id)
cash = client.get_cash(account_id)

# Analyze portfolio
analyzer = PortfolioAnalyzer(portfolio, cash)
summary = analyzer.get_portfolio_summary()
print(summary)
```

### Risk Analysis

```python
from src.risk_analysis import RiskAnalyzer

risk_analyzer = RiskAnalyzer(analyzer.df, cash["free"])
concentration = risk_analyzer.get_concentration_risk()
diversification = risk_analyzer.get_diversification_metrics()
print(f"Concentration risk: {concentration['risk_level']}")
```

### Generate Trading Signals

```python
from src.trading_signals import SignalGenerator

signal_gen = SignalGenerator(analyzer.df, summary["total_value"])
signals = signal_gen.get_all_signals()
for signal_type, signal_list in signals.items():
    print(f"\n{signal_type.upper()} SIGNALS:")
    for signal in signal_list:
        print(f"  {signal}")
```

## Key Metrics

### Portfolio Summary
- Total portfolio value
- Total profit/loss amount and percentage
- Number of active positions
- Cash balance
- Total assets

### Risk Metrics
- **Concentration Risk**: Herfindahl index (0-10000)
- **Diversification**: Effective number of positions
- **Liquidity**: Cash ratio percentage
- **Sector Exposure**: Weight by sector

### Performance Metrics
- Average return percentage
- Volatility (standard deviation)
- Best/worst performers
- Positions in profit/loss

## API Reference

### Trading 212 Client

```python
client = Trading212Client(api_key="your_key")

# Get accounts
accounts = client.get_accounts()

# Get portfolio
portfolio = client.get_portfolio(account_id)

# Get cash balance
cash = client.get_cash(account_id)

# Get open positions
positions = client.get_open_positions(account_id)

# Get order history
orders = client.get_orders(account_id)
```

## Setting Alerts

```python
from src.alerts import PriceAlertManager

alert_manager = PriceAlertManager()

# Create alerts
alert_manager.create_alert("AAPL", "price_above", 150, "Apple above $150")
alert_manager.create_alert("MSFT", "price_below", 300, "Microsoft below $300")

# Check alerts
current_prices = {"AAPL": 155.50, "MSFT": 295.20}
triggered = alert_manager.check_alerts(current_prices)
```

## Configuration

Edit the `.env` file to configure:

- `TRADING212_API_KEY`: Your API key (required)

## Dependencies

See `requirements.txt` for the complete list:

- **pandas**: Data manipulation
- **numpy**: Numerical computing
- **matplotlib/seaborn**: Data visualization
- **requests**: HTTP client
- **python-dotenv**: Environment configuration
- **jupyter**: Interactive notebooks
- **scikit-learn**: Machine learning utilities

## Best Practices

1. **Regular Backups**: Keep local data backups
2. **Monitor Alerts**: Check alerts regularly
3. **Review Signals**: Don't execute signals blindly - always review
4. **Diversify**: Aim for Herfindahl index < 1500
5. **Rebalance**: Review and rebalance quarterly

## Troubleshooting

### API Authentication Error
- Verify API key in `.env` file
- Check that API key is valid and not expired
- Ensure API key has proper permissions

### No Data Returned
- Verify account ID is correct
- Check that account has active positions
- Ensure you're using the correct environment (live vs. demo)

### Import Errors
- Reinstall dependencies: `pip install -r requirements.txt`
- Verify Python version is 3.9 or higher

## Resources

- [Trading 212 API Documentation](https://t212public-api-v2-docs.redoc.ly/)
- [Pandas Documentation](https://pandas.pydata.org/)
- [Jupyter Documentation](https://jupyter.org/)

## License

This project is for personal use with your Trading 212 account.

## Support

For issues with the Trading 212 API, contact [Trading 212 Support](https://www.trading212.com/)

For issues with this project, check the documentation or review the code comments.

## Disclaimer

This is a personal portfolio analysis tool. It does not provide financial advice. Always do your own research and consult with a financial advisor before making investment decisions.
