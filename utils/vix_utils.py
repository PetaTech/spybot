import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def fetch_vix_at_datetime(target_datetime):
    """
    Fetch the VIX close price at a specific datetime using 2-minute interval data.

    Args:
        target_datetime (datetime): The datetime (UTC/local-naive) to get the VIX price for.

    Returns:
        float or None: The VIX close price at the given time, or None if not found.
    """
    # Define a 2-hour window around the target time
    start_dt = target_datetime - timedelta(hours=1)
    end_dt = target_datetime + timedelta(hours=1)

    # Fetch 2-minute interval VIX data
    vix = yf.Ticker("^VIX")
    vix_data = vix.history(start=start_dt, end=end_dt, interval="2m")

    if vix_data.empty:
        print("No VIX data returned. Possibly out of range or non-trading time.")
        return None

    # Remove timezone info for matching
    vix_data.index = vix_data.index.tz_localize(None)

    # Try exact match first
    if target_datetime in vix_data.index:
        return float(vix_data.loc[target_datetime]["Close"])
    else:
        # Use closest timestamp before target
        before = vix_data[vix_data.index <= target_datetime]
        if not before.empty:
            closest_row = before.iloc[-1]
            print(f"No exact VIX match. Closest before: {closest_row.name}")
            return float(closest_row["Close"])

    return None

def fetch_current_vix():
    """Fetch the latest VIX close price using yfinance (1-min intraday data)."""
    vix = yf.Ticker("^VIX")
    vix_data = vix.history(period="1d", interval="1m")
    if not vix_data.empty:
        latest = vix_data.iloc[-1]
        return float(latest['Close'])
    return None 