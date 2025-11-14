import os
import sys
from pathlib import Path

def create_directory_structure():
    """Cria estrutura de diretórios"""
    directories = [
        'config',
        'core',
        'strategies/indicators',
        'risk_management',
        'execution',
        'backtesting',
        'monitoring',
        'tests',
        'data/historical',
        'data/live',
        'data/logs'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        
        # Cria __init__.py
        init_file = Path(directory) / '__init__.py'
        if not init_file.exists() and not directory.startswith('data'):
            init_file.touch()
    
    print("✅ Estrutura de diretórios criada")

def create_env_file():
    """Cria arquivo .env se não existir"""
    env_file = Path('.env')
    
    if env_file.exists():
        print("⚠️  Arquivo .env já existe")
        return
    
    env_content = """# Testnet Keys (obtenha em testnet.binancefuture.com)
BINANCE_TESTNET_API_KEY=your_testnet_api_key_here
BINANCE_TESTNET_API_SECRET=your_testnet_api_secret_here

# Live Keys (CUIDADO!)
BINANCE_LIVE_API_KEY=your_live_api_key_here
BINANCE_LIVE_API_SECRET=your_live_api_secret_here

# Environment
ENVIRONMENT=testnet

# Log Level
LOG_LEVEL=INFO
"""
    
    env_file.write_text(env_content)
    print("✅ Arquivo .env criado")
    print("⚠️  Configure suas chaves API no arquivo .env")

def check_dependencies():
    """Verifica dependências instaladas"""
    required = [
        'pandas',
        'numpy',
        'ta',
        'python-binance',
        'loguru',
        'python-dotenv'
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"⚠️  Dependências faltando: {', '.join(missing)}")
        print("Execute: pip install -r requirements.txt")
        return False
    else:
        print("✅ Todas as dependências instaladas")
        return True

def create_gitignore():
    """Cria .gitignore"""
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/

# Dados e logs
data/
*.log
*.csv
*.json

# Ambiente
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Backups
*.bak
"""
    
    Path('.gitignore').write_text(gitignore_content)
    print("✅ Arquivo .gitignore criado")

def main():
    print("=" * 60)
    print(" " * 15 + "SCALPING BOT SETUP")
    print("=" * 60)
    print()
    
    create_directory_structure()
    create_env_file()
    create_gitignore()
    
    print()
    dependencies_ok = check_dependencies()
    
    print()
    print("=" * 60)
    
    if dependencies_ok:
        print("✅ Setup completo!")
        print()
        print("Próximos passos:")
        print("1. Configure suas chaves API no arquivo .env")
        print("2. Execute: python backtest_runner.py (para testar)")
        print("3. Execute: python testnet_runner.py (para testnet)")
        print("4. Execute: python main.py live (CUIDADO - produção!)")
    else:
        print("⚠️  Instale as dependências primeiro:")
        print("pip install -r requirements.txt")
    
    print("=" * 60)

if __name__ == '__main__':
    main()