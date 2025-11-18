"""
Script rápido para validar se as correções funcionam
Execute: python quick_test.py
"""

from decimal import Decimal
from datetime import datetime, timedelta
from loguru import logger
import pandas as pd
import numpy as np

logger.add("data/logs/quick_test.log", rotation="1 day")

def test_strategies():
    """Testa se todas as estratégias carregam sem erro"""
    print("=" * 60)
    print("TESTANDO CARREGAMENTO DAS ESTRATÉGIAS")
    print("=" * 60)
    
    try:
        from strategies.indicators.rsi_strategy import RSIStrategy
        from strategies.indicators.ema_crossover import EMACrossover
        from strategies.indicators.bollinger_bands import BollingerBandsStrategy
        from strategies.indicators.vwap_strategy import VWAPStrategy
        from strategies.indicators.order_flow import OrderFlowStrategy
        from strategies.scalping_ensemble import ScalpingEnsemble
        from strategies.smart_scalping_ensemble import SmartScalpingEnsemble
        
        print("✅ Todas as estratégias importadas com sucesso")
        return True
    except Exception as e:
        print(f"❌ Erro ao importar estratégias: {e}")
        logger.error(f"Import error: {e}")
        return False

def test_signal_generation():
    """Testa geração de sinais em dados artificiais"""
    print("\n" + "=" * 60)
    print("TESTANDO GERAÇÃO DE SINAIS")
    print("=" * 60)
    
    try:
        from strategies.smart_scalping_ensemble import SmartScalpingEnsemble
        
        # Cria dados artificiais
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=200, freq='5min')
        
        # Trend de alta
        prices = np.linspace(40000, 41000, 200) + np.random.normal(0, 50, 200)
        
        df = pd.DataFrame({
            'open': prices,
            'high': prices + 100,
            'low': prices - 100,
            'close': prices,
            'volume': np.random.uniform(100, 500, 200)
        }, index=dates)
        
        # Cria timeframes
        df_5m = df.copy()
        df_15m = df[::3].copy()  # A cada 3 candles
        
        strategy = SmartScalpingEnsemble()
        
        # Testa sinal
        side, strength, details = strategy.get_ensemble_signal(df_5m, df_15m)
        
        print(f"✅ Sinal gerado: {side} | Força: {strength:.3f}")
        print(f"   - Buy score: {details['buy_score']:.3f}")
        print(f"   - Sell score: {details['sell_score']:.3f}")
        print(f"   - Acordos 5m: BUY={details['buy_agreements_5m']} SELL={details['sell_agreements_5m']}")
        print(f"   - Acordos 15m: BUY={details['buy_agreements_15m']} SELL={details['sell_agreements_15m']}")
        
        return True
    except Exception as e:
        print(f"❌ Erro ao gerar sinal: {e}")
        logger.error(f"Signal generation error: {e}", exc_info=True)
        return False

def test_stop_loss_tp_calculation():
    """Testa cálculo de SL e TP"""
    print("\n" + "=" * 60)
    print("TESTANDO CÁLCULO DE STOP LOSS E TAKE PROFIT")
    print("=" * 60)
    
    try:
        from strategies.smart_scalping_ensemble import SmartScalpingEnsemble
        
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=100, freq='5min')
        prices = np.linspace(40000, 41000, 100)
        
        df = pd.DataFrame({
            'open': prices,
            'high': prices + 100,
            'low': prices - 100,
            'close': prices,
            'volume': np.random.uniform(100, 500, 100)
        }, index=dates)
        
        strategy = SmartScalpingEnsemble()
        
        entry_price = Decimal('40500')
        
        # Testa BUY
        sl_buy = strategy.calculate_stop_loss(df, entry_price, 'BUY')
        tp_buy = strategy.calculate_take_profit(df, entry_price, 'BUY')
        
        print(f"✅ BUY - Entry: ${entry_price}")
        print(f"   SL: ${sl_buy:.2f} (distância: {(entry_price - sl_buy):.2f})")
        print(f"   TP: ${tp_buy:.2f} (distância: {(tp_buy - entry_price):.2f})")
        
        # Valida
        assert sl_buy < entry_price, "SL deve ser menor que entry no BUY"
        assert tp_buy > entry_price, "TP deve ser maior que entry no BUY"
        
        # Testa SELL
        sl_sell = strategy.calculate_stop_loss(df, entry_price, 'SELL')
        tp_sell = strategy.calculate_take_profit(df, entry_price, 'SELL')
        
        print(f"\n✅ SELL - Entry: ${entry_price}")
        print(f"   SL: ${sl_sell:.2f} (distância: {(sl_sell - entry_price):.2f})")
        print(f"   TP: ${tp_sell:.2f} (distância: {(entry_price - tp_sell):.2f})")
        
        assert sl_sell > entry_price, "SL deve ser maior que entry no SELL"
        assert tp_sell < entry_price, "TP deve ser menor que entry no SELL"
        
        # Calcula R:R
        risk_buy = entry_price - sl_buy
        reward_buy = tp_buy - entry_price
        rr_buy = reward_buy / risk_buy
        
        print(f"\n✅ R:R - {rr_buy:.2f}:1")
        
        return True
    except Exception as e:
        print(f"❌ Erro ao calcular SL/TP: {e}")
        logger.error(f"SL/TP calculation error: {e}", exc_info=True)
        return False

def main():
    print("\n")
    print("🧪 TESTE RÁPIDO DO SISTEMA DE SCALPING CORRIGIDO")
    print("=" * 60)
    
    results = {
        'Carregamento': test_strategies(),
        'Geração de Sinais': test_signal_generation(),
        'SL/TP': test_stop_loss_tp_calculation()
    }
    
    print("\n" + "=" * 60)
    print("RESUMO DOS TESTES")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ PASSOU" if passed else "❌ FALHOU"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ TODOS OS TESTES PASSARAM!")
        print("\nAgora execute: python backtest_runner.py")
        print("Espere ver trades LUCROSOS! 💰")
    else:
        print("❌ ALGUNS TESTES FALHARAM")
        print("Verifique os logs em data/logs/quick_test.log")
    print("=" * 60 + "\n")

if __name__ == '__main__':
    main()