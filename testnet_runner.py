from main import ScalpingBot
from loguru import logger

logger.add("data/logs/testnet_{time}.log", rotation="1 day")

if __name__ == '__main__':
    logger.info("🧪 Iniciando em TESTNET mode")
    
    bot = ScalpingBot(environment='testnet')
    bot.start()