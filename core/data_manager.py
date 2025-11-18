import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal
from loguru import logger
from core.binance_client import BinanceClient

class DataManager:
    def __init__(self, client: BinanceClient):
        self.client = client
        self.data_cache: Dict[str, Dict[str, pd.DataFrame]] = {}
    
    def get_ohlcv_data(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500
    ) -> pd.DataFrame:
        """Obtém dados OHLCV"""
        cache_key = f"{symbol}_{timeframe}"
        
        # CORREÇÃO: Binance limita a 1500 candles por request
        if limit > 1500:
            logger.warning(f"Limit {limit} excede máximo da Binance (1500). Ajustando...")
            limit = 1500
        
        try:
            klines = self.client.get_klines(symbol, timeframe, limit)
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            self.data_cache[cache_key] = df
            return df
            
        except Exception as e:
            logger.error(f"Erro ao obter dados {symbol} {timeframe}: {e}")
            return pd.DataFrame()
    
    def get_multi_timeframe_data(
        self,
        symbol: str,
        timeframes: List[str],
        limit: int = 500
    ) -> Dict[str, pd.DataFrame]:
        """Obtém dados de múltiplos timeframes"""
        data = {}
        for tf in timeframes:
            data[tf] = self.get_ohlcv_data(symbol, tf, limit)
        return data
    
    def update_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Atualiza dados em tempo real"""
        return self.get_ohlcv_data(symbol, timeframe, limit=100)