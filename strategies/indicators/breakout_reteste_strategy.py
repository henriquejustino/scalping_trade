import pandas as pd
import ta
import numpy as np
from typing import Tuple, Optional
from decimal import Decimal
from strategies.base_strategy import BaseStrategy

class BreakoutRetesteStrategy(BaseStrategy):
    """Breakout com Reteste (confirmado pelo 15m)"""
    
    def __init__(self, lookback=30, volume_lookback=20, atr_multiplier=1.3):
        super().__init__("Breakout_Reteste")
        self.lookback = lookback
        self.volume_lookback = volume_lookback
        self.atr_multiplier = atr_multiplier
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula indicadores"""
        # Resistência e suporte recentes
        df['resistance'] = df['high'].rolling(window=self.lookback).max()
        df['support'] = df['low'].rolling(window=self.lookback).min()
        
        # Volume
        df['volume_ma'] = df['volume'].rolling(window=self.volume_lookback).mean()
        df['high_volume'] = df['volume'] > df['volume_ma']
        
        # ATR
        df['atr'] = ta.volatility.AverageTrueRange(
            df['high'], df['low'], df['close'], window=14
        ).average_true_range()
        
        # Detecta breakout
        df['breakout_up'] = (
            (df['close'] > df['resistance'].shift(1)) &  # Rompe resistência
            (df['close'] == df['high']) &  # Fecha no topo
            df['high_volume']  # Volume alto
        )
        
        df['breakout_down'] = (
            (df['close'] < df['support'].shift(1)) &  # Rompe suporte
            (df['close'] == df['low']) &  # Fecha no fundo
            df['high_volume']
        )
        
        # Detecta reteste (preço volta próximo da zona rompida)
        df['breakout_level'] = np.nan
        
        # Marca nível do último breakout
        for i in range(1, len(df)):
            if df['breakout_up'].iloc[i]:
                df.loc[df.index[i:], 'breakout_level'] = df['resistance'].iloc[i]
                df.loc[df.index[i:], 'breakout_direction'] = 'UP'
            elif df['breakout_down'].iloc[i]:
                df.loc[df.index[i:], 'breakout_level'] = df['support'].iloc[i]
                df.loc[df.index[i:], 'breakout_direction'] = 'DOWN'
        
        # Reteste = preço volta a 1% do nível rompido
        df['retesting'] = False
        for i in range(len(df)):
            if pd.notna(df['breakout_level'].iloc[i]):
                level = df['breakout_level'].iloc[i]
                distance = abs(df['close'].iloc[i] - level) / level
                df.loc[df.index[i], 'retesting'] = distance < 0.01
        
        return df
    
    def get_entry_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        """Detecta sinal de entrada (requer confirmação de df_15m externamente)"""
        if len(df) < self.lookback + 10:
            return None, 0.0
        
        df = self.calculate_signals(df)
        
        # Procura por reteste nos últimos 5 candles após breakout
        for i in range(-5, 0):
            try:
                if df['breakout_direction'].iloc[i] == 'UP' and df['retesting'].iloc[-1]:
                    # LONG: Breakout up + reteste + recuperação
                    if df['close'].iloc[-1] > df['close'].iloc[-2]:
                        strength = 0.7  # Força moderada, precisa confirmação 15m
                        return 'BUY', strength
                
                elif df['breakout_direction'].iloc[i] == 'DOWN' and df['retesting'].iloc[-1]:
                    # SHORT: Breakout down + reteste + continuação
                    if df['close'].iloc[-1] < df['close'].iloc[-2]:
                        strength = 0.7
                        return 'SELL', strength
            except:
                continue
        
        return None, 0.0
    
    def calculate_stop_loss(self, df: pd.DataFrame, entry_price: Decimal, side: str) -> Decimal:
        """Stop loss: Abaixo/acima da zona rompida ou ATR × 1.3"""
        df = self.calculate_signals(df)
        
        breakout_level = Decimal(str(df['breakout_level'].iloc[-1])) if pd.notna(df['breakout_level'].iloc[-1]) else entry_price
        atr = Decimal(str(df['atr'].iloc[-1]))
        
        if side == 'BUY':
            sl_level = breakout_level * Decimal('0.995')  # 0.5% abaixo
            sl_atr = entry_price - (atr * Decimal(str(self.atr_multiplier)))
            return max(sl_level, sl_atr)
        else:
            sl_level = breakout_level * Decimal('1.005')
            sl_atr = entry_price + (atr * Decimal(str(self.atr_multiplier)))
            return min(sl_level, sl_atr)
    
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