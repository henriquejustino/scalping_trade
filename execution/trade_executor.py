"""
Trade Executor V2 e Order Tracker V2 - Execução Robusta com Validações
"""
from decimal import Decimal
from typing import Optional, Dict, List
from datetime import datetime
from loguru import logger
from core.binance_client import BinanceClient
from core.position_manager import Position, PositionManager
from core.engine.base_engine import Position as BasePosition

# ============================================================================
# FILE: execution/trade_executor_v2.py
# ============================================================================

class TradeExecutorV2:
    """Executor de trades robusto com validações completas"""
    
    def __init__(self, client: BinanceClient, position_sizer):
        self.client = client
        self.position_sizer = position_sizer
        self.position_manager = PositionManager()
        self.executed_trades = []
        self.failed_executions = []
    
    def execute_entry(
        self,
        symbol: str,
        side: str,
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
        signal_strength: float,
        capital: Decimal,
        volume_ratio: float = 1.0,
        regime: str = "RANGING"
    ) -> bool:
        """
        ✅ ROBUSTO: Executa entrada com validações
        """
        
        try:
            # === 1. VALIDAÇÃO BÁSICA ===
            if side not in ['BUY', 'SELL']:
                logger.error(f"Side inválido: {side}")
                return False
            
            if entry_price <= 0 or stop_loss <= 0 or take_profit <= 0:
                logger.error("Preços inválidos")
                return False
            
            # === 2. VALIDAÇÃO DO TRADE ===
            if not self._validate_trade_logic(side, entry_price, stop_loss, take_profit):
                logger.warning("Trade lógicamente inválido")
                return False
            
            # === 3. VALIDAÇÃO DE POSIÇÕES ===
            if self.position_manager.has_position(symbol):
                logger.warning(f"Posição já aberta em {symbol}")
                return False
            
            if len(self.position_manager.get_all_positions()) >= 3:
                logger.warning("Máximo de posições atingido")
                return False
            
            # === 4. CALCULA TAMANHO DA POSIÇÃO ===
            filters = self.client.get_symbol_filters(symbol)
            
            quantity = self.position_sizer.calculate_dynamic_position_size(
                capital=capital,
                entry_price=entry_price,
                stop_loss_price=stop_loss,
                symbol_filters=filters,
                signal_strength=signal_strength,
                volume_ratio=volume_ratio,
                regime=regime
            )
            
            if quantity is None or quantity <= 0:
                logger.warning(f"Quantidade inválida: {quantity}")
                return False
            
            # === 5. COLOCA ORDEM ===
            try:
                order = self.client.place_market_order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity
                )
                
                if not order:
                    logger.error("Ordem retornou None")
                    return False
            except Exception as e:
                logger.error(f"Erro ao colocar ordem: {e}")
                self.failed_executions.append({
                    'timestamp': datetime.now(),
                    'symbol': symbol,
                    'error': str(e)
                })
                return False
            
            # === 6. CRIA POSIÇÃO ===
            distance = abs(take_profit - entry_price)
            from config.settings import settings
            
            if side == 'BUY':
                tp1 = entry_price + (distance * settings.TP1_PERCENTAGE)
                tp2 = entry_price + (distance * settings.TP2_PERCENTAGE)
            else:
                tp1 = entry_price - (distance * settings.TP1_PERCENTAGE)
                tp2 = entry_price - (distance * settings.TP2_PERCENTAGE)
            
            position = Position(
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                tp1=tp1,
                tp2=tp2,
                tp3=take_profit,
                signal_strength=signal_strength
            )
            
            self.position_manager.add_position(position)
            
            self.executed_trades.append({
                'timestamp': datetime.now(),
                'symbol': symbol,
                'side': side,
                'entry_price': float(entry_price),
                'quantity': float(quantity),
                'order_id': order.get('orderId')
            })
            
            logger.info(
                f"✅ TRADE EXECUTADO: {side} {quantity:.6f} {symbol} @ "
                f"${entry_price:.2f} | SL: ${stop_loss:.2f} | TP: ${take_profit:.2f}"
            )
            
            return True
        
        except Exception as e:
            logger.error(f"Erro ao executar entrada: {e}", exc_info=True)
            return False
    
    def execute_exit(
        self,
        symbol: str,
        quantity: Optional[Decimal] = None,
        reason: str = "Manual"
    ) -> bool:
        """Executa saída da posição"""
        
        position = self.position_manager.get_position(symbol)
        if not position:
            logger.warning(f"Posição não encontrada: {symbol}")
            return False
        
        try:
            exit_quantity = quantity if quantity else position.quantity
            exit_side = 'SELL' if position.side == 'BUY' else 'BUY'
            
            order = self.client.place_market_order(
                symbol=symbol,
                side=exit_side,
                quantity=exit_quantity
            )
            
            if not order:
                logger.error("Ordem de saída retornou None")
                return False
            
            # Atualiza posição
            if quantity:
                position.partial_exit(quantity / position.quantity)
            else:
                self.position_manager.close_position(symbol)
            
            logger.info(
                f"✅ SAÍDA EXECUTADA: {exit_side} {exit_quantity:.6f} {symbol} "
                f"({reason})"
            )
            
            return True
        
        except Exception as e:
            logger.error(f"Erro ao executar saída: {e}")
            return False
    
    def _validate_trade_logic(
        self,
        side: str,
        entry: Decimal,
        sl: Decimal,
        tp: Decimal
    ) -> bool:
        """✅ Validação lógica do trade"""
        
        if side == 'BUY':
            if sl >= entry or tp <= entry:
                return False
        else:
            if sl <= entry or tp >= entry:
                return False
        
        # R:R mínimo 1:1
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        
        if reward < risk:
            return False
        
        return True
    
    def has_position(self, symbol: str) -> bool:
        """Verifica se tem posição aberta"""
        return self.position_manager.has_position(symbol)
    
    def get_positions(self) -> List:
        """Retorna todas as posições abertas"""
        return self.position_manager.get_all_positions()