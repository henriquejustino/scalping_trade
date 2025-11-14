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
        """Verifica se pode abrir nova posição"""
        
        # Verifica número máximo de posições
        if len(current_positions) >= settings.MAX_POSITIONS:
            logger.warning(f"Máximo de {settings.MAX_POSITIONS} posições atingido")
            return False