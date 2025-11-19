"""
Signal Validator - Valida sinais antes de executar
Reduz sinais falsos e melhora qualidade
"""
import pandas as pd
from typing import Tuple, Optional
from decimal import Decimal
from loguru import logger

class SignalValidator:
    """Valida qualidade dos sinais de entrada"""
    
    def __init__(self):
        self.min_signal_strength = 0.25
        self.min_volume_ratio = 0.7
    
    def validate(
        self,
        side: Optional[str],
        strength: float,
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame
    ) -> bool:
        """
        ✅ NOVO: Valida sinal antes de retornar
        Checa: força, volume, tendência, volatilidade
        """
        
        if side is None:
            return False
        
        # === 1. FORÇA MÍNIMA ===
        if strength < self.min_signal_strength:
            logger.debug(f"Sinal rejeitado: força baixa {strength:.2f}")
            return False
        
        # === 2. VOLUME ===
        if not self._validate_volume(df_5m):
            logger.debug("Sinal rejeitado: volume insuficiente")
            return False
        
        # === 3. VOLATILIDADE ===
        if not self._validate_volatility(df_5m):
            logger.debug("Sinal rejeitado: volatilidade extrema")
            return False
        
        # === 4. TENDÊNCIA 15m ===
        if not self._validate_trend_alignment(df_5m, df_15m, side):
            logger.debug(f"Sinal rejeitado: desalinhamento de tendência {side}")
            return False
        
        # === 5. PADRÕES RUINS ===
        if self._has_bad_pattern(df_5m, side):
            logger.debug("Sinal rejeitado: padrão ruim detectado")
            return False
        
        return True
    
    def _validate_volume(self, df: pd.DataFrame) -> bool:
        """Valida se volume está aceitável"""
        
        if len(df) < 20:
            return True  # Sem dados suficientes
        
        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].rolling(20).mean().iloc[-1]
        
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Aceita se volume >= 70% da média
        return volume_ratio >= self.min_volume_ratio
    
    def _validate_volatility(self, df: pd.DataFrame) -> bool:
        """Rejeita se volatilidade está extrema"""
        
        if len(df) < 14:
            return True
        
        # Calcula ATR
        high_low = df['high'] - df['low']
        tr1 = high_low
        tr2 = abs(df['high'] - df['close'].shift(1))
        tr3 = abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        
        current_price = df['close'].iloc[-1]
        volatility_pct = (atr / current_price) * 100
        
        # Rejeita se vol > 2%
        if volatility_pct > 2.0:
            logger.debug(f"Volatilidade muito alta: {volatility_pct:.2f}%")
            return False
        
        # Rejeita se vol < 0.2% (muito calmo, spread grande)
        if volatility_pct < 0.2:
            logger.debug(f"Volatilidade muito baixa: {volatility_pct:.2f}%")
            return False
        
        return True
    
    def _validate_trend_alignment(
        self,
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame,
        side: str
    ) -> bool:
        """
        Valida se sinal do 5m está alinhado com tendência 15m
        BUY no 5m deve estar em tendência de alta no 15m
        """
        
        if len(df_15m) < 30:
            return True
        
        # EMA 20/50 no 15m
        ema20 = df_15m['close'].ewm(span=20).mean().iloc[-1]
        ema50 = df_15m['close'].ewm(span=50).mean().iloc[-1]
        current_price_15m = df_15m['close'].iloc[-1]
        
        # Tendência
        trend_up = ema20 > ema50 and current_price_15m > ema20
        trend_down = ema20 < ema50 and current_price_15m < ema20
        trend_neutral = not trend_up and not trend_down
        
        # Valida alinhamento
        if side == 'BUY':
            # BUY OK em tendência de alta OU neutra
            return trend_up or trend_neutral
        else:
            # SELL OK em tendência de baixa OU neutra
            return trend_down or trend_neutral
    
    def _has_bad_pattern(self, df: pd.DataFrame, side: str) -> bool:
        """
        Detecta padrões ruins que rejeitam sinal mesmo que válido
        - Gaps contra sinal
        - Wicks muito longos na direção oposta
        """
        
        if len(df) < 2:
            return False
        
        current_close = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        
        current_open = df['open'].iloc[-1]
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        
        candle_range = current_high - current_low
        
        # === GAP CONTRA SINAL ===
        if side == 'BUY':
            # Gap para baixo é ruim
            if current_open < prev_close * Decimal('0.998'):
                logger.debug("Gap para baixo com sinal BUY")
                return True
        else:
            # Gap para cima é ruim
            if current_open > prev_close * Decimal('1.002'):
                logger.debug("Gap para cima com sinal SELL")
                return True
        
        # === WICK CONTRA SINAL ===
        if side == 'BUY':
            # Wick superior muito longo é ruim (rejeição)
            upper_wick = current_high - max(current_close, current_open)
            if upper_wick > candle_range * Decimal('0.7'):
                logger.debug("Wick superior longo com sinal BUY")
                return True
        else:
            # Wick inferior muito longo é ruim
            lower_wick = min(current_close, current_open) - current_low
            if lower_wick > candle_range * Decimal('0.7'):
                logger.debug("Wick inferior longo com sinal SELL")
                return True
        
        return False
    
    def check_signal_quality(
        self,
        side: str,
        strength: float,
        details: dict
    ) -> Tuple[bool, str]:
        """
        Retorna parecer sobre qualidade do sinal
        Útil para logging e debugging
        """
        
        # Análise de acordos
        buy_agreements_5m = details.get('buy_agreements_5m', 0)
        sell_agreements_5m = details.get('sell_agreements_5m', 0)
        buy_agreements_15m = details.get('buy_agreements_15m', 0)
        sell_agreements_15m = details.get('sell_agreements_15m', 0)
        
        if side == 'BUY':
            agreements_5m = buy_agreements_5m
            agreements_15m = buy_agreements_15m
        else:
            agreements_5m = sell_agreements_5m
            agreements_15m = sell_agreements_15m
        
        total_agreements = agreements_5m + agreements_15m
        
        # Parecer
        if total_agreements >= 4 and strength > 0.7:
            return True, "EXCELLENT - Muita convergência"
        elif total_agreements >= 3 and strength > 0.5:
            return True, "GOOD - Convergência forte"
        elif total_agreements >= 2 and strength > 0.4:
            return True, "OK - Convergência moderada"
        elif strength > 0.3:
            return True, "WEAK - Sinal fraco"
        else:
            return False, "REJECT - Qualidade baixa"
    
    def get_signal_confidence(self, details: dict) -> float:
        """
        Retorna score de confiança do sinal (0-100)
        Baseado em convergência e força
        """
        
        buy_score = details.get('buy_score', 0)
        sell_score = details.get('sell_score', 0)
        
        # Score de converência
        agreements = (
            details.get('buy_agreements_5m', 0) +
            details.get('buy_agreements_15m', 0) +
            details.get('sell_agreements_5m', 0) +
            details.get('sell_agreements_15m', 0)
        )
        
        convergence_score = min(agreements / 4, 1.0) * 50
        
        # Score de força
        max_score = max(buy_score, sell_score)
        strength_score = min(max_score, 1.0) * 50
        
        return convergence_score + strength_score