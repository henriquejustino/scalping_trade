from decimal import Decimal
from loguru import logger
from datetime import datetime, timedelta
from config.symbols import TRADING_SYMBOLS
from core.binance_client import BinanceClient
from core.data_manager import DataManager
from strategies.smart_scalping_ensemble import SmartScalpingEnsemble
from backtesting.backtest_engine import BacktestEngine
from backtesting.performance_metrics import PerformanceMetrics
import json
import pandas as pd

logger.add("data/logs/backtest_multi_{time}.log", rotation="1 day")

def run_multi_symbol_backtest(
    symbols: list = None,
    initial_capital: Decimal = Decimal('10000'),
    slippage_pct: Decimal = Decimal('0.005')  # 0.5%
):
    """
    Executa backtest para múltiplos símbolos
    Com slippage realista e validação de regime
    """
    
    if symbols is None:
        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    
    # Período
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    print("\n" + "="*80)
    print(f"🚀 BACKTEST MULTI-SÍMBOLO COM REGIME E SLIPPAGE")
    print("="*80)
    print(f"📅 Período: {start_date} até {end_date} (últimos 30 dias)")
    print(f"📊 Símbolos: {', '.join(symbols)}")
    print(f"💰 Capital inicial: ${initial_capital}")
    print(f"📉 Slippage: {slippage_pct*100:.2f}%")
    print("="*80 + "\n")
    
    # Inicializa componentes
    client = BinanceClient(environment='backtest')
    data_manager = DataManager(client)
    strategy = SmartScalpingEnsemble()
    
    results_by_symbol = {}
    total_results = {
        'total_trades': 0,
        'total_pnl': 0,
        'trades_list': []
    }
    
    # Backtest para cada símbolo
    for symbol in symbols:
        print(f"\n{'='*80}")
        print(f"Testando: {symbol}")
        print(f"{'='*80}")
        
        try:
            engine = BacktestEngine(
                data_manager=data_manager,
                strategy=strategy,
                initial_capital=initial_capital,
                slippage_pct=slippage_pct
            )
            
            results = engine.run_backtest(symbol, start_date, end_date)
            
            if 'error' in results:
                print(f"❌ Erro: {results['error']}")
                continue
            
            # Exibe resultados
            print(f"\n✅ RESULTADOS - {symbol}")
            print(f"Total de Trades: {results['total_trades']}")
            print(f"Ganhos: {results['winning_trades']} | Perdas: {results['losing_trades']}")
            print(f"Win Rate: {results['win_rate']*100:.2f}%")
            print(f"Profit Factor: {results['profit_factor']:.2f}")
            print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
            print(f"Max Drawdown: {results['max_drawdown']*100:.2f}%")
            print(f"\nRetorno Total: {results['total_return_pct']:.2f}%")
            print(f"Capital Inicial: ${results['initial_capital']:.2f}")
            print(f"Capital Final: ${results['final_capital']:.2f}")
            print(f"PnL Total: ${results['total_pnl']:.2f}")
            
            # Análise por regime
            if results['trades']:
                df_trades = pd.DataFrame(results['trades'])
                print(f"\n📊 Análise por Regime:")
                
                for regime in df_trades['regime'].unique():
                    regime_trades = df_trades[df_trades['regime'] == regime]
                    regime_winrate = len(regime_trades[regime_trades['pnl'] > 0]) / len(regime_trades) if len(regime_trades) > 0 else 0
                    regime_pnl = regime_trades['pnl'].sum()
                    
                    print(f"  {regime}: {len(regime_trades)} trades | WR: {regime_winrate*100:.1f}% | PnL: ${regime_pnl:.2f}")
            
            results_by_symbol[symbol] = results
            total_results['total_trades'] += results['total_trades']
            total_results['total_pnl'] += results['total_pnl']
            total_results['trades_list'].extend(results['trades'])
            
        except Exception as e:
            print(f"❌ Erro ao testar {symbol}: {e}")
            logger.error(f"Error testing {symbol}: {e}", exc_info=True)
    
    # Resumo geral
    print(f"\n{'='*80}")
    print("📈 RESUMO GERAL")
    print(f"{'='*80}")
    
    if len(results_by_symbol) == 0:
        print("❌ Nenhum backtest executado com sucesso")
        return {}
    
    all_trades = total_results['trades_list']
    df_all_trades = pd.DataFrame(all_trades)
    
    total_trades = len(df_all_trades)
    total_wins = len(df_all_trades[df_all_trades['pnl'] > 0])
    overall_wr = total_wins / total_trades if total_trades > 0 else 0
    
    print(f"Símbolos testados: {len(results_by_symbol)}")
    print(f"Total de Trades: {total_trades}")
    print(f"Win Rate Geral: {overall_wr*100:.2f}%")
    print(f"PnL Total Combinado: ${total_results['total_pnl']:.2f}")
    
    # Análise de força de sinal
    print(f"\n📊 Performance por Força de Sinal:")
    for strength_level, threshold in [('MUITO FORTE', 0.8), ('FORTE', 0.6), ('MÉDIO', 0.4)]:
        trades_at_level = df_all_trades[df_all_trades['signal_strength'] >= threshold]
        if len(trades_at_level) > 0:
            wr = len(trades_at_level[trades_at_level['pnl'] > 0]) / len(trades_at_level)
            avg_pnl = trades_at_level['pnl'].mean()
            print(f"  {strength_level} (≥{threshold}): {len(trades_at_level)} trades | WR: {wr*100:.1f}% | Avg PnL: ${avg_pnl:.2f}")
    
    # Análise por regime
    print(f"\n🎯 Performance por Regime de Mercado:")
    for regime in df_all_trades['regime'].unique():
        regime_trades = df_all_trades[df_all_trades['regime'] == regime]
        regime_wr = len(regime_trades[regime_trades['pnl'] > 0]) / len(regime_trades) if len(regime_trades) > 0 else 0
        regime_pnl = regime_trades['pnl'].sum()
        
        print(f"  {regime}: {len(regime_trades)} trades | WR: {regime_wr*100:.1f}% | PnL: ${regime_pnl:.2f}")
    
    # Salva resultados
    output_file = f"data/backtest_results_multi_{start_date}_{end_date}.json"
    with open(output_file, 'w') as f:
        json.dump(results_by_symbol, f, indent=2, default=str)
    
    print(f"\n✅ Resultados salvos em: {output_file}")
    
    return results_by_symbol

if __name__ == '__main__':
    # Testa múltiplos símbolos com capital pequeno
    run_multi_symbol_backtest(
        symbols=['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
        initial_capital=Decimal('5000'),  # $5k por símbolo
        slippage_pct=Decimal('0.005')  # 0.5% slippage realista
    )