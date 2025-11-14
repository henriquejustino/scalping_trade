from decimal import Decimal, ROUND_DOWN
from typing import Optional
import time
from loguru import logger

def round_down(value: Decimal, step: Decimal) -> Decimal:
    """Round down to nearest step size"""
    if step == 0:
        return value
    return (value // step) * step

def round_price(value: Decimal, tick_size: Decimal) -> Decimal:
    """Round price to tick size"""
    if tick_size == 0:
        return value
    return (value / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size

def retry_on_failure(max_retries=3, delay=1):
    """Decorator para retry em falhas"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    logger.warning(f"Tentativa {attempt + 1} falhou: {e}. Retentando...")
                    time.sleep(delay * (attempt + 1))
        return wrapper
    return decorator

def calculate_percentage_change(old_value: Decimal, new_value: Decimal) -> Decimal:
    """Calcula mudança percentual"""
    if old_value == 0:
        return Decimal('0')
    return ((new_value - old_value) / old_value) * Decimal('100')