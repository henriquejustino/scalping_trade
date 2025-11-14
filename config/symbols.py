TRADING_SYMBOLS = [
    'BTCUSDT',
    'ETHUSDT'
    # 'BNBUSDT',
    # 'SOLUSDT',
    # 'ADAUSDT',
    # 'XRPUSDT',
    # 'DOGEUSDT',
    # 'AVAXUSDT',
    # 'DOTUSDT',
    # 'MATICUSDT'
]

SYMBOL_CONFIGS = {
    'BTCUSDT': {
        'min_notional': 5.0,
        'tick_size': 0.01,
        'step_size': 0.00001,
        'max_leverage': 125
    },
    'ETHUSDT': {
        'min_notional': 5.0,
        'tick_size': 0.01,
        'step_size': 0.0001,
        'max_leverage': 100
    },
    # Adicione configs para outros símbolos
}