"""
Multi-Account Configuration
Supports 10+ Tradier accounts (mix of live/paper) with strategy overrides
"""

# === Tradier API URLs (Constants) ===
TRADIER_LIVE_API_URL = 'https://api.tradier.com/v1'
TRADIER_PAPER_API_URL = 'https://sandbox.tradier.com/v1'

TEST_TELEGRAM_BOT_MODE = False
TEST_TELEGRAM_BOT_TOKEN = '8499671099:AAFsxsxQLJ5MLMghPgW9pxJFyiznP484dxw'
TEST_TELEGRAM_CHAT_ID = '-1003173585598'

# === Account Configurations ===
ACCOUNTS = [
    {
        'enabled': True,
        # Live Trading Credentials
        'live': {
            'account_id': '6YB57979',
            'access_token': 'bcuTwm0ocPZja7J2L159sBNnGHBT'
        },

        # Paper Trading Credentials
        'paper': {
            'account_id': 'VA32928735',
            'access_token': 'vZkJpiR828SUs7nO02B0MQ4VmXhd'
        },

        # Strategy Overrides (optional - will use config/strategy.py defaults if not specified)
        'strategy_overrides': {
            'RISK_PER_SIDE': 400,  # Override default 400
        },

        # Telegram Configuration (each account gets own bot/chat)
        'telegram': {
            'bot_token': '8352695755:AAFblmWmOYRUnWC36yjPxGVu9vKU7fljg7k',
            'chat_id': '-1002860850553',
            'enabled': True
        },

        # Logging Configuration
        'logging': {
            'log_prefix': 'account1',
            'separate_files': True,
            'log_level': 'INFO'
        }
    },
    {
        'enabled': True,
        # Live Trading Credentials
        'live': {
            'account_id': '6YB58198',
            'access_token': 'A2I3nmzNJ9R3G8uTJGIy2eb6dosZ'
        },

        # Paper Trading Credentials
        'paper': {
            'account_id': 'VA54807612',
            'access_token': 'gtYAWV6ElGnz71nBbsdKLAbG78wm'
        },

        # Strategy Overrides - Conservative settings
        'strategy_overrides': {
            'RISK_PER_SIDE': 500,
        },

        # Telegram Configuration
        'telegram': {
            'bot_token': '8365769121:AAGTwocVI35c8a-9fMJyLq4jbbuBK2M3Zqk',
            'chat_id': '-1003024731151',
            'enabled': True
        },

        # Logging Configuration
        'logging': {
            'log_prefix': 'account2_conservative',
            'separate_files': True,
            'log_level': 'INFO'
        }
    },
    {
        'enabled': True,
        # Live Trading Credentials
        'live': {
            'account_id': '6YB62290',
            'access_token': 'gfbV67Xs8OvuFuHwsGR6nbgf17ob'
        },

        # Paper Trading Credentials
        'paper': {
            'account_id': 'VA17544996',
            'access_token': 'rMi9xHKc7uU8gvGyzr9gpBE1krtn'
        },

        # Strategy Overrides - Aggressive settings
        'strategy_overrides': {
            'RISK_PER_SIDE': 500,
        },

        # Telegram Configuration
        'telegram': {
            'bot_token': '8344861799:AAEpwdIzxx1SR_igneNJ8YHZD3AU7UQw0Hk',
            'chat_id': '-1002868297314',
            'enabled': True
        },

        # Logging Configuration
        'logging': {
            'log_prefix': 'account3_aggressive',
            'separate_files': True,
            'log_level': 'INFO'
        }
    },
    {
        'enabled': True,  # Disabled example
        # Live Trading Credentials
        'live': {
            'account_id': '6YB62170',
            'access_token': '7MHCiKvMXuJwNxb4mz0NtuM0bPR3'
        },

        # Paper Trading Credentials
        'paper': {
            'account_id': 'VA35345583',
            'access_token': 'TJ8lo3B89EwVG4PL3Qg6WvcfGm4s'
        },

        # Strategy Overrides - Testing settings
        'strategy_overrides': {
            'RISK_PER_SIDE': 1500
        },

        # Telegram Configuration
        'telegram': {
            'bot_token': '8439985889:AAEkQlpjHInjM_l8Npfn3EV7zowcF-sToWI',
            'chat_id': '-1003036527422',
            'enabled': True  # No notifications for disabled account
        },

        # Logging Configuration
        'logging': {
            'log_prefix': 'account4_testing',
            'separate_files': True,
            'log_level': 'DEBUG'
        }
    },

    # Add more accounts as needed (up to 10+)
    # {
    #     'name': 'Live_Account_3',
    #     'account_id': 'YOUR_LIVE_ACCOUNT_ID_3',
    #     'access_token': 'YOUR_LIVE_ACCESS_TOKEN_3',
    #     'api_url': 'https://api.tradier.com/v1',
    #     'mode': 'live',
    #     'enabled': True,
    #     'strategy_overrides': {},
    #     'telegram': {
    #         'bot_token': 'YOUR_TELEGRAM_BOT_TOKEN_5',
    #         'chat_id': 'YOUR_TELEGRAM_CHAT_ID_5',
    #         'enabled': True
    #     },
    #     'logging': {
    #         'log_prefix': 'live_acc3',
    #         'separate_files': True,
    #         'log_level': 'INFO'
    #     }
    # },
]

# === Global Multi-Account Settings ===

# Shared Data Feed Configuration
SHARED_DATA_CONFIG = {
    # Use specific account index for data feed (None = auto-select first enabled account)
    'data_source_account': None,  # Account index or None for auto-select
    'fallback_to_paper': True,    # Use paper account if no live accounts enabled
    'polling_interval': 1,        # 1-second polling (same as current)
    'max_retries': 5,
    'retry_delay': 2
}

# Multi-Account Orchestration
ORCHESTRATION = {
    'startup_delay_between_accounts': 0,  # No delay - start all accounts simultaneously
    'health_check_interval': 30,          # Check account health every 30 seconds
    'auto_restart_failed_accounts': True,
    'max_account_restart_attempts': 3
}


# Logging Configuration
MULTI_ACCOUNT_LOGGING = {
    'central_log_file': 'logs/multi_account_manager.log',
    'account_log_directory': 'logs/accounts/',
    'log_rotation': True,
    'max_log_size_mb': 100,
    'backup_count': 5
}

# === Utility Functions ===

def get_enabled_accounts(mode: str = None):
    """
    Get list of enabled accounts for specified mode

    Args:
        mode: 'live' or 'paper' or None (all enabled accounts)

    Returns:
        List of account configurations with mode-specific credentials
    """
    enabled_accounts = []

    for i, acc in enumerate(ACCOUNTS):
        if not acc.get('enabled', False):
            continue

        if mode and mode not in acc:
            continue

        # Create account config with mode-specific credentials
        account_config = acc.copy()

        if mode:
            # Replace credentials with mode-specific ones
            mode_credentials = acc[mode]
            api_url = TRADIER_LIVE_API_URL if mode == 'live' else TRADIER_PAPER_API_URL
            account_config.update({
                'account_id': mode_credentials['account_id'],
                'access_token': mode_credentials['access_token'],
                'api_url': api_url,
                'mode': mode,
                'account_index': i  # Use index as identifier instead of name
            })

        # Override telegram configuration in test mode
        if TEST_TELEGRAM_BOT_MODE:
            account_config['telegram'] = {
                'bot_token': TEST_TELEGRAM_BOT_TOKEN,
                'chat_id': TEST_TELEGRAM_CHAT_ID,
                'enabled': True
            }

        enabled_accounts.append(account_config)

    return enabled_accounts

def get_live_accounts():
    """Get list of enabled accounts with live credentials"""
    return get_enabled_accounts('live')

def get_paper_accounts():
    """Get list of enabled accounts with paper credentials"""
    return get_enabled_accounts('paper')

def get_account_by_index(index, mode=None):
    """
    Get specific account by index

    Args:
        index: Account index in ACCOUNTS list
        mode: 'live' or 'paper' or None

    Returns:
        Account config with mode-specific credentials if mode specified
    """
    if index < 0 or index >= len(ACCOUNTS):
        return None

    acc = ACCOUNTS[index]
    if mode:
        if mode not in acc:
            return None
        account_config = acc.copy()
        mode_credentials = acc[mode]
        api_url = TRADIER_LIVE_API_URL if mode == 'live' else TRADIER_PAPER_API_URL
        account_config.update({
            'account_id': mode_credentials['account_id'],
            'access_token': mode_credentials['access_token'],
            'api_url': api_url,
            'mode': mode,
            'account_index': index
        })
        # Override telegram configuration in test mode (consistency)
        if TEST_TELEGRAM_BOT_MODE:
            account_config['telegram'] = {
                'bot_token': TEST_TELEGRAM_BOT_TOKEN,
                'chat_id': TEST_TELEGRAM_CHAT_ID,
                'enabled': True
            }
        return account_config
    return acc

def validate_account_config(account, mode=None, account_index=None):
    """
    Validate account configuration

    Args:
        account: Account configuration
        mode: 'live' or 'paper' - validates mode-specific credentials
        account_index: Account index for error messages
    """
    required_fields = ['enabled']
    account_ref = f"Account #{account_index}" if account_index is not None else "Account"

    for field in required_fields:
        if field not in account:
            raise ValueError(f"{account_ref} missing required field: {field}")

    # Validate mode-specific credentials
    if mode:
        if mode not in account:
            raise ValueError(f"{account_ref} missing {mode} configuration")

        mode_config = account[mode]
        required_mode_fields = ['account_id', 'access_token']
        for field in required_mode_fields:
            if field not in mode_config:
                raise ValueError(f"{account_ref} missing {mode}.{field}")
    else:
        # Validate both live and paper configs exist
        for mode_name in ['live', 'paper']:
            if mode_name not in account:
                raise ValueError(f"{account_ref} missing {mode_name} configuration")
            validate_account_config(account, mode_name, account_index)

    return True

def get_data_source_account(mode):
    """
    Get the account to use for shared data feed

    Args:
        mode: 'live' or 'paper'

    Returns:
        Account config with mode-specific credentials
    """
    if SHARED_DATA_CONFIG['data_source_account'] is not None:
        return get_account_by_index(SHARED_DATA_CONFIG['data_source_account'], mode)

    # Auto-select first enabled account for specified mode
    accounts = get_enabled_accounts(mode)
    if accounts:
        return accounts[0]

    raise ValueError(f"No enabled accounts found for {mode} mode")

def get_account_summary(mode=None):
    """
    Get summary of all accounts

    Args:
        mode: 'live' or 'paper' or None (all accounts)

    Returns:
        Dictionary with account statistics
    """
    if mode:
        enabled = get_enabled_accounts(mode)
        return {
            'total_accounts': len(ACCOUNTS),
            'enabled_accounts': len(enabled),
            'mode': mode,
            'disabled_accounts': len(ACCOUNTS) - len(enabled)
        }
    else:
        enabled = get_enabled_accounts()
        live_accounts = get_live_accounts()
        paper_accounts = get_paper_accounts()
        return {
            'total_accounts': len(ACCOUNTS),
            'enabled_accounts': len(enabled),
            'live_accounts': len(live_accounts),
            'paper_accounts': len(paper_accounts),
            'disabled_accounts': len(ACCOUNTS) - len(enabled)
        }