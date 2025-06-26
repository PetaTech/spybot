"""
Pure Data-Driven Trading Engine
Processes one row of market data at a time from external data providers.
Maintains all trading state and logic internally.
"""

import pandas as pd
import numpy as np
import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Union
from abc import ABC, abstractmethod
import time
import os
from dateutil import tz
from utils import fetch_current_vix, fetch_vix_at_datetime


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
            'timestamp': datetime.datetime.now()
        }
        
        self.orders.append(order)
        return order_id
    
    def get_orders(self):
        """Get all tracked orders"""
        return self.orders


class PaperOrderExecutor(OrderExecutor):
    """Paper trading order executor - simulates orders without real execution"""
    
    def __init__(self):
        self.order_counter = 0
    
    def place_order(self, option_type: str, strike: float, contracts: int, 
                   action: str, expiration_date: str, price: Optional[float] = None) -> str:
        """Simulate order placement - returns fake order ID"""
        self.order_counter += 1
        order_id = f"PAPER_{self.order_counter:06d}"
        return order_id


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
        
        # Create appropriate order executor based on mode
        if mode == "backtest":
            self.order_executor = BacktestOrderExecutor()
        elif mode == "paper":
            self.order_executor = PaperOrderExecutor()
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
        self.max_hold_seconds = config.get('MAX_HOLD_SECONDS', 3600)
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
        self.low_vol_profit_target = config.get('LOW_VOL_PROFIT_TARGET', 1.35)
        
        # State tracking
        self.active_trades: List[List[Position]] = []
        self.trade_entry_times: List[datetime.datetime] = []
        self.last_trade_time = None
        self.last_flagged_time = None
        self.last_early_signal_time = None  # Track early signals for cooldown
        self.price_log: List[Tuple[datetime.datetime, float]] = []
        
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
        
        # Skip processing during buffer periods
        if time_since_open < self.market_open_buffer_minutes:
            self.log(f"⏰ SKIPPING: Market open buffer period (+{time_since_open:.1f}min < {self.market_open_buffer_minutes}min)")
            return {
                'timestamp': current_time,
                'action': 'skipped',
                'symbol': symbol,
                'price': close,
                'move_percent': 0.0,
                'signal_detected': False,
                'trades_active': len(self.active_trades),
                'entry_cost': 0.0,
                'exit_value': 0.0,
                'pnl': 0.0,
                'positions': None,
                'error': f'Market open buffer: {time_since_open:.1f}min < {self.market_open_buffer_minutes}min'
            }
        
        if time_until_close < self.market_close_buffer_minutes:
            self.log(f"⏰ SKIPPING: Market close buffer period (-{time_until_close:.1f}min < {self.market_close_buffer_minutes}min)")
            return {
                'timestamp': current_time,
                'action': 'skipped',
                'symbol': symbol,
                'price': close,
                'move_percent': 0.0,
                'signal_detected': False,
                'trades_active': len(self.active_trades),
                'entry_cost': 0.0,
                'exit_value': 0.0,
                'pnl': 0.0,
                'positions': None,
                'error': f'Market close buffer: {time_until_close:.1f}min < {self.market_close_buffer_minutes}min'
            }
        
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
        
        # Check for exits on all active trades
        if self.active_trades:
            print(f"[ENGINE DEBUG] Checking exits for {len(self.active_trades)} active trades")
            trades_to_exit = self.check_all_exit_conditions(market_row.current_time)
            
            for trade_index in reversed(trades_to_exit):
                trade_positions = self.active_trades[trade_index]
                entry_time = self.trade_entry_times[trade_index]
                
                self.log(f"🔄 EXITING TRADE #{trade_index + 1} (held for {(market_row.current_time - entry_time).total_seconds()/60:.1f} minutes)")
                
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
                        
                        # Remove the exited trade
                        self.active_trades.pop(trade_index)
                        self.trade_entry_times.pop(trade_index)
                        
                        self.log(f"✅ Trade #{trade_index + 1} EXIT COMPLETE. P&L: ${trade_pnl:.2f} (Entry: ${entry_cost:.2f} + ${entry_commission:.2f}, Exit: ${exit_value:.2f} - ${exit_commission:.2f})")
                        
                        # Log comprehensive exit result
                        self.log_comprehensive_result(result)
                    else:
                        result['action'] = 'exit_failed'
                        result['error'] = 'Exit execution failed'
                        self.log(f"❌ EXIT FAILED: {result['error']}")
                else:
                    result['action'] = 'exit_failed'
                    result['error'] = 'No expiration date stored'
                    self.log(f"❌ EXIT FAILED: {result['error']}")
        
        # Check for new entry signals
        print(f"[ENGINE DEBUG] Checking for entry signals...")
        if self.should_detect_signal(market_row.current_time):
            result['signal_detected'] = True
            self.total_signals += 1
            self.log(f"🎯 SIGNAL DETECTED! {market_row.symbol} ${market_row.close:.2f} | Move: {move_percent:.2f}% | Active trades: {len(self.active_trades)}")
            
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
                    positions = self.find_valid_options(market_row.close, expiration)
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
        
        # Log overall performance periodically (every 5 trades or when significant events occur)
        if self.total_trades % 5 == 0 and self.total_trades > 0:
            self.log_overall_performance()
        
        # Log summary for this processing cycle
        self.log(f"📋 CYCLE SUMMARY: {current_time.strftime('%H:%M:%S')} | Action: {result['action']} | Signals: {self.total_signals} | Trades: {self.total_trades} | Active: {len(self.active_trades)}")
        
        print(f"[ENGINE DEBUG] Row processing complete, action: {result['action']}")
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
        
        # Check regular cooldown between trades
        if (self.last_trade_time and 
            (current_time - self.last_trade_time).total_seconds() < self.cooldown_period):
            return False
        
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
    
    def find_valid_options(self, price: float, expiration: str) -> List[Position]:
        """Find valid near-the-money call and put options within the VIX-based premium range."""
        print(f"[ENGINE DEBUG] find_valid_options called with price=${price:.2f}, expiration={expiration}")
        if not self.data_provider:
            print("[ENGINE DEBUG] No data provider available")
            return []
        positions = []
        for attempt in range(1, self.max_retries + 1):
            self.log(f"[Attempt {attempt}] Fetching option chain...")
            try:
                current_time = getattr(self, 'last_processed_time', None)
                if not current_time:
                    return []
                df_chain = self.data_provider.get_option_chain("SPY", expiration, current_time)
                if df_chain.empty or "option_type" not in df_chain.columns:
                    self.log("[ERROR] Option chain missing or invalid.")
                    continue
                for option_type in ['C', 'P']:
                    df_side = df_chain[df_chain['option_type'] == option_type].copy()
                    if df_side.empty:
                        continue
                    df_side['dist'] = abs(df_side['strike'] - price)
                    df_side = df_side.sort_values('dist')
                    # Filter for valid options in VIX-based premium range
                    valid = df_side[df_side['ask'].between(self.premium_min, self.premium_max)]
                    if not valid.empty:
                        valid = valid[valid['ask'] > valid['bid'] * self.option_bid_ask_ratio]
                    if valid.empty:
                        self.log(f"ℹ️  No suitable {option_type} options found (premium range: ${self.premium_min:.2f}-${self.premium_max:.2f})")
                        continue
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
    
    def execute_entry(self, positions: List[Position], expiration: str) -> bool:
        """Execute entry orders"""
        if not self.order_executor:
            return False
        
        try:
            for pos in positions:
                order_id = self.order_executor.place_order(
                    pos.type, pos.strike, pos.contracts,
                    action="BUY", expiration_date=expiration
                )
                self.log(f"ENTRY {pos.type} Strike={pos.strike} Qty={pos.contracts} Price={pos.entry_price:.2f} OrderID={order_id}")
            return True
        except Exception as e:
            self.log(f"[ERROR] Entry execution failed: {str(e)}")
            return False
    
    def execute_exit(self, positions: List[Position], expiration: str) -> bool:
        """Execute exit orders"""
        if not self.order_executor:
            return False
        
        try:
            for pos in positions:
                order_id = self.order_executor.place_order(
                    pos.type, pos.strike, pos.contracts,
                    action="SELL", expiration_date=pos.expiration_date
                )
                self.log(f"EXIT {pos.type} Strike={pos.strike} Qty={pos.contracts} OrderID={order_id}")
            return True
        except Exception as e:
            self.log(f"[ERROR] Exit execution failed: {str(e)}")
            return False
    
    def check_exit_conditions(self, positions: List[Position], expiration: str, current_time: datetime.datetime) -> bool:
        """Exit if either leg hits the VIX-based profit target."""
        if not self.data_provider or not positions:
            return False
        try:
            df_chain = self.data_provider.get_option_chain("SPY", expiration, current_time)
            if df_chain.empty:
                return False
            for pos in positions:
                df_pos = df_chain[(df_chain['option_type'] == pos.type) & (df_chain['strike'] == pos.strike)]
                if df_pos.empty:
                    continue
                current_price = df_pos.iloc[0]['bid']
                if current_price >= pos.target:
                    self.log(f"🎯 PROFIT TARGET HIT: {pos.type} {pos.strike} | Entry: ${pos.entry_price:.2f} | Target: ${pos.target:.2f} | Current: ${current_price:.2f}")
                    return True
            return False
        except Exception as e:
            self.log(f"❌ Error checking exit conditions: {e}")
        return False
    
    def check_time_based_exit(self, entry_time: datetime.datetime, current_time: datetime.datetime) -> bool:
        """Check time-based exit"""
        hold_duration = (current_time - entry_time).total_seconds()
        if hold_duration >= self.max_hold_seconds:
            self.log(f"⏰ TIME-BASED EXIT: Trade held for {hold_duration/60:.1f} minutes >= {self.max_hold_seconds/60:.1f} minutes")
            return True
        return False
    
    def check_all_exit_conditions(self, current_time: datetime.datetime) -> List[int]:
        """Check exit conditions for all active trades"""
        trades_to_exit = []
        
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
            # Force exit all trades due to market close buffer
            self.log(f"⏰ MARKET CLOSE BUFFER EXIT: {time_until_close:.1f}min until close < {self.market_close_buffer_minutes}min buffer. Forcing exit of all trades.")
            return list(range(len(self.active_trades)))
        
        for i, (trade_positions, entry_time) in enumerate(zip(self.active_trades, self.trade_entry_times)):
            if self.check_time_based_exit(entry_time, current_time):
                trades_to_exit.append(i)
                continue
            
            if trade_positions and trade_positions[0].expiration_date:
                expiration = trade_positions[0].expiration_date
                
                # Check stop-loss first (highest priority)
                if self.check_stop_loss(trade_positions, expiration, current_time):
                    trades_to_exit.append(i)
                    continue
                
                # Check profit-based exit conditions
                if self.check_exit_conditions(trade_positions, expiration, current_time):
                    trades_to_exit.append(i)
        
        return trades_to_exit
    
    def increment_daily_trades(self):
        """Increment daily trade count"""
        self.daily_trades += 1
        self.log(f"📊 Daily trade count: {self.daily_trades}/{self.max_daily_trades}")
    
    def update_daily_pnl(self, trade_pnl: float):
        """Update daily PnL"""
        self.daily_pnl += trade_pnl
        self.log(f"📊 Daily PnL: ${self.daily_pnl:.2f}")
    
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
            self.log(f"📈 Win Rate: {(self.winning_trades / self.total_trades * 100):.1f}%")
            self.log(f"✅ Winning Trades: {self.winning_trades}")
            self.log(f"❌ Losing Trades: {self.losing_trades}")
            self.log(f"📊 Average Trade P&L: ${(self.total_pnl / self.total_trades):.2f}")
        
        # Daily performance
        self.log(f"📅 Daily Trades: {self.daily_trades}/{self.max_daily_trades}")
        self.log(f"📊 Daily P&L: ${self.daily_pnl:.2f}")
        
        # Active positions
        self.log(f"🔄 Active Trades: {len(self.active_trades)}")
        if self.active_trades:
            for i, (positions, entry_time) in enumerate(zip(self.active_trades, self.trade_entry_times)):
                hold_time = (datetime.datetime.now() - entry_time).total_seconds() / 60
                self.log(f"   Trade {i+1}: {len(positions)} positions, held for {hold_time:.1f} minutes")
        
        # Log files
        self.log(f"📝 Log File: {self.log_file}")
        
        self.log("=" * 80)
        
        # Print summary to console for backtest mode
        if self.mode == "backtest":
            print(f"Backtest Complete: {self.total_trades} trades, ${self.total_pnl:.2f} P&L")
            print(f"Win Rate: {(self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0:.1f}%")
            print(f"Log File: {self.log_file}")

    def finish(self):
        """Call this when trading is finished (end of data or user interrupt) to log final results."""
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
            
            exit_value = 0.0
            for pos in positions:
                df_pos = df_chain[
                    (df_chain['option_type'] == pos.type) & 
                    (df_chain['strike'] == pos.strike)
                ]
                
                if df_pos.empty:
                    continue
                
                current_price = df_pos.iloc[0]['bid']  # Use BID price for exit (selling)
                exit_value += current_price * 100 * pos.contracts
            
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
            return True
        return False

    def _set_vix_parameters(self, force=False, target_datetime=None):
        now = time.time()
        if force or (now - self._vix_last_fetch_time > 300):  # 5 min cache
            # Use historical VIX for backtesting, current VIX for live/paper
            if self.mode == "backtest" and target_datetime:
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
                self.log(f"[VIX] PARAMETERS UPDATED: VIX={vix:.2f}, Regime={self._vix_regime}")
                self.log(f"   📊 Move Threshold: {old_threshold:.2f} → {self.move_threshold:.2f}pts")
                self.log(f"   💰 Premium Range: ${self.premium_min:.2f} - ${self.premium_max:.2f}")
                self.log(f"   🎯 Profit Target: {self.profit_target:.2f}x")
            else:
                self.log(f"[VIX] Refreshed: VIX={vix:.2f}, regime={self._vix_regime} (no changes)")