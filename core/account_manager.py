"""
Account Manager for Multi-Account Trading
Manages individual account with strategy overrides and independent signal processing
"""

import datetime
import os
import logging
import requests
from typing import Dict, Optional, Any
from dataclasses import asdict

from core.trading_engine import TradingEngine
from core.shared_data_provider import MarketData
from utils.tradier_api import set_api_credentials
from config.strategy import *  # Import all default strategy settings


class AccountManager:
    """
    Manages a single trading account with strategy overrides
    Processes shared market data independently for signal generation
    """

    def __init__(self, account_config: Dict):
        """
        Initialize account manager

        Args:
            account_config: Account configuration from config/accounts.py
        """
        self.account_config = account_config
        self.account_index = account_config.get('account_index', 0)
        self.account_id = account_config['account_id']
        self.access_token = account_config['access_token']
        self.api_url = account_config['api_url']
        self.mode = account_config['mode']  # 'live' or 'paper'
        self.enabled = account_config.get('enabled', True)

        # Fetch account name from Tradier API
        self.account_name = self._fetch_account_name()

        # Set up logging for this account
        self._setup_logging()

        # Build strategy configuration with overrides
        self.strategy_config = self._build_strategy_config()

        # DO NOT set global API credentials here - each account will use its own via api_url/access_token/account_id params
        # The trading engine's order executor will use the account-specific credentials passed in

        # Create trading engine for this account
        self.trading_engine = TradingEngine(
            config=self.strategy_config,
            data_provider=None,  # We'll provide data via process_market_data()
            mode=self.mode,
            api_url=self.api_url,
            access_token=self.access_token,
            account_id=self.account_id,
            telegram_config=self.get_telegram_config()
        )

        # Initialize VIX parameters at startup to avoid Unknown/None in first alerts
        try:
            if hasattr(self.trading_engine, '_set_vix_parameters'):
                # Force an initial refresh; method already caches thereafter
                self.trading_engine._set_vix_parameters(force=True, target_datetime=None)
        except Exception as e:
            self.log(f"Initial VIX initialization failed: {e}", level='WARNING')

        # Account state
        self.is_running = False
        self.market_data_count = 0
        self.last_signal_time = None
        self.last_trade_time = None

        self.log(f"AccountManager initialized for {self.account_name} ({self.mode} mode)")

    def _fetch_account_name(self) -> str:
        """
        Fetch account name from Tradier API

        Returns:
            str: Account name from Tradier API or fallback name
        """
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Accept': 'application/json'
            }

            # Get user profile to fetch account name
            url = f"{self.api_url}/user/profile"
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                profile = data.get('profile', {})
                account_name = profile.get('name', profile.get('account', {}).get('account_number', ''))

                if account_name:
                    return f"{account_name} ({self.mode.upper()})"

            # If profile doesn't work, try account endpoint
            url = f"{self.api_url}/accounts/{self.account_id}"
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                account = data.get('account', {})
                account_name = account.get('account_number', account.get('type', ''))

                if account_name:
                    return f"{account_name} ({self.mode.upper()})"

            # Fallback to account ID if API calls fail
            return f"Account {self.account_id} ({self.mode.upper()})"

        except Exception as e:
            # Fallback to a default name if API call fails
            fallback_name = f"Account {self.account_index} ({self.mode.upper()})"
            print(f"⚠️ Failed to fetch account name from Tradier API: {e}")
            print(f"   Using fallback name: {fallback_name}")
            return fallback_name

    def _setup_logging(self):
        """Setup separate logging for this account"""
        log_config = self.account_config.get('logging', {})
        # Use configured log prefix or fallback to account index
        log_prefix = log_config.get('log_prefix', f'account{self.account_index}_{self.mode}')
        log_level = log_config.get('log_level', 'INFO')

        # Create logs/accounts directory if it doesn't exist
        log_dir = 'logs/accounts'
        os.makedirs(log_dir, exist_ok=True)

        # Setup logger for this account using account index for consistency
        logger_name = f"account_{self.account_index}_{self.mode}"
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(getattr(logging, log_level))

        # Create file handler
        log_file = os.path.join(log_dir, f"{log_prefix}.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level))

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)

        # Add handler if not already added
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)

    def _build_strategy_config(self) -> Dict[str, Any]:
        """
        Build strategy configuration with overrides
        Uses config/strategy.py as base, applies account-specific overrides
        """
        # Start with all default strategy settings
        strategy_config = {}

        # Get all uppercase variables from config.strategy (default settings)
        import config.strategy as default_strategy
        for attr_name in dir(default_strategy):
            if not attr_name.startswith('_') and attr_name.isupper():
                strategy_config[attr_name] = getattr(default_strategy, attr_name)

        # Apply account-specific overrides
        strategy_overrides = self.account_config.get('strategy_overrides', {})
        for key, value in strategy_overrides.items():
            if key in strategy_config:
                old_value = strategy_config[key]
                strategy_config[key] = value
                self.log(f"Strategy override: {key} = {value} (was {old_value})")
            else:
                strategy_config[key] = value
                self.log(f"Strategy addition: {key} = {value}")

        # Add account-specific metadata
        strategy_config.update({
            'ACCOUNT_NAME': self.account_name,
            'ACCOUNT_ID': self.account_id,
            'MODE': self.mode,
            'LOG_DIR': f'logs/accounts',
            'LOG_PREFIX': self.account_config.get('logging', {}).get('log_prefix', self.account_name.lower())
        })

        # Convert time strings to datetime.time objects if needed
        if 'MAX_ENTRY_TIME' in strategy_config and isinstance(strategy_config['MAX_ENTRY_TIME'], str):
            strategy_config['MAX_ENTRY_TIME'] = datetime.datetime.strptime(
                strategy_config['MAX_ENTRY_TIME'], '%H:%M'
            ).time()

        return strategy_config

    def start(self):
        """Start the account manager"""
        if not self.enabled:
            self.log(f"Account {self.account_name} is disabled, not starting")
            return False

        self.log(f"Starting account manager for {self.account_name}")
        self.is_running = True
        return True

    def stop(self):
        """Stop the account manager"""
        self.log(f"Stopping account manager for {self.account_name}")
        self.is_running = False

        # Finish trading engine properly
        if hasattr(self.trading_engine, 'finish'):
            self.trading_engine.finish()

    def process_market_data(self, market_data: MarketData) -> Dict:
        """
        Process incoming market data for this account
        Each account processes the same data independently for signal generation

        Args:
            market_data: Shared market data from SharedDataProvider

        Returns:
            Dict: Processing result from trading engine
        """
        if not self.is_running or not self.enabled:
            return {'action': 'skipped', 'reason': 'account_disabled'}

        try:
            self.market_data_count += 1

            # Process through trading engine
            result = self.trading_engine.process_row(
                current_time=market_data.timestamp,
                symbol=market_data.symbol,
                open=market_data.open,
                high=market_data.high,
                low=market_data.low,
                close=market_data.close,
                volume=market_data.volume
            )

            # Track account-specific events
            if result.get('signal_detected'):
                self.last_signal_time = market_data.timestamp

            if result.get('action') in ['entry', 'exit']:
                self.last_trade_time = market_data.timestamp

            # Add account context to result
            result.update({
                'account_name': self.account_name,
                'account_mode': self.mode,
                'market_data_count': self.market_data_count
            })

            return result

        except Exception as e:
            error_msg = f"Error processing market data: {e}"
            self.log(error_msg, level='ERROR')
            return {
                'action': 'error',
                'error': str(e),
                'account_name': self.account_name
            }

    def get_status(self) -> Dict:
        """Get current account status"""
        status = {
            'account_name': self.account_name,
            'account_id': self.account_id,
            'mode': self.mode,
            'enabled': self.enabled,
            'running': self.is_running,
            'market_data_count': self.market_data_count,
            'last_signal_time': self.last_signal_time,
            'last_trade_time': self.last_trade_time,
        }

        # Add trading engine status if available
        if hasattr(self.trading_engine, 'get_status'):
            engine_status = self.trading_engine.get_status()
            status.update({
                'active_trades': len(getattr(self.trading_engine, 'active_trades', [])),
                'daily_trades': getattr(self.trading_engine, 'daily_trades', 0),
                'daily_pnl': getattr(self.trading_engine, 'daily_pnl', 0.0),
                'total_pnl': getattr(self.trading_engine, 'total_pnl', 0.0),
            })

        return status

    def get_strategy_config_summary(self) -> Dict:
        """Get summary of strategy configuration for this account"""
        key_settings = [
            'RISK_PER_SIDE', 'MAX_DAILY_TRADES', 'MAX_DAILY_LOSS',
            'STOP_LOSS_PERCENTAGE', 'COOLDOWN_PERIOD', 'PRICE_WINDOW_SECONDS',
            'VIX_THRESHOLD', 'HIGH_VOL_MOVE_THRESHOLD', 'LOW_VOL_MOVE_THRESHOLD'
        ]

        summary = {}
        for key in key_settings:
            if key in self.strategy_config:
                summary[key] = self.strategy_config[key]

        # Add override information
        overrides = self.account_config.get('strategy_overrides', {})
        summary['overrides_applied'] = list(overrides.keys())
        summary['override_count'] = len(overrides)
        summary['account_overrides'] = overrides  # Add actual override values

        return summary

    def log(self, message: str, level: str = 'INFO'):
        """Log message for this account"""
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(f"[{self.account_name}] {message}")

        # Also print to console for important messages
        if level in ['ERROR', 'WARNING']:
            timestamp = datetime.datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] [{self.account_name}] {level}: {message}")

    def health_check(self) -> bool:
        """Check if account manager is healthy"""
        if not self.enabled or not self.is_running:
            return False

        # During market hours, check if we've processed data recently
        # Outside market hours, always pass health check
        import datetime
        from dateutil import tz

        now = datetime.datetime.now(tz=tz.gettz('America/New_York'))
        market_open = datetime.time(9, 30)
        market_close = datetime.time(16, 0)
        current_time = now.time()

        # Check if market is open (Monday-Friday, 9:30 AM - 4:00 PM ET)
        is_weekday = now.weekday() < 5  # Monday=0, Friday=4
        is_market_hours = market_open <= current_time <= market_close

        if is_weekday and is_market_hours:
            # Market is open, require data processing
            if self.market_data_count == 0:
                return False

        # Outside market hours or weekend, health check passes
        return True

    def restart(self):
        """Restart the account manager"""
        self.log("Restarting account manager")
        self.stop_for_restart()
        return self.start()

    def stop_for_restart(self):
        """Stop the account manager for restart (suppresses final results logging)"""
        self.is_running = False

        # Finish trading engine without logging final results
        if hasattr(self.trading_engine, 'finish'):
            self.trading_engine.finish(suppress_logging=True)

    def update_config(self, new_overrides: Dict):
        """
        Update strategy overrides dynamically
        Note: This requires restarting the trading engine
        """
        self.log(f"Updating strategy configuration with: {new_overrides}")

        # Update account config
        if 'strategy_overrides' not in self.account_config:
            self.account_config['strategy_overrides'] = {}

        self.account_config['strategy_overrides'].update(new_overrides)

        # Rebuild strategy config
        self.strategy_config = self._build_strategy_config()

        # Note: In a full implementation, you'd need to restart the trading engine
        # For now, just log the change
        self.log("Strategy configuration updated (restart required for full effect)")

    def get_telegram_config(self) -> Optional[Dict]:
        """Get telegram configuration for this account"""
        return self.account_config.get('telegram')