from decimal import Decimal
from typing import Dict, List
from datetime import datetime
from loguru import logger
from core.binance_client import BinanceClient
from core.position_manager import PositionManager
from execution.trade_executor import TradeExecutorV2
from config.settings import settings
from decimal import Decimal
from risk_management.position_sizer import PositionSizerV2


class OrderTracker:
    """Rastreia ordens e posições abertas"""
    
    def __init__(self, client: BinanceClient, trade_executor: TradeExecutorV2):
        self.client = client
        self.trade_executor = trade_executor
    
    def monitor_positions(self):
        """Monitora posições abertas para SL/TP"""
        
        for position in self.trade_executor.get_positions():
            try:
                current_price = self.client.get_current_price(position.symbol)
                current_price = Decimal(str(current_price))
                
                # === VERIFICA STOP LOSS ===
                if self._check_stop_loss(position, current_price):
                    self.trade_executor.execute_exit(
                        position.symbol,
                        reason="Stop Loss"
                    )
                    continue
                
                # === VERIFICA TAKE PROFIT LEVELS ===
                tp_level = position.check_take_profit_levels(current_price)
                if tp_level:
                    self._handle_take_profit(position, tp_level)
                
                # === ATUALIZA TRAILING STOP ===
                self.trade_executor.position_manager.update_trailing_stops(
                    position.symbol,
                    current_price
                )
            
            except Exception as e:
                logger.error(f"Erro monitorando {position.symbol}: {e}")
    
    def _check_stop_loss(self, position: PositionSizerV2, current_price: Decimal) -> bool:
        """Verifica se SL foi atingido"""
        
        if position.side == 'BUY':
            return current_price <= position.stop_loss
        else:
            return current_price >= position.stop_loss
    
    def _handle_take_profit(self, position: PositionSizerV2, tp_level: str):
        """Gerencia TP multinível"""
        
        from config.settings import settings
        
        if tp_level == 'TP1':
            exit_qty = position.current_quantity * settings.TP1_EXIT_RATIO
            self.trade_executor.execute_exit(
                position.symbol,
                quantity=exit_qty,
                reason=f"TP1 ({settings.TP1_EXIT_RATIO * 100:.0f}%)"
            )
            position.update_stop_loss(position.entry_price)
        
        elif tp_level == 'TP2':
            exit_qty = position.current_quantity * settings.TP2_EXIT_RATIO
            self.trade_executor.execute_exit(
                position.symbol,
                quantity=exit_qty,
                reason=f"TP2 ({settings.TP2_EXIT_RATIO * 100:.0f}%)"
            )
        
        elif tp_level == 'TP3':
            self.trade_executor.execute_exit(
                position.symbol,
                reason="TP3 (Final)"
            )
    
    def get_open_orders(self) -> List[Dict]:
        """Retorna ordens abertas"""
        return self.trade_executor.executed_trades
    
    def get_failed_executions(self) -> List[Dict]:
        """Retorna execuções falhadas"""
        return self.trade_executor.failed_executions