#!/usr/bin/env python3
"""
Backtest Runner V2 - Executa backtests com todas as validações
Uso: python backtest_runner_v2.py
"""
from decimal import Decimal
from loguru import logger
from datetime import datetime, timedelta
from config.symbols import TRADING_SYMBOLS
from core.binance_client import BinanceClient
from core.data.data_manager import DataManager
from strategies.smart_scalping_ensemble import SmartScalpingEnsemble
from backtesting.backtest_engine import BacktestEngineV2
from monitoring.performance_monitor import PerformanceMonitor
import json

logger.add("data/logs/backtest_v2_{time}.log", rotation="1 day")

class BacktestRunner:
    """Executor de backtests com análise completa"""
    
    def __init__(self):
        self.client = BinanceClient(environment='backtest')
        self.data_manager = DataManager(self.client)
        self.strategy = SmartScalpingEnsemble()
        self.monitor = PerformanceMonitor()
    
    def run_single_symbol(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        initial_capital: Decimal = Decimal('10000'),
        risk_per_trade: Decimal = Decimal('0.02')
    ) -> dict:
        """Executa backtest para um símbolo"""
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 BACKTEST: {symbol}")
        logger.info(f"Período: {start_date} até {end_date}")
        logger.info(f"Capital: ${initial_capital}")
        logger.info(f"{'='*80}\n")
        
        try:
            engine = BacktestEngineV2(
                data_manager=self.data_manager,
                strategy=self.strategy,
                initial_capital=initial_capital,
                risk_per_trade=risk_per_trade
            )
            
            results = engine.run_backtest(symbol, start_date, end_date)
            
            if 'error' in results:
                logger.error(f"❌ Erro no backtest: {results['error']}")
                return results
            
            # Exibe resultados
            self._display_results(symbol, results)
            
            # Salva resultados
            self._save_results(symbol, results, start_date, end_date)
            
            return results
        
        except Exception as e:
            logger.error(f"❌ Erro fatal: {e}", exc_info=True)
            return {'error': str(e)}
    
    def run_multi_symbol(
        self,
        symbols: list = None,
        start_date: str = None,
        end_date: str = None,
        initial_capital: Decimal = Decimal('10000')
    ) -> dict:
        """Executa backtest para múltiplos símbolos"""
        
        if symbols is None:
            symbols = TRADING_SYMBOLS
        
        if start_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🎯 BACKTEST MULTI-SÍMBOLO")
        logger.info(f"Símbolos: {', '.join(symbols)}")
        logger.info(f"Período: {start_date} até {end_date}")
        logger.info(f"{'='*80}\n")
        
        results_by_symbol = {}
        all_trades = []
        total_pnl = Decimal('0')
        
        for symbol in symbols:
            try:
                results = self.run_single_symbol(
                    symbol, start_date, end_date, initial_capital
                )
                
                if 'error' not in results:
                    results_by_symbol[symbol] = results
                    all_trades.extend(results.get('trades', []))
                    total_pnl += Decimal(str(results.get('total_pnl', 0)))
            
            except Exception as e:
                logger.error(f"Erro ao testar {symbol}: {e}")
        
        # === RESUMO GERAL ===
        self._display_summary(results_by_symbol, all_trades, total_pnl)
        
        # === COMPARAÇÃO ENTRE SÍMBOLOS ===
        self._compare_symbols(results_by_symbol)
        
        # === ANÁLISE DE PERFORMANCE POR REGIME ===
        self._analyze_by_regime(all_trades)
        
        return results_by_symbol
    
    def _display_results(self, symbol: str, results: dict):
        """Exibe resultados formatados"""
        
        print(f"\n{'='*80}")
        print(f"📊 RESULTADOS DETALHADOS: {symbol}")
        print(f"{'='*80}")
        
        print(f"\n✅ SUMÁRIO:")
        print(f"  Total de Trades:     {results['total_trades']}")
        print(f"  Trades Vencedores:   {results['winning_trades']}")
        print(f"  Trades Perdedores:   {results['losing_trades']}")
        print(f"  Win Rate:            {results['win_rate']*100:.2f}%")
        
        print(f"\n💰 RESULTADOS FINANCEIROS:")
        print(f"  Capital Inicial:     ${results['initial_capital']:,.2f}")
        print(f"  Capital Final:       ${results['final_capital']:,.2f}")
        print(f"  PnL Total:           ${results['total_pnl']:,.2f}")
        print(f"  Retorno Total:       {results['total_return_pct']:.2f}%")
        print(f"  Avg Win:             ${results['avg_win']:.2f}")
        print(f"  Avg Loss:            ${results['avg_loss']:.2f}")
        
        print(f"\n📈 MÉTRICAS ESTATÍSTICAS:")
        print(f"  Profit Factor:       {results['profit_factor']:.2f}x")
        print(f"  Sharpe Ratio:        {results['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown:        {results['max_drawdown']*100:.2f}%")
        
        # Parecer
        self._give_verdict(results)
        
        print(f"\n{'='*80}\n")
    
    def _give_verdict(self, results: dict):
        """Dá parecer sobre qualidade do backtest"""
        
        score = 0
        max_score = 5
        
        # Win rate
        if results['win_rate'] >= 0.55:
            score += 1
        elif results['win_rate'] >= 0.50:
            score += 0.75
        elif results['win_rate'] >= 0.45:
            score += 0.5
        
        # Profit factor
        if results['profit_factor'] >= 2.0:
            score += 1
        elif results['profit_factor'] >= 1.5:
            score += 0.75
        elif results['profit_factor'] >= 1.2:
            score += 0.5
        
        # Sharpe
        if results['sharpe_ratio'] >= 1.5:
            score += 1
        elif results['sharpe_ratio'] >= 1.0:
            score += 0.75
        elif results['sharpe_ratio'] >= 0.7:
            score += 0.5
        
        # Drawdown
        if results['max_drawdown'] >= -0.10:
            score += 1
        elif results['max_drawdown'] >= -0.15:
            score += 0.75
        elif results['max_drawdown'] >= -0.20:
            score += 0.5
        
        # Retorno
        if results['total_return_pct'] >= 5:
            score += 1
        elif results['total_return_pct'] >= 2:
            score += 0.75
        elif results['total_return_pct'] >= 0:
            score += 0.5
        
        percentage = (score / max_score) * 100
        
        if percentage >= 80:
            grade = "🟢 EXCELENTE - Pronto para testnet"
        elif percentage >= 60:
            grade = "🟡 BOM - Precisa ajustes"
        elif percentage >= 40:
            grade = "🟠 ACEITÁVEL - Muitos ajustes necessários"
        else:
            grade = "🔴 FRACO - Revisar estratégia"
        
        print(f"\n🎯 PARECER: {grade} ({percentage:.0f}/100)")
    
    def _display_summary(self, results_by_symbol: dict, all_trades: list, total_pnl: Decimal):
        """Exibe resumo geral"""
        
        print(f"\n{'='*80}")
        print(f"📊 RESUMO GERAL - TODOS OS SÍMBOLOS")
        print(f"{'='*80}")
        
        print(f"\n✅ ESTATÍSTICAS:")
        print(f"  Símbolos Testados:   {len(results_by_symbol)}")
        print(f"  Total de Trades:     {sum(r['total_trades'] for r in results_by_symbol.values())}")
        print(f"  PnL Total Combinado: ${total_pnl:,.2f}")
        
        avg_wr = sum(r['win_rate'] for r in results_by_symbol.values()) / len(results_by_symbol) if results_by_symbol else 0
        avg_pf = sum(r['profit_factor'] for r in results_by_symbol.values()) / len(results_by_symbol) if results_by_symbol else 0
        
        print(f"\n📈 MÉDIAS:")
        print(f"  Win Rate Médio:      {avg_wr*100:.2f}%")
        print(f"  Profit Factor Médio: {avg_pf:.2f}x")
        
        print(f"\n{'='*80}\n")
    
    def _compare_symbols(self, results_by_symbol: dict):
        """Compara performance entre símbolos"""
        
        if len(results_by_symbol) <= 1:
            return
        
        print(f"\n{'='*80}")
        print(f"🔄 COMPARAÇÃO ENTRE SÍMBOLOS")
        print(f"{'='*80}\n")
        
        sorted_results = sorted(
            results_by_symbol.items(),
            key=lambda x: x[1]['total_return_pct'],
            reverse=True
        )
        
        for symbol, results in sorted_results:
            print(f"{symbol:10} | WR: {results['win_rate']*100:5.1f}% | "
                  f"PF: {results['profit_factor']:5.2f}x | "
                  f"Return: {results['total_return_pct']:6.2f}%")
    
    def _analyze_by_regime(self, all_trades: list):
        """Analisa performance por regime de mercado"""
        
        if not all_trades:
            return
        
        import pandas as pd
        
        df = pd.DataFrame(all_trades)
        
        print(f"\n{'='*80}")
        print(f"🎯 PERFORMANCE POR REGIME")
        print(f"{'='*80}\n")
        
        for regime in df['regime'].unique():
            regime_trades = df[df['regime'] == regime]
            regime_wr = len(regime_trades[regime_trades['winning']]) / len(regime_trades) if len(regime_trades) > 0 else 0
            regime_pnl = regime_trades['pnl'].sum()
            
            print(f"{regime:20} | {len(regime_trades):3} trades | "
                  f"WR: {regime_wr*100:5.1f}% | PnL: ${regime_pnl:10,.2f}")
    
    def _save_results(self, symbol: str, results: dict, start_date: str, end_date: str):
        """Salva resultados em JSON"""
        
        output_file = f"data/backtest_results_v2_{symbol}_{start_date}_{end_date}.json"
        
        # Remove chaves não-serializáveis
        save_data = {k: v for k, v in results.items() if k not in ['error']}
        
        with open(output_file, 'w') as f:
            json.dump(save_data, f, indent=2, default=str)
        
        logger.info(f"✅ Resultados salvos em: {output_file}")

def main():
    runner = BacktestRunner()
    
    # === CONFIGURAÇÕES ===
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')  # 90 dias
    
    print(f"\n🚀 BACKTEST RUNNER V2")
    print(f"Período: {start_date} até {end_date} (90 dias)")
    
    # Executa backtest
    results = runner.run_multi_symbol(
        symbols=['BTCUSDT', 'ETHUSDT'],
        start_date=start_date,
        end_date=end_date,
        initial_capital=Decimal('10000')
    )
    
    logger.info("✅ Backtest completo!")

if __name__ == '__main__':
    main()