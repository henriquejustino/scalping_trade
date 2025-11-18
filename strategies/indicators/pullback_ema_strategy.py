import pandas as pd
import ta
import numpy as np
from typing import Tuple, Optional
from decimal import Decimal
from strategies.base_strategy import BaseStrategy

class PullbackEMAStrategy(BaseStrategy):
    """Pullback para EMA 20/50"""
    
    def __init__(self, fast_period=20, slow_period=50, pullback_tolerance=0.005, atr_multiplier=1.2):
        super().__init__("Pullback_EMA")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.pullback_tolerance = pullback_tolerance
        self.atr_multiplier = atr_multiplier
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula indicadores"""
        # EMAs
        df['ema_20'] = ta.trend.EMAIndicator(df['close'], window=self.fast_period).ema_indicator()
        df['ema_50'] = ta.trend.EMAIndicator(df['close'], window=self.slow_period).ema_indicator()
        
        # Tendência
        df['uptrend'] = df['ema_20'] > df['ema_50']
        df['downtrend'] = df['ema_20'] < df['ema_50']
        
        # ATR
        df['atr'] = ta.volatility.AverageTrueRange(
            df['high'], df['low'], df['close'], window=14
        ).average_true_range()
        
        # Distância do preço até EMA 20
        df['distance_to_ema20'] = (df['close'] - df['ema_20']) / df['ema_20']
        df['near_ema20'] = abs(df['distance_to_ema20']) <= self.pullback_tolerance
        
        # Padrões de candle (simplificados)
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
        df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
        
        # Engolfo de alta
        df['bullish_engulfing'] = (
            (df['close'] > df['open']) &  # Candle atual é verde
            (df['close'].shift(1) < df['open'].shift(1)) &  # Anterior é vermelho
            (df['close'] > df['open'].shift(1)) &  # Fecha acima da abertura anterior
            (df['open'] < df['close'].shift(1))  # Abre abaixo do fechamento anterior
        )
        
        # Engolfo de baixa
        df['bearish_engulfing'] = (
            (df['close'] < df['open']) &
            (df['close'].shift(1) > df['open'].shift(1)) &
            (df['close'] < df['open'].shift(1)) &
            (df['open'] > df['close'].shift(1))
        )
        
        # Martelo (wick inferior > 2x body)
        df['hammer'] = (
            (df['lower_wick'] > df['body'] * 2) &
            (df['upper_wick'] < df['body'] * 0.5) &
            (df['close'] > df['open'])
        )
        
        # Martelo invertido
        df['inverted_hammer'] = (
            (df['upper_wick'] > df['body'] * 2) &
            (df['lower_wick'] < df['body'] * 0.5) &
            (df['close'] < df['open'])
        )
        
        return df
    
    def get_entry_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        """Detecta sinal de entrada"""
        if len(df) < self.slow_period + 5:
            return None, 0.0
        
        df = self.calculate_signals(df)
        
        # LONG: Uptrend + pullback para EMA 20 + padrão de reversão
        if (df['uptrend'].iloc[-1] and 
            df['near_ema20'].iloc[-1] and
            (df['bullish_engulfing'].iloc[-1] or df['hammer'].iloc[-1])):
            
            # Força baseada em quão forte é a tendência e padrão
            trend_strength = abs(df['ema_20'].iloc[-1] - df['ema_50'].iloc[-1]) / df['ema_50'].iloc[-1]
            pattern_bonus = 0.2 if df['bullish_engulfing'].iloc[-1] else 0.1
            
            strength = min(trend_strength * 20 + 0.5 + pattern_bonus, 1.0)
            return 'BUY', strength
        
        # SHORT: Downtrend + pullback para EMA 20 + padrão de reversão
        elif (df['downtrend'].iloc[-1] and 
              df['near_ema20'].iloc[-1] and
              (df['bearish_engulfing'].iloc[-1] or df['inverted_hammer'].iloc[-1])):
            
            trend_strength = abs(df['ema_50'].iloc[-1] - df['ema_20'].iloc[-1]) / df['ema_50'].iloc[-1]
            pattern_bonus = 0.2 if df['bearish_engulfing'].iloc[-1] else 0.1
            
            strength = min(trend_strength * 20 + 0.5 + pattern_bonus, 1.0)
            return 'SELL', strength
        
        return None, 0.0
    
    def calculate_stop_loss(self, df: pd.DataFrame, entry_price: Decimal, side: str) -> Decimal:
        """Stop loss: EMA 50 ou ATR × 1.2"""
        df = self.calculate_signals(df)
        
        ema_50 = Decimal(str(df['ema_50'].iloc[-1]))
        atr = Decimal(str(df['atr'].iloc[-1]))
        
        if side == 'BUY':
            sl_ema = ema_50
            sl_atr = entry_price - (atr * Decimal(str(self.atr_multiplier)))
            return max(sl_ema, sl_atr)
        else:
            sl_ema = ema_50
            sl_atr = entry_price + (atr * Decimal(str(self.atr_multiplier)))
            return min(sl_ema, sl_atr)
    
    def calculate_take_profit(self, df: pd.DataFrame, entry_price: Decimal, side: str) -> Decimal:
        """Take profit: R:R 2:1"""
        df = self.calculate_signals(df)
        
        stop_loss = self.calculate_stop_loss(df, entry_price, side)
        risk = abs(entry_price - stop_loss)
        reward = risk * Decimal('2.0')
        
        if side == 'BUY':
            return entry_price + reward
        else:
            return entry_price - reward