from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Dict, List, Optional
from decimal import Decimal
from loguru import logger
from config.settings import settings
from config.api_keys import APIKeys
from core.utils import retry_on_failure

class BinanceClient:
    def __init__(self, environment='testnet'):
        self.environment = environment
        keys = APIKeys.get_binance_keys(environment)
        
        # CORREÇÃO: Para backtest, também inicializa cliente real para baixar dados históricos
        if environment == 'backtest':
            # Usa cliente público (sem autenticação) para dados históricos
            self.client = Client("", "")
        elif environment == 'testnet':
            self.client = Client(
                keys['api_key'],
                keys['api_secret'],
                testnet=True
            )
        elif environment == 'live':
            self.client = Client(keys['api_key'], keys['api_secret'])
        
        self.symbol_filters = {}
        if self.client:
            self._load_symbol_filters()
    
    def _load_symbol_filters(self):
        """Carrega filtros de símbolos da exchange"""
        try:
            # Para backtest, usa endpoint público
            if self.environment == 'backtest':
                exchange_info = self.client.futures_exchange_info()
            else:
                exchange_info = self.client.futures_exchange_info()
            
            for symbol_info in exchange_info['symbols']:
                symbol = symbol_info['symbol']
                filters = {}
                
                for f in symbol_info['filters']:
                    if f['filterType'] == 'PRICE_FILTER':
                        filters['tickSize'] = Decimal(f['tickSize'])
                    elif f['filterType'] == 'LOT_SIZE':
                        filters['stepSize'] = Decimal(f['stepSize'])
                        filters['minQty'] = Decimal(f['minQty'])
                        filters['maxQty'] = Decimal(f['maxQty'])
                    elif f['filterType'] == 'MIN_NOTIONAL':
                        filters['minNotional'] = Decimal(f['notional'])
                
                self.symbol_filters[symbol] = filters
                
            logger.info(f"Filtros carregados para {len(self.symbol_filters)} símbolos")
        except Exception as e:
            logger.error(f"Erro ao carregar filtros: {e}")
            # Define filtros padrão para continuar
            self._set_default_filters()
    
    def _set_default_filters(self):
        """Define filtros padrão caso não consiga carregar"""
        default_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT']
        for symbol in default_symbols:
            self.symbol_filters[symbol] = {
                'tickSize': Decimal('0.01'),
                'stepSize': Decimal('0.001'),
                'minQty': Decimal('0.001'),
                'maxQty': Decimal('10000'),
                'minNotional': Decimal('5.0')
            }
        logger.warning("Usando filtros padrão")
    
    @retry_on_failure(max_retries=3)
    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> List:
        """Obtém dados de candlestick"""
        if self.client is None:
            raise ValueError("Cliente não inicializado")
        
        # Usa API pública de futures para dados históricos
        return self.client.futures_klines(
            symbol=symbol,
            interval=interval,
            limit=limit
        )
    
    @retry_on_failure(max_retries=3)
    def get_account_balance(self) -> Decimal:
        """Obtém saldo da conta"""
        if self.environment == 'backtest':
            return Decimal('10000')  # Capital inicial para backtest
        
        if self.client is None:
            return Decimal('10000')
        
        account = self.client.futures_account()
        return Decimal(account['totalWalletBalance'])
    
    @retry_on_failure(max_retries=3)
    def place_market_order(self, symbol: str, side: str, quantity: Decimal) -> Dict:
        """Coloca ordem a mercado"""
        if self.environment == 'backtest':
            # Em backtest, simula ordem
            return {
                'orderId': 999999,
                'symbol': symbol,
                'side': side,
                'quantity': float(quantity),
                'status': 'FILLED'
            }
        
        if self.client is None:
            raise ValueError("Cliente não inicializado")
        
        order = self.client.futures_create_order(
            symbol=symbol,
            side=side,
            type='MARKET',
            quantity=float(quantity)
        )
        logger.info(f"Ordem executada: {symbol} {side} {quantity}")
        return order
    
    @retry_on_failure(max_retries=3)
    def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal
    ) -> Dict:
        """Coloca ordem limitada"""
        if self.environment == 'backtest':
            return {
                'orderId': 999999,
                'symbol': symbol,
                'side': side,
                'quantity': float(quantity),
                'price': float(price),
                'status': 'NEW'
            }
        
        if self.client is None:
            raise ValueError("Cliente não inicializado")
        
        order = self.client.futures_create_order(
            symbol=symbol,
            side=side,
            type='LIMIT',
            timeInForce='GTC',
            quantity=float(quantity),
            price=float(price)
        )
        return order
    
    @retry_on_failure(max_retries=3)
    def cancel_order(self, symbol: str, order_id: int) -> Dict:
        """Cancela ordem"""
        if self.environment == 'backtest':
            return {'orderId': order_id, 'status': 'CANCELED'}
        
        if self.client is None:
            raise ValueError("Cliente não inicializado")
        
        return self.client.futures_cancel_order(
            symbol=symbol,
            orderId=order_id
        )
    
    def get_symbol_filters(self, symbol: str) -> Dict:
        """Retorna filtros do símbolo"""
        return self.symbol_filters.get(symbol, {
            'tickSize': Decimal('0.01'),
            'stepSize': Decimal('0.001'),
            'minQty': Decimal('0.001'),
            'minNotional': Decimal('5.0')
        })
    
    @retry_on_failure(max_retries=3)
    def get_current_price(self, symbol: str) -> Decimal:
        """Obtém preço atual"""
        if self.client is None:
            raise ValueError("Cliente não inicializado")
        
        ticker = self.client.futures_symbol_ticker(symbol=symbol)
        return Decimal(ticker['price'])
    
    @retry_on_failure(max_retries=3)
    def get_positions(self) -> List[Dict]:
        """Obtém posições abertas"""
        if self.environment == 'backtest':
            return []
        
        if self.client is None:
            return []
        
        positions = self.client.futures_position_information()
        return [p for p in positions if Decimal(p['positionAmt']) != 0]