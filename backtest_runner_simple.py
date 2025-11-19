#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtest Runner Simples - Sem problemas de encoding
Execute: python backtest_runner_simple.py
"""
from decimal import Decimal
from loguru import logger
from datetime import datetime, timedelta
from config.symbols import TRADING_SYMBOLS
from core.binance_client import BinanceClient
from core.data.data_manager import DataManager
from strategies.smart_scalping_ensemble import SmartScalpingEnsemble
# Tenta importar a versão corrigida (qualquer nome que seja)
try:
    from backtesting.backtest_engine import BacktestEngine
    logger.info("Usando BacktestEngine")
except ImportError:
    try:
        from backtesting.backtest_engine import BacktestEngine
        logger.info("BacktestEngine encontrado em backtest_engine.py")
    except ImportError:
        print("[ERRO] Nao consegui encontrar BacktestEngine")
        print("Procure por: backtesting/backtest_engine.py ou backtesting/backtest_engine_v2.py")
        sys.exit(1)
import json
import sys

# Configure UTF-8 para Windows
if sys.platform == 'win32':
    import os
    os.environ['PYTHONIOENCODING'] = 'utf-8'

logger.add("data/logs/backtest_simple_{time}.log", rotation="1 day")

class BacktestRunner:
    """Executor simples de backtests"""
    
    def __init__(self):
        self.client = BinanceClient(environment='backtest')
        self.data_manager = DataManager(self.client)
        self.strategy = SmartScalpingEnsemble()
    
    def run_single_symbol(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        initial_capital: Decimal = Decimal('10000')
    ) -> dict:
        """Executa backtest para um simbolo"""
        
        print("\n" + "="*80)
        print("BACKTEST: " + symbol)
        print("Periodo: " + start_date + " ate " + end_date)
        print("Capital: $" + str(initial_capital))
        print("="*80 + "\n")
        
        try:
            engine = BacktestEngine(
                data_manager=self.data_manager,
                strategy=self.strategy,
                initial_capital=initial_capital
            )
            
            results = engine.run_backtest(symbol, start_date, end_date)
            
            if 'error' in results:
                print("[ERRO] Backtest falhou: " + str(results['error']))
                logger.error("Erro no backtest: " + str(results['error']))
                return results
            
            # Exibe resultados
            self._display_results(symbol, results)
            
            # Salva resultados
            self._save_results(symbol, results, start_date, end_date)
            
            return results
        
        except Exception as e:
            print("[ERRO] Erro fatal: " + str(e))
            logger.error("Erro fatal: " + str(e), exc_info=True)
            return {'error': str(e)}
    
    def _display_results(self, symbol: str, results: dict):
        """Exibe resultados formatados"""
        
        print("\n" + "="*80)
        print("RESULTADOS DETALHADOS: " + symbol)
        print("="*80)
        
        print("\n[SUMARIO]")
        print("Total de Trades:     " + str(results['total_trades']))
        print("Trades Vencedores:   " + str(results['winning_trades']))
        print("Trades Perdedores:   " + str(results['losing_trades']))
        print("Win Rate:            " + str(round(results['win_rate']*100, 2)) + "%")
        
        print("\n[FINANCEIRO]")
        print("Capital Inicial:     $" + str(round(results['initial_capital'], 2)))
        print("Capital Final:       $" + str(round(results['final_capital'], 2)))
        print("PnL Total:           $" + str(round(results['total_pnl'], 2)))
        print("Retorno Total:       " + str(round(results['total_return_pct'], 2)) + "%")
        print("Avg Win:             $" + str(round(results['avg_win'], 2)))
        print("Avg Loss:            $" + str(round(results['avg_loss'], 2)))
        
        print("\n[METRICAS]")
        print("Profit Factor:       " + str(round(results['profit_factor'], 2)) + "x")
        print("Sharpe Ratio:        " + str(round(results['sharpe_ratio'], 2)))
        print("Max Drawdown:        " + str(round(results['max_drawdown']*100, 2)) + "%")
        
        # Parecer
        self._give_verdict(results)
        
        print("\n" + "="*80 + "\n")
    
    def _give_verdict(self, results: dict):
        """Da parecer sobre qualidade"""
        
        score = 0
        max_score = 5
        
        if results['win_rate'] >= 0.55:
            score += 1
        elif results['win_rate'] >= 0.50:
            score += 0.75
        elif results['win_rate'] >= 0.45:
            score += 0.5
        
        if results['profit_factor'] >= 2.0:
            score += 1
        elif results['profit_factor'] >= 1.5:
            score += 0.75
        elif results['profit_factor'] >= 1.2:
            score += 0.5
        
        if results['sharpe_ratio'] >= 1.5:
            score += 1
        elif results['sharpe_ratio'] >= 1.0:
            score += 0.75
        elif results['sharpe_ratio'] >= 0.7:
            score += 0.5
        
        if results['max_drawdown'] >= -0.10:
            score += 1
        elif results['max_drawdown'] >= -0.15:
            score += 0.75
        elif results['max_drawdown'] >= -0.20:
            score += 0.5
        
        if results['total_return_pct'] >= 5:
            score += 1
        elif results['total_return_pct'] >= 2:
            score += 0.75
        elif results['total_return_pct'] >= 0:
            score += 0.5
        
        percentage = (score / max_score) * 100
        
        if percentage >= 80:
            grade = "[OK] EXCELENTE - Pronto para testnet"
        elif percentage >= 60:
            grade = "[OK] BOM - Precisa ajustes"
        elif percentage >= 40:
            grade = "[AVISO] ACEITAVEL - Muitos ajustes necessarios"
        else:
            grade = "[ERRO] FRACO - Revisar estrategia"
        
        print("[PARECER] " + grade + " (" + str(int(percentage)) + "/100)")
    
    def _save_results(self, symbol: str, results: dict, start_date: str, end_date: str):
        """Salva resultados em JSON"""
        
        output_file = "data/backtest_results_" + symbol + "_" + start_date + "_" + end_date + ".json"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, default=str)
            
            print("[OK] Resultados salvos em: " + output_file)
            logger.info("Resultados salvos em: " + output_file)
        except Exception as e:
            print("[ERRO] Erro ao salvar: " + str(e))
            logger.error("Erro ao salvar: " + str(e))

def main():
    runner = BacktestRunner()
    
    # Configuracoes
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    print("\n" + "="*80)
    print("BACKTEST RUNNER - VERSAO SIMPLES")
    print("="*80)
    print("Periodo: " + start_date + " ate " + end_date + " (30 dias)")
    print("="*80)
    
    # Executa backtest
    results = runner.run_single_symbol(
        symbol='BTCUSDT',
        start_date=start_date,
        end_date=end_date,
        initial_capital=Decimal('10000')
    )
    
    if 'error' not in results and results['total_trades'] > 0:
        print("\n[OK] Backtest completado com sucesso!")
    elif 'error' not in results:
        print("\n[AVISO] Backtest completado mas nenhum trade foi gerado")
    else:
        print("\n[ERRO] Backtest falhou")

if __name__ == '__main__':
    main()