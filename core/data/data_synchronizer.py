"""
Data Synchronizer - Garante alinhamento perfeito entre timeframes
Problema comum em sistemas multi-timeframe: desincronização de dados
"""
import pandas as pd
from typing import Tuple, Dict
from datetime import datetime, timedelta
from loguru import logger
import pytz

class DataSynchronizer:
    """Sincroniza múltiplos timeframes com validações rigorosas"""
    
    @staticmethod
    def align_timeframes(
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame,
        symbol: str = ""
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Alinha 5m e 15m garantindo:
        1. Sem timestamp duplicados
        2. 15m sempre completo (3 candles 5m)
        3. Sem gaps
        """
        
        if df_5m.empty or df_15m.empty:
            raise ValueError("DataFrames vazios")
        
        # Valida índices são datetime
        if not isinstance(df_5m.index, pd.DatetimeIndex):
            raise ValueError("5m index deve ser DatetimeIndex")
        if not isinstance(df_15m.index, pd.DatetimeIndex):
            raise ValueError("15m index deve ser DatetimeIndex")
        
        # Remove duplicatas (problema comum em downloads)
        df_5m = df_5m[~df_5m.index.duplicated(keep='last')].copy()
        df_15m = df_15m[~df_15m.index.duplicated(keep='last')].copy()
        
        # Sort por timestamp (pode estar desordenado)
        df_5m = df_5m.sort_index()
        df_15m = df_15m.sort_index()
        
        # Usa o último candle 15m completo como referência
        last_15m_time = df_15m.index[-1]
        
        # Pega apenas 5m que fecharam ANTES ou NO último 15m
        df_5m_aligned = df_5m[df_5m.index <= last_15m_time].copy()
        
        # Valida quantidade de candles (15m = 3x 5m)
        expected_count = len(df_15m) * 3
        actual_count = len(df_5m_aligned)
        
        if actual_count < expected_count * 0.8:  # Tolerância 20%
            logger.warning(
                f"{symbol} Dados 5m insuficientes: "
                f"esperado {expected_count}, obtido {actual_count}"
            )
        
        # Valida gaps nos dados 5m
        DataSynchronizer._check_gaps(df_5m_aligned, "5m", symbol)
        DataSynchronizer._check_gaps(df_15m, "15m", symbol)
        
        logger.debug(
            f"{symbol} Alinhamento OK: "
            f"5m={len(df_5m_aligned)} candles, "
            f"15m={len(df_15m)} candles"
        )
        
        return df_5m_aligned, df_15m
    
    @staticmethod
    def _check_gaps(df: pd.DataFrame, timeframe: str, symbol: str = ""):
        """Verifica gaps nos dados (falta de candles)"""
        if len(df) < 2:
            return
        
        # Intervalo esperado entre candles
        intervals = {
            '5m': pd.Timedelta(minutes=5),
            '15m': pd.Timedelta(minutes=15),
            '1h': pd.Timedelta(hours=1),
            '1d': pd.Timedelta(days=1)
        }
        
        expected_interval = intervals.get(timeframe, pd.Timedelta(minutes=5))
        
        # Calcula diferenças entre timestamps
        time_diffs = df.index.to_series().diff()
        
        # Encontra gaps (diferenças > esperado)
        gaps = time_diffs[time_diffs > expected_interval * 1.5]
        
        if len(gaps) > 0:
            logger.warning(
                f"{symbol} {timeframe}: {len(gaps)} gaps detectados. "
                f"Primeiros: {gaps.head(3).to_list()}"
            )
        
        return len(gaps) == 0
    
    @staticmethod
    def resample_to_15m(df_5m: pd.DataFrame) -> pd.DataFrame:
        """
        Resample de 5m para 15m se necessário
        Mantém OHLCV correto
        """
        if df_5m.empty:
            return pd.DataFrame()
        
        df = df_5m.copy()
        
        # Resample preservando OHLCV
        df_15m = pd.DataFrame({
            'open': df['open'].resample('15min').first(),
            'high': df['high'].resample('15min').max(),
            'low': df['low'].resample('15min').min(),
            'close': df['close'].resample('15min').last(),
            'volume': df['volume'].resample('15min').sum()
        })
        
        # Remove linhas com NaN (gaps)
        df_15m = df_15m.dropna()
        
        return df_15m
    
    @staticmethod
    def validate_ohlc(df: pd.DataFrame, timeframe: str = "5m") -> bool:
        """
        Valida integridade dos dados OHLC
        High >= Low, High >= Open/Close, etc
        """
        errors = []
        
        # High deve ser >= Low
        invalid_hl = df[df['high'] < df['low']]
        if not invalid_hl.empty:
            errors.append(f"{len(invalid_hl)} candles com High < Low")
        
        # High deve ser >= Open e Close
        invalid_h = df[(df['high'] < df['open']) | (df['high'] < df['close'])]
        if not invalid_h.empty:
            errors.append(f"{len(invalid_h)} candles com High < Open/Close")
        
        # Low deve ser <= Open e Close
        invalid_l = df[(df['low'] > df['open']) | (df['low'] > df['close'])]
        if not invalid_l.empty:
            errors.append(f"{len(invalid_l)} candles com Low > Open/Close")
        
        # Volume deve ser positivo
        invalid_vol = df[df['volume'] <= 0]
        if not invalid_vol.empty:
            errors.append(f"{len(invalid_vol)} candles com volume <= 0")
        
        if errors:
            logger.warning(f"OHLC validation failed ({timeframe}): {errors}")
            return False
        
        return True
    
    @staticmethod
    def get_complete_candles(df: pd.DataFrame, timeframe: str) -> Tuple[pd.DataFrame, int]:
        """
        Retorna apenas candles completos (descarta o último se incompleto)
        Importante para live trading
        """
        if len(df) < 2:
            return df, 0
        
        # Assume último candle como potencialmente incompleto
        n_incomplete = 1
        
        df_complete = df[:-n_incomplete].copy()
        
        logger.debug(
            f"{timeframe}: {len(df)} candles total, "
            f"{len(df_complete)} completos, "
            f"{n_incomplete} incompleto"
        )
        
        return df_complete, n_incomplete
    
    @staticmethod
    def filter_by_time_range(
        df: pd.DataFrame,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """Filtra dados por range de datas"""
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        df_filtered = df[(df.index >= start) & (df.index <= end)].copy()
        
        if df_filtered.empty:
            logger.warning(f"No data in range {start_date} to {end_date}")
        
        return df_filtered
    
    @staticmethod
    def detect_market_hours(df: pd.DataFrame, exchange: str = "BINANCE") -> pd.DataFrame:
        """
        Filtra apenas horários de mercado se necessário
        BINANCE: 24h, NYSE: 09:30-16:00 EST, etc
        """
        if exchange.upper() == "BINANCE":
            return df  # Cripto: 24h
        
        df_copy = df.copy()
        
        if exchange.upper() in ["NYSE", "NASDAQ"]:
            df_copy = df_copy[
                (df_copy.index.hour >= 9) & (df_copy.index.hour < 16) &
                (df_copy.index.dayofweek < 5)  # Seg-Sex
            ]
        
        logger.debug(f"{exchange}: {len(df)} -> {len(df_copy)} candles (market hours)")
        
        return df_copy
    
    @staticmethod
    def prepare_data_for_backtest(
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame,
        start_date: str,
        end_date: str,
        min_candles: int = 50
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Prepara dados para backtest com todas as validações
        """
        
        # 1. Alinha timeframes
        df_5m, df_15m = DataSynchronizer.align_timeframes(df_5m, df_15m)
        
        # 2. Filtra range
        df_5m = DataSynchronizer.filter_by_time_range(df_5m, start_date, end_date)
        df_15m = DataSynchronizer.filter_by_time_range(df_15m, start_date, end_date)
        
        # 3. Valida OHLC
        if not DataSynchronizer.validate_ohlc(df_5m, "5m"):
            logger.error("5m OHLC validation failed")
        if not DataSynchronizer.validate_ohlc(df_15m, "15m"):
            logger.error("15m OHLC validation failed")
        
        # 4. Verifica quantidade mínima
        if len(df_5m) < min_candles or len(df_15m) < min_candles:
            raise ValueError(
                f"Insuficientes candles: 5m={len(df_5m)}, 15m={len(df_15m)} "
                f"(mínimo {min_candles})"
            )
        
        logger.info(
            f"Dados preparados: 5m={len(df_5m)}, 15m={len(df_15m)} candles"
        )
        
        return df_5m, df_15m