"""
Analytics Engine for Trading Bot Strategy Optimization
Comprehensive backtesting manager that runs multiple backtest_single.py instances
"""

import pandas as pd
import numpy as np
import datetime
import json
import os
import itertools
import random
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Iterator
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
from dataclasses import dataclass, asdict
import csv
import gc
import sys
import io

# Import your existing modules
from backtest_single import run_backtest, create_config
from config.strategy import *
from config.backtest_single import *
from config.backtest_batch import *


@dataclass
class OptimizationResult:
    """Container for optimization results"""
    config: Dict
    win_rate: float
    total_pnl: float
    max_drawdown: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    profit_factor: float
    execution_time: float


def _run_backtest_worker_standalone(config: Dict) -> OptimizationResult:
    """
    Standalone worker function for parallel backtest execution
    This runs in a separate process and can be properly pickled
    """
    # Import here to avoid pickling issues
    from backtest_single import run_backtest
    import time
    
    start_time = time.time()
    
    try:
        # Run backtest using the backtest_single.py function
        result = run_backtest(
            config=config,
            return_results=True
        )
        
        execution_time = time.time() - start_time
        
        return OptimizationResult(
            config=config,
            win_rate=result.get('win_rate', 0.0),
            total_pnl=result.get('total_pnl', 0.0),
            max_drawdown=result.get('max_drawdown', 0.0),
            total_trades=result.get('total_trades', 0),
            winning_trades=result.get('winning_trades', 0),
            losing_trades=result.get('losing_trades', 0),
            avg_win=result.get('avg_win', 0.0),
            avg_loss=result.get('avg_loss', 0.0),
            profit_factor=result.get('profit_factor', 0.0),
            execution_time=execution_time
        )
        
    except Exception as e:
        print(f"Error in backtest: {e}")
        # Return a default result for failed runs
        return OptimizationResult(
            config=config,
            win_rate=0.0,
            total_pnl=0.0,
            max_drawdown=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            avg_win=0.0,
            avg_loss=0.0,
            profit_factor=0.0,
            execution_time=time.time() - start_time
        )


class AnalyticsEngine:
    """
    Comprehensive backtesting manager for strategy optimization
    Runs multiple backtest_single.py instances with different configurations
    """
    
    def __init__(self, base_config: Dict = None):
        """
        Initialize analytics engine
        
        Args:
            base_config: Base configuration dictionary (uses create_config() if None)
        """
        self.base_config = base_config or create_config()
        
        # Results storage
        self.results: List[OptimizationResult] = []
        
        # Use fixed parameters from config
        self.fixed_params = FIXED_PARAMETERS
        
        print(f"📋 Analytics Engine Configuration:")
        print(f"  Tunable Parameters: {len(TUNABLE_PARAMETERS)}")
        print(f"  Fixed Parameters: {len(self.fixed_params)}")
        print(f"  Max Combinations: {MAX_COMBINATIONS}")
        print(f"  Save Results: {SAVE_RESULTS}")
        print(f"  Top N Results: {TOP_N_RESULTS}")
    
    def generate_config_combinations(self) -> List[Dict]:
        """
        Generate configuration combinations for grid search
        Uses parameters from config/analytics.py
        """
        print("🔧 Generating configuration combinations...")
        tunable_params = TUNABLE_PARAMETERS
        
        # Generate all possible combinations
        param_names = list(tunable_params.keys())
        param_values = list(tunable_params.values())
        combinations = list(itertools.product(*param_values))
        
        print(f"📊 Grid search analysis:")
        print(f"  Total possible combinations: {len(combinations)}")
        print(f"  Max combinations limit: {MAX_COMBINATIONS}")
        
        # Limit combinations if too many
        if len(combinations) > MAX_COMBINATIONS:
            print(f"⚠️  Limiting combinations from {len(combinations)} to {MAX_COMBINATIONS}")
            combinations = random.sample(combinations, MAX_COMBINATIONS)
        
        configs = []
        for combo in combinations:
            config = self.base_config.copy()
            for name, value in zip(param_names, combo):
                config[name] = value
            configs.append(config)
        
        print(f"✅ Generated {len(configs)} configuration combinations for grid search")
        return configs
    
    def run_single_backtest(self, config: Dict) -> OptimizationResult:
        """
        Run a single backtest using backtest_single.py run_backtest function
        
        Args:
            config: Configuration dictionary
            
        Returns:
            OptimizationResult with performance metrics
        """
        start_time = time.time()
        
        try:
            # Run backtest using the backtest_single.py function
            # backtest_single.py handles all data file management internally
            result = run_backtest(
                config=config,
                return_results=True
            )
            
            execution_time = time.time() - start_time
            
            return OptimizationResult(
                config=config,
                win_rate=result.get('win_rate', 0.0),
                total_pnl=result.get('total_pnl', 0.0),
                max_drawdown=result.get('max_drawdown', 0.0),
                total_trades=result.get('total_trades', 0),
                winning_trades=result.get('winning_trades', 0),
                losing_trades=result.get('losing_trades', 0),
                avg_win=result.get('avg_win', 0.0),
                avg_loss=result.get('avg_loss', 0.0),
                profit_factor=result.get('profit_factor', 0.0),
                execution_time=execution_time
            )
            
        except Exception as e:
            print(f"Error in backtest: {e}")
            # Return a default result for failed runs
            return OptimizationResult(
                config=config,
                win_rate=0.0,
                total_pnl=0.0,
                max_drawdown=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_factor=0.0,
                execution_time=time.time() - start_time
            )
    
    def run_optimization(self) -> List[OptimizationResult]:
        """
        Run grid search optimization across multiple configurations in parallel
        
        Returns:
            List of OptimizationResult objects
        """
        # Generate configurations (grid search only)
        configs = self.generate_config_combinations()
        
        print(f"\n🚀 Starting grid search optimization:")
        print(f"  📋 Configurations to test: {len(configs)}")
        print(f"  🎯 Total backtests to run: {len(configs)}")
        
        # Check if running in Google Colab
        is_colab = self._is_running_in_colab()
        if is_colab:
            print("🔄 Detected Google Colab environment - using batching")
            return self._run_optimization_batched(configs)
        else:
            return self._run_optimization_parallel(configs)
    
    def _is_running_in_colab(self) -> bool:
        """Check if running in Google Colab environment"""
        try:
            import google.colab
            return True
        except ImportError:
            return False
    
    def _run_optimization_parallel(self, configs: List[Dict]) -> List[OptimizationResult]:
        """Run optimization using ProcessPoolExecutor for parallel processing"""
        all_results = []
        completed = 0
        total_runs = len(configs)
        start_time = time.time()
        
        # Use ProcessPoolExecutor with limited workers to avoid memory issues
        max_workers = min(8, mp.cpu_count())  # Default limit of 8
        print(f"🔄 Parallel execution setup:")
        print(f"  👥 Workers: {max_workers}")
        print(f"  ⚡ CPU Cores: {mp.cpu_count()}")
        print(f"  🎯 Target: {total_runs} backtests")
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all backtest tasks using the standalone worker function
            future_to_config = {}
            for config in configs:
                future = executor.submit(_run_backtest_worker_standalone, config)
                future_to_config[future] = config
            
            print(f"✅ All {total_runs} tasks submitted to executor")
            print(f"🔄 Collecting results...")
            
            # Collect results as they complete
            for future in as_completed(future_to_config):
                config = future_to_config[future]
                try:
                    result = future.result()
                    all_results.append(result)
                    completed += 1
                    
                    # Print progress every 5 backtests
                    if completed % 5 == 0:
                        elapsed = time.time() - start_time
                        eta = (elapsed / completed) * (total_runs - completed) if completed > 0 else 0
                        print(f"  ✅ Progress: {completed}/{total_runs} ({completed/total_runs*100:.1f}%) - ETA: {eta:.1f}s")
                        
                except Exception as e:
                    print(f"❌ Error in parallel backtest: {e}")
                    # Add default result for failed runs
                    all_results.append(OptimizationResult(
                        config=config,
                        win_rate=0.0,
                        total_pnl=0.0,
                        max_drawdown=0.0,
                        total_trades=0,
                        winning_trades=0,
                        losing_trades=0,
                        avg_win=0.0,
                        avg_loss=0.0,
                        profit_factor=0.0,
                        execution_time=0.0
                    ))
                    completed += 1
        
        total_time = time.time() - start_time
        print(f"✅ Parallel execution completed in {total_time:.2f}s")
        
        # Sort by win rate and total PnL
        print("📊 Sorting results by performance...")
        all_results.sort(key=lambda x: (x.win_rate, x.total_pnl), reverse=True)
        
        return all_results
    
    def _run_optimization_batched(self, configs: List[Dict]) -> List[OptimizationResult]:
        """Run optimization in batches for Colab environment"""
        BATCH_SIZE = 100  # Batch size for Colab
        all_results = []
        total_runs = len(configs)
        
        print(f"🔄 Processing {total_runs} configs in batches of {BATCH_SIZE}")
        
        # Process configs in batches
        for batch_start in range(0, total_runs, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_runs)
            batch_configs = configs[batch_start:batch_end]
            
            print(f"📦 Processing batch {batch_start//BATCH_SIZE + 1}: configs {batch_start+1}-{batch_end}")
            
            # Run batch in parallel
            batch_results = self._run_optimization_parallel(batch_configs)
            all_results.extend(batch_results)
            
            print(f"✅ Completed batch {batch_start//BATCH_SIZE + 1}: {len(batch_results)} results")
        
        # Sort by win rate and total PnL
        all_results.sort(key=lambda x: (x.win_rate, x.total_pnl), reverse=True)
        
        return all_results
    
    def print_top_results(self, results: List[OptimizationResult], top_n: int = None, log_file: io.TextIOBase = None):
        """Print top N results with detailed statistics, and optionally write to a log file"""
        top_n = top_n or TOP_N_RESULTS
        output = io.StringIO()
        print(f"\n{'='*80}", file=output)
        print(f"TOP {top_n} STRATEGY CONFIGURATIONS", file=output)
        print(f"{'='*80}", file=output)
        for i, result in enumerate(results[:top_n], 1):
            print(f"\n{i}. Configuration (Win Rate: {result.win_rate:.1f}%, PnL: ${result.total_pnl:.2f})", file=output)
            print(f"{'='*60}", file=output)
            print("Tunable Parameters:", file=output)
            for key, value in result.config.items():
                if key not in self.fixed_params:
                    print(f"  {key}: {value}", file=output)
            print(f"\nPerformance Metrics:", file=output)
            print(f"  Win Rate: {result.win_rate:.1f}%", file=output)
            print(f"  Total PnL: ${result.total_pnl:.2f}", file=output)
            print(f"  Max Drawdown: ${result.max_drawdown:.2f}", file=output)
            print(f"  Total Trades: {result.total_trades:.0f}", file=output)
            print(f"  Winning Trades: {result.winning_trades:.0f}", file=output)
            print(f"  Losing Trades: {result.losing_trades:.0f}", file=output)
            print(f"  Execution Time: {result.execution_time:.2f}s", file=output)
        # Print to console
        print(output.getvalue())
        # Also write to log file if provided
        if log_file:
            log_file.write(output.getvalue())
            log_file.flush()


def write_analytics_log(summary_text: str, results_text: str):
    """Write the analytics summary and results to a timestamped log file in logs/"""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = logs_dir / f"backtest_batch_log_{timestamp}.txt"
    with open(log_path, "w") as f:
        f.write(summary_text)
        f.write("\n\n")
        f.write(results_text)
    print(f"📄 Analytics log saved to: {log_path}")


def main():
    """Main function to run analytics"""
    print("🚀 Starting Trading Bot Analytics Engine (Grid Search Only)")
    print("="*60)
    
    # Print system information
    print(f"💻 System Information:")
    print(f"  CPU Cores: {mp.cpu_count()}")
    print(f"  Max Workers: {min(8, mp.cpu_count())}")
    print(f"  Python Version: {mp.sys.version}")
    print()
    
    # Initialize analytics engine
    analytics_start_time = time.time()
    print("🔧 Initializing Analytics Engine...")
    analytics = AnalyticsEngine()
    init_time = time.time() - analytics_start_time
    print(f"✅ Analytics Engine initialized in {init_time:.2f}s")
    
    # Run optimization (grid search only)
    print("\n🔄 Running grid search optimization...")
    optimization_start_time = time.time()
    results = analytics.run_optimization()
    optimization_time = time.time() - optimization_start_time
    
    # Print top results
    print("\n📊 Analyzing results...")
    results_start_time = time.time()
    # Capture summary and results output
    summary_buf = io.StringIO()
    print(f"\n{'='*80}", file=summary_buf)
    print(f"📈 ANALYTICS COMPLETE - PERFORMANCE SUMMARY", file=summary_buf)
    print(f"{'='*80}", file=summary_buf)
    print(f"✅ Total Configurations Tested: {len(results)}", file=summary_buf)
    total_time = time.time() - analytics_start_time
    avg_time_per_config = optimization_time / len(results) if results else 0
    print(f"⏱️ Total Runtime: {total_time:.2f}s ({total_time/60:.1f} minutes)", file=summary_buf)
    print(f"🔧 Initialization Time: {init_time:.2f}s", file=summary_buf)
    print(f"🔄 Optimization Time: {optimization_time:.2f}s", file=summary_buf)
    print(f"📊 Results Analysis Time: {time.time() - results_start_time:.2f}s", file=summary_buf)
    print(f"⚡  Average Time per Config: {avg_time_per_config:.2f}s", file=summary_buf)
    print(f"{'='*80}", file=summary_buf)
    summary_text = summary_buf.getvalue()
    # Print and log top results
    results_buf = io.StringIO()
    analytics.print_top_results(results, log_file=results_buf)
    results_text = results_buf.getvalue()
    # Write to log file
    write_analytics_log(summary_text, results_text)


if __name__ == "__main__":
    main() 