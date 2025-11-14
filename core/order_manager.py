from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger
from core.binance_client import BinanceClient

class OrderManager:
    """Gerencia ordens ativas na exchange"""
    
    def __init__(self, client: BinanceClient):
        self.client = client
        self.active_orders: Dict[str, List[Dict]] = {}
    
    def place_stop_loss_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        stop_price: Decimal
    ) -> Optional[Dict]:
        """Coloca ordem de stop loss"""
        try:
            from core.utils import round_price
            filters = self.client.get_symbol_filters(symbol)
            
            stop_price = round_price(stop_price, filters['tickSize'])
            
            order = self.client.client.futures_create_order(
                symbol=symbol,
                side=side,
                type='STOP_MARKET',
                stopPrice=float(stop_price),
                quantity=float(quantity),
                closePosition=False
            )
            
            if symbol not in self.active_orders:
                self.active_orders[symbol] = []
            
            self.active_orders[symbol].append({
                'orderId': order['orderId'],
                'type': 'STOP_LOSS',
                'price': stop_price,
                'timestamp': datetime.now()
            })
            
            logger.info(f"Stop loss colocado: {symbol} @ {stop_price}")
            return order
            
        except Exception as e:
            logger.error(f"Erro ao colocar stop loss {symbol}: {e}")
            return None
    
    def place_take_profit_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        limit_price: Decimal
    ) -> Optional[Dict]:
        """Coloca ordem de take profit"""
        try:
            from core.utils import round_price
            filters = self.client.get_symbol_filters(symbol)
            
            limit_price = round_price(limit_price, filters['tickSize'])
            
            order = self.client.place_limit_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=limit_price
            )
            
            if symbol not in self.active_orders:
                self.active_orders[symbol] = []
            
            self.active_orders[symbol].append({
                'orderId': order['orderId'],
                'type': 'TAKE_PROFIT',
                'price': limit_price,
                'timestamp': datetime.now()
            })
            
            logger.info(f"Take profit colocado: {symbol} @ {limit_price}")
            return order
            
        except Exception as e:
            logger.error(f"Erro ao colocar take profit {symbol}: {e}")
            return None
    
    def cancel_all_orders(self, symbol: str) -> bool:
        """Cancela todas as ordens de um símbolo"""
        try:
            if symbol not in self.active_orders:
                return True
            
            for order in self.active_orders[symbol]:
                self.client.cancel_order(symbol, order['orderId'])
            
            self.active_orders[symbol] = []
            logger.info(f"Todas as ordens canceladas: {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao cancelar ordens {symbol}: {e}")
            return False
    
    def update_stop_loss(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        new_stop_price: Decimal
    ) -> bool:
        """Atualiza stop loss (cancela e recria)"""
        try:
            # Cancela stop loss existente
            if symbol in self.active_orders:
                for order in self.active_orders[symbol]:
                    if order['type'] == 'STOP_LOSS':
                        self.client.cancel_order(symbol, order['orderId'])
                        self.active_orders[symbol].remove(order)
            
            # Coloca novo stop loss
            self.place_stop_loss_order(symbol, side, quantity, new_stop_price)
            return True
            
        except Exception as e:
            logger.error(f"Erro ao atualizar stop loss {symbol}: {e}")
            return False