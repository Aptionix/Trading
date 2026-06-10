# Trading 212 Portfolio Analysis Project

This project provides a comprehensive framework for analyzing and planning your Trading 212 broker portfolio.

## Project Overview

- **Language**: Python 3.9+
- **Type**: Data analysis with Jupyter notebooks
- **Key Features**: 
  - Portfolio performance analysis
  - Risk assessment
  - Asset allocation insights
  - Price alerts and monitoring
  - Trading signals
  - Historical performance tracking

## Project Structure

```
Trading/
├── src/                      # Python modules
│   ├── __init__.py
│   ├── api_client.py        # Trading 212 API integration
│   ├── portfolio.py         # Portfolio analysis functions
│   ├── risk_analysis.py     # Risk assessment tools
│   ├── alerts.py            # Price alert system
│   └── trading_signals.py   # Trading signal generation
├── notebooks/                # Jupyter notebooks for analysis
│   └── portfolio_analysis.ipynb
├── data/                     # Local data storage
├── requirements.txt          # Python dependencies
├── .gitignore
└── README.md
```

## Getting Started

1. **Install Dependencies**: `pip install -r requirements.txt`
2. **Configure API Credentials**: Create a `.env` file with your Trading 212 API key
3. **Run Analysis**: Open notebooks in Jupyter or use Python scripts directly

## Key Dependencies

- pandas: Data manipulation and analysis
- numpy: Numerical computations
- matplotlib/seaborn: Data visualization
- requests: HTTP client for API calls
- python-dotenv: Environment variable management
- jupyter: Interactive notebooks

## Setup Checklist Status

- [x] Project scaffolded
- [ ] Dependencies installed
- [ ] API credentials configured
- [ ] First analysis notebook ready
