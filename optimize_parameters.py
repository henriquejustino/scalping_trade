"""
Script para otimização de parâmetros via grid search
"""
from decimal import Decimal
from itertools import product
from loguru import logger
import pandas as pd

logger.add("data/logs/optimization.log")

def optimize_rsi_parameters(symbol='BTCUSDT', start_date='2024-10-01', end_date='2024-12-31'):
    """Otimiza parâmetros do RSI"""
    
    from core.binance_client import BinanceClient
    from core.data_manager import DataManager
    from strategies.indicators.rsi_strategy import RSIStrategy
    from backtesting.backtest_engine import BacktestEngine
    
    print("🔍 Otimizando parâmetros RSI...")
    print(f"Símbolo: {symbol}")
    print(f"Período: {start_date} - {end_date}")
    print()
    
    # Grid de parâmetros
    periods = [10, 14, 20]
    oversold_levels = [25, 30, 35]
    overbought_levels = [65, 70, 75]
    
    results = []
    
    for period, oversold, overbought in product(periods, oversold_levels, overbought_levels):
        try:
            print(f"Testando: period={period}, oversold={oversold}, overbought={overbought}")
            
            # Cria estratégia com parâmetros
            strategy = RSIStrategy(
                period=period,
                oversold=oversold,
                overbought=overbought
            )
            
            client = BinanceClient(environment='backtest')
            data_manager = DataManager(client)
            
            engine = BacktestEngine(
                data_manager=data_manager,
                strategy=strategy,
                initial_capital=Decimal('10000')
            )
            
            # Executa backtest
            result = engine.run_backtest(symbol, start_date, end_date)
            
            if 'error' not in result:
                results.append({
                    'period': period,
                    'oversold': oversold,
                    'overbought': overbought,
                    'total_return': result['total_return_pct'],
                    'win_rate': result['win_rate'],
                    'sharpe': result['sharpe_ratio'],
                    'max_dd': result['max_drawdown'],
                    'profit_factor': result['profit_factor']
                })
                
                print(f"  ✅ Retorno: {result['total_return_pct']:.2f}%")
            
        except Exception as e:
            print(f"  ❌ Erro: {e}")
    
    # Análise dos resultados
    df = pd.DataFrame(results)
    
    if len(df) > 0:
        print("\n" + "=" * 80)
        print("🏆 MELHORES PARÂMETROS")
        print("=" * 80)
        
        # Ordena por retorno total
        best = df.nlargest(5, 'total_return')
        
        print("\nTop 5 por Retorno Total:")
        print(best.to_string(index=False))
        
        # Salva resultados
        output_file = f"data/optimization_rsi_{symbol}_{start_date}_{end_date}.csv"
        df.to_csv(output_file, index=False)
        print(f"\n📊 Resultados salvos em: {output_file}")
    else:
        print("❌ Nenhum resultado válido")

if __name__ == '__main__':
    optimize_rsi_parameters()