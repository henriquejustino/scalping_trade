from decimal import Decimal
from typing import Dict, Tuple, Optional
import pandas as pd
from loguru import logger

class SignalGenerator:
    """Gera sinais consolidados com validação"""
    
    @staticmethod
    def validate_signal(
        side: Optional[str],
        strength: float,
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame,
        min_strength: float = 0.3
    ) -> Tuple[Optional[str], float]:
        """Valida sinal antes de retornar"""
        
        if side is None or strength < min_strength:
            return None, 0.0
        
        # Valida com volume
        current_volume = df_5m['volume'].iloc[-1]
        avg_volume = df_5m['volume'].rolling(20).mean().iloc[-1]
        
        if current_volume < avg_volume * 0.7:
            logger.debug("Sinal rejeitado: volume baixo")
            return None, 0.0
        
        # Valida com volatilidade
        atr = df_5m['high'].rolling(14).max() - df_5m['low'].rolling(14).min()
        current_atr = atr.iloc[-1]
        
        if current_atr < atr.mean() * 0.5:
            logger.debug("Sinal rejeitado: volatilidade baixa")
            return None, 0.0
        
        # Valida tendência no 15m
        ema_15m = df_15m['close'].ewm(span=21).mean()
        current_price = df_15m['close'].iloc[-1]
        
        if side == 'BUY' and current_price < ema_15m.iloc[-1] * 0.995:
            strength *= 0.8  # Reduz força se contra tendência
        elif side == 'SELL' and current_price > ema_15m.iloc[-1] * 1.005:
            strength *= 0.8
        
        return side, strength
    
    @staticmethod
    def check_market_conditions(df: pd.DataFrame) -> Dict:
        """Verifica condições gerais do mercado"""
        
        # Volatilidade
        returns = df['close'].pct_change()
        volatility = returns.std()
        
        # Tendência
        ema_fast = df['close'].ewm(span=9).mean()
        ema_slow = df['close'].ewm(span=21).mean()
        trend = 'BULL' if ema_fast.iloc[-1] > ema_slow.iloc[-1] else 'BEAR'
        
        # Volume
        volume_ratio = df['volume'].iloc[-1] / df['volume'].rolling(20).mean().iloc[-1]
        
        return {
            'volatility': float(volatility),
            'trend': trend,
            'volume_ratio': float(volume_ratio),
            'tradeable': volatility > 0.001 and volume_ratio > 0.5
        }