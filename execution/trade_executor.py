from decimal import Decimal
from typing import Optional
from loguru import logger
from core.binance_client import BinanceClient
from core.position_manager import Position, PositionManager
from risk_management.position_sizer import PositionSizer
from config.settings import settings
import pandas as pd

class TradeExecutor:
    def __init__(
        self,
        client: BinanceClient,
        position_manager: PositionManager,
        position_sizer: PositionSizer
    ):
        self.client = client
        self.position_manager = position_manager
        self.position_sizer = position_sizer
    
    def execute_entry(
        self,
        symbol: str,
        side: str,
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
        signal_strength: float,
        capital: Decimal
    ) -> bool:
        """Executa entrada na posição"""
        
        try:
            # Obtém filtros do símbolo
            filters = self.client.get_symbol_filters(symbol)
            if not filters:
                logger.error(f"Filtros não encontrados para {symbol}")
                return False
            
            # Calcula tamanho da posição
            quantity = self.position_sizer.calculate_dynamic_position_size(
                capital=capital,
                entry_price=entry_price,
                stop_loss_price=stop_loss,
                symbol_filters=filters,
                signal_strength=signal_strength
            )
            
            if quantity is None:
                logger.warning(f"Não foi possível calcular posição para {symbol}")
                return False
            
            # Executa ordem
            order = self.client.place_market_order(
                symbol=symbol,
                side=side,
                quantity=quantity
            )
            
            # Calcula níveis de take profit
            distance = abs(take_profit - entry_price)
            if side == 'BUY':
                tp1 = entry_price + (distance * settings.TP1_PERCENTAGE)
                tp2 = entry_price + (distance * settings.TP2_PERCENTAGE)
                tp3 = take_profit
            else:
                tp1 = entry_price - (distance * settings.TP1_PERCENTAGE)
                tp2 = entry_price - (distance * settings.TP2_PERCENTAGE)
                tp3 = take_profit
            
            # Cria posição
            position = Position(
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                quantity=quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                tp1=tp1,
                tp2=tp2,
                tp3=tp3,
                signal_strength=signal_strength
            )
            
            self.position_manager.add_position(position)
            
            logger.info(
                f"🎯 Trade executado: {symbol} {side} {quantity} @ {entry_price}\n"
                f"   SL: {stop_loss} | TP1: {tp1} | TP2: {tp2} | TP3: {tp3}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao executar trade {symbol}: {e}")
            return False
    
    def execute_exit(
        self,
        symbol: str,
        quantity: Optional[Decimal] = None,
        reason: str = ""
    ) -> bool:
        """Executa saída da posição"""
        
        position = self.position_manager.get_position(symbol)
        if not position:
            logger.warning(f"Posição não encontrada: {symbol}")
            return False
        
        try:
            exit_quantity = quantity if quantity else position.current_quantity
            
            # Ordem inversa
            exit_side = 'SELL' if position.side == 'BUY' else 'BUY'
            
            order = self.client.place_market_order(
                symbol=symbol,
                side=exit_side,
                quantity=exit_quantity
            )
            
            # Atualiza posição
            if quantity:
                position.partial_exit(quantity / position.current_quantity)
            else:
                current_price = self.client.get_current_price(symbol)
                pnl = position.calculate_pnl(current_price)
                pnl_pct = position.calculate_pnl_percentage(current_price)
                
                logger.info(
                    f"💰 Trade fechado: {symbol} {reason}\n"
                    f"   PnL: ${pnl:.2f} ({pnl_pct:.2f}%)"
                )
                
                self.position_manager.close_position(symbol)
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao sair da posição {symbol}: {e}")
            return False