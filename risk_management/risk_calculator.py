from decimal import Decimal
from typing import List, Dict
from loguru import logger
from config.settings import settings

class RiskCalculator:
    def __init__(self):
        self.settings = settings
    
    def can_open_position(
        self,
        current_positions: List[Dict],
        new_position_risk: Decimal
    ) -> bool:
        """
        Verifica se pode abrir nova posição
        Valida contra limites de:
        1. Número máximo de posições simultâneas
        2. Risco total acumulado
        """
        
        # === VERIFICA NÚMERO MÁXIMO DE POSIÇÕES ===
        if len(current_positions) >= settings.MAX_POSITIONS:
            logger.warning(
                f"Máximo de {settings.MAX_POSITIONS} posições atingido. "
                f"Atualmente: {len(current_positions)}"
            )
            return False
        
        # === VERIFICA RISCO TOTAL ===
        current_risk = sum(
            Decimal(str(pos.get('risk', 0))) 
            for pos in current_positions
        )
        
        total_risk = current_risk + new_position_risk
        
        if total_risk > settings.MAX_TOTAL_RISK:
            logger.warning(
                f"Risco total seria {total_risk*100:.2f}% (máximo: {settings.MAX_TOTAL_RISK*100:.2f}%). "
                f"Risco atual: {current_risk*100:.2f}% | Nova posição: {new_position_risk*100:.2f}%"
            )
            return False
        
        logger.debug(
            f"✅ Pode abrir posição. "
            f"Risco total: {total_risk*100:.2f}% / {settings.MAX_TOTAL_RISK*100:.2f}%"
        )
        
        return True
    
    def calculate_position_risk(
        self,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        capital: Decimal
    ) -> Decimal:
        """Calcula o risco em % do capital para uma posição"""
        
        if stop_loss_price == 0 or capital == 0:
            return Decimal('0')
        
        risk_distance = abs(entry_price - stop_loss_price)
        risk_percentage = (risk_distance / entry_price)
        
        return risk_percentage
    
    def validate_position_size(
        self,
        position_value_usd: Decimal
    ) -> bool:
        """Valida se tamanho da posição está dentro dos limites"""
        
        if position_value_usd < settings.MIN_POSITION_SIZE_USD:
            logger.warning(
                f"Posição ${position_value_usd:.2f} abaixo do mínimo "
                f"${settings.MIN_POSITION_SIZE_USD}"
            )
            return False
        
        if position_value_usd > settings.MAX_POSITION_SIZE_USD:
            logger.warning(
                f"Posição ${position_value_usd:.2f} acima do máximo "
                f"${settings.MAX_POSITION_SIZE_USD}"
            )
            return False
        
        return True
    
    def get_max_position_size(self, capital: Decimal) -> Decimal:
        """Retorna tamanho máximo de posição baseado no capital"""
        
        # Máximo 10% do capital por posição
        max_from_capital = capital * Decimal('0.10')
        
        # Mas respeitando o limite global
        return min(max_from_capital, settings.MAX_POSITION_SIZE_USD)
    
    def calculate_risk_adjusted_quantity(
        self,
        capital: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        risk_percentage: Decimal
    ) -> Decimal:
        """
        Calcula quantidade ajustada ao risco
        
        Fórmula:
        risk_amount = capital × risk_percentage
        sl_distance = abs(entry_price - stop_loss)
        quantity = risk_amount / sl_distance
        """
        
        if entry_price == 0 or stop_loss_price == entry_price:
            return Decimal('0')
        
        risk_amount = capital * risk_percentage
        sl_distance = abs(entry_price - stop_loss_price)
        
        quantity = risk_amount / sl_distance
        
        return quantity