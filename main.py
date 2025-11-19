#!/usr/bin/env python3
"""
Scalping Bot V2 - Com todas as proteções e robustez
Uso: python main_v2.py testnet (ou) python main_v2.py live
"""
import time
import sys
from decimal import Decimal
from loguru import logger
from config.settings import settings
from config.symbols import TRADING_SYMBOLS
from core.binance_client import BinanceClient
from core.data.data_manager import DataManager
from strategies.smart_scalping_ensemble import SmartScalpingEnsemble
from risk_management.position_sizer import PositionSizerV2
from execution.trade_executor import TradeExecutorV2
from execution.order_tracker import OrderTrackerV2
from monitoring.performance_monitor import PerformanceMonitor
from monitoring.circuit_breaker import CircuitBreaker
from monitoring.alert_system import AlertSystemV2

# Configure logging
logger.add(
    f"{settings.LOG_DIR}/scalping_bot_v2_{{time}}.log",
    rotation="1 day",
    retention="7 days",
    level=settings.LOG_LEVEL,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
)

class ScalpingBotV2:
    """Bot de scalping com todas as proteções v2"""
    
    def __init__(self, environment: str = 'testnet'):
        logger.info(f"Inicializando Scalping Bot V2 em modo: {environment}")
        
        self.environment = environment
        self.client = BinanceClient(environment)
        self.data_manager = DataManager(self.client)
        self.strategy = SmartScalpingEnsemble()
        self.position_sizer = PositionSizerV2()
        
        self.trade_executor = TradeExecutorV2(self.client, self.position_sizer)
        self.order_tracker = OrderTrackerV2(self.client, self.trade_executor)
        
        self.performance_monitor = PerformanceMonitor()
        self.circuit_breaker = CircuitBreaker()
        self.alert_system = AlertSystemV2()
        
        self.symbols = TRADING_SYMBOLS
        self.running = False
        self.cycle_count = 0
        
        logger.info(f"✅ Bot inicializado | Símbolos: {', '.join(self.symbols)}")
    
    def start(self):
        """Inicia o bot"""
        
        logger.info("="*80)
        logger.info("🚀 BOT INICIADO")
        logger.info("="*80)
        logger.info(f"Modo: {self.environment}")
        logger.info(f"Símbolos: {', '.join(self.symbols)}")
        logger.info(f"Max Positions: {settings.MAX_POSITIONS}")
        logger.info(f"Risk per Trade: {settings.BASE_RISK_PER_TRADE*100:.1f}%")
        logger.info("="*80)
        
        if self.environment == 'live':
            confirm = input("\n⚠️  MODO LIVE! Digite 'CONFIRMO LIVE' para continuar: ")
            if confirm != 'CONFIRMO LIVE':
                logger.warning("Bot cancelado pelo usuário")
                sys.exit(0)
        
        self.running = True
        
        try:
            while self.running:
                self.run_cycle()
                time.sleep(30)  # Verifica a cada 30 segundos
        
        except KeyboardInterrupt:
            logger.info("Bot interrompido pelo usuário")
            self.stop()
        except Exception as e:
            logger.critical(f"Erro fatal: {e}", exc_info=True)
            self.stop()
    
    def run_cycle(self):
        """Executa um ciclo de trading"""
        
        self.cycle_count += 1
        
        try:
            # === 1. VERIFICA CIRCUIT BREAKER ===
            if not self.circuit_breaker.check_circuit(Decimal('0'), self.get_current_equity())[0]:
                logger.critical("⛔ CIRCUIT BREAKER ATIVADO - PARANDO BOT")
                self.stop()
                return
            
            # === 2. MONITORA POSIÇÕES ABERTAS ===
            self.order_tracker.monitor_positions()
            
            # === 3. PROCURA NOVAS OPORTUNIDADES ===
            for symbol in self.symbols:
                if self.trade_executor.has_position(symbol):
                    continue
                
                self.scan_symbol(symbol)
            
            # === 4. LOG PERIÓDICO ===
            if self.cycle_count % 20 == 0:  # A cada 10 minutos
                self._log_status()
        
        except Exception as e:
            logger.error(f"Erro no ciclo {self.cycle_count}: {e}", exc_info=True)
            self.alert_system.alert("CYCLE_ERROR", f"Erro no ciclo: {e}")
    
    def scan_symbol(self, symbol: str):
        """Escaneia símbolo para sinais"""
        
        try:
            # === 1. OBTÉM DADOS ===
            df_5m = self.data_manager.update_data(symbol, '5m')
            df_15m = self.data_manager.update_data(symbol, '15m')
            
            if len(df_5m) < 100 or len(df_15m) < 100:
                return
            
            # === 2. OBTÉM SINAL ===
            side, strength, details = self.strategy.get_ensemble_signal(df_5m, df_15m)
            
            if side is None:
                return
            
            # === 3. EXECUTA TRADE ===
            current_price = Decimal(str(df_5m['close'].iloc[-1]))
            stop_loss = self.strategy.calculate_stop_loss(df_5m, current_price, side)
            take_profit = self.strategy.calculate_take_profit(df_5m, current_price, side)
            
            # Executa
            success = self.trade_executor.execute_entry(
                symbol=symbol,
                side=side,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                signal_strength=strength,
                capital=self.get_current_equity()
            )
            
            if success:
                self.performance_monitor.log_signal(symbol, side, strength)
        
        except Exception as e:
            logger.error(f"Erro ao escanear {symbol}: {e}")
    
    def get_current_equity(self) -> Decimal:
        """Retorna equity atual (capital + posições abertas)"""
        
        try:
            balance = self.client.get_account_balance()
            return Decimal(str(balance))
        except Exception as e:
            logger.error(f"Erro ao obter saldo: {e}")
            return Decimal('0')
    
    def _log_status(self):
        """Log de status periódico"""
        
        equity = self.get_current_equity()
        positions = len(self.trade_executor.get_positions())
        
        logger.info(
            f"📊 Status | "
            f"Ciclo: {self.cycle_count} | "
            f"Equity: ${equity:.2f} | "
            f"Posições: {positions}/{settings.MAX_POSITIONS}"
        )
    
    def stop(self):
        """Para o bot e fecha posições"""
        
        logger.warning("🛑 Parando bot...")
        self.running = False
        
        # Fecha todas as posições
        positions = self.trade_executor.get_positions()
        for position in positions:
            try:
                self.trade_executor.execute_exit(
                    position.symbol,
                    reason="Bot stopped"
                )
            except Exception as e:
                logger.error(f"Erro ao fechar {position.symbol}: {e}")
        
        # Salva sessão
        self.performance_monitor.save_session()
        
        logger.info("✅ Bot parado")

def main():
    """Função principal"""
    
    # Valida ambiente
    if len(sys.argv) < 2:
        env = 'testnet'
        logger.warning("Ambiente não especificado, usando: testnet")
    else:
        env = sys.argv[1]
    
    if env not in ['testnet', 'live', 'backtest']:
        logger.error("Ambiente inválido. Use: testnet, live ou backtest")
        sys.exit(1)
    
    # Cria e inicia bot
    bot = ScalpingBotV2(environment=env)
    bot.start()

if __name__ == '__main__':
    main()