"""
Pure Data-Driven Trading Engine
Processes one row of market data at a time from external data providers.
Maintains all trading state and logic internally.
"""

import pandas as pd
import numpy as np
import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Union
from abc import ABC, abstractmethod
import time
import os
from dateutil import tz
from utils import fetch_current_vix, fetch_vix_at_datetime
import requests
import urllib.parse
import calendar
import json
import pytz
from zoneinfo import ZoneInfo

@dataclass
class Position:
    """Represents a trading position"""
    type: str  # 'C' for call, 'P' for put
    strike: float
    entry_price: float
    contracts: int
    target: float
    symbol: str = "SPY"
    expiration_date: str = ""
    entry_time: datetime.datetime = None
    trade_id: int = field(default=None)  # Add trade_id to Position
    entry_order_id: str = field(default=None)  # Entry order ID
    limit_order_id: str = field(default=None)  # Limit sell order ID
    limit_price: float = field(default=None)  # Limit sell price


@dataclass
class MarketRow:
    """Standardized market data row"""
    current_time: datetime.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str = "SPY"


class OrderExecutor(ABC):
    """Abstract base class for order execution"""
    
    @abstractmethod
    def place_order(self, option_type: str, strike: float, contracts: int, 
                   action: str, expiration_date: str, price: Optional[float] = None) -> str:
        """Place an order and return order ID"""
        pass
    
    @abstractmethod
    def place_limit_order(self, option_type: str, strike: float, contracts: int, 
                         action: str, expiration_date: str, limit_price: float) -> str:
        """Place a limit order and return order ID"""
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> Dict:
        """Get order status"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        pass


class BacktestOrderExecutor(OrderExecutor):
    """Backtest order executor - tracks orders for PnL calculation"""
    
    def __init__(self):
        self.orders = []
        self.order_counter = 0
    
    def place_order(self, option_type: str, strike: float, contracts: int, 
                   action: str, expiration_date: str, price: Optional[float] = None) -> str:
        """Track order for backtest analysis"""
        self.order_counter += 1
        order_id = f"BACKTEST_{self.order_counter:06d}"
        
        order = {
            'id': order_id,
            'type': option_type,
            'strike': strike,
            'contracts': contracts,
            'action': action,
            'expiration': expiration_date,
            'price': price,
            'order_type': 'market',
            'status': 'filled',
            'timestamp': datetime.datetime.now()
        }
        
        self.orders.append(order)
        return order_id
    
    def place_limit_order(self, option_type: str, strike: float, contracts: int, 
                         action: str, expiration_date: str, limit_price: float) -> str:
        """Track limit order for backtest analysis"""
        self.order_counter += 1
        order_id = f"BACKTEST_LIMIT_{self.order_counter:06d}"
        
        order = {
            'id': order_id,
            'type': option_type,
            'strike': strike,
            'contracts': contracts,
            'action': action,
            'expiration': expiration_date,
            'price': limit_price,
            'order_type': 'limit',
            'status': 'open',
            'timestamp': datetime.datetime.now()
        }
        
        self.orders.append(order)
        return order_id
    
    def get_order_status(self, order_id: str) -> Dict:
        """Get order status for backtest"""
        for order in self.orders:
            if order['id'] == order_id:
                return {
                    'id': order_id,
                    'status': order.get('status', 'open'),
                    'state': order.get('status', 'open'),
                    'filled_quantity': order['contracts'] if order.get('status') == 'filled' else 0,
                    'remaining_quantity': 0 if order.get('status') == 'filled' else order['contracts'],
                    'avg_fill_price': order.get('price', 0.0),
                    'symbol': f"{order['type']}{order['strike']}",
                    'side': order['action'],
                    'price': order.get('price', 0.0),
                    'type': order.get('order_type', 'market')
                }
        return {'id': order_id, 'status': 'not_found', 'state': 'not_found'}
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order for backtest"""
        for order in self.orders:
            if order['id'] == order_id:
                order['status'] = 'cancelled'
                return True
        return False
    
    def get_orders(self):
        """Get all tracked orders"""
        return self.orders


class PaperOrderExecutor(OrderExecutor):
    """Paper trading order executor - places ACTUAL orders in sandbox environment"""
    
    def __init__(self, api_url: str, access_token: str, account_id: str):
        self.api_url = api_url
        self.access_token = access_token
        self.account_id = account_id
        self.order_counter = 0
    
    def place_order(self, option_type: str, strike: float, contracts: int, 
                   action: str, expiration_date: str, price: Optional[float] = None) -> str:
        """Place ACTUAL order in sandbox environment"""
        # Import here to avoid circular imports
        from utils.tradier_api import place_order
        
        # Place real order in sandbox
        order_id = place_order(option_type, strike, contracts, action=action, 
                              expiration_date=expiration_date, price=price)
        
        # Log the order placement
        print(f"🔴 SANDBOX ORDER PLACED: {action} {contracts} {option_type} {strike} exp:{expiration_date} -> ID: {order_id}")
        
        return order_id
    
    def place_limit_order(self, option_type: str, strike: float, contracts: int, 
                         action: str, expiration_date: str, limit_price: float) -> str:
        """Place ACTUAL limit order in sandbox environment"""
        # Import here to avoid circular imports
        from utils.tradier_api import place_limit_order
        
        # Place real limit order in sandbox
        order_id = place_limit_order(option_type, strike, contracts, action=action, 
                                    expiration_date=expiration_date, limit_price=limit_price)
        
        # Log the order placement
        print(f"🎯 SANDBOX LIMIT ORDER PLACED: {action} {contracts} {option_type} {strike} @ ${limit_price:.2f} -> ID: {order_id}")
        
        return order_id
    
    def get_order_status(self, order_id: str) -> Dict:
        """Get ACTUAL order status from sandbox"""
        from utils.tradier_api import get_order_status
        return get_order_status(order_id)
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel ACTUAL order in sandbox"""
        from utils.tradier_api import cancel_order
        return cancel_order(order_id)


class LiveOrderExecutor(OrderExecutor):
    """Live order executor using Tradier API"""
    
    def __init__(self, api_url: str, access_token: str, account_id: str):
        self.api_url = api_url
        self.access_token = access_token
        self.account_id = account_id
    
    def place_order(self, option_type: str, strike: float, contracts: int, 
                   action: str, expiration_date: str, price: Optional[float] = None) -> str:
        """Place order using live API"""
        # Import here to avoid circular imports
        from utils.tradier_api import place_order
        return place_order(option_type, strike, contracts, action=action, 
                          expiration_date=expiration_date, price=price)
    
    def place_limit_order(self, option_type: str, strike: float, contracts: int, 
                         action: str, expiration_date: str, limit_price: float) -> str:
        """Place limit order using live API"""
        # Import here to avoid circular imports
        from utils.tradier_api import place_limit_order
        return place_limit_order(option_type, strike, contracts, action=action, 
                                expiration_date=expiration_date, limit_price=limit_price)
    
    def get_order_status(self, order_id: str) -> Dict:
        """Get order status from live API"""
        from utils.tradier_api import get_order_status
        return get_order_status(order_id)
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel order using live API"""
        from utils.tradier_api import cancel_order
        return cancel_order(order_id)


class DataProvider(ABC):
    """Abstract base class for data providers"""
    
    @abstractmethod
    def get_option_chain(self, symbol: str, expiration_date: str) -> pd.DataFrame:
        """Get option chain for given symbol and expiration"""
        pass


class TradingEngine:
    """
    Pure data-driven trading engine that processes one row at a time.
    Maintains all trading state and logic internally.
    """
    
    def __init__(self, config: Dict, data_provider: DataProvider, mode: str = "backtest", 
                 api_url: str = None, access_token: str = None, account_id: str = None):
        """
        Initialize trading engine with configuration and dependencies
        
        Args:
            config: Dictionary containing strategy parameters
            data_provider: Provider for options data
            mode: Trading mode ('backtest', 'paper', 'live')
            api_url: API URL for live/paper trading
            access_token: API access token for live/paper trading
            account_id: Account ID for live/paper trading
        """
        # Dependencies
        self.data_provider = data_provider
        self.config = config # Store config for backtest mode
        
        # Create appropriate order executor based on mode
        if mode == "backtest":
            self.order_executor = BacktestOrderExecutor()
        elif mode == "paper":
            if not all([api_url, access_token, account_id]):
                raise ValueError("Paper mode requires api_url, access_token, and account_id for sandbox orders")
            self.order_executor = PaperOrderExecutor(api_url, access_token, account_id)
        elif mode == "live":
            if not all([api_url, access_token, account_id]):
                raise ValueError("Live mode requires api_url, access_token, and account_id")
            self.order_executor = LiveOrderExecutor(api_url, access_token, account_id)
        else:
            raise ValueError(f"Unknown mode: {mode}")
        
        # Strategy parameters
        self.cooldown_period = config.get('COOLDOWN_PERIOD', 20 * 60)
        self.risk_per_side = config.get('RISK_PER_SIDE', 400)
        self.max_retries = config.get('MAX_RETRIES', 6)
        self.retry_delay = config.get('RETRY_DELAY', 1)
        self.price_window_seconds = config.get('PRICE_WINDOW_SECONDS', 30 * 60)
        self.max_entry_time = config.get('MAX_ENTRY_TIME', datetime.time(15, 0))
        self.stop_loss_percentage = config.get('STOP_LOSS_PERCENTAGE', 30.0)
        self.emergency_stop_loss = config.get('EMERGENCY_STOP_LOSS', 2000)
        
        # Market timing parameters for theta decay management
        self.market_open_buffer_minutes = config.get('MARKET_OPEN_BUFFER_MINUTES', 15)
        self.market_close_buffer_minutes = config.get('MARKET_CLOSE_BUFFER_MINUTES', 15)
        self.early_signal_cooldown_minutes = config.get('EARLY_SIGNAL_COOLDOWN_MINUTES', 30)
        
        # Commission and slippage parameters
        self.commission_per_contract = config.get('COMMISSION_PER_CONTRACT', 0.65)
        self.slippage = config.get('SLIPPAGE', 0.01)
        
        # Option filtering parameters
        self.option_ask_min = config.get('OPTION_ASK_MIN', 0.01)
        self.option_ask_max = config.get('OPTION_ASK_MAX', 100.0)
        self.option_bid_ask_ratio = config.get('OPTION_BID_ASK_RATIO', 0.5)
        
        # Daily limits
        self.max_daily_trades = config.get('MAX_DAILY_TRADES', 5)
        self.max_daily_loss = config.get('MAX_DAILY_LOSS', 1000)
        
        # Market hours
        self.market_open = config.get('MARKET_OPEN', '09:30')
        self.market_close = config.get('MARKET_CLOSE', '16:00')
        self.timezone = config.get('TIMEZONE', 'America/New_York')
        
        # Reference price type for percentage calculations
        self.reference_price_type = config.get('REFERENCE_PRICE_TYPE', 'window_high_low')
        
        # VIX-based strategy parameters from config
        self.vix_threshold = config.get('VIX_THRESHOLD', 25)
        self.high_vol_move_threshold = config.get('HIGH_VOL_MOVE_THRESHOLD', 3.5)
        self.high_vol_premium_min = config.get('HIGH_VOL_PREMIUM_MIN', 1.05)
        self.high_vol_premium_max = config.get('HIGH_VOL_PREMIUM_MAX', 2.20)
        self.high_vol_profit_target = config.get('HIGH_VOL_PROFIT_TARGET', 1.35)
        self.low_vol_move_threshold = config.get('LOW_VOL_MOVE_THRESHOLD', 2.5)
        self.low_vol_premium_min = config.get('LOW_VOL_PREMIUM_MIN', 0.40)
        self.low_vol_premium_max = config.get('LOW_VOL_PREMIUM_MAX', 1.05)
        self.low_vol_profit_target = config.get('LOW_VOL_PROFIT_TARGET', 1.25)
        
        # State tracking
        self.active_trades: List[List[Position]] = []
        self.trade_entry_times: List[datetime.datetime] = []
        self.last_trade_time = None
        self.last_flagged_time = None
        self.last_early_signal_time = None  # Track early signals for cooldown
        self.price_log: List[Tuple[datetime.datetime, float]] = []
        
        # Limit order tracking
        self.active_limit_orders: Dict[str, Dict] = {}  # order_id -> order info
        self.last_order_check_time = None  # Track when we last checked order status
        self.order_check_interval = 3  # Check order status every 3 seconds
        
        # Daily tracking
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.current_date = None
        
        # Logging setup
        self.log_dir = config.get('LOG_DIR', 'logs')
        self.mode = mode
        self.setup_logging()
        
        # Performance metrics
        self.total_signals = 0
        self.total_trades = 0
        self.total_pnl = 0.0
        self.winning_trades = 0
        self.losing_trades = 0
        
        self.log(f"🚀 Trading Engine initialized in {self.mode} mode")
        self.log(f"📊 Strategy: {self.cooldown_period//60}min cooldown")
        self.log(f"📈 Reference price type: {self.reference_price_type}")
        self.log(f"⏰ Market timing: {self.market_open_buffer_minutes}min open buffer, {self.market_close_buffer_minutes}min close buffer")
        self.log(f"🔄 Early signal cooldown: {self.early_signal_cooldown_minutes}min")
        self.log(f"💸 Commission: ${self.commission_per_contract:.2f} per contract, Slippage: ${self.slippage:.2f} per contract")
        self.log(f"💰 Pricing: Entry at ASK, Exit at BID (realistic trading)")
        self.log(f"🛑 Stop Loss: {self.stop_loss_percentage:.1f}% loss threshold")
        self.log(f"🚨 Emergency Stop Loss: ${self.emergency_stop_loss} daily loss limit")
        
        # VIX parameters initialization
        self._vix_last_fetch_time = 0
        self._vix_value = None
        self._vix_regime = None
        self._set_vix_parameters(force=True)
        self.log(f"VIX regime: {self._vix_regime} (VIX={self._vix_value})")
        self.log(f"VIX config: threshold={self.vix_threshold}, high_vol_move={self.high_vol_move_threshold}, low_vol_move={self.low_vol_move_threshold}")
        
        # Add a list to store detailed signal/trade logs
        self.signal_trade_log = []
        self.trade_id_counter = 0  # Unique trade ID for each signal
        
        # Initialize Telegram notifications
        self.telegram_notifier = None
        self.account_holder_name = "Trading Account"
        self._init_telegram_notifications()
    
    def _init_telegram_notifications(self):
        """Initialize Telegram notifications if enabled"""
        try:
            from config.telegram import (
                TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ENABLED,
                SEND_SIGNAL_ALERTS, SEND_ENTRY_ALERTS, SEND_EXIT_ALERTS,
                SEND_LIMIT_HIT_ALERTS, SEND_STOP_LOSS_ALERTS, 
                SEND_DAILY_LIMIT_ALERTS, SEND_SYSTEM_ALERTS
            )
            from utils.telegram_bot import TelegramNotifier, TelegramConfig
            
            if TELEGRAM_ENABLED and TELEGRAM_BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
                # Get account holder name
                if self.mode in ['live', 'paper']:
                    try:
                        from utils.tradier_api import get_account_profile
                        profile = get_account_profile()
                        self.account_holder_name = profile['name']
                    except Exception as e:
                        self.log(f"[TELEGRAM] Could not fetch account name: {e}")
                
                # Initialize Telegram notifier
                config = TelegramConfig(
                    bot_token=TELEGRAM_BOT_TOKEN,
                    chat_id=TELEGRAM_CHAT_ID,
                    enabled=TELEGRAM_ENABLED
                )
                
                self.telegram_notifier = TelegramNotifier(config, self.account_holder_name)
                
                # Store notification preferences
                self.telegram_settings = {
                    'signal_alerts': SEND_SIGNAL_ALERTS,
                    'entry_alerts': SEND_ENTRY_ALERTS, 
                    'exit_alerts': SEND_EXIT_ALERTS,
                    'limit_hit_alerts': SEND_LIMIT_HIT_ALERTS,
                    'stop_loss_alerts': SEND_STOP_LOSS_ALERTS,
                    'daily_limit_alerts': SEND_DAILY_LIMIT_ALERTS,
                    'system_alerts': SEND_SYSTEM_ALERTS
                }
                
                self.log(f"[TELEGRAM] Initialized for account: {self.account_holder_name}")
                
                # Send system start alert
                if self.telegram_settings['system_alerts']:
                    self._send_system_start_alert()
            else:
                self.log("[TELEGRAM] Disabled or not configured")
                
        except ImportError:
            self.log("[TELEGRAM] Configuration not found, notifications disabled")
        except Exception as e:
            self.log(f"[TELEGRAM] Initialization failed: {e}")
    
    def setup_logging(self):
        """Setup logging infrastructure"""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        
        current_time = datetime.datetime.now(tz=tz.gettz(self.timezone))
        current_date = current_time.strftime("%Y-%m-%d")
        current_time_str = current_time.strftime("%H-%M-%S")
        
        if self.mode == 'backtest':
            self.log_file = os.path.join(self.log_dir, f"{self.mode}_single_log_{current_date}_{current_time_str}.txt")
        else:
            self.log_file = os.path.join(self.log_dir, f"{self.mode}_log_{current_date}_{current_time_str}.txt")
    
    def log(self, msg: str):
        """Log a message to both console and file (without timestamp)"""
        print(msg)
        
        with open(self.log_file, "a", encoding='utf-8') as f:
            f.write(msg + "\n")
    
    def process_row(self, 
                   current_time: datetime.datetime,     # quote_datetime
                   symbol: str,                      # symbol
                   open: float,                      # open
                   high: float,                      # high
                   low: float,                       # low
                   close: float,                     # close
                   volume: int) -> Dict:             # trade_volume
        """
        Process one row of market data with explicit parameters
        
        Args:
            current_time: Market data timestamp
            symbol: Trading symbol (e.g., 'SPY')
            open: Opening price
            high: High price
            low: Low price
            close: Closing price
            volume: Trading volume
            
        Returns:
            Dict containing processing results and actions taken
        """
        self._set_vix_parameters(target_datetime=current_time)  # Pass current_time for backtesting
        print(f"[ENGINE DEBUG] Processing row at {current_time}, SPY ${close:.2f}")
        
        # Check if we're in buffer periods and skip processing
        market_open_time = datetime.datetime.strptime(self.market_open, '%H:%M').time()
        market_open_datetime = datetime.datetime.combine(current_time.date(), market_open_time)
        if current_time.tzinfo is not None and market_open_datetime.tzinfo is None:
            market_open_datetime = market_open_datetime.replace(tzinfo=current_time.tzinfo)
        time_since_open = (current_time - market_open_datetime).total_seconds() / 60
        
        market_close_time = datetime.datetime.strptime(self.market_close, '%H:%M').time()
        market_close_datetime = datetime.datetime.combine(current_time.date(), market_close_time)
        if current_time.tzinfo is not None and market_close_datetime.tzinfo is None:
            market_close_datetime = market_close_datetime.replace(tzinfo=current_time.tzinfo)
        time_until_close = (market_close_datetime - current_time).total_seconds() / 60
        
        # Check if we're in buffer periods (for entry blocking)
        in_open_buffer = time_since_open < self.market_open_buffer_minutes
        in_close_buffer = time_until_close < self.market_close_buffer_minutes
        
        if in_open_buffer:
            self.log(f"⏰ MARKET OPEN BUFFER: +{time_since_open:.1f}min < {self.market_open_buffer_minutes}min")
        if in_close_buffer:
            self.log(f"⏰ MARKET CLOSE BUFFER: -{time_until_close:.1f}min < {self.market_close_buffer_minutes}min")
        
        # Store current time for options queries
        self.last_processed_time = current_time
        
        # Create MarketRow for internal processing
        market_row = MarketRow(
            current_time=current_time,
            open=open,
            high=high,
            low=low,
            close=close,
            volume=volume,
            symbol=symbol
        )
        
        # Initialize result
        result = {
            'timestamp': market_row.current_time,
            'action': 'none',
            'symbol': market_row.symbol,
            'price': market_row.close,
            'move_percent': 0.0,
            'signal_detected': False,
            'trades_active': len(self.active_trades),
            'entry_cost': 0.0,
            'exit_value': 0.0,
            'pnl': 0.0,
            'positions': None,
            'error': None
        }
        
        # Update price log
        self.update_price(market_row.current_time, market_row.close)
        
        # Calculate current move
        move_percent, absolute_move, reference_price = self.calculate_percentage_move(market_row.current_time)
        result['move_percent'] = move_percent
        
        self.log(f"📊 Processing: SPY=${market_row.close:.2f} | Move: {move_percent:.2f}% ({absolute_move:.2f}pts) | Active trades: {len(self.active_trades)}")
        
        print(f"[ENGINE DEBUG] Move calculation: {move_percent:.2f}% ({absolute_move:.2f} points)")
        
        # Check limit order status first (every 3 seconds)
        self.check_limit_order_fills(market_row.current_time)
        
        # ALWAYS check for exits on all active trades (even during buffer periods)
        if self.active_trades:
            print(f"[ENGINE DEBUG] Checking exits for {len(self.active_trades)} active trades")
            trades_to_exit = self.check_all_exit_conditions(market_row.current_time)
            
            for trade_index in reversed(trades_to_exit):
                trade_positions = self.active_trades[trade_index]
                entry_time = self.trade_entry_times[trade_index]
                trade_id = None
                if trade_positions and hasattr(trade_positions[0], 'trade_id'):
                    trade_id = getattr(trade_positions[0], 'trade_id', None)
                if trade_id is not None:
                    self.log(f"🔄 EXITING TRADE (Trade ID: {trade_id}, held for {(market_row.current_time - entry_time).total_seconds()/60:.1f} minutes)")
                else:
                    self.log(f"🔄 EXITING TRADE (held for {(market_row.current_time - entry_time).total_seconds()/60:.1f} minutes)")
                
                # Execute exit
                if trade_positions and trade_positions[0].expiration_date:
                    expiration = trade_positions[0].expiration_date
                    if self.execute_exit(trade_positions, expiration):
                        result['action'] = 'exit'
                        result['positions'] = trade_positions.copy()
                        self.last_trade_time = market_row.current_time
                        
                        # Calculate P&L with commission and slippage
                        entry_cost = sum(pos.entry_price * 100 * pos.contracts for pos in trade_positions)
                        entry_commission = self.calculate_total_trade_cost(trade_positions, is_exit=False)
                        total_entry_cost = entry_cost + entry_commission
                        
                        # Get current bid prices for exit calculation
                        exit_value = self.calculate_exit_value(trade_positions, expiration, market_row.current_time)
                        exit_commission = self.calculate_total_trade_cost(trade_positions, is_exit=True)
                        
                        # Total P&L = Exit Value - Entry Cost - Entry Commission - Exit Commission
                        trade_pnl = exit_value - entry_cost - entry_commission - exit_commission
                        
                        result['entry_cost'] = entry_cost
                        result['entry_commission'] = entry_commission
                        result['total_entry_cost'] = total_entry_cost
                        result['exit_value'] = exit_value
                        result['exit_commission'] = exit_commission
                        result['pnl'] = trade_pnl
                        
                        self.update_daily_pnl(trade_pnl)
                        self.update_trade_metrics(trade_pnl)
                        
                        # Update analytics log with real exit values
                        if trade_id is not None:
                            for entry in reversed(self.signal_trade_log):
                                if entry.get('trade_id') == trade_id:
                                    entry['exit_value'] = exit_value
                                    entry['exit_commission'] = exit_commission
                                    entry['pnl'] = trade_pnl
                                    break
                        
                        # Remove the exited trade
                        self.active_trades.pop(trade_index)
                        self.trade_entry_times.pop(trade_index)
                        
                        self.log(f"✅ Trade #{trade_index + 1} EXIT COMPLETE. P&L: ${trade_pnl:.2f} (Entry: ${entry_cost:.2f} + ${entry_commission:.2f}, Exit: ${exit_value:.2f} - ${exit_commission:.2f})")
                        
                        # Send Telegram trade exit alert
                        trade_id = getattr(trade_positions[0], 'trade_id', trade_index + 1) if trade_positions else trade_index + 1
                        holding_time_minutes = (market_row.current_time - entry_time).total_seconds() / 60
                        holding_time = f"{holding_time_minutes:.1f} minutes"
                        
                        exit_data = {
                            'trade_id': trade_id,
                            'exit_time': market_row.current_time,
                            'holding_time': holding_time,
                            'positions': self._positions_to_dict(trade_positions),
                            'exit_reason': 'Manual Exit',
                            'entry_cost': entry_cost,
                            'entry_commission': entry_commission,
                            'total_entry_cost': entry_cost + entry_commission,
                            'exit_value': exit_value,
                            'exit_commission': exit_commission,
                            'pnl': trade_pnl,
                            'daily_pnl': self.daily_pnl,
                            'daily_trades': self.daily_trades,
                            'total_trades': self.total_trades,
                            'timing_status': self.get_market_timing_status(market_row.current_time)
                        }
                        self._send_exit_alert(exit_data)
                        
                        # Log comprehensive exit result
                        self.log_comprehensive_result(result)
                        # Update analytics log for forced exit
                        trade_id = None
                        if trade_positions and hasattr(trade_positions[0], 'trade_id'):
                            trade_id = getattr(trade_positions[0], 'trade_id', None)
                        if trade_id is not None:
                            for entry in reversed(self.signal_trade_log):
                                if entry.get('trade_id') == trade_id:
                                    if entry.get('exit_time') is None:
                                        entry['exit_time'] = market_row.current_time
                                        entry['exit_value'] = result.get('exit_value') if 'exit_value' in result else None
                                        entry['exit_commission'] = result.get('exit_commission') if 'exit_commission' in result else None
                                        entry['pnl'] = result.get('pnl') if 'pnl' in result else None
                                        entry['exit_reason'] = 'market close'
                                    # If already closed, do not overwrite exit info
                                    break
                    else:
                        result['action'] = 'exit_failed'
                        result['error'] = 'Exit execution failed'
                        self.log(f"❌ EXIT FAILED: {result['error']}")
                else:
                    result['action'] = 'exit_failed'
                    result['error'] = 'No expiration date stored'
                    self.log(f"❌ EXIT FAILED: {result['error']}")
        
        # Only check for new entry signals if NOT in buffer periods
        if not in_open_buffer and not in_close_buffer:
            print(f"[ENGINE DEBUG] Checking for entry signals...")
            if self.should_detect_signal(market_row.current_time):
                result['signal_detected'] = True
                self.total_signals += 1
                self.log(f"🎯 SIGNAL DETECTED! {market_row.symbol} ${market_row.close:.2f} | Move: {move_percent:.2f}% | Active trades: {len(self.active_trades)}")
                
                # Send signal alert to Telegram
                signal_data = {
                    'detection_time': market_row.current_time,
                    'condition': f"Move {move_percent:.2f}% in window, signal detected",
                    'market_price': market_row.close,
                    'move_percent': move_percent,
                    'move_points': absolute_move,
                    'vix_regime': getattr(self, '_vix_regime', 'Unknown'),
                    'vix_value': getattr(self, '_vix_value', None),
                    'active_trades': len(self.active_trades),
                    'symbol': market_row.symbol
                }
                self._send_signal_alert(signal_data)
                
                # Check entry conditions
                self.log(f"🔍 Checking entry conditions...")
                if self.is_entry_allowed(market_row.current_time):
                    if not self.check_daily_limits(market_row.current_time):
                        result['action'] = 'signal_skipped'
                        result['error'] = 'Daily limits reached'
                        self.log(f"⏭️ SIGNAL SKIPPED: {result['error']}")
                    else:
                        self.log(f"🚀 ENTRY SIGNAL APPROVED! Move {move_percent:.2f}% | Active trades: {len(self.active_trades)}")
                        expiration = market_row.current_time.strftime("%Y-%m-%d")
                        # Diagnostic logging for options loading
                        self.log(f"[DIAG] Requesting option chain for time: {market_row.current_time}, expiration: {expiration}")
                        print(f"[ENGINE DEBUG] About to call find_valid_options for price ${close:.2f}, expiration {expiration}")
                        positions = self.find_valid_options(market_row.close, expiration, market_row.current_time)
                        print(f"[ENGINE DEBUG] find_valid_options returned {len(positions)} positions")
                        if len(positions) == 2:
                            # Execute entry
                            if self.execute_entry(positions, expiration):
                                self.active_trades.append(positions)
                                self.trade_entry_times.append(market_row.current_time)
                                self.last_trade_time = market_row.current_time
                                
                                entry_cost = sum(pos.entry_price * 100 * pos.contracts for pos in positions)
                                entry_commission = self.calculate_total_trade_cost(positions, is_exit=False)
                                total_entry_cost = entry_cost + entry_commission
                                
                                result['action'] = 'entry'
                                result['positions'] = positions.copy()
                                result['entry_cost'] = entry_cost
                                result['entry_commission'] = entry_commission
                                result['total_entry_cost'] = total_entry_cost
                                
                                self.increment_daily_trades()
                                self.log(f"✅ TRADE ENTERED! Cost: ${total_entry_cost:.2f} (${entry_cost:.2f} + ${entry_commission:.2f} commission)")
                                
                                # Send Telegram entry alert
                                trade_id = getattr(positions[0], 'trade_id', len(self.active_trades)) if positions else len(self.active_trades)
                                entry_data = {
                                    'trade_id': trade_id,
                                    'entry_time': market_row.current_time,
                                    'positions': self._positions_to_dict(positions),
                                    'market_price': market_row.close,
                                    'total_risk': self.risk_per_side * 2,
                                    'risk_per_side': self.risk_per_side,
                                    'entry_cost': entry_cost,
                                    'commission': entry_commission,
                                    'total_entry_cost': total_entry_cost,
                                    'expiration_date': expiration,
                                    'trades_active': len(self.active_trades),
                                    'symbol': 'SPY',
                                    'limit_orders_info': 'Limit orders placed for profit targets',
                                    'timing_status': self.get_market_timing_status(market_row.current_time)
                                }
                                self._send_entry_alert(entry_data)
                                
                                self.log_comprehensive_result(result)
                            else:
                                result['action'] = 'entry_failed'
                                result['error'] = 'Entry execution failed'
                                self.log(f"❌ ENTRY FAILED: {result['error']}")
                        else:
                            result['action'] = 'signal_skipped'
                            result['error'] = f'Only {len(positions)} valid options found (need 2)'
                            self.log(f"⏭️ SIGNAL SKIPPED: {result['error']}")
                else:
                    result['action'] = 'signal_skipped'
                    result['error'] = 'Entry not allowed (market timing/cooldown)'
                    self.log(f"⏭️ SIGNAL SKIPPED: {result['error']}")
            else:
                self.log(f"   ❌ No signal detected (move: {move_percent:.2f}%, threshold: {self.move_threshold:.2f}pts)")
        else:
            # In buffer period - skip entry but log the reason
            if in_open_buffer:
                result['action'] = 'skipped'
                result['error'] = f'Market open buffer: {time_since_open:.1f}min < {self.market_open_buffer_minutes}min'
            elif in_close_buffer:
                result['action'] = 'skipped'
                result['error'] = f'Market close buffer: {time_until_close:.1f}min < {self.market_close_buffer_minutes}min'
        
        # Log overall performance periodically (every 5 trades or when significant events occur)
        if self.total_trades % 5 == 0 and self.total_trades > 0:
            self.log_overall_performance()
        
        # Log summary for this processing cycle
        self.log(f"📋 CYCLE SUMMARY: {current_time.strftime('%H:%M:%S')} | Action: {result['action']} | Signals: {self.total_signals} | Trades: {self.total_trades} | Active: {len(self.active_trades)}")
        
        print(f"[ENGINE DEBUG] Row processing complete, action: {result['action']}")
        
        # Collect detailed info for every signal/trade
        log_entry = {
            'timestamp': result['timestamp'],
            'action': result['action'],
            'symbol': result['symbol'],
            'price': result['price'],
            'move_percent': result['move_percent'],
            'signal_detected': result['signal_detected'],
            'trades_active': result['trades_active'],
            'entry_cost': result.get('entry_cost'),
            'entry_commission': result.get('entry_commission'),
            'total_entry_cost': result.get('total_entry_cost'),
            'exit_value': result.get('exit_value'),
            'exit_commission': result.get('exit_commission'),
            'pnl': result.get('pnl'),
            'positions': [],
            'error': result.get('error'),
            'exit_reason': None,  # New field for exit reason
        }
        # Determine exit reason if this is an exit
        if result['action'] == 'exit':
            # Try to infer from error or context
            if result.get('error'):
                log_entry['exit_reason'] = result['error']
            elif hasattr(self, '_last_exit_reason') and self._last_exit_reason:
                log_entry['exit_reason'] = self._last_exit_reason
            else:
                log_entry['exit_reason'] = 'N/A'
        if result.get('positions'):
            for pos in result['positions']:
                log_entry['positions'].append({
                    'type': getattr(pos, 'type', None),
                    'strike': getattr(pos, 'strike', None),
                    'entry_price': getattr(pos, 'entry_price', None),
                    'contracts': getattr(pos, 'contracts', None),
                    'target': getattr(pos, 'target', None),
                    'symbol': getattr(pos, 'symbol', None),
                    'expiration_date': getattr(pos, 'expiration_date', None),
                    'entry_time': getattr(pos, 'entry_time', None),
                })
        self.signal_trade_log.append(log_entry)
        
        # Debug log for every action
        self.log(f"[DEBUG] process_row action: {result['action']}")
        # Log a signal for any action that means a real entry
        entry_actions = ['entry', 'trade_entered', 'buy', 'signal_approved']
        if (isinstance(result['action'], str) and (
                result['action'].lower().find('entry') != -1 or
                result['action'] in entry_actions)):
            self.trade_id_counter += 1
            trade_id = self.trade_id_counter
            # Assign trade_id to all positions in this entry
            if result.get('positions'):
                for pos in result['positions']:
                    setattr(pos, 'trade_id', trade_id)
            log_entry = {
                'trade_id': trade_id,
                'timestamp': result['timestamp'],
                'action': result['action'],
                'symbol': result['symbol'],
                'price': result['price'],
                'move_percent': result['move_percent'],
                'signal_detected': result['signal_detected'],
                'trades_active': result['trades_active'],
                'entry_cost': result.get('entry_cost'),
                'entry_commission': result.get('entry_commission'),
                'total_entry_cost': result.get('total_entry_cost'),
                'positions': [],
                'entry_time': result['timestamp'],
                'exit_time': None,
                'exit_value': None,
                'exit_commission': None,
                'pnl': None,
                'exit_reason': None,
            }
            if result.get('positions'):
                for pos in result['positions']:
                    pos_dict = {
                        'type': getattr(pos, 'type', None),
                        'strike': getattr(pos, 'strike', None),
                        'entry_price': getattr(pos, 'entry_price', None),
                        'contracts': getattr(pos, 'contracts', None),
                        'target': getattr(pos, 'target', None),
                        'symbol': getattr(pos, 'symbol', None),
                        'expiration_date': getattr(pos, 'expiration_date', None),
                        'entry_time': getattr(pos, 'entry_time', None),
                        'trade_id': getattr(pos, 'trade_id', None),
                    }
                    log_entry['positions'].append(pos_dict)
            self.signal_trade_log.append(log_entry)
            self.log(f"[DEBUG] Signal appended to analytics log. Total signals: {len(self.signal_trade_log)} (trade_id={trade_id})")
        elif result['action'] == 'exit':
            if self.signal_trade_log:
                # Try to match by trade_id from positions if available
                trade_id = None
                if result.get('positions') and len(result['positions']) > 0:
                    trade_id = getattr(result['positions'][0], 'trade_id', None)
                    # If not set on Position, try to infer from analytics log
                    if trade_id is None:
                        for entry in reversed(self.signal_trade_log):
                            if entry.get('exit_time') is None and entry.get('symbol') == result.get('symbol'):
                                trade_id = entry.get('trade_id')
                                break
                last_open = None
                if trade_id is not None:
                    for entry in reversed(self.signal_trade_log):
                        if entry.get('trade_id') == trade_id and entry.get('exit_time') is None:
                            last_open = entry
                            break
                else:
                    for entry in reversed(self.signal_trade_log):
                        if entry.get('exit_time') is None and entry.get('symbol') == result.get('symbol'):
                            last_open = entry
                            break
                if last_open is not None:
                    last_open['exit_time'] = result['timestamp']
                    last_open['exit_value'] = result.get('exit_value')
                    last_open['exit_commission'] = result.get('exit_commission')
                    last_open['pnl'] = result.get('pnl')
                    last_open['exit_reason'] = None
                    if result.get('error'):
                        last_open['exit_reason'] = result['error']
                    elif hasattr(self, '_last_exit_reason') and self._last_exit_reason:
                        last_open['exit_reason'] = self._last_exit_reason
                    else:
                        last_open['exit_reason'] = 'N/A'
        
        return result
    
    def update_price(self, current_time: datetime.datetime, price: float):
        """Update price log"""
        self.price_log.append((current_time, price))
        
        # Keep prices for window duration plus buffer
        cutoff_time = current_time - datetime.timedelta(seconds=self.price_window_seconds + 300)
        old_count = len(self.price_log)
        self.price_log = [p for p in self.price_log if p[0] >= cutoff_time]
        new_count = len(self.price_log)
        
        if old_count != new_count:
            self.log(f"🧹 Cleaned price log: {old_count} → {new_count} entries (removed {old_count - new_count} old entries)")
        
        self.log(f"📈 Price updated: {current_time.strftime('%H:%M:%S')} SPY=${price:.2f} (log size: {len(self.price_log)} entries)")
    
    def calculate_percentage_move(self, current_time: datetime.datetime) -> Tuple[float, float, float]:
        """Calculate percentage move within the window"""
        if len(self.price_log) < 2:
            return 0.0, 0.0, 0.0
        
        window_start = current_time - datetime.timedelta(seconds=self.price_window_seconds)
        window_prices = [p[1] for p in self.price_log if p[0] >= window_start and p[0] <= current_time]
        
        if len(window_prices) < 2:
            return 0.0, 0.0, 0.0
        
        absolute_move = max(window_prices) - min(window_prices)
        
        # Use configurable reference price type
        if self.reference_price_type == 'window_high_low':
            reference_price = min(window_prices)  # Use low as reference for percentage calculation
        elif self.reference_price_type == 'open':
            reference_price = window_prices[0]  # Use first price in window
        elif self.reference_price_type == 'prev_close':
            # Use the price before the window
            prev_prices = [p[1] for p in self.price_log if p[0] < window_start]
            reference_price = prev_prices[-1] if prev_prices else window_prices[0]
        elif self.reference_price_type == 'vwap':
            # Calculate VWAP (Volume Weighted Average Price) - simplified to average for now
            reference_price = sum(window_prices) / len(window_prices)
        else:
            # Default to window low
            reference_price = min(window_prices)
        
        if reference_price <= 0:
            return 0.0, absolute_move, reference_price
        
        percentage_move = (absolute_move / reference_price) * 100
        return percentage_move, absolute_move, reference_price
    
    def should_detect_signal(self, current_time: datetime.datetime) -> bool:
        """Detect signal using window-based absolute move (VIX-based)."""
        window_minutes = self.price_window_seconds // 60
        cooldown_minutes = self.cooldown_period // 60

        self.log(f"🔍 SIGNAL DETECTION CHECK at {current_time.strftime('%H:%M:%S')}")
        self.log(f"   ⚙️  Window: {window_minutes}min, Cooldown: {cooldown_minutes}min, Threshold: {self.move_threshold:.2f}pts")

        # Cooldown filter
        if self.last_flagged_time is not None:
            time_since_last = (current_time - self.last_flagged_time).total_seconds() / 60
            self.log(f"   ⏰ Last signal: {time_since_last:.1f}min ago")
            if time_since_last < cooldown_minutes:
                self.log(f"   ❌ Cooldown active: {time_since_last:.1f}min < {cooldown_minutes}min")
                return False
            else:
                self.log(f"   ✅ Cooldown expired: {time_since_last:.1f}min >= {cooldown_minutes}min")

        # Get window
        window_start = current_time - datetime.timedelta(minutes=window_minutes)
        window_prices = [p[1] for p in self.price_log if window_start <= p[0] <= current_time]
        
        self.log(f"   📊 Window: {window_start.strftime('%H:%M:%S')} to {current_time.strftime('%H:%M:%S')}")
        self.log(f"   📈 Price log entries: {len(self.price_log)} total")
        self.log(f"   🎯 Prices in window: {len(window_prices)} entries")
        
        if not window_prices:
            self.log(f"   ❌ No prices in window - insufficient data")
            return False
        
        # Log price range details
        high = max(window_prices)
        low = min(window_prices)
        if low == 0:
            self.log(f"   ❌ Invalid low price: {low}")
            return False
        
        absolute_move = high - low
        self.log(f"   📊 Price Range: High=${high:.2f}, Low=${low:.2f}, Move=${absolute_move:.2f}pts")
        self.log(f"   🎯 Threshold Check: {absolute_move:.2f} >= {self.move_threshold:.2f} = {absolute_move >= self.move_threshold}")
        
        if absolute_move >= self.move_threshold:
            self.last_flagged_time = current_time
            self.log(f"🎯 WINDOW SIGNAL DETECTED: {absolute_move:.2f}pt move in {window_minutes}min window (high={high:.2f}, low={low:.2f}) [Threshold: {self.move_threshold:.2f}]")
            return True
        else:
            self.log(f"   ❌ No signal: {absolute_move:.2f}pts < {self.move_threshold:.2f}pts threshold")
            return False
    
    def is_market_open(self, current_time: datetime.datetime) -> bool:
        """Check if market is open"""
        market_open_time = datetime.datetime.strptime(self.market_open, '%H:%M').time()
        market_close_time = datetime.datetime.strptime(self.market_close, '%H:%M').time()
        return market_open_time <= current_time.time() <= market_close_time
    
    def is_entry_allowed(self, current_time: datetime.datetime) -> bool:
        """Check if entry is allowed based on market timing and cooldown rules"""
        # Check if market is open
        if not self.is_market_open(current_time):
            return False
        
        # Check if enough time has passed since market open (15-minute buffer)
        market_open_time = datetime.datetime.strptime(self.market_open, '%H:%M').time()
        market_open_datetime = datetime.datetime.combine(current_time.date(), market_open_time)
        if current_time.tzinfo is not None and market_open_datetime.tzinfo is None:
            market_open_datetime = market_open_datetime.replace(tzinfo=current_time.tzinfo)
        time_since_open = (current_time - market_open_datetime).total_seconds() / 60
        
        if time_since_open < self.market_open_buffer_minutes:
            # Early signal detected - apply cooldown
            if self.last_early_signal_time is None:
                self.last_early_signal_time = current_time
                self.log(f"⏰ EARLY SIGNAL: Market open for {time_since_open:.1f}min < {self.market_open_buffer_minutes}min buffer. Applying {self.early_signal_cooldown_minutes}min cooldown.")
            return False
        
        # Check early signal cooldown
        if self.last_early_signal_time:
            time_since_early_signal = (current_time - self.last_early_signal_time).total_seconds() / 60
            if time_since_early_signal < self.early_signal_cooldown_minutes:
                self.log(f"⏳ EARLY SIGNAL COOLDOWN: {time_since_early_signal:.1f}min < {self.early_signal_cooldown_minutes}min cooldown period")
                return False
            else:
                # Cooldown expired, clear early signal tracking
                self.last_early_signal_time = None
                self.log(f"✅ Early signal cooldown expired. Ready for trading.")
        
        # Check if we're too close to market close (15-minute buffer)
        market_close_time = datetime.datetime.strptime(self.market_close, '%H:%M').time()
        market_close_datetime = datetime.datetime.combine(current_time.date(), market_close_time)
        if current_time.tzinfo is not None and market_close_datetime.tzinfo is None:
            market_close_datetime = market_close_datetime.replace(tzinfo=current_time.tzinfo)
        time_until_close = (market_close_datetime - current_time).total_seconds() / 60
        
        if time_until_close < self.market_close_buffer_minutes:
            self.log(f"⏰ TOO CLOSE TO CLOSE: {time_until_close:.1f}min until close < {self.market_close_buffer_minutes}min buffer")
            return False
        
        # Note: Regular cooldown between trades is already handled by signal detection cooldown
        # The last_flagged_time cooldown in should_detect_signal() provides sufficient spacing
        
        return True
    
    def check_daily_limits(self, current_time: datetime.datetime) -> bool:
        """Check daily limits"""
        current_date = current_time.date()
        
        if self.current_date != current_date:
            self.daily_trades = 0
            self.daily_pnl = 0.0
            self.current_date = current_date
            self.log(f"📅 New trading day: {current_date}")
        
        if self.daily_trades >= self.max_daily_trades:
            self.log(f"⚠️ Daily trade limit reached: {self.daily_trades}/{self.max_daily_trades}")
            return False
        
        if self.daily_pnl <= -self.max_daily_loss:
            self.log(f"⚠️ Daily loss limit reached: ${self.daily_pnl:.2f} <= -${self.max_daily_loss}")
            return False
        
        return True
    
    def find_valid_options(self, price: float, expiration: str, current_time: datetime.datetime) -> List[Position]:
        if self.mode == "backtest":
            return self.find_valid_options_backtest(price, expiration, current_time)
        # Original logic for live/paper
        if not self.data_provider:
            print("[ENGINE DEBUG] No data provider available")
            return []
        positions = []
        for attempt in range(1, self.max_retries + 1):
            self.log(f"[Attempt {attempt}] Fetching option chain...")
            try:
                if not current_time:
                    return []
                df_chain = self.data_provider.get_option_chain("SPY", expiration, current_time)
                if df_chain.empty or "option_type" not in df_chain.columns:
                    self.log("[ERROR] Option chain missing or invalid.")
                    continue
                # Remove detailed debug: columns, sample, unique values
                self.log(f"[DEBUG] Option chain loaded: {len(df_chain)} contracts")
                self.log(f"[DEBUG] Premium range: ${self.premium_min:.2f}-${self.premium_max:.2f}, Bid/Ask ratio: {self.option_bid_ask_ratio}")
                for option_type, option_label in [('C', 'call'), ('P', 'put')]:
                    df_side = df_chain[df_chain['option_type'] == option_label].copy()
                    self.log(f"[DEBUG] {option_type} side: {len(df_side)} contracts before filtering")
                    if df_side.empty:
                        continue
                    df_side['dist'] = abs(df_side['strike'] - price)
                    df_side = df_side.sort_values('dist')
                    # Filter for valid options in VIX-based premium range
                    valid = df_side[df_side['ask'].between(self.premium_min, self.premium_max)]
                    if not valid.empty:
                        valid = valid[valid['ask'] > valid['bid'] * self.option_bid_ask_ratio]
                    self.log(f"[DEBUG] {option_type} side: {len(valid)} contracts after filtering")
                    if valid.empty:
                        self.log(f"[DEBUG] No valid {option_type} options after filtering. Available strikes and prices:")
                        for _, row in df_side.iterrows():
                            self.log(f"    Strike={row['strike']}, Bid={row['bid']}, Ask={row['ask']}")
                        continue
                    for _, row in valid.iterrows():
                        self.log(f"[DEBUG] {option_type} candidate: Strike={row['strike']}, Bid={row['bid']}, Ask={row['ask']}")
                    row = valid.iloc[0]
                    strike = row['strike']
                    entry_price = row['ask']
                    contracts = int(self.risk_per_side // (entry_price * 100))
                    positions.append(Position(
                        type=option_type,
                        strike=strike,
                        entry_price=entry_price,
                        contracts=contracts,
                        target=entry_price * self.profit_target,
                        expiration_date=expiration,
                        entry_time=datetime.datetime.now()
                    ))
                if len(positions) == 2:
                    self.log(f"✅ Valid options found for both sides (premium range: ${self.premium_min:.2f}-${self.premium_max:.2f})")
                    break
                else:
                    self.log("⏳ Waiting for better option availability...")
            except Exception as e:
                self.log(f"[ERROR] Failed to fetch option chain: {str(e)}")
            if attempt < self.max_retries and self.retry_delay > 0:
                time.sleep(self.retry_delay)
        return positions
    
    def find_valid_options_backtest(self, price: float, expiration: str, current_time: datetime.datetime) -> list:
        """Backtest-optimized: Use Polygon minute-level OHLC endpoint for option prices at signal time, with pagination support."""
        print(f"[ENGINE DEBUG] find_valid_options_backtest called with price=${price:.2f}, expiration={expiration}")
        positions = []
        signal_time = current_time

        # Ensure signal_time is timezone-aware UTC
        if signal_time.tzinfo is None:
            signal_time = signal_time.replace(tzinfo=ZoneInfo("America/New_York"))

        # Convert to Unix millisecond timestamp
        signal_ts = int(signal_time.timestamp() * 1000)
        self.log(f"[=========] signal_time: {signal_time} (tzinfo={signal_time.tzinfo}), signal_ts: {signal_ts}")

        for attempt in range(1, self.max_retries + 1):
            self.log(f"[Attempt {attempt}] Fetching option contracts from file...")
            try:
                # 1. Load contracts file (OPT_PATH)
                opt_path = self.config.get('OPT_PATH')
                contracts_df = pd.read_parquet(opt_path)
                # 2. Filter for date/expiration
                contracts_df = contracts_df[(contracts_df['date'] == expiration) & (contracts_df['expiration_date'] == expiration) & (contracts_df['underlying_ticker'] == 'SPY')]
                if contracts_df.empty:
                    self.log("[ERROR] No contracts found for date/expiration.")
                    continue
                # 3. For each side (call/put), select ATM contracts
                for option_type, contract_type in [('C', 'call'), ('P', 'put')]:
                    df_side = contracts_df[contracts_df['contract_type'] == contract_type]
                    if df_side.empty:
                        self.log(f"[WARN] No contracts for {contract_type} side.")
                        continue
                    # Find ATM strike
                    df_side['strike_diff'] = (df_side['strike_price'] - price).abs()
                    df_side = df_side.sort_values('strike_diff')
                    # Only consider top 5 closest strikes
                    for _, row in df_side.head(5).iterrows():
                        ticker = row['ticker']
                        strike = row['strike_price']
                        self.log(f"[CONTRACT] Considering {ticker} (strike={strike}, type={option_type})")
                        # 4. Fetch minute OHLC for this contract for the backtest date, with pagination
                        api_key = self.config.get('POLYGON_API_KEY', '')
                        date_str = signal_time.strftime('%Y-%m-%d')
                        base_url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/minute/{date_str}/{date_str}"
                        params = {
                            "adjusted": "true",
                            "sort": "asc",
                            "limit": 50000,
                            "apiKey": api_key
                        }
                        all_bars = []
                        next_url = None
                        page_count = 1
                        for ohlc_attempt in range(3):
                            try:
                                self.log(f"[PAGINATION] Start fetching minute bars for {ticker} on {date_str}")
                                while True:
                                    if next_url:
                                        # Ensure apiKey is present in next_url
                                        parsed = urllib.parse.urlparse(next_url)
                                        query = dict(urllib.parse.parse_qsl(parsed.query))
                                        if 'apiKey' not in query:
                                            query['apiKey'] = api_key
                                            next_url = parsed._replace(query=urllib.parse.urlencode(query)).geturl()
                                        self.log(f"[QUOTES] Fetching page {page_count} for {ticker} from {next_url}")
                                        resp = requests.get(next_url)
                                    else:
                                        self.log(f"[QUOTES] Fetching page {page_count} for {ticker} from {base_url}")
                                        resp = requests.get(base_url, params=params)
                                    if resp.status_code == 429:
                                        self.log(f"[RATE LIMIT] Hit Polygon rate limit, sleeping 15s...")
                                        time.sleep(15)
                                        continue
                                    elif resp.status_code != 200:
                                        self.log(f"[ERROR] Polygon minute OHLC error for {ticker}: {resp.status_code} {resp.text}")
                                        break
                                    data = resp.json()
                                    if 'results' in data and data['results']:
                                        all_bars.extend(data['results'])
                                    next_url = data.get('next_url')
                                    if not next_url:
                                        break
                                    page_count += 1
                                    time.sleep(0.05)
                                self.log(f"[PAGINATION] Done fetching minute bars for {ticker}. Total bars: {len(all_bars)}")
                                if not all_bars:
                                    self.log(f"[NO DATA] No minute OHLC data for {ticker} on {date_str}")
                                    break
                                # Find the bar with timestamp <= signal_ts, closest to signal_ts
                                if all_bars:
                                    min_bar_ts = min(bar['t'] for bar in all_bars)
                                    max_bar_ts = max(bar['t'] for bar in all_bars)
                                else:
                                    min_bar_ts = max_bar_ts = None
                                bars_before = [bar for bar in all_bars if bar['t'] <= signal_ts]
                                if not bars_before:
                                    self.log(f"[NO BAR] No minute bar before or at signal time for {ticker}. signal_ts={signal_ts}, earliest={min_bar_ts}, latest={max_bar_ts}")
                                    break
                                best_bar = max(bars_before, key=lambda bar: bar['t'])
                                option_price = best_bar.get('c')
                                if option_price is None:
                                    self.log(f"[NO PRICE] No close price for {ticker} at {best_bar['t']}")
                                    break
                                self.log(f"[SELECTED] {ticker} selected bar: ts={best_bar['t']} close={option_price}")
                                pos = {
                                    'option_type': option_type,
                                    'strike': strike,
                                    'bid': option_price,  # Use close as both bid/ask for now
                                    'ask': option_price,
                                    'expiration_date': expiration,
                                    'ticker': ticker,
                                    'contract_type': contract_type
                                }
                                positions.append(pos)
                                self.log(f"[OHLC] {ticker} {date_str} minute={best_bar['t']} close={option_price}")
                                break
                            except Exception as e:
                                self.log(f"[EXCEPTION] Error fetching minute OHLC for {ticker}: {e}")
                                time.sleep(1)
                        time.sleep(0.05)  # Throttle requests
                # After collecting all candidate positions, pick the best call and best put
                best_call = None
                best_put = None
                call_candidates = [p for p in positions if p['option_type'] == 'C']
                put_candidates = [p for p in positions if p['option_type'] == 'P']
                if call_candidates:
                    best_call = min(call_candidates, key=lambda p: abs(p['strike'] - price))
                if put_candidates:
                    best_put = min(put_candidates, key=lambda p: abs(p['strike'] - price))
                final_positions = []
                if best_call:
                    from core.trading_engine import Position
                    final_positions.append(Position(
                        type=best_call['option_type'],
                        strike=best_call['strike'],
                        entry_price=best_call['ask'],
                        contracts=1,  # or use your logic for contracts
                        target=best_call['ask'],  # or your logic for target
                        symbol='SPY',
                        expiration_date=best_call['expiration_date'],
                        entry_time=None
                    ))
                if best_put:
                    from core.trading_engine import Position
                    final_positions.append(Position(
                        type=best_put['option_type'],
                        strike=best_put['strike'],
                        entry_price=best_put['ask'],
                        contracts=1,  # or use your logic for contracts
                        target=best_put['ask'],  # or your logic for target
                        symbol='SPY',
                        expiration_date=best_put['expiration_date'],
                        entry_time=None
                    ))
                if len(final_positions) == 2:
                    return final_positions
                else:
                    self.log(f"[WARN] Only found {len(final_positions)} valid options (call/put), retrying...")
                    positions = []
                    # If we didn't find a bar, increment signal_time for the next attempt
                    signal_time = signal_time + datetime.timedelta(minutes=1)
                    signal_ts = int(signal_time.timestamp() * 1000)
                    time.sleep(self.retry_delay)
            except Exception as e:
                self.log(f"[ERROR] Backtest option selection failed: {e}")
                time.sleep(self.retry_delay)
        return []
    
    def execute_entry(self, positions: List[Position], expiration: str) -> bool:
        """Execute entry orders and immediately place limit sell orders"""
        if not self.order_executor:
            return False
        try:
            for pos in positions:
                # Place entry order (market buy)
                entry_order_id = self.order_executor.place_order(
                    pos.type, pos.strike, pos.contracts,
                    action="BUY", expiration_date=expiration
                )
                pos.entry_order_id = entry_order_id
                
                # Calculate limit sell price using VIX-based profit target
                profit_multiplier = getattr(self, 'profit_target', 1.35)  # Default to 1.35 if not set
                limit_price = round(pos.entry_price * profit_multiplier, 2)
                pos.limit_price = limit_price
                
                # Place limit sell order immediately
                limit_order_id = self.order_executor.place_limit_order(
                    pos.type, pos.strike, pos.contracts,
                    action="SELL", expiration_date=expiration, limit_price=limit_price
                )
                pos.limit_order_id = limit_order_id
                
                # Track the limit order only if it was successfully placed
                if limit_order_id != "FAILED":
                    self.active_limit_orders[limit_order_id] = {
                        'position': pos,
                        'trade_positions': positions,  # Reference to full trade
                        'expiration': expiration,
                        'target_price': limit_price,
                        'placed_time': datetime.datetime.now()
                    }
                
                self.log(f"ENTRY {pos.type} Strike={pos.strike} Qty={pos.contracts} Price={pos.entry_price:.2f} EntryOrderID={entry_order_id}")
                
                if limit_order_id != "FAILED":
                    self.log(f"🎯 LIMIT SELL ORDER PLACED: {pos.type} Strike={pos.strike} @ ${limit_price:.2f} ({profit_multiplier:.2f}x target) LimitOrderID={limit_order_id}")
                else:
                    self.log(f"❌ LIMIT SELL ORDER FAILED: {pos.type} Strike={pos.strike} @ ${limit_price:.2f} - will use manual exits only")
            
            self.total_trades += 1  # Increment total trades on entry
            return True
        except Exception as e:
            self.log(f"[ERROR] Entry execution failed: {str(e)}")
            return False
    
    def execute_exit(self, positions: List[Position], expiration: str) -> bool:
        """Execute exit orders and cancel any pending limit orders"""
        if not self.order_executor:
            return False
        try:
            # First, cancel all limit orders for this trade
            self.cancel_trade_limit_orders(positions)
            
            # Then place market sell orders
            for pos in positions:
                order_id = self.order_executor.place_order(
                    pos.type, pos.strike, pos.contracts,
                    action="SELL", expiration_date=pos.expiration_date
                )
                self.log(f"EXIT {pos.type} Strike={pos.strike} Qty={pos.contracts} OrderID={order_id}")
            self.total_trades += 1  # Increment total trades on exit
            return True
        except Exception as e:
            self.log(f"[ERROR] Exit execution failed: {str(e)}")
            return False
    
    def check_combined_profit_exit(self, positions: List[Position], expiration: str, current_time: datetime.datetime) -> bool:
        """Exit if combined P&L of the position reaches the VIX-based profit target (self.profit_target multiplier)."""
        if not self.data_provider or not positions:
            return False
        try:
            # Calculate total entry cost (including commission)
            entry_cost = sum(pos.entry_price * 100 * pos.contracts for pos in positions)
            entry_commission = self.calculate_total_trade_cost(positions, is_exit=False)
            total_entry_cost = entry_cost + entry_commission

            # Get current exit value (using bid prices)
            exit_value = self.calculate_exit_value(positions, expiration, current_time)
            exit_commission = self.calculate_total_trade_cost(positions, is_exit=True)
            total_exit_value = exit_value - exit_commission

            # Calculate profit target value (VIX-based multiplier)
            target_value = total_entry_cost * self.profit_target
            if total_exit_value >= target_value:
                profit_percentage = ((total_exit_value - total_entry_cost) / total_entry_cost) * 100
                self.log(f"🎯 COMBINED PROFIT TARGET HIT: Exit Value ${total_exit_value:.2f} >= Target ${target_value:.2f} (Profit: {profit_percentage:.1f}%)")
                self.log(f"   Entry Cost: ${total_entry_cost:.2f}, Exit Value: ${total_exit_value:.2f}")
                return True
            else:
                profit_percentage = ((total_exit_value - total_entry_cost) / total_entry_cost) * 100
                self.log(f"⏳ Combined profit check: Exit Value ${total_exit_value:.2f} < Target ${target_value:.2f} (Profit: {profit_percentage:.1f}%)")
            return False
        except Exception as e:
            self.log(f"❌ Error checking combined profit exit: {e}")
            return False

    def check_limit_order_fills(self, current_time: datetime.datetime):
        """Check if any limit orders have been filled and handle automatic closure"""
        # Only check every few seconds to avoid hitting API limits
        if (self.last_order_check_time is None or 
            (current_time - self.last_order_check_time).total_seconds() >= self.order_check_interval):
            
            self.last_order_check_time = current_time
            
            if not self.active_limit_orders:
                return
            
            self.log(f"🔍 CHECKING LIMIT ORDERS: {len(self.active_limit_orders)} active orders")
            
            filled_orders = []
            
            for order_id, order_info in list(self.active_limit_orders.items()):
                try:
                    status = self.order_executor.get_order_status(order_id)
                    
                    # Check if order is filled (completely or partially)
                    if status.get('status', '').lower() in ['filled', 'partially_filled'] or status.get('filled_quantity', 0) > 0:
                        filled_orders.append(order_id)
                        filled_position = order_info['position']
                        trade_positions = order_info['trade_positions']
                        expiration = order_info['expiration']
                        
                        self.log(f"🎯 LIMIT ORDER FILLED! {filled_position.type} Strike={filled_position.strike} @ ${status.get('avg_fill_price', filled_position.limit_price):.2f}")
                        self.log(f"🎯 Order Status: {status.get('status')} | Filled: {status.get('filled_quantity', 0)}/{filled_position.contracts}")
                        
                        # Send Telegram limit order fill alert
                        fill_price = status.get('avg_fill_price', filled_position.limit_price)
                        profit_percent = ((fill_price - filled_position.entry_price) / filled_position.entry_price) * 100 if filled_position.entry_price > 0 else 0
                        trade_id = getattr(filled_position, 'trade_id', 'N/A')
                        
                        limit_fill_data = {
                            'fill_time': current_time,
                            'option_type': filled_position.type,
                            'strike': filled_position.strike,
                            'fill_price': fill_price,
                            'profit_percent': profit_percent,
                            'trade_id': trade_id,
                            'filled_position': filled_position,
                            'order_status': status,
                            'filled_quantity': status.get('filled_quantity', 0),
                            'timing_status': self.get_market_timing_status(current_time)
                        }
                        self._send_limit_hit_alert(limit_fill_data)
                        
                        # Find trade index to remove
                        trade_index = None
                        for i, trade in enumerate(self.active_trades):
                            if any(pos.trade_id == filled_position.trade_id for pos in trade if hasattr(pos, 'trade_id')):
                                trade_index = i
                                break
                        
                        if trade_index is not None:
                            # Cancel all other limit orders for this trade
                            self.cancel_trade_limit_orders(trade_positions, exclude_order_id=order_id)
                            
                            # Market sell the remaining position(s)
                            remaining_positions = [pos for pos in trade_positions if pos.limit_order_id != order_id]
                            if remaining_positions:
                                self.log(f"📈 MARKET SELLING REMAINING POSITIONS: {len(remaining_positions)} positions")
                                for remaining_pos in remaining_positions:
                                    try:
                                        market_order_id = self.order_executor.place_order(
                                            remaining_pos.type, remaining_pos.strike, remaining_pos.contracts,
                                            action="SELL", expiration_date=expiration
                                        )
                                        self.log(f"📈 MARKET SELL: {remaining_pos.type} Strike={remaining_pos.strike} OrderID={market_order_id}")
                                    except Exception as e:
                                        self.log(f"❌ Failed to market sell remaining position: {e}")
                            
                            # Calculate P&L for the filled trade
                            entry_cost = sum(pos.entry_price * 100 * pos.contracts for pos in trade_positions)
                            entry_commission = self.calculate_total_trade_cost(trade_positions, is_exit=False)
                            
                            # For the filled position, use the actual fill price
                            filled_value = status.get('avg_fill_price', filled_position.limit_price) * 100 * filled_position.contracts
                            
                            # For remaining positions, estimate exit value at current bid
                            remaining_exit_value = 0
                            if remaining_positions:
                                remaining_exit_value = self.calculate_exit_value(remaining_positions, expiration, current_time)
                            
                            total_exit_value = filled_value + remaining_exit_value
                            exit_commission = self.calculate_total_trade_cost(trade_positions, is_exit=True)
                            
                            trade_pnl = total_exit_value - entry_cost - entry_commission - exit_commission
                            
                            self.log(f"✅ LIMIT ORDER TRADE COMPLETE: Entry=${entry_cost:.2f} Exit=${total_exit_value:.2f} P&L=${trade_pnl:.2f}")
                            
                            # Send Telegram trade exit alert
                            trade_id = getattr(filled_position, 'trade_id', trade_index + 1) if hasattr(filled_position, 'trade_id') else trade_index + 1
                            entry_time = self.trade_entry_times[trade_index] if trade_index is not None and trade_index < len(self.trade_entry_times) else current_time
                            holding_time_minutes = (current_time - entry_time).total_seconds() / 60
                            holding_time = f"{holding_time_minutes:.1f} minutes"
                            
                            exit_data = {
                                'trade_id': trade_id,
                                'exit_time': current_time,
                                'holding_time': holding_time,
                                'positions': self._positions_to_dict(trade_positions),
                                'exit_reason': 'Limit Order Fill',
                                'entry_cost': entry_cost,
                                'entry_commission': entry_commission,
                                'total_entry_cost': entry_cost + entry_commission,
                                'exit_value': total_exit_value,
                                'exit_commission': exit_commission,
                                'pnl': trade_pnl,
                                'daily_pnl': self.daily_pnl,
                                'daily_trades': self.daily_trades,
                                'total_trades': self.total_trades,
                                'filled_position': filled_position,
                                'fill_price': status.get('avg_fill_price', filled_position.limit_price),
                                'timing_status': self.get_market_timing_status(current_time)
                            }
                            self._send_exit_alert(exit_data)
                            
                            # Update metrics
                            self.update_daily_pnl(trade_pnl)
                            self.update_trade_metrics(trade_pnl)
                            
                            # Remove the trade from active trades
                            self.active_trades.pop(trade_index)
                            self.trade_entry_times.pop(trade_index)
                            
                        else:
                            self.log(f"⚠️ Could not find trade index for filled limit order {order_id}")
                
                except Exception as e:
                    self.log(f"❌ Error checking limit order {order_id}: {e}")
                    # If we can't check the order status, keep it in tracking for now
                    # It will be cleaned up in finish() if needed
            
            # Remove filled orders from tracking
            for order_id in filled_orders:
                if order_id in self.active_limit_orders:
                    del self.active_limit_orders[order_id]
    
    def cancel_trade_limit_orders(self, trade_positions: List[Position], exclude_order_id: str = None):
        """Cancel all limit orders for a trade, optionally excluding one order"""
        for pos in trade_positions:
            if pos.limit_order_id and pos.limit_order_id != exclude_order_id:
                try:
                    if self.order_executor.cancel_order(pos.limit_order_id):
                        self.log(f"✅ CANCELLED LIMIT ORDER: {pos.type} Strike={pos.strike} OrderID={pos.limit_order_id}")
                        # Remove from tracking
                        if pos.limit_order_id in self.active_limit_orders:
                            del self.active_limit_orders[pos.limit_order_id]
                    else:
                        self.log(f"⚠️ FAILED TO CANCEL LIMIT ORDER: {pos.limit_order_id}")
                except Exception as e:
                    self.log(f"❌ Error cancelling limit order {pos.limit_order_id}: {e}")

    def check_all_exit_conditions(self, current_time: datetime.datetime) -> List[int]:
        trades_to_exit = []
        self._last_exit_reason = None  # Reset before checking
        # Check emergency stop-loss first (highest priority - affects all trades)
        if self.check_emergency_stop_loss(current_time):
            self.log(f"🚨 EMERGENCY STOP LOSS: Forcing exit of all {len(self.active_trades)} active trades")
            return list(range(len(self.active_trades)))
        # Check market close buffer exit (force exit 15 minutes before close)
        market_close_time = datetime.datetime.strptime(self.market_close, '%H:%M').time()
        market_close_datetime = datetime.datetime.combine(current_time.date(), market_close_time)
        if current_time.tzinfo is not None and market_close_datetime.tzinfo is None:
            market_close_datetime = market_close_datetime.replace(tzinfo=current_time.tzinfo)
        time_until_close = (market_close_datetime - current_time).total_seconds() / 60
        if time_until_close < self.market_close_buffer_minutes:
            self.log(f"⏰ MARKET CLOSE BUFFER EXIT: {time_until_close:.1f}min until close < {self.market_close_buffer_minutes}min buffer. Forcing exit of all trades.")
            self._last_exit_reason = 'market close'
            return list(range(len(self.active_trades)))
        for i, (trade_positions, entry_time) in enumerate(zip(self.active_trades, self.trade_entry_times)):
            if trade_positions and trade_positions[0].expiration_date:
                expiration = trade_positions[0].expiration_date
                if self.check_stop_loss(trade_positions, expiration, current_time):
                    trades_to_exit.append(i)
                    self._last_exit_reason = 'stop loss'
                    # Update analytics log immediately for stop loss
                    self._update_analytics_exit(trade_positions, current_time, 'stop loss')
                    continue
                if self.check_combined_profit_exit(trade_positions, expiration, current_time):
                    trades_to_exit.append(i)
                    self._last_exit_reason = 'profit target'
                    # Update analytics log immediately for profit target
                    self._update_analytics_exit(trade_positions, current_time, 'profit target')
        return trades_to_exit

    def _update_analytics_exit(self, trade_positions, exit_time, exit_reason):
        # Helper to update analytics log for a specific exit reason
        trade_id = None
        if trade_positions and hasattr(trade_positions[0], 'trade_id'):
            trade_id = getattr(trade_positions[0], 'trade_id', None)
        if trade_id is not None:
            for entry in reversed(self.signal_trade_log):
                if entry.get('trade_id') == trade_id and entry.get('exit_time') is None:
                    entry['exit_time'] = exit_time
                    # These values may be None if not available, but set them if you have them
                    entry['exit_value'] = None
                    entry['exit_commission'] = None
                    entry['pnl'] = None
                    entry['exit_reason'] = exit_reason
                    break

    def increment_daily_trades(self):
        """Increment daily trade count"""
        self.daily_trades += 1
        self.log(f"📊 Daily trade count: {self.daily_trades}/{self.max_daily_trades}")
    
    def update_daily_pnl(self, trade_pnl: float):
        """Update daily PnL"""
        self.daily_pnl += trade_pnl
        self.log(f"📊 Daily P&L: ${self.daily_pnl:.2f}")
    
    def update_trade_metrics(self, trade_pnl: float):
        """Update overall trade metrics"""
        self.total_pnl += trade_pnl
        if trade_pnl > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1
    
    def get_status(self) -> Dict:
        """Get current engine status"""
        return {
            'active_trades_count': len(self.active_trades),
            'total_signals': self.total_signals,
            'total_trades': self.total_trades,
            'total_pnl': self.total_pnl,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
            'daily_trades': self.daily_trades,
            'daily_pnl': self.daily_pnl,
            'last_trade_time': self.last_trade_time,
            'last_flagged_time': self.last_flagged_time,
            'last_early_signal_time': self.last_early_signal_time,
            'market_open_buffer_minutes': self.market_open_buffer_minutes,
            'market_close_buffer_minutes': self.market_close_buffer_minutes,
            'early_signal_cooldown_minutes': self.early_signal_cooldown_minutes,
            'stop_loss_percentage': self.stop_loss_percentage,
            'emergency_stop_loss': self.emergency_stop_loss
        }
    
    def get_summary(self) -> Dict:
        """Get trading summary"""
        return {
            'mode': self.mode,
            'total_signals': self.total_signals,
            'total_trades': self.total_trades,
            'total_pnl': self.total_pnl,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0,
            'avg_trade_pnl': (self.total_pnl / self.total_trades) if self.total_trades > 0 else 0,
            'active_trades': len(self.active_trades),
            'log_file': self.log_file,
            'market_timing': {
                'open_buffer_minutes': self.market_open_buffer_minutes,
                'close_buffer_minutes': self.market_close_buffer_minutes,
                'early_signal_cooldown_minutes': self.early_signal_cooldown_minutes
            },
            'risk_management': {
                'stop_loss_percentage': self.stop_loss_percentage,
                'emergency_stop_loss': self.emergency_stop_loss,
                'max_daily_loss': self.max_daily_loss
            }
        }

    def log_comprehensive_result(self, result: Dict):
        """Log comprehensive result for each processed row"""
        timestamp = result['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate market timing info
        current_time = result['timestamp']
        market_open_time = datetime.datetime.strptime(self.market_open, '%H:%M').time()
        market_open_datetime = datetime.datetime.combine(current_time.date(), market_open_time)
        if current_time.tzinfo is not None and market_open_datetime.tzinfo is None:
            market_open_datetime = market_open_datetime.replace(tzinfo=current_time.tzinfo)
        time_since_open = (current_time - market_open_datetime).total_seconds() / 60
        
        market_close_time = datetime.datetime.strptime(self.market_close, '%H:%M').time()
        market_close_datetime = datetime.datetime.combine(current_time.date(), market_close_time)
        if current_time.tzinfo is not None and market_close_datetime.tzinfo is None:
            market_close_datetime = market_close_datetime.replace(tzinfo=current_time.tzinfo)
        time_until_close = (market_close_datetime - current_time).total_seconds() / 60
        
        # Build detailed log message
        log_parts = [
            f"⏰ {timestamp}",
            f"💰 {result['symbol']} ${result['price']:.2f}",
            f"📈 Move: {result['move_percent']:.2f}%",
            f"🎯 Signal: {'YES' if result['signal_detected'] else 'NO'}",
            f"📊 Action: {result['action'].upper()}",
            f"🔄 Active Trades: {result['trades_active']}",
            f"⏰ Market: +{time_since_open:.1f}min / -{time_until_close:.1f}min"
        ]
        
        # Add early signal status
        if self.last_early_signal_time:
            time_since_early = (current_time - self.last_early_signal_time).total_seconds() / 60
            log_parts.append(f"🔄 Early cooldown: {time_since_early:.1f}min")
        
        # Add action-specific details
        if result['action'] == 'entry':
            log_parts.extend([
                f"💵 Entry Cost: ${result['entry_cost']:.2f}",
                f"💸 Commission: ${result.get('entry_commission', 0):.2f}",
                f"💰 Total Cost: ${result.get('total_entry_cost', result['entry_cost']):.2f}",
                f"📋 Positions: {len(result['positions'])}"
            ])
            if result.get('positions'):
                for i, pos in enumerate(result['positions']):
                    log_parts.append(f"   {i+1}. {pos.type} {pos.strike} @ ${pos.entry_price:.2f} x {pos.contracts}")
        
        elif result['action'] == 'exit':
            log_parts.extend([
                f"💵 Exit Value: ${result['exit_value']:.2f}",
                f"💸 Exit Commission: ${result.get('exit_commission', 0):.2f}",
                f"📈 P&L: ${result['pnl']:.2f}",
                f"📋 Positions: {len(result['positions'])}"
            ])
            if result.get('positions'):
                for i, pos in enumerate(result['positions']):
                    log_parts.append(f"   {i+1}. {pos.type} {pos.strike} @ ${pos.entry_price:.2f} x {pos.contracts}")
        
        elif result['action'] in ['entry_failed', 'exit_failed']:
            log_parts.append(f"❌ Error: {result.get('error', 'Unknown error')}")
        
        elif result['action'] == 'signal_skipped':
            log_parts.append(f"⏭️ Skipped: {result.get('error', 'Unknown reason')}")
        
        elif result['action'] == 'skipped':
            log_parts.append(f"⏰ Buffer Skip: {result.get('error', 'Buffer period')}")
        
        # Add daily and overall metrics
        log_parts.extend([
            f"📅 Daily Trades: {self.daily_trades}/{self.max_daily_trades}",
            f"📊 Daily P&L: ${self.daily_pnl:.2f}",
            f"🏆 Total Trades: {self.total_trades}",
            f"💰 Total P&L: ${self.total_pnl:.2f}",
            f"📈 Win Rate: {(self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0:.1f}%"
        ])
        
        # Log the comprehensive result
        self.log(" | ".join(log_parts))

    def log_overall_performance(self):
        """Log overall trading performance"""
        self.log(f"📊 Overall Performance:")
        self.log(f"🏆 Total Trades: {self.total_trades}")
        self.log(f"💰 Total P&L: ${self.total_pnl:.2f}")
        self.log(f"📈 Win Rate: {(self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0:.1f}%")
    
    def log_final_results(self):
        """Log comprehensive final results when backtest/trading session ends"""
        self.log("=" * 80)
        self.log("🏁 FINAL TRADING RESULTS")
        self.log("=" * 80)
        
        # Overall performance
        self.log(f"📊 Trading Mode: {self.mode.upper()}")
        self.log(f"🎯 Total Signals Detected: {self.total_signals}")
        self.log(f"🏆 Total Trades Executed: {self.total_trades}")
        self.log(f"💰 Total P&L: ${self.total_pnl:.2f}")
        
        if self.total_trades > 0:
            # Fix win rate calculation: only use closed trades
            closed_trades = [entry for entry in self.signal_trade_log if entry.get('exit_time')]
            num_wins = sum(1 for entry in closed_trades if entry.get('pnl') is not None and entry.get('pnl') > 0)
            num_losses = sum(1 for entry in closed_trades if entry.get('pnl') is not None and entry.get('pnl') <= 0)
            win_rate = (num_wins / (num_wins + num_losses) * 100) if (num_wins + num_losses) > 0 else 0.0
            # Print correct win rate and trade counts in summary
            self.log(f"📈 Win Rate: {win_rate:.1f}%")
            self.log(f"✅ Winning Trades: {num_wins}")
            self.log(f"❌ Losing Trades: {num_losses}")
            self.log(f"📊 Average Trade P&L: ${(self.total_pnl / self.total_trades):.2f}")
        
        # Daily performance
        self.log(f"📅 Daily Trades: {self.daily_trades}/{self.max_daily_trades}")
        self.log(f"📊 Daily P&L: ${self.daily_pnl:.2f}")
        
        # Active positions
        self.log(f"🔄 Active Trades: {len(self.active_trades)}")
        if self.active_trades:
            for i, (positions, entry_time) in enumerate(zip(self.active_trades, self.trade_entry_times)):
                import datetime as dt
                # Handle timezone-aware datetime subtraction
                current_time = dt.datetime.now()
                if entry_time.tzinfo is not None and current_time.tzinfo is None:
                    # If entry_time is timezone-aware but current_time is not, make current_time timezone-aware
                    current_time = current_time.replace(tzinfo=entry_time.tzinfo)
                elif entry_time.tzinfo is None and current_time.tzinfo is not None:
                    # If current_time is timezone-aware but entry_time is not, make entry_time timezone-aware
                    entry_time = entry_time.replace(tzinfo=current_time.tzinfo)
                
                hold_time = (current_time - entry_time).total_seconds() / 60
                self.log(f"   Trade {i+1}: {len(positions)} positions, held for {hold_time:.1f} minutes")
        
        # Log files
        self.log(f"📝 Log File: {self.log_file}")
        self.log("=" * 80)
        # Append detailed signal/trade analytics in a professional, narrative style
        self.log("================ DETAILED SIGNAL/TRADE ANALYTICS ================")
        filtered_signals = [entry for entry in self.signal_trade_log if 'entry_time' in entry]
        if not filtered_signals:
            self.log("No signals (entries) detected during this backtest.")
        else:
            for idx, entry in enumerate(filtered_signals, 1):
                entry_time = entry.get('entry_time', 'N/A')
                self.log(f"Signal {idx} (Trade ID: {entry.get('trade_id', 'N/A')}):")
                self.log(f"  Detection Time: {entry_time}")
                detection_cond = f"Move {entry.get('move_percent', 0):.2f}% in window, signal detected"
                self.log(f"  Detection Condition: {detection_cond}")
                if entry['positions']:
                    self.log(f"  Selected Options:")
                    for pos in entry['positions']:
                        self.log(f"    - {pos.get('type', '').upper()} {pos.get('symbol', '')} {pos.get('strike', '')} Exp: {pos.get('expiration_date', '')} Entry: ${pos.get('entry_price', '')} Contracts: {pos.get('contracts', '')}")
                else:
                    self.log(f"  Selected Options: None")
                self.log(f"  Entry Time: {entry_time}")
                self.log(f"  Entry Cost: ${entry.get('entry_cost', '')}")
                self.log(f"  Commission: ${entry.get('entry_commission', '')}")
                self.log(f"  Total Entry Cost: ${entry.get('total_entry_cost', '')}")
                if entry.get('exit_time'):
                    self.log(f"  Exit Time: {entry.get('exit_time', 'N/A')}")
                    self.log(f"  Exit Value: ${entry.get('exit_value', '')}")
                    self.log(f"  Exit Commission: ${entry.get('exit_commission', '')}")
                    self.log(f"  P&L: ${entry.get('pnl', 'N/A')}")
                    pnl = entry.get('pnl')
                    if pnl is not None:
                        result_str = 'WIN' if pnl > 0 else 'LOSS'
                        self.log(f"  Result: {result_str}")
                    try:
                        import datetime
                        entry_time_dt = entry.get('entry_time')
                        exit_time_dt = entry.get('exit_time')
                        if isinstance(entry_time_dt, str):
                            entry_time_dt = datetime.datetime.fromisoformat(str(entry_time_dt))
                        if isinstance(exit_time_dt, str):
                            exit_time_dt = datetime.datetime.fromisoformat(str(exit_time_dt))
                        holding = exit_time_dt - entry_time_dt
                        self.log(f"  Holding Time: {holding}")
                    except Exception:
                        pass
                    self.log(f"  Exit Reason: {entry.get('exit_reason', 'N/A')}")
                else:
                    self.log(f"  Exit: Still Open or Not Exited During Backtest")
                    self.log(f"  P&L: N/A")
                    self.log(f"  Result: OPEN")
                self.log(f"  Trades Active at Entry: {entry.get('trades_active', '')}")
                self.log(f"  Market Price at Entry: ${entry.get('price', '')}")
                self.log(f"  Symbol: {entry.get('symbol', '')}")
                self.log(f"  ---")
        self.log("=" * 80)
        
        self.log("=" * 80)

    def finish(self):
        """Call this when trading is finished (end of data or user interrupt) to log final results."""
        # Cancel any remaining limit orders before finishing
        if self.active_limit_orders:
            self.log(f"🧹 CLEANUP: Cancelling {len(self.active_limit_orders)} remaining limit orders...")
            for order_id, order_info in list(self.active_limit_orders.items()):
                try:
                    # First check if order is still cancellable
                    status = self.order_executor.get_order_status(order_id)
                    if status.get('status', '').lower() in ['filled', 'cancelled']:
                        self.log(f"🔍 CLEANUP: Order {order_id} already {status.get('status', 'unknown')}, skipping cancel")
                        continue
                        
                    if self.order_executor.cancel_order(order_id):
                        self.log(f"✅ CLEANUP: Cancelled limit order {order_id}")
                    else:
                        self.log(f"⚠️ CLEANUP: Could not cancel limit order {order_id}")
                except Exception as e:
                    # Don't log as error if order was already filled/cancelled
                    if "400" in str(e):
                        self.log(f"🔍 CLEANUP: Order {order_id} likely already filled/cancelled")
                    else:
                        self.log(f"❌ CLEANUP ERROR: Failed to cancel {order_id}: {e}")
            
            # Clear the tracking
            self.active_limit_orders.clear()
            self.log(f"🧹 CLEANUP COMPLETE: All limit orders processed")
        
        # Send system stop alert to Telegram
        self._send_system_stop_alert()
        
        self.log_final_results()

    def get_market_timing_status(self, current_time: datetime.datetime) -> Dict:
        """Get current market timing status for debugging"""
        market_open_time = datetime.datetime.strptime(self.market_open, '%H:%M').time()
        market_open_datetime = datetime.datetime.combine(current_time.date(), market_open_time)
        if current_time.tzinfo is not None and market_open_datetime.tzinfo is None:
            market_open_datetime = market_open_datetime.replace(tzinfo=current_time.tzinfo)
        time_since_open = (current_time - market_open_datetime).total_seconds() / 60
        
        market_close_time = datetime.datetime.strptime(self.market_close, '%H:%M').time()
        market_close_datetime = datetime.datetime.combine(current_time.date(), market_close_time)
        if current_time.tzinfo is not None and market_close_datetime.tzinfo is None:
            market_close_datetime = market_close_datetime.replace(tzinfo=current_time.tzinfo)
        time_until_close = (market_close_datetime - current_time).total_seconds() / 60
        
        early_signal_cooldown_remaining = 0
        if self.last_early_signal_time:
            time_since_early = (current_time - self.last_early_signal_time).total_seconds() / 60
            early_signal_cooldown_remaining = max(0, self.early_signal_cooldown_minutes - time_since_early)
        
        return {
            'time_since_open_minutes': time_since_open,
            'time_until_close_minutes': time_until_close,
            'open_buffer_met': time_since_open >= self.market_open_buffer_minutes,
            'close_buffer_met': time_until_close >= self.market_close_buffer_minutes,
            'early_signal_cooldown_remaining': early_signal_cooldown_remaining,
            'in_early_signal_cooldown': self.last_early_signal_time is not None and early_signal_cooldown_remaining > 0
        }
    
    def log_market_timing_status(self, current_time: datetime.datetime):
        """Log current market timing status for debugging"""
        status = self.get_market_timing_status(current_time)
        self.log(f"⏰ Market Timing: Open +{status['time_since_open_minutes']:.1f}min, Close -{status['time_until_close_minutes']:.1f}min")
        self.log(f"   Open buffer: {'✅' if status['open_buffer_met'] else '❌'} ({self.market_open_buffer_minutes}min)")
        self.log(f"   Close buffer: {'✅' if status['close_buffer_met'] else '❌'} ({self.market_close_buffer_minutes}min)")
        if status['in_early_signal_cooldown']:
            self.log(f"   Early signal cooldown: {status['early_signal_cooldown_remaining']:.1f}min remaining")

    def calculate_commission_cost(self, positions: List[Position], is_exit: bool = False) -> float:
        """Calculate commission costs for a trade"""
        total_contracts = sum(pos.contracts for pos in positions)
        # Commission applies to both entry and exit
        commission_cost = total_contracts * self.commission_per_contract
        return commission_cost
    
    def calculate_slippage_cost(self, positions: List[Position]) -> float:
        """Calculate slippage costs for a trade"""
        total_contracts = sum(pos.contracts for pos in positions)
        # Slippage applies per contract
        slippage_cost = total_contracts * self.slippage
        return slippage_cost
    
    def calculate_total_trade_cost(self, positions: List[Position], is_exit: bool = False) -> float:
        """Calculate total costs including commission and slippage"""
        commission = self.calculate_commission_cost(positions, is_exit)
        slippage = self.calculate_slippage_cost(positions)
        return commission + slippage

    def calculate_exit_value(self, positions: List[Position], expiration: str, current_time: datetime.datetime) -> float:
        """Calculate exit value for a trade"""
        if not self.data_provider or not positions:
            return 0.0
        
        try:
            # Fetch option chain for exit calculation
            df_chain = self.data_provider.get_option_chain("SPY", expiration, current_time)
            
            if df_chain.empty:
                return 0.0
            
            # Map Tradier API 'call'/'put' to 'C'/'P' format
            if 'option_type' in df_chain.columns:
                df_chain['option_type'] = df_chain['option_type'].map({'call': 'C', 'put': 'P'}).fillna(df_chain['option_type'])
            
            exit_value = 0.0
            for pos in positions:
                df_pos = df_chain[
                    (df_chain['option_type'] == pos.type) & 
                    (df_chain['strike'] == pos.strike)
                ]
                
                if df_pos.empty:
                    self.log(f"[DEBUG] No match found for {pos.type} {pos.strike} in option chain")
                    continue
                
                current_price = df_pos.iloc[0]['bid']  # Use BID price for exit (selling)
                exit_value += current_price * 100 * pos.contracts
                self.log(f"[DEBUG] Exit price for {pos.type} {pos.strike}: ${current_price:.2f} x {pos.contracts} contracts")
            
            return exit_value
        except Exception as e:
            self.log(f"[ERROR] Failed to calculate exit value: {str(e)}")
            return 0.0

    def check_stop_loss(self, positions: List[Position], expiration: str, current_time: datetime.datetime) -> bool:
        """Check if stop-loss condition is met"""
        if not self.data_provider or not positions:
            return False
        
        try:
            # Calculate total entry cost (including commission)
            entry_cost = sum(pos.entry_price * 100 * pos.contracts for pos in positions)
            entry_commission = self.calculate_total_trade_cost(positions, is_exit=False)
            total_entry_cost = entry_cost + entry_commission
            
            # Get current exit value (using bid prices)
            exit_value = self.calculate_exit_value(positions, expiration, current_time)
            
            # Calculate current loss percentage
            if total_entry_cost > 0:
                loss_percentage = ((total_entry_cost - exit_value) / total_entry_cost) * 100
                
                if loss_percentage >= self.stop_loss_percentage:
                    self.log(f"🛑 STOP LOSS TRIGGERED! Loss: {loss_percentage:.1f}% >= {self.stop_loss_percentage:.1f}%")
                    self.log(f"   Entry Cost: ${total_entry_cost:.2f}, Exit Value: ${exit_value:.2f}")
                    
                    # Send Telegram stop loss alert
                    estimated_loss = total_entry_cost - exit_value
                    trade_id = getattr(positions[0], 'trade_id', 'N/A') if positions else 'N/A'
                    
                    stop_data = {
                        'trigger_time': current_time,
                        'trade_id': trade_id,
                        'positions': self._positions_to_dict(positions),
                        'loss_percent': loss_percentage,
                        'entry_cost': total_entry_cost,
                        'exit_value': exit_value,
                        'estimated_loss': estimated_loss,
                        'stop_loss_limit': self.stop_loss_percentage,
                        'timing_status': self.get_market_timing_status(current_time)
                    }
                    self._send_stop_loss_alert(stop_data)
                    
                    return True
                else:
                    self.log(f"⏳ Stop loss check: {loss_percentage:.1f}% < {self.stop_loss_percentage:.1f}%")
            
            return False
            
        except Exception as e:
            self.log(f"❌ Error checking stop loss: {e}")
            return False

    def check_emergency_stop_loss(self, current_time: datetime.datetime) -> bool:
        """Check if emergency stop-loss condition is met (total daily loss)"""
        if self.daily_pnl <= -self.emergency_stop_loss:
            self.log(f"🚨 EMERGENCY STOP LOSS TRIGGERED! Daily P&L: ${self.daily_pnl:.2f} <= -${self.emergency_stop_loss}")
            
            # Send Telegram emergency stop loss alert
            emergency_stop_data = {
                'trigger_time': current_time,
                'trade_id': 'EMERGENCY',
                'loss_percent': ((-self.daily_pnl / self.emergency_stop_loss) * 100) if self.emergency_stop_loss > 0 else 100,
                'estimated_loss': -self.daily_pnl,
                'stop_loss_limit': self.emergency_stop_loss,
                'daily_pnl': self.daily_pnl,
                'emergency_stop_limit': self.emergency_stop_loss,
                'active_trades': len(self.active_trades),
                'timing_status': self.get_market_timing_status(current_time)
            }
            self._send_stop_loss_alert(emergency_stop_data)
            
            return True
        return False

    def _set_vix_parameters(self, force=False, target_datetime=None):
        now = time.time()
        if force or (now - self._vix_last_fetch_time > 300):  # 5 min cache
            # Use static VIX for backtesting if enabled
            if self.mode == "backtest" and getattr(self, 'config', None) and self.config.get('STATIC_VIX_MODE', False):
                vix = self.config.get('STATIC_VIX_VALUE', 20.0)
                self.log(f"[VIX] Backtest mode: Using STATIC VIX value {vix}")
            # Use historical VIX for backtesting, current VIX for live/paper
            elif self.mode == "backtest" and target_datetime:
                vix = fetch_vix_at_datetime(target_datetime)
                self.log(f"[VIX] Backtest mode: Fetching VIX for {target_datetime}")
            else:
                vix = fetch_current_vix()
                self.log(f"[VIX] Live/Paper mode: Fetching current VIX")
            
            self._vix_last_fetch_time = now
            self._vix_value = vix
            
            old_threshold = getattr(self, 'move_threshold', None)
            old_regime = getattr(self, '_vix_regime', None)
            
            if vix is not None and vix > self.vix_threshold:
                self._vix_regime = 'high_volatility'
                self.move_threshold = self.high_vol_move_threshold
                self.premium_min = self.high_vol_premium_min
                self.premium_max = self.high_vol_premium_max
                self.profit_target = self.high_vol_profit_target
            else:
                self._vix_regime = 'low_volatility'
                self.move_threshold = self.low_vol_move_threshold
                self.premium_min = self.low_vol_premium_min
                self.premium_max = self.low_vol_premium_max
                self.profit_target = self.low_vol_profit_target
            
            # Log changes
            if old_threshold != self.move_threshold or old_regime != self._vix_regime:
                old_threshold_str = f"{old_threshold:.2f}" if old_threshold is not None else "None"
                vix_str = f"{vix:.2f}" if vix is not None else "None"
                self.log(f"[VIX] PARAMETERS UPDATED: VIX={vix_str}, Regime={self._vix_regime}")
                self.log(f"   📊 Move Threshold: {old_threshold_str} → {self.move_threshold:.2f}pts")
                self.log(f"   💰 Premium Range: ${self.premium_min:.2f} - ${self.premium_max:.2f}")
                self.log(f"   🎯 Profit Target: {self.profit_target:.2f}x")
            else:
                vix_str = f"{vix:.2f}" if vix is not None else "None"
                self.log(f"[VIX] Refreshed: VIX={vix_str}, regime={self._vix_regime} (no changes)")
    
    # === Telegram Alert Methods ===
    
    def _send_system_start_alert(self):
        """Send system start alert to Telegram"""
        if not self.telegram_notifier:
            return
        
        # Get actual market status
        current_time = datetime.datetime.now(tz=tz.gettz(self.timezone))
        timing_status = self.get_market_timing_status(current_time)
        
        # Market is open if we're past open time and before close time
        time_since_open = timing_status['time_since_open_minutes']
        time_until_close = timing_status['time_until_close_minutes']
        market_is_open = (time_since_open >= 0 and time_until_close > 0)
        market_status = "OPEN" if market_is_open else "CLOSED"
        
        # Format timestamp in correct timezone  
        ny_time = current_time.astimezone(tz.gettz(self.timezone))
            
        status_data = {
            'status': 'started',
            'timestamp': ny_time,
            'mode': self.mode,
            'market_status': market_status,
            'vix_regime': getattr(self, '_vix_regime', 'Unknown'),
            'risk_per_side': self.risk_per_side,
            'total_risk': self.risk_per_side * 2
        }
        
        self.telegram_notifier.send_system_status_alert(status_data)
    
    def _positions_to_dict(self, positions):
        """Convert Position objects to dictionaries for Telegram alerts"""
        if not positions:
            return []
        
        position_dicts = []
        for pos in positions:
            pos_dict = {
                'type': pos.type,
                'symbol': pos.symbol,
                'strike': pos.strike,
                'entry_price': pos.entry_price,
                'contracts': pos.contracts,
                'target': pos.target,
                'expiration': pos.expiration_date,
                'entry_time': pos.entry_time,
                'trade_id': getattr(pos, 'trade_id', None),
                'entry_order_id': getattr(pos, 'entry_order_id', None),
                'limit_order_id': getattr(pos, 'limit_order_id', None),
                'limit_price': getattr(pos, 'limit_price', None)
            }
            position_dicts.append(pos_dict)
        return position_dicts
    
    def _send_signal_alert(self, signal_data):
        """Send signal detection alert to Telegram"""
        if not (self.telegram_notifier and self.telegram_settings.get('signal_alerts', False)):
            return
            
        self.telegram_notifier.send_signal_alert(signal_data)
    
    def _send_entry_alert(self, entry_data):
        """Send trade entry alert to Telegram"""
        if not (self.telegram_notifier and self.telegram_settings.get('entry_alerts', False)):
            return
            
        self.telegram_notifier.send_entry_alert(entry_data)
    
    def _send_limit_hit_alert(self, limit_data):
        """Send limit order fill alert to Telegram"""
        if not (self.telegram_notifier and self.telegram_settings.get('limit_hit_alerts', False)):
            return
            
        self.telegram_notifier.send_limit_hit_alert(limit_data)
    
    def _send_exit_alert(self, exit_data):
        """Send trade exit alert to Telegram"""
        if not (self.telegram_notifier and self.telegram_settings.get('exit_alerts', False)):
            return
            
        self.telegram_notifier.send_exit_alert(exit_data)
    
    def _send_stop_loss_alert(self, stop_data):
        """Send stop loss alert to Telegram"""
        if not (self.telegram_notifier and self.telegram_settings.get('stop_loss_alerts', False)):
            return
            
        self.telegram_notifier.send_stop_loss_alert(stop_data)
    
    def _send_system_stop_alert(self):
        """Send system stop alert to Telegram"""
        if not (self.telegram_notifier and self.telegram_settings.get('system_alerts', False)):
            return
        
        # Format timestamp in correct timezone
        current_time = datetime.datetime.now(tz=tz.gettz(self.timezone))
        ny_time = current_time.astimezone(tz.gettz(self.timezone))
            
        status_data = {
            'status': 'stopped',
            'timestamp': ny_time,
            'mode': self.mode,
            'market_status': 'CLOSED',
            'final_pnl': getattr(self, 'total_pnl', 0),
            'total_trades': getattr(self, 'total_trades', 0)
        }
        
        self.telegram_notifier.send_system_status_alert(status_data)