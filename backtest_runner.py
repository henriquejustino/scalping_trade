from decimal import Decimal
from loguru import logger
from datetime import datetime, timedelta
from config.symbols import TRADING_SYMBOLS
from core.binance_client import BinanceClient
from core.data_manager import DataManager
from strategies.scalping_ensemble import ScalpingEnsemble
from backtesting.backtest_engine import BacktestEngine
from backtesting.performance_metrics import PerformanceMetrics
import json

logger.add("data/logs/backtest_{time}.log", rotation="1 day")

def run_backtest(
    symbol: str,
    start_date: str,
    end_date: str,
    initial_capital: Decimal = Decimal('10000')
):
    """Executa backtest para um símbolo"""
    
    logger.info(f"\n{'='*60}")
    logger.info(f"BACKTEST: {symbol}")
    logger.info(f"Período: {start_date} até {end_date}")
    logger.info(f"Capital inicial: ${initial_capital}")
    logger.info(f"{'='*60}\n")
    
    # Inicializa componentes
    client = BinanceClient(environment='backtest')
    data_manager = DataManager(client)
    strategy = ScalpingEnsemble()
    
    engine = BacktestEngine(
        data_manager=data_manager,
        strategy=strategy,
        initial_capital=initial_capital
    )
    
    # Executa backtest
    results = engine.run_backtest(symbol, start_date, end_date)
    
    if 'error' in results:
        logger.error(f"Erro: {results['error']}")
        return None
    
    # Calcula métricas
    metrics = PerformanceMetrics.calculate_metrics(results)
    
    # Exibe resultados
    print(f"\n{'='*60}")
    print(f"RESULTADOS - {symbol}")
    print(f"{'='*60}")
    print(f"Total de Trades: {results['total_trades']}")
    print(f"Win Rate: {results['win_rate']*100:.2f}%")
    print(f"Profit Factor: {results['profit_factor']:.2f}")
    print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
    print(f"Max Drawdown: {results['max_drawdown']*100:.2f}%")
    print(f"\nCapital Inicial: ${results['initial_capital']:.2f}")
    print(f"Capital Final: ${results['final_capital']:.2f}")
    print(f"Retorno Total: {results['total_return_pct']:.2f}%")
    print(f"\nPnL Total: ${results['total_pnl']:.2f}")
    print(f"Média Ganho: ${results['avg_win']:.2f}")
    print(f"Média Perda: ${results['avg_loss']:.2f}")
    
    # Métricas por força de sinal
    print(f"\n{'='*60}")
    print("MÉTRICAS POR FORÇA DE SINAL")
    print(f"{'='*60}")
    for key in ['very_strong', 'strong', 'medium', 'weak']:
        signal_key = f'signal_{key}'
        if signal_key in metrics:
            m = metrics[signal_key]
            print(f"\n{key.upper()}:")
            print(f"  Trades: {m['trades']}")
            print(f"  Win Rate: {m['win_rate']*100:.2f}%")
            print(f"  Avg PnL: ${m['avg_pnl']:.2f}")
    
    # Salva resultados
    output_file = f"data/backtest_results_{symbol}_{start_date}_{end_date}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info(f"\nResultados salvos em: {output_file}")
    
    return results


def run_multi_symbol_backtest(
    symbols: list,
    start_date: str,
    end_date: str
):
    """Executa backtest para múltiplos símbolos"""
    
    all_results = {}
    
    for symbol in symbols:
        try:
            results = run_backtest(symbol, start_date, end_date)
            if results is not None:
                all_results[symbol] = results
        except Exception as e:
            logger.error(f"Erro no backtest de {symbol}: {e}")
    
    # Resumo geral
    print(f"\n{'='*60}")
    print("RESUMO GERAL")
    print(f"{'='*60}")
    
    if len(all_results) == 0:
        print("❌ Nenhum backtest executado com sucesso")
        return {}
    
    total_return = sum(r['total_return_pct'] for r in all_results.values())
    avg_win_rate = sum(r['win_rate'] for r in all_results.values()) / len(all_results)
    
    print(f"Símbolos testados: {len(all_results)}")
    print(f"Retorno total combinado: {total_return:.2f}%")
    print(f"Win Rate médio: {avg_win_rate*100:.2f}%")
    
    return all_results


if __name__ == '__main__':
    # CORREÇÃO: Usa últimos 30 dias de dados REAIS
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    print(f"📅 Período do backtest: {start_date} até {end_date}")
    print(f"   (Últimos 30 dias de dados reais)\n")
    
    # Backtest único
    run_backtest(
        symbol='BTCUSDT',
        start_date=start_date,
        end_date=end_date,
        initial_capital=Decimal('1000')
    )
    
    # Para testar múltiplos símbolos, descomente:
    # run_multi_symbol_backtest(
    #     symbols=['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
    #     start_date=start_date,
    #     end_date=end_date
    # )