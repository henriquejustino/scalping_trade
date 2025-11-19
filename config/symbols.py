TRADING_SYMBOLS = [
    'BTCUSDT',
    'ETHUSDT'
]

SYMBOL_CONFIGS = {
    'BTCUSDT': {
        'min_notional': 5.0,
        'tick_size': 0.01,
        'step_size': 0.00001,
        'max_leverage': 125,
        'base_spread': 0.005
    },
    'ETHUSDT': {
        'min_notional': 5.0,
        'tick_size': 0.01,
        'step_size': 0.0001,
        'max_leverage': 100,
        'base_spread': 0.005
    },
}