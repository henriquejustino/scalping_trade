import os
from dotenv import load_dotenv

load_dotenv()

class APIKeys:
    @staticmethod
    def get_binance_keys(environment='testnet'):
        if environment == 'testnet':
            return {
                'api_key': os.getenv('BINANCE_TESTNET_API_KEY'),
                'api_secret': os.getenv('BINANCE_TESTNET_API_SECRET')
            }
        elif environment == 'live':
            return {
                'api_key': os.getenv('BINANCE_LIVE_API_KEY'),
                'api_secret': os.getenv('BINANCE_LIVE_API_SECRET')
            }
        else:
            return {'api_key': '', 'api_secret': ''}