from decimal import Decimal
from typing import Dict
from datetime import datetime
from loguru import logger
from core.binance_client import BinanceClient
from core.position_manager import PositionManager
from execution.trade_executor import TradeExecutor
from config.settings import settings

class OrderTracker:
    def __init__(
        self,
        client: BinanceClient,
        position_manager: PositionManager,
        trade_executor: TradeExecutor
    ):
        self.client = client
        self.position_manager = position_manager
        self.trade_executor = trade_executor
    
    def monitor_positions(self):
        """Monitora posições abertas"""
        
        for position in self.position_manager.get_all_positions():
            try:
                current_price = self.client.get_current_price(position.symbol)
                
                # Verifica stop loss
                if self._check_stop_loss(position, current_price):
                    self.trade_executor.execute_exit(
                        position.symbol,
                        reason="Stop Loss"
                    )
                    continue
                
                # Verifica take profit levels
                tp_level = position.check_take_profit_levels(current_price)
                if tp_level:
                    self._handle_take_profit(position, tp_level)
                
                # Atualiza trailing stop
                self.position_manager.update_trailing_stops(
                    position.symbol,
                    current_price
                )
                
            except Exception as e:
                logger.error(f"Erro monitorando {position.symbol}: {e}")
    
    def _check_stop_loss(self, position, current_price: Decimal) -> bool:
        """Verifica se stop loss foi atingido"""
        
        if position.side == 'BUY':
            return current_price <= position.stop_loss
        else:
            return current_price >= position.stop_loss
    
    def _handle_take_profit(self, position, tp_level: str):
        """Gerencia take profit multinível"""
        
        if tp_level == 'TP1':
            exit_quantity = position.current_quantity * settings.TP1_EXIT_RATIO
            self.trade_executor.execute_exit(
                position.symbol,
                quantity=exit_quantity,
                reason=f"TP1 ({settings.TP1_EXIT_RATIO * 100:.0f}%)"
            )
            
            # Move stop loss para breakeven
            position.update_stop_loss(position.entry_price)
            
        elif tp_level == 'TP2':
            exit_quantity = position.current_quantity * settings.TP2_EXIT_RATIO
            self.trade_executor.execute_exit(
                position.symbol,
                quantity=exit_quantity,
                reason=f"TP2 ({settings.TP2_EXIT_RATIO * 100:.0f}%)"
            )
            
        elif tp_level == 'TP3':
            self.trade_executor.execute_exit(
                position.symbol,
                reason="TP3 (Final)"
            )
