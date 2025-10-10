"""
Trading Coordinator - Single-threaded coordinator for multi-account trading
Handles signal detection, order execution, and exit monitoring for all accounts
"""

import time
import datetime
import threading
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from core.shared_data_provider import SharedDataProvider, MarketData
from core.account_manager import AccountManager


@dataclass
class Signal:
    """Represents a trading signal"""
    timestamp: datetime.datetime
    symbol: str
    price: float
    move_percent: float
    move_points: float
    reference_price: float
    expiration: str
    vix_regime: str
    vix_value: float


class TradingCoordinator:
    """
    Single-threaded coordinator that:
    1. Collects market data once
    2. Detects signals once
    3. Checks each account's trading state
    4. Executes orders in parallel for ready accounts
    5. Monitors exits and executes in parallel
    """

    def __init__(self, data_provider: SharedDataProvider, account_managers: Dict[str, AccountManager]):
        self.data_provider = data_provider
        self.account_managers = account_managers
        self.executor = ThreadPoolExecutor(max_workers=20)

        # Coordinator state
        self.running = False
        self.main_thread = None

        # Signal detection state (shared across all accounts)
        self.price_log = []  # List of (timestamp, price) tuples
        self.last_flagged_time = None
        self.total_signals = 0

        # Get strategy parameters from first account (all accounts share same strategy)
        first_account = next(iter(account_managers.values()))
        engine = first_account.trading_engine

        # Import strategy parameters
        self.move_threshold_min = getattr(engine, 'move_threshold_min_points', 3.0)
        self.move_threshold_max = getattr(engine, 'move_threshold_max_points', 20.0)
        self.price_window_seconds = getattr(engine, 'price_window_seconds', 30 * 60)
        self.cooldown_period = getattr(engine, 'cooldown_period', 20 * 60)
        self.market_open = getattr(engine, 'market_open', '09:30')
        self.market_close = getattr(engine, 'market_close', '16:00')
        self.market_open_buffer_minutes = getattr(engine, 'market_open_buffer_minutes', 15)
        self.market_close_buffer_minutes = getattr(engine, 'market_close_buffer_minutes', 15)
        self.max_entry_time = getattr(engine, 'max_entry_time', datetime.time(15, 0))

        print(f"✅ TradingCoordinator initialized with {len(account_managers)} accounts")
        print(f"   Strategy: Move threshold {self.move_threshold_min}-{self.move_threshold_max} pts, {self.price_window_seconds/60:.0f}min window")

    def start(self):
        """Start the coordinator's main loop"""
        if self.running:
            print("⚠️  TradingCoordinator already running")
            return

        print("🚀 Starting TradingCoordinator main loop...")
        self.running = True

        # Start main coordination loop in a thread
        self.main_thread = threading.Thread(target=self._main_loop, daemon=True)
        self.main_thread.start()

        print("✅ TradingCoordinator started")

    def stop(self):
        """Stop the coordinator"""
        if not self.running:
            return

        print("🛑 Stopping TradingCoordinator...")
        self.running = False

        if self.main_thread:
            self.main_thread.join(timeout=5)

        self.executor.shutdown(wait=True)
        print("✅ TradingCoordinator stopped")

    def _main_loop(self):
        """Main coordination loop - runs in single thread"""
        print("📊 TradingCoordinator main loop started")

        while self.running:
            try:
                # 1. Get market data (once)
                market_data = self.data_provider.get_latest_data()

                if market_data is None:
                    time.sleep(1)
                    continue

                # 2. Update price log
                self._update_price_log(market_data.timestamp, market_data.close)

                # 3. Update VIX parameters (cached, only updates every 5 minutes)
                self._update_vix_parameters(market_data)

                # 4. Update all account states (sequential, but fast)
                self._update_account_states(market_data)

                # 5. Check for exit conditions first (accounts with positions)
                self._check_and_execute_exits(market_data)

                # 6. Check for entry signal
                signal = self._detect_signal(market_data)

                if signal:
                    # 7. Handle entry for ready accounts
                    self._handle_entry(signal, market_data)

                # Sleep until next iteration
                time.sleep(1)

            except Exception as e:
                print(f"❌ Error in TradingCoordinator main loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)

        print("⚠️  TradingCoordinator main loop exited")

    def _update_price_log(self, timestamp: datetime.datetime, price: float):
        """Update price log for signal detection"""
        self.price_log.append((timestamp, price))

        # Remove old prices outside window
        cutoff_time = timestamp - datetime.timedelta(seconds=self.price_window_seconds)
        self.price_log = [(t, p) for t, p in self.price_log if t >= cutoff_time]

    def _update_vix_parameters(self, market_data: MarketData):
        """
        Update VIX parameters for all accounts
        VIX is cached internally (5-minute TTL), so this is efficient
        """
        try:
            # Update VIX for all accounts (cached, only fetches every 5 minutes)
            for account_mgr in self.account_managers.values():
                engine = account_mgr.trading_engine
                if hasattr(engine, '_set_vix_parameters'):
                    engine._set_vix_parameters(force=False, target_datetime=market_data.timestamp)
        except Exception as e:
            print(f"⚠️ Error updating VIX parameters: {e}")

    def _update_account_states(self, market_data: MarketData):
        """Update cooldowns and state for all accounts (fast, sequential)"""
        try:
            # Check daily limits for all accounts (includes daily reset logic)
            for account_mgr in self.account_managers.values():
                # Increment market data count so health checks pass
                account_mgr.market_data_count += 1

                engine = account_mgr.trading_engine
                if hasattr(engine, 'check_daily_limits'):
                    engine.check_daily_limits(market_data.timestamp)
        except Exception as e:
            print(f"⚠️ Error updating account states: {e}")

    def _detect_signal(self, market_data: MarketData) -> Optional[Signal]:
        """
        Detect trading signal (ONCE, globally)
        Returns Signal object if detected, None otherwise
        """
        current_time = market_data.timestamp
        current_price = market_data.close

        # Check market timing
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

        # Check buffer periods
        in_open_buffer = time_since_open < self.market_open_buffer_minutes
        in_close_buffer = time_until_close < self.market_close_buffer_minutes
        past_max_entry_time = current_time.time() > self.max_entry_time

        # Skip signal detection during buffer periods or past max entry time
        if in_open_buffer or in_close_buffer or past_max_entry_time:
            return None

        # Check cooldown
        if self.last_flagged_time is not None:
            seconds_since_last_signal = (current_time - self.last_flagged_time).total_seconds()
            if seconds_since_last_signal < self.cooldown_period:
                return None

        # Calculate move percentage
        if len(self.price_log) < 2:
            return None

        # Get window high/low
        window_prices = [p for t, p in self.price_log]
        window_high = max(window_prices)
        window_low = min(window_prices)

        # Calculate move from window high/low
        move_from_high = ((current_price - window_high) / window_high) * 100
        move_from_low = ((current_price - window_low) / window_low) * 100

        # Check if price moved above high or below low
        absolute_move_high = current_price - window_high
        absolute_move_low = window_low - current_price

        # Detect breakout
        signal_detected = False
        move_percent = 0.0
        absolute_move = 0.0
        reference_price = current_price

        # Upward breakout
        if absolute_move_high > self.move_threshold_min and absolute_move_high < self.move_threshold_max:
            signal_detected = True
            move_percent = move_from_high
            absolute_move = absolute_move_high
            reference_price = window_high

        # Downward breakout
        elif absolute_move_low > self.move_threshold_min and absolute_move_low < self.move_threshold_max:
            signal_detected = True
            move_percent = -move_from_low
            absolute_move = absolute_move_low
            reference_price = window_low

        if signal_detected:
            self.last_flagged_time = current_time
            self.total_signals += 1

            # Get VIX from first account's engine
            first_account = next(iter(self.account_managers.values()))
            vix_regime = getattr(first_account.trading_engine, '_vix_regime', 'low_volatility')
            vix_value = getattr(first_account.trading_engine, '_vix_value', 0.0)

            print(f"🎯 SIGNAL DETECTED: {market_data.symbol} ${current_price:.2f} | Move: {move_percent:.2f}% ({absolute_move:.2f}pts)")

            # Send signal alert to all accounts
            signal_data = {
                'detection_time': current_time,
                'condition': f"Move {move_percent:.2f}% in window, signal detected",
                'market_price': current_price,
                'move_percent': move_percent,
                'move_points': absolute_move,
                'vix_regime': vix_regime,
                'vix_value': vix_value,
                'active_trades': 0,  # Will be updated per account
                'symbol': market_data.symbol
            }

            # Send signal alert to each account
            for account_name, account_mgr in self.account_managers.items():
                try:
                    # Update active trades count for this account
                    signal_data['active_trades'] = len(account_mgr.trading_engine.active_trades)
                    account_mgr.trading_engine._send_signal_alert(signal_data)
                except Exception as e:
                    print(f"❌ Error sending signal alert to {account_name}: {e}")

            return Signal(
                timestamp=current_time,
                symbol=market_data.symbol,
                price=current_price,
                move_percent=move_percent,
                move_points=absolute_move,
                reference_price=reference_price,
                expiration=current_time.strftime("%Y-%m-%d"),
                vix_regime=vix_regime,
                vix_value=vix_value
            )

        return None

    def _handle_entry(self, signal: Signal, market_data: MarketData):
        """
        Handle entry for all ready accounts
        1. Query which accounts can trade
        2. Fetch option chain once
        3. Select option once
        4. Execute all orders in parallel
        """
        print(f"📋 Processing entry signal for {len(self.account_managers)} accounts...")

        # 1. Query which accounts can trade
        ready_accounts = []
        for account_name, account_mgr in self.account_managers.items():
            if account_mgr.can_trade(signal.timestamp):
                ready_accounts.append((account_name, account_mgr))
                print(f"   ✅ {account_name} ready to trade")
            else:
                reason = account_mgr.get_cannot_trade_reason(signal.timestamp)
                print(f"   ❌ {account_name} cannot trade: {reason}")

        if not ready_accounts:
            print(f"⚠️  No accounts ready to trade")
            return

        print(f"🎯 {len(ready_accounts)} accounts ready, fetching options...")

        # 2. Fetch option chain ONCE
        option_chain = self.data_provider.get_option_chain(
            symbol=signal.symbol,
            expiration=signal.expiration,
            current_time=signal.timestamp
        )

        if option_chain is None or (hasattr(option_chain, 'empty') and option_chain.empty):
            print(f"❌ No options available for {signal.expiration}")
            return

        # 3. Select option ONCE (using first account's logic)
        first_account = ready_accounts[0][1]
        positions = first_account.trading_engine.find_valid_options(
            signal.price,
            signal.expiration,
            signal.timestamp
        )

        if len(positions) != 2:
            print(f"❌ Could not find valid options (got {len(positions)} positions, need 2)")
            return

        print(f"✅ Selected options: {positions[0].type} ${positions[0].strike} @ ${positions[0].entry_price:.2f}, "
              f"{positions[1].type} ${positions[1].strike} @ ${positions[1].entry_price:.2f}")

        # 4. Execute all orders IN PARALLEL
        self._execute_orders_parallel(ready_accounts, positions, signal)

    def _execute_orders_parallel(self, ready_accounts: List[Tuple[str, AccountManager]],
                                 positions: List, signal: Signal):
        """
        Execute entry orders for all accounts simultaneously
        Each account calculates its own contracts based on RISK_PER_SIDE
        """
        print(f"⚡ Executing {len(ready_accounts)} orders in parallel...")

        # Submit all orders simultaneously
        futures = {}
        for account_name, account_mgr in ready_accounts:
            # Each account needs to recalculate contracts based on its own RISK_PER_SIDE
            # But uses the same option prices from positions
            future = self.executor.submit(
                self._execute_single_account_entry,
                account_name,
                account_mgr,
                positions,
                signal
            )
            futures[future] = account_name

        # Wait for all to complete
        results = {}
        for future in as_completed(futures):
            account_name = futures[future]
            try:
                result = future.result()
                results[account_name] = result
                if result['success']:
                    print(f"   ✅ {account_name}: Order executed successfully")
                else:
                    print(f"   ❌ {account_name}: Order failed - {result.get('error', 'Unknown')}")
            except Exception as e:
                print(f"   ❌ {account_name}: Exception - {e}")
                results[account_name] = {'success': False, 'error': str(e)}

        print(f"✅ Parallel execution complete: {sum(1 for r in results.values() if r['success'])}/{len(ready_accounts)} successful")

    def _execute_single_account_entry(self, account_name: str, account_mgr: AccountManager,
                                     positions: List, signal: Signal) -> Dict:
        """Execute entry for a single account"""
        try:
            # Recalculate contracts for this account's risk per side
            account_positions = []
            for pos in positions:
                # Calculate contracts based on this account's risk per side
                risk_per_side = account_mgr.trading_engine.risk_per_side
                contracts = int(risk_per_side // (pos.entry_price * 100))
                contracts = max(1, contracts)

                # Create new position with account-specific contracts
                from core.trading_engine import Position
                account_pos = Position(
                    type=pos.type,
                    strike=pos.strike,
                    entry_price=pos.entry_price,
                    contracts=contracts,
                    target=pos.target,
                    symbol=pos.symbol,
                    expiration_date=pos.expiration_date,
                    entry_time=signal.timestamp,
                    trade_id=account_mgr.trading_engine.trade_id_counter + 1
                )
                account_positions.append(account_pos)

            # Execute entry through account's trading engine
            success = account_mgr.trading_engine.execute_entry(account_positions, signal.expiration)

            if success:
                # Add to account's active trades
                account_mgr.trading_engine.active_trades.append(account_positions)
                account_mgr.trading_engine.trade_entry_times.append(signal.timestamp)
                account_mgr.trading_engine.last_trade_time = signal.timestamp
                account_mgr.trading_engine.increment_daily_trades()

                # Calculate entry cost and send telegram alert
                engine = account_mgr.trading_engine
                entry_cost = sum(pos.entry_price * 100 * pos.contracts for pos in account_positions)
                entry_commission = engine.calculate_total_trade_cost(account_positions, is_exit=False)
                total_entry_cost = entry_cost + entry_commission

                trade_id = getattr(account_positions[0], 'trade_id', len(engine.active_trades)) if account_positions else len(engine.active_trades)

                entry_data = {
                    'trade_id': trade_id,
                    'entry_time': signal.timestamp,
                    'positions': engine._positions_to_dict(account_positions),
                    'market_price': signal.price,
                    'total_risk': engine.risk_per_side * 2,
                    'risk_per_side': engine.risk_per_side,
                    'entry_cost': entry_cost,
                    'commission': entry_commission,
                    'total_entry_cost': total_entry_cost,
                    'expiration_date': signal.expiration,
                    'trades_active': len(engine.active_trades),
                    'symbol': signal.symbol,
                    'limit_orders_info': 'Limit orders placed for profit targets',
                    'timing_status': engine.get_market_timing_status(signal.timestamp)
                }

                # Send entry alert
                try:
                    engine._send_entry_alert(entry_data)
                except Exception as e:
                    print(f"❌ Error sending entry alert for {account_name}: {e}")

                # Add to analytics log
                try:
                    analytics_entry = {
                        'trade_id': trade_id,
                        'signal_time': signal.timestamp,
                        'entry_time': signal.timestamp,
                        'vix_regime': signal.vix_regime,
                        'vix_value': signal.vix_value,
                        'move_percent': signal.move_percent,
                        'reference_price': signal.reference_price,
                        'spy_price': signal.price,
                        'expiration': signal.expiration,
                        'positions': [
                            {
                                'type': pos.type,
                                'symbol': pos.symbol,
                                'strike': pos.strike,
                                'expiration_date': pos.expiration_date,
                                'entry_price': pos.entry_price,
                                'contracts': pos.contracts
                            }
                            for pos in account_positions
                        ],
                        'entry_cost': entry_cost,
                        'entry_commission': entry_commission,
                        'total_entry_cost': total_entry_cost,
                        'exit_time': None,
                        'exit_value': None,
                        'exit_commission': None,
                        'pnl': None,
                        'exit_reason': None
                    }
                    engine.signal_trade_log.append(analytics_entry)
                except Exception as e:
                    print(f"❌ Error logging analytics for {account_name}: {e}")

                return {'success': True, 'positions': account_positions}
            else:
                return {'success': False, 'error': 'execute_entry returned False'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _check_and_execute_exits(self, market_data: MarketData):
        """
        Check exit conditions and execute exits for accounts with positions
        Exit conditions are checked for each account independently
        """
        # Get all accounts with positions
        accounts_with_positions = [
            (name, mgr) for name, mgr in self.account_managers.items()
            if len(mgr.trading_engine.active_trades) > 0
        ]

        if not accounts_with_positions:
            return

        # Check if market is closing (force exit all positions)
        current_time = market_data.timestamp
        market_close_time = datetime.datetime.strptime(self.market_close, '%H:%M').time()
        market_close_datetime = datetime.datetime.combine(current_time.date(), market_close_time)
        if current_time.tzinfo is not None and market_close_datetime.tzinfo is None:
            market_close_datetime = market_close_datetime.replace(tzinfo=current_time.tzinfo)
        time_until_close = (market_close_datetime - current_time).total_seconds() / 60

        # Force close all positions close to market close
        if time_until_close < self.market_close_buffer_minutes:
            print(f"⚠️  MARKET CLOSE APPROACHING ({time_until_close:.1f}min remaining), forcing all exits...")
            for account_name, account_mgr in accounts_with_positions:
                engine = account_mgr.trading_engine
                self._force_close_all_positions(account_name, account_mgr, market_data)
            return

        # Check each account's positions for exits
        for account_name, account_mgr in accounts_with_positions:
            engine = account_mgr.trading_engine

            # Check limit order fills first
            try:
                limit_result = engine.check_limit_order_fills(market_data.timestamp)
                if limit_result and limit_result.get('action') == 'exit':
                    # Telegram notification handled by account's engine
                    pass
            except Exception as e:
                print(f"❌ Error checking limit orders for {account_name}: {e}")

            # Check all active trades for exit conditions
            try:
                trades_to_exit = engine.check_all_exit_conditions(market_data.timestamp)

                if trades_to_exit:
                    # Execute exits for this account
                    for trade_index in reversed(trades_to_exit):
                        trade_positions = engine.active_trades[trade_index]
                        entry_time = engine.trade_entry_times[trade_index]

                        if trade_positions and trade_positions[0].expiration_date:
                            expiration = trade_positions[0].expiration_date

                            # Execute exit
                            if engine.execute_exit(trade_positions, expiration):
                                # Calculate P&L
                                entry_cost = sum(pos.entry_price * 100 * pos.contracts for pos in trade_positions)
                                entry_commission = engine.calculate_total_trade_cost(trade_positions, is_exit=False)
                                exit_value = engine.calculate_exit_value(trade_positions, expiration, market_data.timestamp)
                                exit_commission = engine.calculate_total_trade_cost(trade_positions, is_exit=True)
                                trade_pnl = exit_value - entry_cost - entry_commission - exit_commission

                                # Update metrics
                                engine.update_daily_pnl(trade_pnl)
                                engine.update_trade_metrics(trade_pnl)

                                # Send telegram exit alert
                                trade_id = getattr(trade_positions[0], 'trade_id', None) if trade_positions else None
                                if trade_id is None:
                                    trade_id = trade_index + 1

                                holding_time_minutes = (market_data.timestamp - entry_time).total_seconds() / 60
                                holding_time = f"{holding_time_minutes:.1f} minutes"

                                # Calculate win rate
                                completed_trades = [entry for entry in engine.signal_trade_log if entry.get('pnl') is not None]
                                total_completed_trades = len(completed_trades)
                                wins = sum(1 for entry in completed_trades if entry.get('pnl', 0) > 0)
                                win_rate = (wins / total_completed_trades * 100) if total_completed_trades > 0 else 0.0

                                exit_data = {
                                    'trade_id': trade_id,
                                    'exit_time': market_data.timestamp,
                                    'holding_time': holding_time,
                                    'positions': engine._positions_to_dict(trade_positions),
                                    'exit_reason': engine._last_exit_reason or 'System Exit',
                                    'entry_cost': entry_cost,
                                    'entry_commission': entry_commission,
                                    'total_entry_cost': entry_cost + entry_commission,
                                    'exit_value': exit_value,
                                    'exit_commission': exit_commission,
                                    'pnl': trade_pnl,
                                    'daily_pnl': engine.daily_pnl,
                                    'daily_trades': engine.daily_trades,
                                    'total_trades': engine.total_trades,
                                    'win_rate': win_rate,
                                    'total_pnl': engine.total_pnl,
                                    'timing_status': engine.get_market_timing_status(market_data.timestamp)
                                }

                                try:
                                    engine._send_exit_alert(exit_data)
                                except Exception as e:
                                    print(f"❌ Error sending exit alert for {account_name}: {e}")

                                # Update analytics log
                                try:
                                    if trade_id is not None:
                                        for analytics_entry in reversed(engine.signal_trade_log):
                                            if analytics_entry.get('trade_id') == trade_id:
                                                analytics_entry['exit_time'] = market_data.timestamp
                                                analytics_entry['exit_value'] = exit_value
                                                analytics_entry['exit_commission'] = exit_commission
                                                analytics_entry['pnl'] = trade_pnl
                                                analytics_entry['exit_reason'] = engine._last_exit_reason or 'System Exit'
                                                break
                                except Exception as e:
                                    print(f"❌ Error updating analytics for {account_name}: {e}")

                                # Remove trade
                                engine.active_trades.pop(trade_index)
                                engine.trade_entry_times.pop(trade_index)

                                print(f"   ✅ {account_name}: Exit executed, P&L: ${trade_pnl:.2f}")
            except Exception as e:
                print(f"❌ Error checking exits for {account_name}: {e}")

    def _force_close_all_positions(self, account_name: str, account_mgr: AccountManager, market_data: MarketData):
        """
        Force close all positions for an account (e.g., at market close)
        """
        engine = account_mgr.trading_engine

        if len(engine.active_trades) == 0:
            return

        print(f"🚨 Force closing {len(engine.active_trades)} trades for {account_name}")

        # Close all trades
        for trade_index in reversed(range(len(engine.active_trades))):
            try:
                trade_positions = engine.active_trades[trade_index]
                entry_time = engine.trade_entry_times[trade_index]

                if not trade_positions or not trade_positions[0].expiration_date:
                    continue

                expiration = trade_positions[0].expiration_date

                # Execute exit
                if engine.execute_exit(trade_positions, expiration):
                    # Calculate P&L
                    entry_cost = sum(pos.entry_price * 100 * pos.contracts for pos in trade_positions)
                    entry_commission = engine.calculate_total_trade_cost(trade_positions, is_exit=False)
                    exit_value = engine.calculate_exit_value(trade_positions, expiration, market_data.timestamp)
                    exit_commission = engine.calculate_total_trade_cost(trade_positions, is_exit=True)
                    trade_pnl = exit_value - entry_cost - entry_commission - exit_commission

                    # Update metrics
                    engine.update_daily_pnl(trade_pnl)
                    engine.update_trade_metrics(trade_pnl)

                    # Send telegram exit alert
                    trade_id = getattr(trade_positions[0], 'trade_id', None) if trade_positions else None
                    if trade_id is None:
                        trade_id = trade_index + 1

                    holding_time_minutes = (market_data.timestamp - entry_time).total_seconds() / 60
                    holding_time = f"{holding_time_minutes:.1f} minutes"

                    # Calculate win rate
                    completed_trades = [entry for entry in engine.signal_trade_log if entry.get('pnl') is not None]
                    total_completed_trades = len(completed_trades)
                    wins = sum(1 for entry in completed_trades if entry.get('pnl', 0) > 0)
                    win_rate = (wins / total_completed_trades * 100) if total_completed_trades > 0 else 0.0

                    exit_data = {
                        'trade_id': trade_id,
                        'exit_time': market_data.timestamp,
                        'holding_time': holding_time,
                        'positions': engine._positions_to_dict(trade_positions),
                        'exit_reason': 'Market Close - Forced Exit',
                        'entry_cost': entry_cost,
                        'entry_commission': entry_commission,
                        'total_entry_cost': entry_cost + entry_commission,
                        'exit_value': exit_value,
                        'exit_commission': exit_commission,
                        'pnl': trade_pnl,
                        'daily_pnl': engine.daily_pnl,
                        'daily_trades': engine.daily_trades,
                        'total_trades': engine.total_trades,
                        'win_rate': win_rate,
                        'total_pnl': engine.total_pnl,
                        'timing_status': engine.get_market_timing_status(market_data.timestamp)
                    }

                    try:
                        engine._send_exit_alert(exit_data)
                    except Exception as e:
                        print(f"❌ Error sending forced exit alert for {account_name}: {e}")

                    # Update analytics log
                    try:
                        if trade_id is not None:
                            for analytics_entry in reversed(engine.signal_trade_log):
                                if analytics_entry.get('trade_id') == trade_id:
                                    analytics_entry['exit_time'] = market_data.timestamp
                                    analytics_entry['exit_value'] = exit_value
                                    analytics_entry['exit_commission'] = exit_commission
                                    analytics_entry['pnl'] = trade_pnl
                                    analytics_entry['exit_reason'] = 'Market Close - Forced Exit'
                                    break
                    except Exception as e:
                        print(f"❌ Error updating analytics for forced exit {account_name}: {e}")

                    # Remove trade
                    engine.active_trades.pop(trade_index)
                    engine.trade_entry_times.pop(trade_index)

                    print(f"   ✅ {account_name}: Trade {trade_id} force closed, P&L: ${trade_pnl:.2f}")
                else:
                    print(f"   ❌ {account_name}: Failed to execute forced exit for trade {trade_index}")

            except Exception as e:
                print(f"❌ Error force closing trade {trade_index} for {account_name}: {e}")
                import traceback
                traceback.print_exc()

    def get_stats(self) -> Dict:
        """Get coordinator statistics"""
        return {
            'running': self.running,
            'total_signals': self.total_signals,
            'last_signal_time': self.last_flagged_time,
            'accounts': len(self.account_managers),
            'price_log_size': len(self.price_log)
        }
