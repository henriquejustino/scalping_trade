import pandas as pd
import ta
import numpy as np
from typing import Tuple, Optional
from decimal import Decimal
from strategies.base_strategy import BaseStrategy

class BollingerRSIAdvanced(BaseStrategy):
    """Bollinger Bands + RSI (Reversão e Continuação)"""
    
    def __init__(self, bb_period=20, bb_std=2, rsi_period=14, wick_threshold=0.25):
        super().__init__("Bollinger_RSI_Advanced")
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.wick_threshold = wick_threshold
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula indicadores"""
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(
            df['close'],
            window=self.bb_period,
            window_dev=self.bb_std
        )
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_middle'] = bb.bollinger_mavg()
        
        # RSI
        df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=self.rsi_period).rsi()
        
        # ATR
        df['atr'] = ta.volatility.AverageTrueRange(
            df['high'], df['low'], df['close'], window=14
        ).average_true_range()
        
        # Análise de wicks
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        df['lower_wick'] = df[['open', 'close']].min(axis=1) - df['low']
        df['upper_wick'] = df['high'] - df[['open', 'close']].max(axis=1)
        
        df['large_lower_wick'] = df['lower_wick'] > (df['range'] * self.wick_threshold)
        df['large_upper_wick'] = df['upper_wick'] > (df['range'] * self.wick_threshold)
        
        # Condições de reversão
        df['below_lower_band'] = df['close'] < df['bb_lower']
        df['above_upper_band'] = df['close'] > df['bb_upper']
        
        # Condições de continuação
        df['breakout_upper'] = df['close'] > df['bb_upper']
        df['breakout_lower'] = df['close'] < df['bb_lower']
        
        return df
    
    def get_entry_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        """Detecta sinal de entrada"""
        if len(df) < max(self.bb_period, self.rsi_period) + 5:
            return None, 0.0
        
        df = self.calculate_signals(df)
        
        current_rsi = df['rsi'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        
        # === REVERSÃO LONG ===
        if (df['below_lower_band'].iloc[-2] and  # Candle anterior abaixo
            current_rsi < 25 and  # RSI extremo
            df['large_lower_wick'].iloc[-1]):  # Rejeição com wick
            
            strength = 1.0 - (current_rsi / 25)  # Quanto menor RSI, mais forte
            strength = min(strength + 0.2, 1.0)  # Bônus por wick
            return 'BUY', strength
        
        # === REVERSÃO SHORT ===
        elif (df['above_upper_band'].iloc[-2] and
              current_rsi > 75 and
              df['large_upper_wick'].iloc[-1]):
            
            strength = (current_rsi - 75) / 25
            strength = min(strength + 0.2, 1.0)
            return 'SELL', strength
        
        # === CONTINUAÇÃO LONG ===
        elif (df['breakout_upper'].iloc[-1] and
              50 <= current_rsi <= 60):
            
            strength = 0.6 + ((current_rsi - 50) / 100)  # Força moderada
            return 'BUY', strength
        
        # === CONTINUAÇÃO SHORT ===
        elif (df['breakout_lower'].iloc[-1] and
              40 <= current_rsi <= 50):
            
            strength = 0.6 + ((50 - current_rsi) / 100)
            return 'SELL', strength
        
        return None, 0.0
    
    def calculate_stop_loss(self, df: pd.DataFrame, entry_price: Decimal, side: str) -> Decimal:
        """Stop loss: 1 ATR ou banda oposta"""
        df = self.calculate_signals(df)
        
        atr = Decimal(str(df['atr'].iloc[-1]))
        bb_upper = Decimal(str(df['bb_upper'].iloc[-1]))
        bb_lower = Decimal(str(df['bb_lower'].iloc[-1]))
        
        if side == 'BUY':
            sl_atr = entry_price - atr
            sl_band = bb_lower * Decimal('0.995')  # 0.5% abaixo da banda
            return max(sl_atr, sl_band)
        else:
            sl_atr = entry_price + atr
            sl_band = bb_upper * Decimal('1.005')
            return min(sl_atr, sl_band)
    
    def calculate_take_profit(self, df: pd.DataFrame, entry_price: Decimal, side: str) -> Decimal:
        """Take profit: Banda média (reversão) ou 1.5:1 (continuação)"""
        df = self.calculate_signals(df)
        
        bb_middle = Decimal(str(df['bb_middle'].iloc[-1]))
        current_rsi = df['rsi'].iloc[-1]
        
        # Reversão: target = banda média
        if current_rsi < 30 or current_rsi > 70:
            return bb_middle
        
        # Continuação: R:R 1.5:1
        else:
            stop_loss = self.calculate_stop_loss(df, entry_price, side)
            risk = abs(entry_price - stop_loss)
            reward = risk * Decimal('1.5')
            
            if side == 'BUY':
                return entry_price + reward
            else:
                return entry_price - reward