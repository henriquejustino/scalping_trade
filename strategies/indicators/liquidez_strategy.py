import pandas as pd
import ta
import numpy as np
from typing import Tuple, Optional
from decimal import Decimal
from strategies.base_strategy import BaseStrategy

class LiquidezStrategy(BaseStrategy):
    """Coleta de Liquidez (Wicks + Volume)"""
    
    def __init__(self, wick_threshold=0.3, volume_lookback=20, liquidez_lookback=20, atr_multiplier=1.2):
        super().__init__("Liquidez_Strategy")
        self.wick_threshold = wick_threshold
        self.volume_lookback = volume_lookback
        self.liquidez_lookback = liquidez_lookback
        self.atr_multiplier = atr_multiplier
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula indicadores"""
        # Análise de wicks
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
        df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
        
        # Wicks longos
        df['long_lower_wick'] = df['lower_wick'] > (df['range'] * self.wick_threshold)
        df['long_upper_wick'] = df['upper_wick'] > (df['range'] * self.wick_threshold)
        
        # Volume
        df['volume_ma'] = df['volume'].rolling(window=self.volume_lookback).mean()
        df['high_volume'] = df['volume'] > df['volume_ma']
        
        # ATR
        df['atr'] = ta.volatility.AverageTrueRange(
            df['high'], df['low'], df['close'], window=14
        ).average_true_range()
        
        # Zonas de liquidez (mínimas e máximas recentes)
        df['recent_low'] = df['low'].rolling(window=self.liquidez_lookback).min()
        df['recent_high'] = df['high'].rolling(window=self.liquidez_lookback).max()
        
        # Proximidade de zona de liquidez
        df['near_recent_low'] = abs(df['low'] - df['recent_low']) / df['close'] < 0.01
        df['near_recent_high'] = abs(df['high'] - df['recent_high']) / df['close'] < 0.01
        
        # Fechamento relativo ao candle
        df['candle_midpoint'] = (df['high'] + df['low']) / 2
        df['closes_above_mid'] = df['close'] > df['candle_midpoint']
        df['closes_below_mid'] = df['close'] < df['candle_midpoint']
        
        return df
    
    def get_entry_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        """Detecta sinal de entrada"""
        if len(df) < self.liquidez_lookback + 5:
            return None, 0.0
        
        df = self.calculate_signals(df)
        
        # LONG: Wick inferior longo + volume alto + rejeita zona de liquidez + fecha acima da metade
        if (df['long_lower_wick'].iloc[-1] and
            df['high_volume'].iloc[-1] and
            df['near_recent_low'].iloc[-1] and
            df['closes_above_mid'].iloc[-1]):
            
            # Força baseada no tamanho do wick e volume
            wick_ratio = df['lower_wick'].iloc[-1] / df['range'].iloc[-1]
            volume_ratio = df['volume'].iloc[-1] / df['volume_ma'].iloc[-1]
            
            strength = min((wick_ratio * 0.8) + (volume_ratio * 0.3), 1.0)
            return 'BUY', strength
        
        # SHORT: Wick superior longo + volume alto + rejeita zona de liquidez + fecha abaixo da metade
        elif (df['long_upper_wick'].iloc[-1] and
              df['high_volume'].iloc[-1] and
              df['near_recent_high'].iloc[-1] and
              df['closes_below_mid'].iloc[-1]):
            
            wick_ratio = df['upper_wick'].iloc[-1] / df['range'].iloc[-1]
            volume_ratio = df['volume'].iloc[-1] / df['volume_ma'].iloc[-1]
            
            strength = min((wick_ratio * 0.8) + (volume_ratio * 0.3), 1.0)
            return 'SELL', strength
        
        return None, 0.0
    
    def calculate_stop_loss(self, df: pd.DataFrame, entry_price: Decimal, side: str) -> Decimal:
        """Stop loss: Abaixo/acima da mínima/máxima do wick ou ATR × 1.2"""
        df = self.calculate_signals(df)
        
        wick_extreme = Decimal(str(df['low'].iloc[-1])) if side == 'BUY' else Decimal(str(df['high'].iloc[-1]))
        atr = Decimal(str(df['atr'].iloc[-1]))
        
        if side == 'BUY':
            sl_wick = wick_extreme * Decimal('0.998')  # 0.2% abaixo
            sl_atr = entry_price - (atr * Decimal(str(self.atr_multiplier)))
            return max(sl_wick, sl_atr)
        else:
            sl_wick = wick_extreme * Decimal('1.002')
            sl_atr = entry_price + (atr * Decimal(str(self.atr_multiplier)))
            return min(sl_wick, sl_atr)
    
    def calculate_take_profit(self, df: pd.DataFrame, entry_price: Decimal, side: str) -> Decimal:
        """Take profit: R:R 1.5:1"""
        df = self.calculate_signals(df)
        
        stop_loss = self.calculate_stop_loss(df, entry_price, side)
        risk = abs(entry_price - stop_loss)
        reward = risk * Decimal('1.5')
        
        if side == 'BUY':
            return entry_price + reward
        else:
            return entry_price - reward