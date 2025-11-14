import time
from decimal import Decimal
from loguru import logger
from config.settings import settings
from config.symbols import TRADING_SYMBOLS
from core.binance_client import BinanceClient
from core.data_manager import DataManager
from core.position_manager import PositionManager
from strategies.scalping_ensemble import ScalpingEnsemble
from risk_management.position_sizer import PositionSizer
from risk_management.risk_calculator import RiskCalculator
from execution.trade_executor import TradeExecutor
from execution.order_tracker import OrderTracker

# Configurar logging
logger.add(
    f"{settings.LOG_DIR}/scalping_bot_{{time}}.log",
    rotation="1 day",
    retention="7 days",
    level=settings.LOG_LEVEL
)

class ScalpingBot:
    def __init__(self, environment='testnet'):
        logger.info(f"Inicializando bot em modo: {environment}")
        
        self.environment = environment
        self.client = BinanceClient(environment)
        self.data_manager = DataManager(self.client)
        self.position_manager = PositionManager()
        self.strategy = ScalpingEnsemble()
        self.position_sizer = PositionSizer()
        self.risk_calculator = RiskCalculator()
        
        self.trade_executor = TradeExecutor(
            self.client,
            self.position_manager,
            self.position_sizer
        )
        
        self.order_tracker = OrderTracker(
            self.client,
            self.position_manager,
            self.trade_executor
        )
        
        self.symbols = TRADING_SYMBOLS
        self.running = False
    
    def start(self):
        """Inicia o bot"""
        logger.info("🚀 BOT INICIADO")
        logger.info(f"Símbolos: {', '.join(self.symbols)}")
        
        self.running = True
        
        try:
            while self.running:
                self.run_cycle()
                time.sleep(30)  # Verifica a cada 30 segundos
                
        except KeyboardInterrupt:
            logger.info("Bot interrompido pelo usuário")
            self.stop()
        except Exception as e:
            logger.error(f"Erro fatal: {e}")
            self.stop()
    
    def run_cycle(self):
        """Executa um ciclo de trading"""
        
        try:
            # Monitora posições abertas
            self.order_tracker.monitor_positions()
            
            # Busca novas oportunidades
            for symbol in self.symbols:
                if self.position_manager.has_position(symbol):
                    continue
                
                self.scan_symbol(symbol)
                
        except Exception as e:
            logger.error(f"Erro no ciclo: {e}")
    
    def scan_symbol(self, symbol: str):
        """Escaneia símbolo para sinais"""
        
        try:
            # Obtém dados
            df_5m = self.data_manager.update_data(symbol, '5m')
            df_15m = self.data_manager.update_data(symbol, '15m')
            
            if len(df_5m) < 100 or len(df_15m) < 100:
                return
            
            # Verifica sinal
            side, strength, details = self.strategy.get_ensemble_signal(df_5m, df_15m)
            
            if side is None:
                return
            
            logger.info(
                f"🎯 Sinal detectado: {symbol} {side} "
                f"(Força: {strength:.2f})"
            )
            
            # Verifica se pode abrir posição
            capital = self.client.get_account_balance()
            current_positions = [
                {'risk': Decimal('0.02')}  # Simplificado
                for _ in self.position_manager.get_all_positions()
            ]
            
            if not self.risk_calculator.can_open_position(
                current_positions,
                Decimal(str(strength * 0.03))
            ):
                logger.warning(f"Risco máximo atingido, ignorando {symbol}")
                return
            
            # Calcula preços
            current_price = Decimal(str(df_5m['close'].iloc[-1]))
            stop_loss = self.strategy.calculate_stop_loss(df_5m, current_price, side)
            take_profit = self.strategy.calculate_take_profit(df_5m, current_price, side)
            
            # Executa trade
            self.trade_executor.execute_entry(
                symbol=symbol,
                side=side,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                signal_strength=strength,
                capital=capital
            )
            
        except Exception as e:
            logger.error(f"Erro ao escanear {symbol}: {e}")
    
    def stop(self):
        """Para o bot"""
        logger.info("🛑 Parando bot...")
        self.running = False
        
        # Fecha todas as posições
        for position in self.position_manager.get_all_positions():
            try:
                self.trade_executor.execute_exit(
                    position.symbol,
                    reason="Bot stopped"
                )
            except Exception as e:
                logger.error(f"Erro ao fechar {position.symbol}: {e}")
        
        logger.info("Bot parado")


if __name__ == '__main__':
    import sys
    
    env = sys.argv[1] if len(sys.argv) > 1 else 'testnet'
    
    if env not in ['testnet', 'live']:
        logger.error("Ambiente inválido. Use: testnet ou live")
        sys.exit(1)
    
    if env == 'live':
        confirm = input("⚠️  MODO LIVE! Digite 'CONFIRMO' para continuar: ")
        if confirm != 'CONFIRMO':
            logger.info("Cancelado pelo usuário")
            sys.exit(0)
    
    bot = ScalpingBot(environment=env)
    bot.start()