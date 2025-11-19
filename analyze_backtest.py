#!/usr/bin/env python3
"""
Analisador de Backtest - Diz se o sistema está BOM ou RUIM
Execute: python analyze_backtest.py
"""

import json
import os
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from loguru import logger

logger.add("data/logs/backtest_results_v2_{symbol}_{start_date}_{end_date}.log", rotation="1 day")

class BacktestAnalyzer:
    """Analisa resultados de backtest e emite parecer profissional"""
    
    # Limiares de qualidade (PROFISSIONAL)
    EXCELLENT = {
        'win_rate': 0.55,        # 55%+
        'profit_factor': 2.0,     # 2.0+
        'sharpe_ratio': 1.5,      # 1.5+
        'max_drawdown': -0.10,    # Máx -10%
        'total_return': 0.05      # 5%+
    }
    
    GOOD = {
        'win_rate': 0.50,         # 50%+
        'profit_factor': 1.5,     # 1.5+
        'sharpe_ratio': 1.0,      # 1.0+
        'max_drawdown': -0.15,    # Máx -15%
        'total_return': 0.02      # 2%+
    }
    
    ACCEPTABLE = {
        'win_rate': 0.45,         # 45%+
        'profit_factor': 1.2,     # 1.2+
        'sharpe_ratio': 0.7,      # 0.7+
        'max_drawdown': -0.20,    # Máx -20%
        'total_return': 0.00      # 0%+ (breakeven)
    }
    
    POOR = {
        'win_rate': 0.40,         # 40%
        'profit_factor': 1.0,     # 1.0
        'sharpe_ratio': 0.5,      # 0.5
        'max_drawdown': -0.30,    # -30%
        'total_return': -0.05     # -5%
    }
    
    def __init__(self, results_file: str = None):
        self.results_file = results_file
        self.results = None
        self.overall_grade = None
    
    def load_results(self, file_path: str = None):
        """Carrega resultado do backtest"""
        if file_path is None:
            # Procura o arquivo mais recente
            pattern = "data/backtest_results_multi_*.json"
            files = sorted(Path(".").glob(pattern), key=os.path.getctime, reverse=True)
            if not files:
                print("❌ Nenhum arquivo de backtest encontrado")
                return False
            file_path = str(files[0])
        
        try:
            with open(file_path, 'r') as f:
                self.results = json.load(f)
            print(f"✅ Carregado: {file_path}")
            return True
        except Exception as e:
            print(f"❌ Erro ao carregar: {e}")
            return False
    
    def evaluate_symbol(self, symbol_results: dict) -> dict:
        """Avalia resultado de um símbolo"""
        
        try:
            wr = symbol_results.get('win_rate', 0)
            pf = symbol_results.get('profit_factor', 0)
            sr = symbol_results.get('sharpe_ratio', 0)
            dd = symbol_results.get('max_drawdown', 0)
            ret = symbol_results.get('total_return_pct', 0) / 100
            
            # Conta pontos
            score = 0
            max_score = 5
            
            if wr >= self.EXCELLENT['win_rate']:
                score += 1
            elif wr >= self.GOOD['win_rate']:
                score += 0.75
            elif wr >= self.ACCEPTABLE['win_rate']:
                score += 0.5
            
            if pf >= self.EXCELLENT['profit_factor']:
                score += 1
            elif pf >= self.GOOD['profit_factor']:
                score += 0.75
            elif pf >= self.ACCEPTABLE['profit_factor']:
                score += 0.5
            
            if sr >= self.EXCELLENT['sharpe_ratio']:
                score += 1
            elif sr >= self.GOOD['sharpe_ratio']:
                score += 0.75
            elif sr >= self.ACCEPTABLE['sharpe_ratio']:
                score += 0.5
            
            if dd >= self.EXCELLENT['max_drawdown']:
                score += 1
            elif dd >= self.GOOD['max_drawdown']:
                score += 0.75
            elif dd >= self.ACCEPTABLE['max_drawdown']:
                score += 0.5
            
            if ret >= self.EXCELLENT['total_return']:
                score += 1
            elif ret >= self.GOOD['total_return']:
                score += 0.75
            elif ret >= self.ACCEPTABLE['total_return']:
                score += 0.5
            
            # Grade
            if score >= 4.5:
                grade = '🟢 EXCELENTE'
            elif score >= 3.5:
                grade = '🟢 BOM'
            elif score >= 2.5:
                grade = '🟡 ACEITÁVEL'
            elif score >= 1.5:
                grade = '🔴 RUIM'
            else:
                grade = '🔴 MUITO RUIM'
            
            return {
                'score': score,
                'max_score': max_score,
                'percentage': (score / max_score) * 100,
                'grade': grade,
                'metrics': {
                    'win_rate': wr,
                    'profit_factor': pf,
                    'sharpe_ratio': sr,
                    'max_drawdown': dd,
                    'total_return': ret
                }
            }
        except Exception as e:
            logger.error(f"Erro ao avaliar: {e}")
            return None
    
    def print_detailed_analysis(self):
        """Exibe análise detalhada"""
        
        if not self.results:
            print("❌ Nenhum resultado carregado")
            return
        
        print("\n" + "="*80)
        print("📊 ANÁLISE DETALHADA DE BACKTEST")
        print("="*80 + "\n")
        
        overall_trades = 0
        overall_pnl = 0
        symbol_evaluations = {}
        
        # Analisa cada símbolo
        for symbol, results in self.results.items():
            print(f"\n{'─'*80}")
            print(f"📈 {symbol}")
            print(f"{'─'*80}")
            
            evaluation = self.evaluate_symbol(results)
            if evaluation is None:
                continue
            
            symbol_evaluations[symbol] = evaluation
            overall_trades += results.get('total_trades', 0)
            overall_pnl += results.get('total_pnl', 0)
            
            # Exibe métricas
            metrics = evaluation['metrics']
            print(f"Win Rate:         {metrics['win_rate']*100:>6.2f}% {'✅' if metrics['win_rate'] >= 0.50 else '❌'}")
            print(f"Profit Factor:    {metrics['profit_factor']:>6.2f}x {'✅' if metrics['profit_factor'] >= 1.5 else '❌'}")
            print(f"Sharpe Ratio:     {metrics['sharpe_ratio']:>6.2f}  {'✅' if metrics['sharpe_ratio'] >= 1.0 else '❌'}")
            print(f"Max Drawdown:     {metrics['max_drawdown']*100:>6.2f}% {'✅' if metrics['max_drawdown'] >= -0.15 else '❌'}")
            print(f"Total Return:     {metrics['total_return']*100:>6.2f}% {'✅' if metrics['total_return'] >= 0.02 else '⚠️'}")
            
            print(f"\nTrades:           {results.get('total_trades', 0)}")
            print(f"Wins/Losses:      {results.get('winning_trades', 0)}/{results.get('losing_trades', 0)}")
            print(f"Total PnL:        ${results.get('total_pnl', 0):>10.2f}")
            print(f"Capital Final:    ${results.get('final_capital', 0):>10.2f}")
            
            print(f"\n🎯 PARECER: {evaluation['grade']} ({evaluation['percentage']:.0f}/100)")
        
        # Resumo geral
        print(f"\n{'='*80}")
        print("📊 RESUMO GERAL")
        print(f"{'='*80}")
        
        avg_grade = sum(e['percentage'] for e in symbol_evaluations.values()) / len(symbol_evaluations) if symbol_evaluations else 0
        
        print(f"Símbolos analisados: {len(symbol_evaluations)}")
        print(f"Total de trades:     {overall_trades}")
        print(f"PnL combinado:       ${overall_pnl:,.2f}")
        print(f"\nGrade média: {avg_grade:.0f}/100")
        
        if avg_grade >= 80:
            self.overall_grade = "✅ SISTEMA VIÁVEL - Pronto para testnet"
            color = "🟢"
        elif avg_grade >= 60:
            self.overall_grade = "⚠️ SISTEMA MARGINAL - Precisa ajustes"
            color = "🟡"
        else:
            self.overall_grade = "❌ SISTEMA NÃO VIÁVEL - Revisar estratégia"
            color = "🔴"
        
        print(f"\n{color} {self.overall_grade}")
        
        print(f"\n{'='*80}")
        print("📋 CHECKLIST DE QUALIDADE")
        print(f"{'='*80}")
        
        checks = {
            'Win Rate ≥ 50%': any(e['metrics']['win_rate'] >= 0.50 for e in symbol_evaluations.values()),
            'Profit Factor ≥ 1.5': any(e['metrics']['profit_factor'] >= 1.5 for e in symbol_evaluations.values()),
            'Sharpe Ratio ≥ 1.0': any(e['metrics']['sharpe_ratio'] >= 1.0 for e in symbol_evaluations.values()),
            'Max Drawdown ≤ -15%': any(e['metrics']['max_drawdown'] <= -0.15 for e in symbol_evaluations.values()),
            'Retorno positivo': overall_pnl > 0,
            '30+ trades': overall_trades >= 30,
            'Consistência entre símbolos': len([e for e in symbol_evaluations.values() if e['percentage'] >= 60]) >= len(symbol_evaluations) * 0.7
        }
        
        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"{status} {check}")
        
        print(f"\n{'='*80}\n")
    
    def get_recommendations(self):
        """Emite recomendações"""
        
        if not self.results or not self.overall_grade:
            return
        
        print("💡 RECOMENDAÇÕES")
        print("="*80)
        
        if "VIÁVEL" in self.overall_grade:
            print("""
✅ Sistema está BOM! Próximos passos:

1. Execute em TESTNET por 1-2 semanas
   python testnet_runner.py

2. Monitore:
   - Win rate real vs backtest
   - Slippage real vs 0.5%
   - Drawdown durante live trading

3. Se resultados forem similares ao backtest:
   - Aumente capital gradualmente
   - Monitore constantemente
   
4. Se diferente do backtest:
   - Identifique o gap
   - Ajuste parâmetros
   - Volte ao backtest
            """)
        elif "MARGINAL" in self.overall_grade:
            print("""
⚠️ Sistema MARGINAL. Recomendações:

1. Aumente rigor:
   - Aumente threshold de força de sinal (de 0.25 para 0.35)
   - Rejeite regime HIGH_VOLATILITY
   - Aumente slippage para 1%

2. Teste ajustes no backtest:
   python backtest_multi_symbol.py

3. Se melhorar:
   - Pode ir para testnet
   - Com capital reduzido
            """)
        else:
            print("""
❌ Sistema NÃO VIÁVEL. Recomendações:

1. Revise a estratégia:
   - Verifique sinais fracos
   - Aumente validação de regime
   - Aumente validação de volume

2. Tente:
   - Diferentes timeframes (agora é 5m/15m)
   - Diferentes símbolos
   - Diferentes parâmetros de indicadores

3. Volte ao backtest após cada ajuste
            """)
        
        print("="*80 + "\n")

def main():
    analyzer = BacktestAnalyzer()
    
    if not analyzer.load_results():
        return 1
    
    analyzer.print_detailed_analysis()
    analyzer.get_recommendations()
    
    return 0

if __name__ == '__main__':
    exit(main())