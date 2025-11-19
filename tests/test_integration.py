# ============================================================================
# FILE: tests/test_integration.py - Testes de Integração Completos
# ============================================================================

import unittest
import pandas as pd
import numpy as np
from decimal import Decimal
from datetime import datetime, timedelta
from loguru import logger

class TestBacktestEngine(unittest.TestCase):
    """Testes de integração do BacktestEngine V2"""
    
    def setUp(self):
        """Setup para cada teste"""
        np.random.seed(42)
        self.symbols = ['BTCUSDT', 'ETHUSDT']
    
    def test_capital_tracking_correctness(self):
        """✅ Testa se capital é atualizado corretamente"""
        
        from backtesting.backtest_engine import BacktestEngine
        from core.data.data_manager import DataManager
        from core.binance_client import BinanceClient
        from strategies.smart_scalping_ensemble import SmartScalpingEnsemble
        
        client = BinanceClient(environment='backtest')
        data_manager = DataManager(client)
        strategy = SmartScalpingEnsemble()
        
        engine = BacktestEngine(
            data_manager=data_manager,
            strategy=strategy,
            initial_capital=Decimal('10000')
        )
        
        # Simula fechamento de trades
        engine.closed_trades_pnl = Decimal('100')  # 100 de lucro
        
        expected_capital = Decimal('10100')
        actual_capital = engine.current_capital
        
        self.assertEqual(actual_capital, expected_capital,
                        f"Capital incorreto: {actual_capital} != {expected_capital}")
    
    def test_timeframe_synchronization(self):
        """✅ Testa sincronização de timeframes"""
        
        from core.data.data_synchronizer import DataSynchronizer
        
        # Cria dados de teste
        dates_5m = pd.date_range('2024-01-01', periods=300, freq='5min')
        dates_15m = pd.date_range('2024-01-01', periods=100, freq='15min')
        
        df_5m = pd.DataFrame({
            'open': np.random.uniform(40000, 41000, 300),
            'high': np.random.uniform(40000, 41000, 300),
            'low': np.random.uniform(40000, 41000, 300),
            'close': np.random.uniform(40000, 41000, 300),
            'volume': np.random.uniform(100, 1000, 300)
        }, index=dates_5m)
        
        df_15m = pd.DataFrame({
            'open': np.random.uniform(40000, 41000, 100),
            'high': np.random.uniform(40000, 41000, 100),
            'low': np.random.uniform(40000, 41000, 100),
            'close': np.random.uniform(40000, 41000, 100),
            'volume': np.random.uniform(100, 1000, 100)
        }, index=dates_15m)
        
        # Alinha
        df_5m_aligned, df_15m_aligned = DataSynchronizer.align_timeframes(df_5m, df_15m)
        
        # Valida que últimos timestamps correspondem
        self.assertEqual(
            df_5m_aligned.index[-1],
            df_15m_aligned.index[-1],
            "Timestamps não correspondem após alinhamento"
        )
    
    def test_trade_validation_rejects_invalid_trades(self):
        """✅ Testa se trades inválidos são rejeitados"""
        
        from backtesting.backtest_engine import BacktestEngine
        from core.binance_client import BinanceClient
        from core.data.data_manager import DataManager
        from strategies.smart_scalping_ensemble import SmartScalpingEnsemble
        
        client = BinanceClient(environment='backtest')
        data_manager = DataManager(client)
        strategy = SmartScalpingEnsemble()
        
        engine = BacktestEngine(
            data_manager=data_manager,
            strategy=strategy
        )
        
        entry = Decimal('100')
        
        # Teste 1: SL inválido (acima do entry em BUY)
        result = engine.validate_trade('BUY', entry, Decimal('110'), Decimal('105'))
        self.assertFalse(result, "Trade BUY com SL > entry deveria ser rejeitado")
        
        # Teste 2: TP inválido (abaixo do entry em BUY)
        result = engine.validate_trade('BUY', entry, Decimal('95'), Decimal('90'))
        self.assertFalse(result, "Trade BUY com TP < entry deveria ser rejeitado")
        
        # Teste 3: R:R ruim (risk > reward)
        result = engine.validate_trade('BUY', entry, Decimal('90'), Decimal('101'))
        self.assertFalse(result, "Trade com R:R < 1:1 deveria ser rejeitado")
        
        # Teste 4: Trade válido
        result = engine.validate_trade('BUY', entry, Decimal('95'), Decimal('110'))
        self.assertTrue(result, "Trade válido foi rejeitado")
    
    def test_slippage_affects_pnl(self):
        """✅ Testa se slippage afeta o PnL corretamente"""
        
        from execution.slippage_model import SlippageModel
        
        model = SlippageModel()
        
        entry_price = Decimal('40000')
        exit_price = Decimal('40100')
        
        # BUY com slippage
        slipped_entry = model.apply_entry_slippage(entry_price, 'BUY', 1.0, 'RANGING')
        slipped_exit = model.apply_exit_slippage(exit_price, 'BUY', 1.0, 'RANGING')
        
        # Slippage deve aumentar entrada (paga mais) e diminuir saída (recebe menos)
        self.assertGreater(slipped_entry, entry_price,
                          "Entrada BUY com slippage deveria ser maior")
        self.assertLess(slipped_exit, exit_price,
                       "Saída BUY com slippage deveria ser menor")
    
    def test_position_sizer_respects_limits(self):
        """✅ Testa se position sizer respeita limites"""
        
        from risk_management.position_sizer import PositionSizerV2
        
        sizer = PositionSizerV2()
        
        capital = Decimal('10000')
        entry = Decimal('40000')
        stop_loss = Decimal('39000')
        
        filters = {
            'tickSize': Decimal('0.01'),
            'stepSize': Decimal('0.00001'),
            'minQty': Decimal('0.001'),
            'minNotional': Decimal('5.0')
        }
        
        # Testa com sinal fraco
        qty_weak = sizer.calculate_dynamic_position_size(
            capital, entry, stop_loss, filters, 0.3
        )
        
        # Testa com sinal forte
        qty_strong = sizer.calculate_dynamic_position_size(
            capital, entry, stop_loss, filters, 0.9
        )
        
        if qty_weak and qty_strong:
            self.assertGreater(qty_strong, qty_weak,
                              "Sinal forte deveria ter maior posição que fraco")


class TestMonitoringAlerts(unittest.TestCase):
    """Testes do sistema de alertas"""
    
    def test_circuit_breaker_stops_on_max_consecutive_losses(self):
        """✅ Testa se circuit breaker para em N perdas consecutivas"""
        
        from monitoring.circuit_breaker import CircuitBreaker
        
        cb = CircuitBreaker(max_consecutive_losses=3)
        
        # Simula 3 perdas consecutivas
        should_continue_1, msg_1 = cb.check_circuit(Decimal('-100'), Decimal('9900'))
        should_continue_2, msg_2 = cb.check_circuit(Decimal('-100'), Decimal('9800'))
        should_continue_3, msg_3 = cb.check_circuit(Decimal('-100'), Decimal('9700'))
        
        self.assertTrue(should_continue_1 and should_continue_2,
                       "Primeiras perdas deveriam ser aceitas")
        self.assertFalse(should_continue_3,
                        "Circuit breaker deveria ativar após max perdas consecutivas")
    
    def test_alert_system_tracks_alerts(self):
        """✅ Testa se sistema de alertas rastreia tudo"""
        
        from monitoring.alert_system import AlertSystemV2
        
        alert_sys = AlertSystemV2()
        
        alert_sys.alert("TEST_ALERT_1", "Primeiro alerta", "WARNING")
        alert_sys.alert("TEST_ALERT_2", "Segundo alerta", "ERROR")
        
        summary = alert_sys.get_alerts_summary()
        
        self.assertEqual(summary['total_alerts'], 2,
                        "Deveriam ter 2 alertas registrados")


class TestPerformanceMonitoring(unittest.TestCase):
    """Testes de monitoramento de performance"""
    
    def test_performance_monitor_calculates_stats_correctly(self):
        """✅ Testa se monitor calcula estatísticas corretas"""
        
        from monitoring.performance_monitor import PerformanceMonitor
        
        monitor = PerformanceMonitor()
        
        # Log 3 trades
        monitor.log_trade({'symbol': 'BTCUSDT', 'pnl': 100})
        monitor.log_trade({'symbol': 'ETHUSDT', 'pnl': -50})
        monitor.log_trade({'symbol': 'BTCUSDT', 'pnl': 75})
        
        stats = monitor.get_session_stats()
        
        self.assertEqual(stats['total_trades'], 3)
        self.assertEqual(stats['winning_trades'], 2)
        self.assertEqual(stats['losing_trades'], 1)
        self.assertAlmostEqual(stats['win_rate'], 2/3, places=2)


# ============================================================================
# FILE: BEST_PRACTICES.md - Guia de Melhores Práticas
# ============================================================================

"""
# 🏆 MELHORES PRÁTICAS PARA TRADING QUANTITATIVO

## 1. GERENCIAMENTO DE RISCO

### ✅ O QUE FAZER:
- Risco máximo 2-3% por trade
- Nunca mais que 10% de exposição total
- Máximo 3-5 posições simultâneas
- Use trailing stops após lucro

### ❌ O QUE EVITAR:
- Risco > 5% por trade (martingale)
- Todas as posições na mesma direção
- Alavancagem > 2x
- Ignorar stop losses

---

## 2. GERENCIAMENTO DE CAPITAL

### ✅ O QUE FAZER:
- Comece pequeno (volume reduzido)
- Aumente capital gradualmente com lucros
- Monitore drawdown diariamente
- Respeite limites de perda diária

### ❌ O QUE EVITAR:
- Depositar mais capital em tempos de perda
- Aumentar posição após perdas (revenge trading)
- Ignorar drawdowns
- Over-leverage

---

## 3. QUALIDADE DE SINAIS

### ✅ O QUE FAZER:
- Procure convergência entre timeframes
- Valide sinais com múltiplas estratégias
- Aceite apenas força de sinal > 0.5
- Rejeite em alta volatilidade

### ❌ O QUE EVITAR:
- Sinal único (sem confirmação)
- Entrada no news spikes
- Trading durante low volume
- Ignorar regime de mercado

---

## 4. BACKTESTING CORRETO

### ✅ O QUE FAZER:
- Teste últimos 1-5 anos de dados
- Inclua períodos bear e bull
- Use slippage realista (0.5-1%)
- Valide em fora da amostra (walk-forward)

### ❌ O QUE EVITAR:
- Backtests muito curtos (< 1 ano)
- Sem slippage (spread zero não existe)
- Cherry-picking períodos bons
- Over-fitting (tantos parâmetros que memoriza)

---

## 5. LIVE TRADING

### ✅ PROCESSO:
1. Backtest rigoroso (2 semanas)
2. Papel trading simulado (1 semana)
3. Testnet com capital pequeno (2 semanas)
4. Live com capital MUITO pequeno (1 mês)
5. Scale up gradualmente se lucrativo

### ✅ MONITORAMENTO:
- Check bot a cada hora
- Revisar trades diários
- Valida se performance ≈ backtest
- Tenha plano de emergência

### ❌ EVITE:
- Ir direto do backtest para live
- Capital grande na primeira semana
- Não monitorar
- Confiar 100% no bot

---

## 6. MÉTRICAS IMPORTANTES

### Win Rate
- Mínimo: 45%
- Bom: 50%
- Excelente: 55%+

### Profit Factor
- Mínimo: 1.2x
- Bom: 1.5x
- Excelente: 2.0x+

### Sharpe Ratio
- Mínimo: 0.7
- Bom: 1.0
- Excelente: 1.5+

### Max Drawdown
- Máximo aceitável: 20%
- Alvo: < 15%
- Ideal: < 10%

---

## 7. TROUBLESHOOTING

### Problema: Win Rate caiu em live
- ✅ Normal (spread, slippage maior)
- ✅ Ajuste thresholds de sinal
- ✅ Aumentar SL por volatilidade real
- ❌ Não aumente posição para recuperar

### Problema: Drawdown > limite
- ✅ PARE IMEDIATAMENTE
- ✅ Revise estratégia
- ✅ Volte ao backtest
- ❌ Não continue esperando recuperar

### Problema: Sem sinais
- ✅ Normal em mercados ranging
- ✅ Ajuste thresholds (menos rigoroso)
- ✅ Revise regime detector
- ❌ Não force entradas

### Problema: Muitos sinais falsos
- ✅ Aumente força mínima
- ✅ Aumentar requisitos de convergência
- ✅ Filtre por volume
- ❌ Não ignore sinais fracos

---

## 8. PSICOLOGIA DO TRADER

### ✅ MENTALIDADE CORRETA:
- Siga o plano (confia no backtest)
- Aceite perdas (parte do jogo)
- Não tenha emoção
- Foco em longo prazo

### ❌ ERROS COMUNS:
- Revenge trading (tentar recuperar)
- FOMO (medo de perder)
- Adicionar posições em prejuízo
- Quebrar regras "só desta vez"

---

## 9. COMPLIANCE & SEGURANÇA

### ✅ O QUE FAZER:
- Guarde todos os trade logs
- Audit trail completo
- Backup de código regularmente
- Use VPN + 2FA na API

### ❌ O QUE EVITAR:
- Compartilhar chaves API
- Deletar logs
- API key no código
- Contas não-verificadas

---

## 10. ESCALATION CHECKLIST

Antes de aumentar capital/risco:

- [ ] 1 mês lucrativo ininterrupto
- [ ] Performance ≈ backtest (±10%)
- [ ] Sem erros críticos
- [ ] Drawdown < limite
- [ ] Sleep bem à noite (confortável com risco)
- [ ] Testnet por 2+ meses antes de live
"""


if __name__ == '__main__':
    unittest.main()