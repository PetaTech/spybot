import yfinance as yf

def fetch_current_vix():
    """Fetch the latest VIX close price using yfinance (1-min intraday data)."""
    vix = yf.Ticker("^VIX")
    vix_data = vix.history(period="1d", interval="1m")
    if not vix_data.empty:
        latest = vix_data.iloc[-1]
        return float(latest['Close'])
    return None 