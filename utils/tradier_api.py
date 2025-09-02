# tradier_api.py

import requests
import pandas as pd
import datetime
from typing import Dict, List

# === Tradier API Client Class ===
class TradierAPI:
    """Tradier API client for making requests"""
    
    def __init__(self, api_url: str, access_token: str, account_id: str):
        self.api_url = api_url
        self.access_token = access_token
        self.account_id = account_id
    
    def request(self, endpoint: str, params=None, method="GET"):
        """Make a request to the Tradier API"""
        url = f"{self.api_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }
        
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
            
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

    # Convert action to proper option side format
    if action.upper() == "BUY":
        side = "buy_to_open"
    elif action.upper() == "SELL":
        side = "sell_to_close"
    else:
        side = action.lower()  # Fallback for other formats
    
    payload = {
        "class": "option",
        "symbol": symbol,  # ✅ Underlying symbol (SPY)
        "option_symbol": option_symbol,  # ✅ Full OCC symbol (SPY250812C00642000)
        "side": side,  # ✅ Proper option side (buy_to_open/sell_to_close)
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

def place_limit_order(option_type: str, strike: float, contracts: int, 
                      action: str = "BUY", symbol: str = "SPY", 
                      expiration_date: str = None, limit_price: float = None) -> str:
    """Place a LIMIT order and return order ID"""
    api = get_api_instance()

    # Fetch option chain and find matching OCC symbol
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

    option_symbol = desired.iloc[0]['symbol']

    # Convert action to proper option side format
    if action.upper() == "BUY":
        side = "buy_to_open"
    elif action.upper() == "SELL":
        side = "sell_to_close"
    else:
        side = action.lower()
    
    payload = {
        "class": "option",
        "symbol": symbol,
        "option_symbol": option_symbol,
        "side": side,
        "quantity": contracts,
        "type": "limit",  # LIMIT order instead of market
        "price": limit_price,  # Limit price
        "duration": "day"
    }

    try:
        result = api.post_request(f"/accounts/{api.account_id}/orders", payload)
        order_id = result.get("order", {}).get("id", "N/A")
        print(f"🎯 LIMIT ORDER PLACED: {action} {contracts} {option_type} {strike} @ ${limit_price:.2f} -> ID: {order_id}")
        return order_id
    except Exception as e:
        print(f"[ERROR] Limit order failed: {str(e)}")
        return "FAILED"


def get_order_status(order_id: str) -> Dict:
    """Get order status by order ID"""
    api = get_api_instance()
    
    try:
        result = api.request(f"/accounts/{api.account_id}/orders/{order_id}")
        order = result.get("order", {})
        
        status_info = {
            'id': order.get('id', 'N/A'),
            'status': order.get('status', 'unknown'),
            'state': order.get('state', 'unknown'),
            'filled_quantity': int(order.get('exec_quantity', 0)),
            'remaining_quantity': int(order.get('remaining_quantity', 0)),
            'avg_fill_price': float(order.get('avg_fill_price', 0.0)),
            'symbol': order.get('option_symbol', order.get('symbol', 'N/A')),
            'side': order.get('side', 'N/A'),
            'price': float(order.get('price', 0.0)),
            'type': order.get('type', 'N/A')
        }
        
        return status_info
    except Exception as e:
        print(f"[ERROR] Failed to get order status for {order_id}: {str(e)}")
        return {'id': order_id, 'status': 'error', 'state': 'error'}


def cancel_order(order_id: str) -> bool:
    """Cancel an order by order ID"""
    api = get_api_instance()
    
    try:
        result = api.request(f"/accounts/{api.account_id}/orders/{order_id}", method="DELETE")
        success = result.get("order", {}).get("status") == "ok"
        
        if success:
            print(f"✅ ORDER CANCELLED: {order_id}")
        else:
            print(f"❌ CANCEL FAILED: {order_id}")
            
        return success
    except Exception as e:
        print(f"[ERROR] Failed to cancel order {order_id}: {str(e)}")
        return False


def get_all_orders(status_filter: str = None) -> List[Dict]:
    """Get all orders, optionally filtered by status"""
    api = get_api_instance()
    
    try:
        result = api.request(f"/accounts/{api.account_id}/orders")
        orders = result.get("orders", {}).get("order", [])
        
        # Ensure orders is a list (API returns dict for single order)
        if isinstance(orders, dict):
            orders = [orders]
        
        # Filter by status if requested
        if status_filter:
            orders = [order for order in orders if order.get('status', '').lower() == status_filter.lower()]
        
        return orders
    except Exception as e:
        print(f"[ERROR] Failed to get orders: {str(e)}")
        return []


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
