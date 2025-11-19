from decimal import Decimal
from typing import List
import os

class Settings:
    # API Configuration
    BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
    BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')
    
    # Environment: 'backtest', 'testnet', 'live'
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'backtest')
    
    # URLs
    TESTNET_API_URL = 'https://testnet.binancefuture.com'
    TESTNET_WS_URL = 'wss://stream.binancefuture.com'
    LIVE_API_URL = 'https://fapi.binance.com'
    LIVE_WS_URL = 'wss://fstream.binance.com'
    
    # Trading Configuration
    TIMEFRAMES = ['5m', '15m']
    PRIMARY_TIMEFRAME = '5m'
    SECONDARY_TIMEFRAME = '15m'
    
    # ✅ RISK MANAGEMENT - CORRIGIDO
    BASE_RISK_PER_TRADE = Decimal('0.02')      # 2% base
    MAX_RISK_PER_TRADE = Decimal('0.03')       # Máx 3%
    MIN_RISK_PER_TRADE = Decimal('0.015')      # Mín 1.5%
    
    MAX_TOTAL_RISK = Decimal('0.10')           # 10% max exposure
    MAX_POSITIONS = 3                          # Máximo 3 posições simultâneas
    
    MIN_POSITION_SIZE_USD = Decimal('15.0')
    MAX_POSITION_SIZE_USD = Decimal('5000.0')
    
    # ✅ STOP LOSS E TAKE PROFIT
    TP1_PERCENTAGE = Decimal('0.5')            # 50% da distância
    TP2_PERCENTAGE = Decimal('0.75')           # 75% da distância
    TP3_PERCENTAGE = Decimal('1.0')            # 100% (target completo)
    
    TP1_EXIT_RATIO = Decimal('0.3')            # Sai 30% no TP1
    TP2_EXIT_RATIO = Decimal('0.4')            # Sai 40% no TP2
    TP3_EXIT_RATIO = Decimal('0.3')            # Sai 30% no TP3
    
    # ✅ SIGNAL THRESHOLDS
    SIGNAL_VERY_STRONG = 0.8
    SIGNAL_STRONG = 0.6
    SIGNAL_MEDIUM = 0.4
    SIGNAL_WEAK = 0.2
    MIN_SIGNAL_STRENGTH = 0.25
    
    # ✅ DRAWDOWN LIMITS
    MAX_DRAWDOWN = Decimal('0.15')             # 15% máximo
    MAX_DAILY_LOSS = Decimal('0.05')           # 5% por dia
    
    # ✅ PERFORMANCE TARGETS
    MIN_SHARPE_RATIO = 1.5
    MIN_WIN_RATE = 0.45
    TARGET_PROFIT_FACTOR = 1.5
    
    # Trailing Stop
    TRAILING_STOP_ACTIVATION = Decimal('0.005')  # 0.5%
    TRAILING_STOP_DISTANCE = Decimal('0.003')     # 0.3%
    
    # Logging
    LOG_LEVEL = 'INFO'
    LOG_TO_FILE = True
    LOG_DIR = 'data/logs'
    
    # Database (para tracking de trades)
    USE_DATABASE = True
    DB_PATH = 'data/trades.db'
    
    # Circuit Breakers
    CIRCUIT_BREAKER_ENABLED = True
    CIRCUIT_BREAKER_CONSECUTIVE_LOSSES = 5
    CIRCUIT_BREAKER_MAX_DRAWDOWN_PER_HOUR = Decimal('0.05')

settings = Settings()