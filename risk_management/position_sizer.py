"""
Position Sizer V2 - Dimensionamento Robusto com Validações
Correções:
1. Volume é FATOR DE RISCO, não rejeição binária
2. Risco dinâmico por força de sinal
3. Limites rigorosos de posição
"""
from decimal import Decimal
from typing import Optional, Dict
from loguru import logger
from config.settings import settings
from core.utils import round_down

class PositionSizerV2:
    """Dimensionador de posição robusto e adaptativo"""
    
    def __init__(self):
        self.settings = settings
        self.trade_history = []  # Para learning futuro
    
    def calculate_dynamic_position_size(
        self,
        capital: Decimal,
        entry_price: Decimal,
        stop_loss_price: Decimal,
        symbol_filters: dict,
        signal_strength: float,
        volume_ratio: float = 1.0,
        regime: str = "RANGING"
    ) -> Optional[Decimal]:
        """
        Calcula tamanho da posição com múltiplos fatores:
        - Risco dinâmico baseado em força de sinal
        - Ajuste de risco por volume (não rejeição!)
        - Limite por regime de mercado
        - Validações rigorosas
        """
        
        # === 1. VALIDAÇÃO BÁSICA ===
        if capital <= 0 or entry_price <= 0 or stop_loss_price == entry_price:
            logger.error(f"Parâmetros inválidos: capital={capital}, entry={entry_price}, sl={stop_loss_price}")
            return None
        
        # === 2. RISCO DINÂMICO POR FORÇA DE SINAL ===
        risk_multiplier = self._get_risk_multiplier(signal_strength, volume_ratio, regime)
        dynamic_risk = settings.BASE_RISK_PER_TRADE * risk_multiplier
        
        # Limita ao máximo
        dynamic_risk = min(dynamic_risk, settings.MAX_RISK_PER_TRADE)
        dynamic_risk = max(dynamic_risk, settings.MIN_RISK_PER_TRADE)
        
        logger.debug(
            f"Risco dinâmico: {float(dynamic_risk)*100:.2f}% "
            f"(força={signal_strength:.2f}, vol={volume_ratio:.2f}, regime={regime})"
        )
        
        # === 3. CALCULA POSIÇÃO ===
        stop_loss_distance = abs(entry_price - stop_loss_price)
        
        # Distância em % do preço
        sl_distance_pct = stop_loss_distance / entry_price
        
        # Risco em dólares
        risk_amount = capital * dynamic_risk
        
        # Quantidade = Risco em $ / Distância do SL em $
        position_size_usd = risk_amount / stop_loss_distance
        quantity = position_size_usd / entry_price
        
        # === 4. ARREDONDA PARA STEP SIZE ===
        quantity = round_down(quantity, symbol_filters['stepSize'])
        
        if quantity < symbol_filters['minQty']:
            logger.debug(
                f"Quantidade {quantity} abaixo do mínimo {symbol_filters['minQty']}"
            )
            return None
        
        # === 5. VALIDA NOTIONAL ===
        notional = quantity * entry_price
        if notional < symbol_filters['minNotional']:
            logger.debug(
                f"Notional {notional} abaixo do mínimo {symbol_filters['minNotional']}"
            )
            return None
        
        # === 6. LIMITES DE POSIÇÃO ===
        position_value = quantity * entry_price
        
        if position_value < settings.MIN_POSITION_SIZE_USD:
            logger.debug(
                f"Valor ${position_value:.2f} abaixo do mínimo ${settings.MIN_POSITION_SIZE_USD}"
            )
            return None
        
        if position_value > settings.MAX_POSITION_SIZE_USD:
            max_quantity = settings.MAX_POSITION_SIZE_USD / entry_price
            quantity = round_down(max_quantity, symbol_filters['stepSize'])
            logger.info(f"Posição ajustada ao máximo: {quantity}")
        
        # === 7. LOG ===
        logger.info(
            f"✅ Posição calculada:\n"
            f"   Quantidade: {quantity:.6f}\n"
            f"   Valor: ${position_value:.2f}\n"
            f"   Risco: {float(dynamic_risk)*100:.2f}%\n"
            f"   SL Distance: {float(sl_distance_pct)*100:.3f}%\n"
            f"   Volume Ratio: {volume_ratio:.2f}x"
        )
        
        return quantity
    
    def _get_risk_multiplier(
        self,
        signal_strength: float,
        volume_ratio: float,
        regime: str
    ) -> Decimal:
        """
        ✅ NOVO: Calcula multiplicador de risco dinâmico
        Baseado em 3 fatores: força de sinal, volume, regime
        """
        
        base_multiplier = Decimal('1.0')
        
        # === AJUSTE POR FORÇA DE SINAL ===
        if signal_strength >= 0.8:
            base_multiplier *= Decimal('1.5')  # 3% risco
            logger.debug(f"Bônus sinal MUITO FORTE: x1.5")
        elif signal_strength >= 0.6:
            base_multiplier *= Decimal('1.25')  # 2.5% risco
            logger.debug(f"Bônus sinal FORTE: x1.25")
        elif signal_strength >= 0.4:
            base_multiplier *= Decimal('1.0')  # 2% risco (padrão)
        else:
            base_multiplier *= Decimal('0.75')  # 1.5% risco
            logger.debug(f"Penalidade sinal FRACO: x0.75")
        
        # === AJUSTE POR VOLUME ===
        # Volume BAIXO = penalidade, não rejeição!
        if volume_ratio >= 1.5:
            base_multiplier *= Decimal('1.15')  # Bonus volume alto
            logger.debug(f"Bônus volume alto: x1.15")
        elif volume_ratio >= 1.2:
            base_multiplier *= Decimal('1.1')
        elif volume_ratio >= 0.8:
            base_multiplier *= Decimal('1.0')  # OK
        elif volume_ratio >= 0.5:
            base_multiplier *= Decimal('0.8')  # Penalidade moderada
            logger.debug(f"Penalidade volume baixo: x0.8")
        else:
            base_multiplier *= Decimal('0.6')  # Penalidade severa
            logger.debug(f"Penalidade volume muito baixo: x0.6")
        
        # === AJUSTE POR REGIME ===
        if regime == "TRENDING_UP" or regime == "TRENDING_DOWN":
            base_multiplier *= Decimal('1.1')  # 10% bonus em tendência
            logger.debug(f"Bônus em tendência: x1.1")
        elif regime == "HIGH_VOLATILITY":
            base_multiplier *= Decimal('0.8')  # 20% penalidade em alta vol
            logger.debug(f"Penalidade alta volatilidade: x0.8")
        elif regime == "BREAKOUT_FORMING":
            base_multiplier *= Decimal('0.7')  # 30% penalidade (incerto)
            logger.debug(f"Penalidade breakout forming: x0.7")
        
        return base_multiplier
    
    def validate_position_size(
        self,
        quantity: Decimal,
        entry_price: Decimal,
        symbol_filters: dict
    ) -> Tuple[bool, str]:
        """Valida se posição está dentro de limites"""
        
        # Quantidade mínima
        if quantity < symbol_filters['minQty']:
            return False, f"Quantidade {quantity} < mínimo {symbol_filters['minQty']}"
        
        # Notional mínimo
        notional = quantity * entry_price
        if notional < symbol_filters['minNotional']:
            return False, f"Notional {notional} < mínimo {symbol_filters['minNotional']}"
        
        # Limites de posição
        position_value = quantity * entry_price
        
        if position_value < settings.MIN_POSITION_SIZE_USD:
            return False, f"Valor ${position_value} < mínimo ${settings.MIN_POSITION_SIZE_USD}"
        
        if position_value > settings.MAX_POSITION_SIZE_USD:
            return False, f"Valor ${position_value} > máximo ${settings.MAX_POSITION_SIZE_USD}"
        
        return True, "OK"
    
    def calculate_kelly_position_size(
        self,
        capital: Decimal,
        win_rate: float,
        avg_win: Decimal,
        avg_loss: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal
    ) -> Optional[Decimal]:
        """
        ✅ NOVO: Calcula posição usando Critério de Kelly
        Kelly % = (win_rate * avg_win - loss_rate * avg_loss) / avg_win
        
        Mais sofisticado, mas requer histórico de trades
        """
        
        if win_rate <= 0 or win_rate >= 1:
            return None
        
        loss_rate = 1 - win_rate
        
        # W/L ratio (reward/risk)
        avg_win_abs = abs(avg_win)
        avg_loss_abs = abs(avg_loss)
        
        if avg_loss_abs == 0:
            return None
        
        wl_ratio = avg_win_abs / avg_loss_abs
        
        # Kelly %
        kelly_pct = (win_rate * wl_ratio - loss_rate) / wl_ratio
        
        # Limita Kelly a máximo 25% (1/4 Kelly é mais conservador)
        kelly_pct = min(kelly_pct, Decimal('0.25'))
        kelly_pct = max(kelly_pct, Decimal('0.01'))
        
        # Posição = Kelly% * Capital / SL Distance
        sl_distance = abs(entry_price - stop_loss)
        quantity = (kelly_pct * capital) / (entry_price * sl_distance)
        
        logger.info(
            f"Kelly Position: {kelly_pct:.4f} Kelly = "
            f"{quantity:.6f} lots (w.rate={win_rate:.2%})"
        )
        
        return quantity
    
    def calculate_volatility_adjusted_size(
        self,
        quantity: Decimal,
        atr: Decimal,
        atr_historical_avg: Decimal
    ) -> Decimal:
        """
        ✅ NOVO: Ajusta posição por volatilidade
        High volatility = menor posição
        Low volatility = maior posição
        """
        
        if atr_historical_avg == 0:
            return quantity
        
        volatility_ratio = atr / atr_historical_avg
        
        # Limita ajuste
        if volatility_ratio > 2.0:
            adjusted = quantity * Decimal('0.6')  # Corta 40% em muito alta vol
            logger.info(f"Posição reduzida por volatilidade: {volatility_ratio:.2f}x")
        elif volatility_ratio > 1.5:
            adjusted = quantity * Decimal('0.8')
        elif volatility_ratio < 0.5:
            adjusted = quantity * Decimal('1.2')  # Aumenta 20% em baixa vol
        else:
            adjusted = quantity
        
        return adjusted