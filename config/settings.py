from decimal import Decimal
from typing import List
import os

class Settings:
    # API Configuration
    BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
    BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')
    
    # Environment: 'backtest', 'testnet', 'live'
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'testnet')
    
    # Testnet URLs
    TESTNET_API_URL = 'https://testnet.binancefuture.com'
    TESTNET_WS_URL = 'wss://stream.binancefuture.com'
    
    # Trading Configuration
    TIMEFRAMES = ['5m', '15m']
    PRIMARY_TIMEFRAME = '5m'
    SECONDARY_TIMEFRAME = '15m'
    
    # Risk Management
    BASE_RISK_PER_TRADE = Decimal('0.02')  # 2%
    MAX_RISK_PER_TRADE = Decimal('0.03')   # 3%
    MIN_RISK_PER_TRADE = Decimal('0.015')  # 1.5%
    
    MAX_TOTAL_RISK = Decimal('0.10')  # 10% max exposure
    MAX_POSITIONS = 3
    
    MIN_POSITION_SIZE_USD = Decimal('15.0')
    MAX_POSITION_SIZE_USD = Decimal('5000.0')
    
    # Signal Thresholds
    SIGNAL_VERY_STRONG = 0.8
    SIGNAL_STRONG = 0.6
    SIGNAL_MEDIUM = 0.4
    SIGNAL_WEAK = 0.2
    
    # Take Profit Levels
    TP1_PERCENTAGE = Decimal('0.5')   # 50%
    TP2_PERCENTAGE = Decimal('0.75')  # 75%
    TP3_PERCENTAGE = Decimal('1.0')   # 100%
    
    TP1_EXIT_RATIO = Decimal('0.3')   # Sai 30% no TP1
    TP2_EXIT_RATIO = Decimal('0.4')   # Sai 40% no TP2
    TP3_EXIT_RATIO = Decimal('0.3')   # Sai 30% no TP3
    
    # Stop Loss
    TRAILING_STOP_ACTIVATION = Decimal('0.005')  # 0.5%
    TRAILING_STOP_DISTANCE = Decimal('0.003')     # 0.3%
    
    # Performance
    MIN_SHARPE_RATIO = 1.5
    MIN_WIN_RATE = 0.45
    MAX_DRAWDOWN = 0.15
    
    # Logging
    LOG_LEVEL = 'INFO'
    LOG_TO_FILE = True
    LOG_DIR = 'data/logs'

settings = Settings()