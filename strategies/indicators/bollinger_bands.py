import pandas as pd
import ta
from typing import Tuple, Optional
from decimal import Decimal
from strategies.base_strategy import BaseStrategy

class BollingerBandsStrategy(BaseStrategy):
    def __init__(self, period=20, std_dev=2, atr_multiplier=1.8):
        super().__init__("Bollinger_Bands")
        self.period = period
        self.std_dev = std_dev
        self.atr_multiplier = atr_multiplier
    
    def calculate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        bb = ta.volatility.BollingerBands(
            df['close'],
            window=self.period,
            window_dev=self.std_dev
        )
        
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_middle'] = bb.bollinger_mavg()
        df['bb_width'] = bb.bollinger_wband()
        
        # BB Percent: 0 = lower, 1 = upper
        df['bb_percent'] = (df['close'] - df['bb_lower']) / \
                           (df['bb_upper'] - df['bb_lower'] + 1e-10)  # Evita divisão por zero
        
        # ATR para scaling
        df['atr'] = ta.volatility.AverageTrueRange(
            df['high'], df['low'], df['close'], window=14
        ).average_true_range().fillna(100)
        
        # Squeeze detection (volatilidade baixa = oportunidade de breakout)
        df['bb_width_ma'] = df['bb_width'].rolling(window=20).mean()
        df['squeeze'] = df['bb_width'] < (df['bb_width_ma'] * 0.5)
        
        return df
    
    def get_entry_signal(self, df: pd.DataFrame) -> Tuple[Optional[str], float]:
        if len(df) < self.period + 10:
            return None, 0.0
        
        df = self.calculate_signals(df)
        
        current_close = df['close'].iloc[-1]
        bb_lower = df['bb_lower'].iloc[-1]
        bb_upper = df['bb_upper'].iloc[-1]
        bb_percent = df['bb_percent'].iloc[-1]
        bb_width = df['bb_width'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        
        # Volatilidade como fator de confiança
        volatility_factor = min(bb_width / 0.04, 1.0)
        
        # === LONG: Toque na banda inferior + reversão ===
        if current_close <= bb_lower * 1.003:  # 0.3% de tolerância
            # Preço deve estar subindo
            if current_close >= prev_close:
                strength = max(0.3, (1.0 - bb_percent) * 0.8) * volatility_factor
                return 'BUY', min(strength, 1.0)
        
        # === SHORT: Toque na banda superior + reversão ===
        elif current_close >= bb_upper * 0.997:
            if current_close <= prev_close:
                strength = max(0.3, bb_percent * 0.8) * volatility_factor
                return 'SELL', min(strength, 1.0)
        
        return None, 0.0
    
    def calculate_stop_loss(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        """SL: 1.8 ATR ou banda oposta (o que for mais perto)"""
        df = self.calculate_signals(df)
        
        atr = Decimal(str(df['atr'].iloc[-1]))
        bb_lower = Decimal(str(df['bb_lower'].iloc[-1]))
        bb_upper = Decimal(str(df['bb_upper'].iloc[-1]))
        
        atr_stop = atr * Decimal(str(self.atr_multiplier))
        
        if side == 'BUY':
            # SL é o menor entre: ATR stop ou 1% abaixo do preço
            sl_atr = entry_price - atr_stop
            sl_band = bb_lower * Decimal('0.98')  # Banda com margem
            return max(sl_atr, sl_band)
        else:
            sl_atr = entry_price + atr_stop
            sl_band = bb_upper * Decimal('1.02')
            return min(sl_atr, sl_band)
    
    def calculate_take_profit(
        self,
        df: pd.DataFrame,
        entry_price: Decimal,
        side: str
    ) -> Decimal:
        """TP: Banda média (reversão) ou 1.5x SL (continuação)"""
        df = self.calculate_signals(df)
        
        bb_middle = Decimal(str(df['bb_middle'].iloc[-1]))
        
        # Assume reversão = target na banda média
        # Mas vamos usar R:R 1:1.5 para ser conservador
        stop_loss = self.calculate_stop_loss(df, entry_price, side)
        risk = abs(entry_price - stop_loss)
        reward = risk * Decimal('1.5')
        
        if side == 'BUY':
            return entry_price + reward
        else:
            return entry_price - reward