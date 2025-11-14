#!/usr/bin/env python3
"""
Quick Start Guide - Executa primeiro backtest
"""
from decimal import Decimal
from datetime import datetime, timedelta
from loguru import logger

logger.add("data/logs/quickstart.log")

def run_quick_backtest():
    """Executa backtest rápido para demonstração"""
    
    print("=" * 60)
    print(" " * 15 + "QUICK START - BACKTEST")
    print("=" * 60)
    print()
    
    try:
        from core.binance_client import BinanceClient
        from core.data_manager import DataManager
        from strategies.scalping_ensemble import ScalpingEnsemble
        from backtesting.backtest_engine import BacktestEngine
        
        print("📥 Inicializando componentes...")
        
        client = BinanceClient(environment='backtest')
        data_manager = DataManager(client)
        strategy = ScalpingEnsemble()
        
        engine = BacktestEngine(
            data_manager=data_manager,
            strategy=strategy,
            initial_capital=Decimal('10000')
        )
        
        print("✅ Componentes inicializados")
        print()
        print("📊 Executando backtest em BTCUSDT...")
        print("   Período: últimos 30 dias")
        print("   Capital: $10,000")
        print()
        
        # Calcula datas
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        results = engine.run_backtest(
            symbol='BTCUSDT',
            start_date=start_date,
            end_date=end_date
        )
        
        if 'error' in results:
            print(f"❌ Erro: {results['error']}")
            return
        
        # Exibe resultados
        print()
        print("=" * 60)
        print("📈 RESULTADOS")
        print("=" * 60)
        print()
        print(f"Total de Trades: {results['total_trades']}")
        print(f"Win Rate: {results['win_rate']*100:.2f}%")
        print(f"Profit Factor: {results['profit_factor']:.2f}")
        print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        print(f"Max Drawdown: {results['max_drawdown']*100:.2f}%")
        print()
        print(f"Capital Inicial: ${results['initial_capital']:,.2f}")
        print(f"Capital Final: ${results['final_capital']:,.2f}")
        print(f"Retorno: {results['total_return_pct']:.2f}%")
        print(f"PnL Total: ${results['total_pnl']:,.2f}")
        print()
        
        # Análise por força de sinal
        from backtesting.performance_metrics import PerformanceMetrics
        metrics = PerformanceMetrics.calculate_metrics(results)
        
        print("=" * 60)
        print("🎯 ANÁLISE POR FORÇA DE SINAL")
        print("=" * 60)
        
        for strength in ['very_strong', 'strong', 'medium', 'weak']:
            key = f'signal_{strength}'
            if key in metrics:
                m = metrics[key]
                print(f"\n{strength.upper()}:")
                print(f"  Trades: {m['trades']}")
                print(f"  Win Rate: {m['win_rate']*100:.2f}%")
                print(f"  Avg PnL: ${m['avg_pnl']:.2f}")
        
        print()
        print("=" * 60)
        print("✅ Backtest completo!")
        print()
        print("Próximos passos:")
        print("1. Ajuste parâmetros em config/settings.py")
        print("2. Teste com outros símbolos")
        print("3. Execute em testnet: python testnet_runner.py")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    run_quick_backtest()