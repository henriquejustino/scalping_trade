"""
Data Manager V2 - Gerenciador de Dados Robusto
Carrega, valida, sincroniza e fornece dados OHLCV
"""
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from loguru import logger
import pytz
from core.binance_client import BinanceClient
from core.data.data_synchronizer import DataSynchronizer

logger.add("data/logs/data_manager_{time}.log", rotation="1 day")

class DataManager:
    """Gerencia dados OHLCV com validações e sincronização"""
    
    def __init__(self, client: BinanceClient):
        self.client = client
        self.data_cache: Dict[str, Dict[str, pd.DataFrame]] = {}
        self.data_stats: Dict[str, Dict] = {}
        self.last_update: Dict[str, datetime] = {}
        self.synchronizer = DataSynchronizer()
    
    def get_ohlcv_data(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500
    ) -> pd.DataFrame:
        """
        ✅ ROBUSTO: Obtém dados OHLCV com validações
        
        Args:
            symbol: Ex. 'BTCUSDT'
            timeframe: Ex. '5m', '15m', '1h'
            limit: Quantidade de candles (máx 1500)
        
        Returns:
            DataFrame com OHLCV ou vazio se erro
        """
        
        try:
            # === 1. VALIDAÇÃO ===
            if limit > 1500:
                logger.warning(f"Limit {limit} > 1500, ajustando")
                limit = 1500
            
            if limit < 10:
                logger.error(f"Limit {limit} muito pequeno")
                return pd.DataFrame()
            
            # === 2. VERIFICA CACHE ===
            cache_key = f"{symbol}_{timeframe}"
            
            if cache_key in self.data_cache:
                cached_data = self.data_cache[cache_key]
                if cached_data is not None and not cached_data.empty:
                    # Cache com menos de 1 minuto
                    if (datetime.now() - self.last_update.get(cache_key, datetime.now())).total_seconds() < 60:
                        logger.debug(f"✅ Cache hit: {cache_key}")
                        return cached_data
            
            # === 3. CARREGA DA EXCHANGE ===
            logger.debug(f"📥 Carregando {symbol} {timeframe}...")
            
            klines = self.client.get_klines(symbol, timeframe, limit)
            
            if not klines:
                logger.warning(f"Nenhum dado retornado: {symbol} {timeframe}")
                return pd.DataFrame()
            
            # === 4. CONVERTE PARA DATAFRAME ===
            df = self._convert_klines_to_df(klines, timeframe)
            
            if df.empty:
                logger.warning(f"DataFrame vazio após conversão: {symbol}")
                return pd.DataFrame()
            
            # === 5. VALIDA DADOS ===
            if not DataSynchronizer.validate_ohlc(df, timeframe):
                logger.error(f"OHLC inválido para {symbol} {timeframe}")
                return pd.DataFrame()
            
            # === 6. ARMAZENA NO CACHE ===
            if symbol not in self.data_cache:
                self.data_cache[symbol] = {}
            
            self.data_cache[symbol][timeframe] = df
            self.last_update[cache_key] = datetime.now()
            
            # === 7. REGISTRA STATS ===
            self._update_stats(symbol, timeframe, df)
            
            logger.info(
                f"✅ Dados carregados: {symbol} {timeframe} | "
                f"{len(df)} candles | "
                f"Range: ${df['close'].min():.2f} - ${df['close'].max():.2f}"
            )
            
            return df
        
        except Exception as e:
            logger.error(f"❌ Erro ao carregar {symbol} {timeframe}: {e}")
            return pd.DataFrame()
    
    def _convert_klines_to_df(self, klines: List, timeframe: str) -> pd.DataFrame:
        """Converte klines da Binance para DataFrame"""
        
        try:
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            # Converte timestamp
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Converte tipos
            for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Remove linhas com NaN
            df = df.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
            
            # Sort por timestamp
            df = df.sort_index()
            
            return df
        
        except Exception as e:
            logger.error(f"Erro ao converter klines: {e}")
            return pd.DataFrame()
    
    def get_multi_timeframe_data(
        self,
        symbol: str,
        timeframes: List[str],
        limit: int = 500
    ) -> Dict[str, pd.DataFrame]:
        """
        ✅ Obtém dados de múltiplos timeframes
        
        Returns:
            Dict com {timeframe: DataFrame}
        """
        
        data = {}
        
        for tf in timeframes:
            df = self.get_ohlcv_data(symbol, tf, limit)
            if not df.empty:
                data[tf] = df
        
        return data
    
    def update_data(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """
        ✅ Atualiza dados em tempo real (apenas últimos N candles)
        Mais rápido que carregar histórico completo
        """
        
        return self.get_ohlcv_data(symbol, timeframe, limit)
    
    def get_aligned_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        ✅ Retorna 5m e 15m perfeitamente sincronizados
        
        Args:
            symbol: Ex. 'BTCUSDT'
            start_date: Ex. '2024-01-01'
            end_date: Ex. '2024-01-31'
        
        Returns:
            (df_5m_aligned, df_15m_aligned)
        """
        
        try:
            # Carrega ambos
            df_5m = self.get_ohlcv_data(symbol, '5m', limit=1500)
            df_15m = self.get_ohlcv_data(symbol, '15m', limit=1500)
            
            if df_5m.empty or df_15m.empty:
                return pd.DataFrame(), pd.DataFrame()
            
            # Alinha
            df_5m, df_15m = DataSynchronizer.align_timeframes(df_5m, df_15m, symbol)
            
            # Filtra por data range
            df_5m = DataSynchronizer.filter_by_time_range(df_5m, start_date, end_date)
            df_15m = DataSynchronizer.filter_by_time_range(df_15m, start_date, end_date)
            
            return df_5m, df_15m
        
        except Exception as e:
            logger.error(f"Erro ao obter dados alinhados: {e}")
            return pd.DataFrame(), pd.DataFrame()
    
    def get_live_data(
        self,
        symbol: str,
        timeframe: str
    ) -> pd.DataFrame:
        """
        ✅ Obtém dados para live trading (últimos candles apenas)
        Ignora cache e força atualização
        """
        
        try:
            # Limpa cache para forçar atualização
            cache_key = f"{symbol}_{timeframe}"
            if cache_key in self.last_update:
                del self.last_update[cache_key]
            
            # Carrega dados recentes
            df = self.get_ohlcv_data(symbol, timeframe, limit=100)
            
            # Retorna apenas candles completos (descarta último se incompleto)
            df_complete, n_incomplete = DataSynchronizer.get_complete_candles(df, timeframe)
            
            return df_complete
        
        except Exception as e:
            logger.error(f"Erro ao obter live data: {e}")
            return pd.DataFrame()
    
    def _update_stats(self, symbol: str, timeframe: str, df: pd.DataFrame):
        """Registra estatísticas dos dados"""
        
        if df.empty:
            return
        
        key = f"{symbol}_{timeframe}"
        
        self.data_stats[key] = {
            'rows': len(df),
            'min_price': float(df['low'].min()),
            'max_price': float(df['high'].max()),
            'avg_price': float(df['close'].mean()),
            'avg_volume': float(df['volume'].mean()),
            'total_volume': float(df['volume'].sum()),
            'volatility': float(df['close'].std()),
            'date_range': f"{df.index[0]} to {df.index[-1]}"
        }
    
    def get_data_stats(self, symbol: str = None) -> Dict:
        """Retorna estatísticas dos dados carregados"""
        
        if symbol:
            return {k: v for k, v in self.data_stats.items() if k.startswith(symbol)}
        return self.data_stats
    
    def get_cache_info(self) -> Dict:
        """Retorna informações do cache"""
        
        info = {
            'cached_symbols': list(self.data_cache.keys()),
            'cache_size': len(self.data_cache),
            'last_updates': {k: v.isoformat() for k, v in self.last_update.items()}
        }
        
        return info
    
    def clear_cache(self, symbol: str = None):
        """Limpa cache de dados"""
        
        if symbol:
            if symbol in self.data_cache:
                del self.data_cache[symbol]
                logger.info(f"Cache cleared for {symbol}")
        else:
            self.data_cache.clear()
            self.last_update.clear()
            logger.info("Cache cleared completely")
    
    def validate_data_quality(
        self,
        symbol: str,
        timeframe: str,
        min_candles: int = 50
    ) -> Tuple[bool, str]:
        """
        ✅ Valida qualidade dos dados
        
        Returns:
            (is_valid, message)
        """
        
        df = self.get_ohlcv_data(symbol, timeframe)
        
        if df.empty:
            return False, "Dados vazios"
        
        if len(df) < min_candles:
            return False, f"Dados insuficientes: {len(df)} < {min_candles}"
        
        # Valida OHLC
        if not DataSynchronizer.validate_ohlc(df, timeframe):
            return False, "OHLC inválido"
        
        # Valida gaps
        if not DataSynchronizer._check_gaps(df, timeframe, symbol):
            return False, "Gaps detectados nos dados"
        
        # Valida volume
        if (df['volume'] <= 0).any():
            return False, "Volume zero ou negativo detectado"
        
        return True, "✅ Qualidade OK"
    
    def resample_data(
        self,
        symbol: str,
        from_timeframe: str,
        to_timeframe: str
    ) -> pd.DataFrame:
        """
        ✅ Resample de um timeframe para outro
        
        Ex: 5m -> 15m, 15m -> 1h
        """
        
        try:
            df = self.get_ohlcv_data(symbol, from_timeframe, limit=1500)
            
            if df.empty:
                return pd.DataFrame()
            
            # Resample preservando OHLCV
            df_resampled = pd.DataFrame({
                'open': df['open'].resample(to_timeframe).first(),
                'high': df['high'].resample(to_timeframe).max(),
                'low': df['low'].resample(to_timeframe).min(),
                'close': df['close'].resample(to_timeframe).last(),
                'volume': df['volume'].resample(to_timeframe).sum()
            })
            
            df_resampled = df_resampled.dropna()
            
            logger.info(
                f"✅ Resampled {symbol}: {from_timeframe} -> {to_timeframe} | "
                f"{len(df)} -> {len(df_resampled)} candles"
            )
            
            return df_resampled
        
        except Exception as e:
            logger.error(f"Erro ao fazer resample: {e}")
            return pd.DataFrame()
    
    def get_price_info(self, symbol: str, timeframe: str = '5m') -> Dict:
        """
        ✅ Retorna informações de preço atual
        """
        
        df = self.get_ohlcv_data(symbol, timeframe, limit=50)
        
        if df.empty:
            return {}
        
        current_price = float(df['close'].iloc[-1])
        prev_price = float(df['close'].iloc[-2]) if len(df) > 1 else current_price
        
        change = ((current_price - prev_price) / prev_price * 100) if prev_price != 0 else 0
        
        return {
            'symbol': symbol,
            'current_price': current_price,
            'prev_price': prev_price,
            'price_change_pct': change,
            'high_24h': float(df['high'].tail(288).max()) if timeframe == '5m' else float(df['high'].max()),
            'low_24h': float(df['low'].tail(288).min()) if timeframe == '5m' else float(df['low'].min()),
            'avg_volume': float(df['volume'].mean()),
            'volatility': float(df['close'].std())
        }
    
    def get_time_to_next_candle(self, timeframe: str) -> int:
        """
        ✅ Retorna segundos até próximo candle fechar
        """
        
        intervals = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '1h': 3600,
            '1d': 86400
        }
        
        interval_seconds = intervals.get(timeframe, 300)
        
        # UTC
        now = datetime.utcnow()
        unix_timestamp = now.timestamp()
        
        # Calcula tempo até próximo intervalo
        time_to_next = interval_seconds - (int(unix_timestamp) % interval_seconds)
        
        return time_to_next
    
    def log_data_summary(self):
        """Loga sumário de dados em cache"""
        
        logger.info("\n" + "="*80)
        logger.info("📊 DATA MANAGER SUMMARY")
        logger.info("="*80)
        
        for symbol, timeframes in self.data_cache.items():
            logger.info(f"\n{symbol}:")
            for tf, df in timeframes.items():
                if not df.empty:
                    logger.info(
                        f"  {tf}: {len(df)} candles | "
                        f"Price: ${df['close'].iloc[-1]:.2f} | "
                        f"Range: ${df['low'].min():.2f}-${df['high'].max():.2f}"
                    )
        
        logger.info("="*80 + "\n")