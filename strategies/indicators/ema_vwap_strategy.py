import pandas as pd
import ta
from typing import Tuple, Optional
from decimal import Decimal
from strategies.base_strategy import BaseStrategy

class EMAVWAPCrossover(BaseStrategy):
    """EMA 9/21 + VWAP - Crossover Filtrado por Preço Justo"""
    
    def __init__(self, ema_fast=9, ema_slow=21, volume_lookback=20):
        super().__init__("EMA_VWAP_Crossover")
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.volume_lookback = volume_lookback
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        # EMAs
        df['ema_fast'] = ta.trend.EMAIndicator(
            df['close'],
            window=self.ema_fast
        ).ema_indicator()
        
        df['ema_slow'] = ta.trend.EMAIndicator(
            df['close'],
            window=self.ema_slow
        ).ema_indicator()
        
        # VWAP
        df['typical_price'] = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (df['typical_price'] * df['volume']).cumsum() / df['volume'].cumsum()
        
        # Volume
        df['volume_ma'] = df['volume'].rolling(window=self.volume_lookback).mean()
        df['volume_above_avg'] = df['volume'] > df['volume_ma']
        
        # Crossovers
        df['ema_cross_up'] = (df['ema_fast'] > df['ema_slow']) & \
                              (df['ema_fast'].shift(1) <= df['ema_slow'].shift(1))
        
        df['ema_cross_down'] = (df['ema_fast'] < df['ema_slow']) & \
                                (df['ema_fast'].shift(1) >= df['ema_slow'].shift(1))
        
        # Posição relativa ao VWAP
        df['price_above_vwap'] = df['close'] > df['vwap']
        df['price_below_vwap'] = df['close'] < df['vwap']
        
        return df
    
    def get_entry_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        if len(df) < max(self.ema_slow, self.volume_lookback) + 5:
            return None, 0.0
        
        df = self.calculate_signals(df)
        
        # LONG: EMA cross up + preço acima VWAP + volume alto
        if (df['ema_cross_up'].iloc[-1] and 
            df['price_above_vwap'].iloc[-1] and 
            df['volume_above_avg'].iloc[-1]):
            
            # Calcula força do sinal
            distance_from_vwap = (df['close'].iloc[-1] - df['vwap'].iloc[-1]) / df['vwap'].iloc[-1]
            volume_ratio = df['volume'].iloc[-1] / df['volume_ma'].iloc[-1]
            
            strength = min(
                0.5 +  # Base
                (abs(distance_from_vwap) * 100) * 5 +  # Distância do VWAP
                (volume_ratio - 1) * 0.2,  # Volume extra
                1.0
            )
            
            return 'BUY', strength
        
        # SHORT: EMA cross down + preço abaixo VWAP + volume alto
        elif (df['ema_cross_down'].iloc[-1] and 
              df['price_below_vwap'].iloc[-1] and 
              df['volume_above_avg'].iloc[-1]):
            
            distance_from_vwap = abs((df['close'].iloc[-1] - df['vwap'].iloc[-1]) / df['vwap'].iloc[-1])
            volume_ratio = df['volume'].iloc[-1] / df['volume_ma'].iloc[-1]
            
            strength = min(
                0.5 +
                (distance_from_vwap * 100) * 5 +
                (volume_ratio - 1) * 0.2,
                1.0
            )
            
            return 'SELL', strength
        
        return None, 0.0
    
    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        df = self.calculate_signals(df)
        
        # ATR para stop dinâmico
        atr = ta.volatility.AverageTrueRange(
            df['high'],
            df['low'],
            df['close'],
            window=14
        ).average_true_range().iloc[-1]
        
        ema_slow_value = Decimal(str(df['ema_slow'].iloc[-1]))
        atr_stop = Decimal(str(atr)) * Decimal('1.5')
        
        if side == 'BUY':
            # Usa o menor entre EMA 21 e ATR stop
            ema_stop = ema_slow_value
            atr_based = entry_price - atr_stop
            return max(ema_stop, atr_based)  # Mais conservador
        else:
            ema_stop = ema_slow_value
            atr_based = entry_price + atr_stop
            return min(ema_stop, atr_based)
    
    def calculate_take_profit(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        df = self.calculate_signals(df)
        
        # Calcula stop loss para usar no R:R
        stop_loss = self.calculate_stop_loss(df, entry_price, side)
        risk = abs(entry_price - stop_loss)
        
        # R:R de 1.5:1 a 2:1 (média 1.75:1)
        reward = risk * Decimal('1.75')
        
        if side == 'BUY':
            return entry_price + reward
        else:
            return entry_price - reward