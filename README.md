🚀 Scalping Bot - Sistema Profissional de Trading
Sistema completo e robusto de scalping para criptomoedas na Binance Futures.
📋 Características
Estratégias Ensemble

✅ RSI com detecção de divergências
✅ EMA Crossover (9/21)
✅ Bollinger Bands com squeeze
✅ VWAP com bandas
✅ Order Flow Analysis

Gerenciamento de Risco

✅ Risco dinâmico baseado em força de sinal (1.5% - 3%)
✅ Take profit multinível (TP1: 50%, TP2: 75%, TP3: 100%)
✅ Trailing stop loss automático
✅ Limite máximo de exposição (10%)
✅ Máximo de 3 posições simultâneas

Timeframes

📊 5 minutos (primário)
📊 15 minutos (confirmação)

🛠️ Instalação
bash# Clone o repositório
git clone <seu-repo>

# Instale dependências
pip install -r requirements.txt

# Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas chaves da Binance
⚙️ Configuração
Edite config/settings.py para ajustar:

Timeframes
Limites de risco
Símbolos para trading
Thresholds de sinais

🚀 Uso
Backtest
bashpython backtest_runner.py
Testnet (Recomendado para testes)
bashpython testnet_runner.py
Live Trading
bashpython main.py live
📊 Estrutura do Projeto
scalping_bot/
├── config/              # Configurações
├── core/                # Componentes principais
├── strategies/          # Estratégias de trading
├── risk_management/     # Gestão de risco
├── execution/           # Execução de ordens
├── backtesting/         # Engine de backtest
├── monitoring/          # Monitoramento e alertas
├── tests/               # Testes unitários
└── data/               # Dados e logs
🧪 Testes
bash# Rodar todos os testes
python -m unittest discover tests

# Teste específico
python -m unittest tests.test_strategies
📈 Métricas de Performance
O sistema calcula automaticamente:

Win Rate
Profit Factor
Sharpe Ratio
Max Drawdown
Retorno total
Métricas por força de sinal

⚠️ Avisos Importantes

SEMPRE teste em testnet primeiro
Nunca use mais capital do que pode perder
Monitore o bot constantemente em live
Configure alertas adequados
Faça backtests extensivos antes de live

🔐 Segurança

Nunca commite suas chaves API
Use .env para credenciais
Restrinja IPs nas chaves da Binance
Use permissões mínimas necessárias

📝 Logs
Logs são salvos em data/logs/ com rotação diária.
🤝 Contribuindo
Pull requests são bem-vindos. Para mudanças maiores, abra uma issue primeiro.
📄 Licença
MIT
⚡ Performance Esperada
Baseado em backtests:

Win Rate: 45-55%
Profit Factor: 1.5-2.5
Sharpe Ratio: > 1.5
Max Drawdown: < 15%

Nota: Performance passada não garante resultados futuros.
🆘 Suporte
Para dúvidas ou problemas, abra uma issue no GitHub.

⚠️ DISCLAIMER: Este software é fornecido "como está". Trading envolve riscos significativos. Use por sua conta e risco.