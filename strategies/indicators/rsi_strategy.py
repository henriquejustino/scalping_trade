import pandas as pd
import ta
from typing import Tuple, Optional
from decimal import Decimal
from strategies.base_strategy import BaseStrategy

class RSIStrategy(BaseStrategy):
    def __init__(self, period=14, oversold=30, overbought=70, atr_multiplier=2.0):
        super().__init__("RSI_Strategy")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.atr_multiplier = atr_multiplier
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        df['rsi'] = ta.momentum.RSIIndicator(
            df['close'],
            window=self.period
        ).rsi()
        
        # ATR para dimensionar SL e TP
        df['atr'] = ta.volatility.AverageTrueRange(
            df['high'], df['low'], df['close'], window=14
        ).average_true_range().fillna(100)
        
        # Divergência CORRIGIDA: procura em janela de 5 candles
        df['divergence'] = 0
        
        for i in range(5, len(df)):
            # Topo local no preço e base no RSI = divergência bearish
            if (df['high'].iloc[i] > df['high'].iloc[i-1] and 
                df['high'].iloc[i] > df['high'].iloc[i+1] if i+1 < len(df) else True):
                rsi_window = df['rsi'].iloc[max(0, i-5):i+1]
                if len(rsi_window) >= 3 and rsi_window.iloc[-1] < rsi_window.max() - 10:
                    df.loc[df.index[i], 'divergence'] = -1
            
            # Fundo local no preço e topo no RSI = divergência bullish
            if (df['low'].iloc[i] < df['low'].iloc[i-1] and
                df['low'].iloc[i] < df['low'].iloc[i+1] if i+1 < len(df) else True):
                rsi_window = df['rsi'].iloc[max(0, i-5):i+1]
                if len(rsi_window) >= 3 and rsi_window.iloc[-1] > rsi_window.min() + 10:
                    df.loc[df.index[i], 'divergence'] = 1
        
        return df
    
    def get_entry_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        if len(df) < self.period + 5:
            return None, 0.0
        
        df = self.calculate_signals(df)
        current_rsi = df['rsi'].iloc[-1]
        prev_rsi = df['rsi'].iloc[-2]
        
        # LONG: RSI cruza acima de oversold OU divergência bullish
        if current_rsi < self.oversold and prev_rsi <= current_rsi:
            # Força baseada em quão extremo é o RSI
            strength = max(0.5, (self.oversold - current_rsi) / self.oversold)
            
            # Bônus por divergência
            if df['divergence'].iloc[-1] == 1:
                strength = min(strength + 0.3, 1.0)
            
            return 'BUY', strength
        
        # SHORT: RSI cruza abaixo de overbought OU divergência bearish
        elif current_rsi > self.overbought and prev_rsi >= current_rsi:
            strength = max(0.5, (current_rsi - self.overbought) / (100 - self.overbought))
            
            if df['divergence'].iloc[-1] == -1:
                strength = min(strength + 0.3, 1.0)
            
            return 'SELL', strength
        
        return None, 0.0
    
    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        """SL: 2 ATR com mínimo de 20 pips"""
        df = self.calculate_signals(df)
        
        atr = Decimal(str(df['atr'].iloc[-1]))
        min_sl = entry_price * Decimal('0.005')  # Mínimo 0.5%
        
        sl_distance = max(atr * Decimal(str(self.atr_multiplier)), min_sl)
        
        if side == 'BUY':
            return entry_price - sl_distance
        else:
            return entry_price + sl_distance
    
    def calculate_take_profit(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        """TP: 1.5x ATR (mantém R:R ~1:1.5 com SL 2xATR)"""
        df = self.calculate_signals(df)
        
        atr = Decimal(str(df['atr'].iloc[-1]))
        tp_distance = atr * Decimal('1.5')
        
        if side == 'BUY':
            return entry_price + tp_distance
        else:
            return entry_price - tp_distance