# tradier_api.py

import requests
import pandas as pd
import datetime

# === Tradier API Client Class ===
class TradierAPI:
    """Tradier API client for making requests"""
    
    def __init__(self, api_url: str, access_token: str, account_id: str):
        self.api_url = api_url
        self.access_token = access_token
        self.account_id = account_id
    
    def request(self, endpoint: str, params=None):
        """Make a GET request to the Tradier API"""
        url = f"{self.api_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    
    def post_request(self, endpoint: str, data=None):
        """Make a POST request to the Tradier API"""
        url = f"{self.api_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Order failed: {response.status_code} - {response.text}")

# === Global API instance (for backward compatibility) ===
_api_instance = None

def set_api_credentials(api_url: str, access_token: str, account_id: str):
    """Set global API credentials for backward compatibility"""
    global _api_instance
    _api_instance = TradierAPI(api_url, access_token, account_id)

def get_api_instance() -> TradierAPI:
    """Get the global API instance"""
    if _api_instance is None:
        raise ValueError("API credentials not set. Call set_api_credentials() first.")
    return _api_instance

# === Backward Compatibility Functions ===
def get_spy_ohlc():
    """Get current SPY OHLC data"""
    api = get_api_instance()
    data = api.request("/markets/quotes", params={"symbols": "SPY"})
    quote = data.get("quotes", {}).get("quote", {})

    if quote.get("open", 0.0) is None:
        return None
    
    # Extract OHLC data from Tradier quote
    ohlc = {
        'open': float(quote.get("open", 0.0)),
        'high': float(quote.get("high", 0.0)), 
        'low': float(quote.get("low", 0.0)),
        'close': float(quote.get("last", 0.0)),  # 'last' is current close
        'volume': int(quote.get("volume", 0))
    }
    
    return ohlc

def get_option_chain(symbol: str, expiration_date: str) -> pd.DataFrame:
    """Get option chain for given symbol and expiration"""
    api = get_api_instance()
    data = api.request("/markets/options/chains", params={
        "symbol": symbol, 
        "expiration": expiration_date, 
        "greeks": "false"
    })
    options = data.get("options", {}).get("option", [])
    return pd.DataFrame(options)

def place_order(option_type: str, strike: float, contracts: int, 
                action: str = "BUY", symbol: str = "SPY", 
                expiration_date: str = None, price: float = None) -> str:
    """Place an order and return order ID"""
    api = get_api_instance()

    # ✅ Fetch option chain and find matching OCC symbol
    chain_df = get_option_chain(symbol, expiration_date)
    if chain_df.empty:
        raise Exception("No options returned from Tradier chain API")

    # Match the desired strike and type
    desired = chain_df[
        (chain_df['strike'] == strike) &
        (chain_df['option_type'].str.upper() == ('CALL' if option_type.upper() == 'C' else 'PUT'))
    ]

    if desired.empty:
        raise Exception(f"Could not find matching option for {symbol} {option_type} {strike} {expiration_date}")

    option_symbol = desired.iloc[0]['symbol']  # ✅ Use Tradier-provided OCC symbol

    payload = {
        "class": "option",
        "symbol": option_symbol,
        "side": action.lower(),
        "quantity": contracts,
        "type": "market",
        "duration": "day"
    }

    try:
        result = api.post_request(f"/accounts/{api.account_id}/orders", payload)
        return result.get("order", {}).get("id", "N/A")
    except Exception as e:
        print(f"[ERROR] Order failed: {str(e)}")
        return "FAILED"

def test_connection():
    """Test connection to Tradier API and check account status"""
    api = get_api_instance()
    
    print("\n🚀 Testing Tradier API Connection...")
    print(f"Testing with Account ID: {api.account_id}")
    print(f"API URL: {api.api_url}")
    
    try:
        # Test getting account balance
        balance_data = api.request(f"/accounts/{api.account_id}/balances")
        print("\n✅ Successfully connected to Tradier API!")
        print("\nAccount Information:")
        print(f"Account ID: {api.account_id}")
        print(f"Is test account: {'Yes' if 'sandbox' in api.api_url else 'No'}")
        
        # Print account balance details
        print("\nAccount Balance Details:")
        try:
            # Get the main balances data
            balances = balance_data.get('balances', {})
            
            # Print main balance fields
            print(f"Total Equity: ${balances.get('total_equity', 'N/A')}")
            print(f"Total Cash: ${balances.get('total_cash', 'N/A')}")
            print(f"Open P/L: ${balances.get('open_pl', 'N/A')}")
            print(f"Close P/L: ${balances.get('close_pl', 'N/A')}")
            print(f"Market Value: ${balances.get('market_value', 'N/A')}")
            print(f"Long Market Value: ${balances.get('long_market_value', 'N/A')}")
            print(f"Short Market Value: ${balances.get('short_market_value', 'N/A')}")
            print(f"Option Long Value: ${balances.get('option_long_value', 'N/A')}")
            print(f"Option Short Value: ${balances.get('option_short_value', 'N/A')}")
            
            # Get margin data if available
            margin_data = balances.get('margin', {})
            print("\nMargin Details:")
            print(f"Stock Buying Power: ${margin_data.get('stock_buying_power', 'N/A')}")
            print(f"Option Buying Power: ${margin_data.get('option_buying_power', 'N/A')}")
            print(f"Fed Call: ${margin_data.get('fed_call', 'N/A')}")
            print(f"Maintenance Call: ${margin_data.get('maintenance_call', 'N/A')}")
            print(f"Stock Short Value: ${margin_data.get('stock_short_value', 'N/A')}")
            
        except Exception as e:
            print(f"Error accessing balance data: {str(e)}")
            print("Note: Some balance fields may not be available in test mode")
        
        # Test getting SPY price
        print("\nTesting SPY Price...")
        ohlc = get_spy_ohlc()
        if ohlc is None:
            print(f"SPY price data is currently unavailable")
            return True
        else:
            spy_price = ohlc['close']
            print(f"Current SPY Price: ${spy_price:.2f}")
        
        return True
    
    except Exception as e:
        print(f"\n❌ Error testing connection: {str(e)}")
        print("Please check:")
        print("1. Your API token is correct")
        print("2. Your account ID is correct")
        print("3. You have proper permissions")
        return False

# === OCC Symbol Builder ===
def get_option_symbol(symbol: str, strike: float, option_type: str, expiration_date=None) -> str:
    """Build OCC option symbol"""
    if expiration_date is None:
        expiration_date = datetime.date.today()
    else:
        expiration_date = datetime.datetime.strptime(expiration_date, "%Y-%m-%d").date()
    
    expiry_str = expiration_date.strftime("%y%m%d")
    cp = "C" if option_type.upper() == "C" else "P"
    strike_str = f"{int(strike * 1000):08d}"  # E.g., 600.0 -> 00600000
    return f"{symbol.upper()}{expiry_str}{cp}{strike_str}"
