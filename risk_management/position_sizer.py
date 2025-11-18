from decimal import Decimal
from typing import Optional, Dict
from loguru import logger
from config.settings import settings

class PositionSizer:
    def __init__(self):
        self.settings = settings
    
    def calculate_dynamic_position_size(
        self,
        capital: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        symbol_filters: dict,
        signal_strength: float,
        volume_ratio: float = 1.0
    ) -> Optional[Decimal]:
        """Calcula tamanho da posição com risco dinâmico"""
        
        # === VALIDAÇÃO DE VOLUME ===
        # Não entra se volume está abaixo da média (illiquid)
        if volume_ratio < 0.8:
            logger.warning(f"Volume baixo: {volume_ratio:.2f}x (mínimo 0.8x). Rejeitando trade.")
            return None
        
        # Risco dinâmico baseado na força do sinal E volume
        if signal_strength >= settings.SIGNAL_VERY_STRONG and volume_ratio > 1.3:
            risk_multiplier = Decimal("1.5")  # 3%
            logger.info(f"💪 Sinal MUITO FORTE ({signal_strength:.2f}) + Volume HIGH - 3% risco")
        elif signal_strength >= settings.SIGNAL_STRONG and volume_ratio > 1.1:
            risk_multiplier = Decimal("1.25")  # 2.5%
            logger.info(f"👍 Sinal FORTE ({signal_strength:.2f}) + Volume OK - 2.5% risco")
        elif signal_strength >= settings.SIGNAL_MEDIUM:
            risk_multiplier = Decimal("1.0")  # 2%
            logger.info(f"✋ Sinal MÉDIO ({signal_strength:.2f}) - 2% risco")
        else:
            risk_multiplier = Decimal("0.75")  # 1.5%
            logger.info(f"⚠️ Sinal FRACO ({signal_strength:.2f}) - 1.5% risco")
        
        dynamic_risk = settings.BASE_RISK_PER_TRADE * risk_multiplier
        
        # Calcula distância do stop loss
        stop_loss_distance = abs(entry_price - stop_loss_price) / entry_price
        
        if stop_loss_distance == 0:
            logger.warning("Distância do stop loss é zero")
            return None
        
        # Calcula tamanho da posição
        risk_amount = capital * dynamic_risk
        position_size_usd = risk_amount / stop_loss_distance
        quantity = position_size_usd / entry_price
        
        # Arredonda para step size
        from core.utils import round_down
        quantity = round_down(Decimal(str(quantity)), symbol_filters['stepSize'])
        
        # Verifica quantidade mínima
        if quantity < symbol_filters['minQty']:
            logger.warning(f"Quantidade {quantity} abaixo do mínimo")
            return None
        
        # Verifica notional mínimo
        notional = quantity * entry_price
        if notional < symbol_filters['minNotional']:
            logger.warning(f"Notional {notional} abaixo do mínimo")
            return None
        
        # Limites de posição
        position_value = quantity * entry_price
        
        if position_value < settings.MIN_POSITION_SIZE_USD:
            logger.warning(
                f"Valor ${position_value} abaixo do mínimo "
                f"${settings.MIN_POSITION_SIZE_USD}"
            )
            return None
        
        if position_value > settings.MAX_POSITION_SIZE_USD:
            max_quantity = settings.MAX_POSITION_SIZE_USD / entry_price
            quantity = round_down(
                Decimal(str(max_quantity)),
                symbol_filters['stepSize']
            )
            logger.info(f"Posição ajustada ao máximo: {quantity}")
        
        logger.info(
            f"Posição calculada: {quantity} "
            f"(${quantity * entry_price:.2f}) "
            f"Risco: {dynamic_risk * 100:.2f}% | Volume: {volume_ratio:.2f}x"
        )
        
        return quantity