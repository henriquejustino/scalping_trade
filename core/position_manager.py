from decimal import Decimal
from typing import Optional, Dict
from dataclasses import dataclass
from datetime import datetime
from loguru import logger
from config.settings import settings

@dataclass
class Position:
    symbol: str
    side: str
    entry_price: Decimal
    quantity: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    tp1: Decimal
    tp2: Decimal
    tp3: Decimal
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    current_quantity: Decimal = None
    entry_time: datetime = None
    signal_strength: float = 0.0
    
    def __post_init__(self):
        if self.current_quantity is None:
            self.current_quantity = self.quantity
        if self.entry_time is None:
            self.entry_time = datetime.now()
    
    def calculate_pnl(self, current_price: Decimal) -> Decimal:
        """Calcula PnL atual"""
        if self.side == 'BUY':
            return (current_price - self.entry_price) * self.current_quantity
        else:
            return (self.entry_price - current_price) * self.current_quantity
    
    def calculate_pnl_percentage(self, current_price: Decimal) -> Decimal:
        """Calcula PnL em percentual"""
        if self.side == 'BUY':
            return ((current_price - self.entry_price) / self.entry_price) * Decimal('100')
        else:
            return ((self.entry_price - current_price) / self.entry_price) * Decimal('100')
    
    def update_stop_loss(self, new_stop_loss: Decimal):
        """Atualiza stop loss (trailing)"""
        if self.side == 'BUY':
            if new_stop_loss > self.stop_loss:
                logger.info(
                    f"{self.symbol} Stop loss atualizado: "
                    f"{self.stop_loss} -> {new_stop_loss}"
                )
                self.stop_loss = new_stop_loss
        else:
            if new_stop_loss < self.stop_loss:
                logger.info(
                    f"{self.symbol} Stop loss atualizado: "
                    f"{self.stop_loss} -> {new_stop_loss}"
                )
                self.stop_loss = new_stop_loss
    
    def check_take_profit_levels(self, current_price: Decimal) -> Optional[str]:
        """Verifica níveis de take profit"""
        
        if self.side == 'BUY':
            if not self.tp1_hit and current_price >= self.tp1:
                self.tp1_hit = True
                return 'TP1'
            elif not self.tp2_hit and current_price >= self.tp2:
                self.tp2_hit = True
                return 'TP2'
            elif not self.tp3_hit and current_price >= self.tp3:
                self.tp3_hit = True
                return 'TP3'
        else:  # SELL
            if not self.tp1_hit and current_price <= self.tp1:
                self.tp1_hit = True
                return 'TP1'
            elif not self.tp2_hit and current_price <= self.tp2:
                self.tp2_hit = True
                return 'TP2'
            elif not self.tp3_hit and current_price <= self.tp3:
                self.tp3_hit = True
                return 'TP3'
        
        return None
    
    def partial_exit(self, exit_ratio: Decimal) -> Decimal:
        """Saída parcial da posição"""
        exit_quantity = self.current_quantity * exit_ratio
        self.current_quantity -= exit_quantity
        
        logger.info(
            f"{self.symbol} Saída parcial: {exit_quantity} "
            f"(restante: {self.current_quantity})"
        )
        
        return exit_quantity


class PositionManager:
    def __init__(self):
        self.positions: Dict[str, Position] = {}
    
    def add_position(self, position: Position):
        """Adiciona nova posição"""
        self.positions[position.symbol] = position
        logger.info(
            f"✅ Posição aberta: {position.symbol} {position.side} "
            f"{position.quantity} @ {position.entry_price}"
        )
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Obtém posição por símbolo"""
        return self.positions.get(symbol)
    
    def close_position(self, symbol: str) -> Optional[Position]:
        """Fecha e remove posição"""
        position = self.positions.pop(symbol, None)
        if position:
            logger.info(f"❌ Posição fechada: {symbol}")
        return position
    
    def get_all_positions(self) -> list:
        """Retorna todas as posições abertas"""
        return list(self.positions.values())
    
    def has_position(self, symbol: str) -> bool:
        """Verifica se tem posição aberta no símbolo"""
        return symbol in self.positions
    
    def update_trailing_stops(self, symbol: str, current_price: Decimal):
        """Atualiza trailing stop loss"""
        position = self.get_position(symbol)
        if not position:
            return
        
        pnl_pct = position.calculate_pnl_percentage(current_price)
        
        # Ativa trailing stop após lucro mínimo
        if pnl_pct >= settings.TRAILING_STOP_ACTIVATION * Decimal('100'):
            if position.side == 'BUY':
                new_stop = current_price * (Decimal('1') - settings.TRAILING_STOP_DISTANCE)
                position.update_stop_loss(new_stop)
            else:
                new_stop = current_price * (Decimal('1') + settings.TRAILING_STOP_DISTANCE)
                position.update_stop_loss(new_stop)
