import os
import pandas as pd
import yaml
from sqlalchemy import create_engine
from urllib.parse import quote_plus

# ==========================================
# 1. CONFIGURAÇÕES DE CONEXÃO
# ==========================================
USUARIO = "root"
SENHA = "Acd9854Yui2026!"  # Substitua pela sua senha do MySQL
HOST = "127.0.0.1"
PORTA = "3306"
BANCO = "saidjur"

# quote_plus garante tratamento correto para caracteres especiais na senha
senha_codificada = quote_plus(SENHA)
DATABASE_URI = f"mysql+pymysql://{USUARIO}:{senha_codificada}@{HOST}:{PORTA}/{BANCO}"

# Caminho do dicionário de tradução
CAMINHO_YAML = "d:/SaidJur/dicionarios.yaml"  # Ajuste o nome/caminho se necessário
ARQUIVO_SAIDA = "d:/SaidJur/prazos_traduzidos.xlsx"

# ==========================================
# 2. CONSULTA SQL (Estrutura Real da Tabela)
# ==========================================
QUERY_SQL = """
    SELECT 
        id,
        prazo,
        adm,
        code_red,
        inserted_for_jurify,
        automatic,
        created_at,
        created_at_userid,
        updated_at,
        updated_at_userid
    FROM prazos
"""

# ==========================================
# 3. ALGORITMO DE TRADUÇÃO E PROCESSAMENTO
# ==========================================
def executar_traducao_sql():
    try:
        # Carregar Dicionário YAML
        print("📖 Carregando dicionário YAML...")
        if not os.path.exists(CAMINHO_YAML):
            print(f"⚠️ Arquivo YAML não encontrado em: {CAMINHO_YAML}")
            print("Por favor, crie o arquivo YAML com os de/para antes de continuar.")
            return

        with open(CAMINHO_YAML, "r", encoding="utf-8") as file:
            dicionario = yaml.safe_load(file) or {}

        # Conectar ao Banco e Ler Dados
        print("🔌 Conectando ao banco de dados MySQL...")
        engine = create_engine(DATABASE_URI)

        print("📊 Executando consulta SQL na tabela 'prazos'...")
        df = pd.read_sql_query(QUERY_SQL, con=engine)
        print(f"✅ {len(df)} registros carregados com sucesso!")

        # Traduzir Coluna 'prazo'
        print("🔄 Aplicando traduções na coluna 'prazo'...")
        
        # Cria uma nova coluna 'prazo_traduzido' mantendo a original intacta
        df["prazo_traduzido"] = df["prazo"].map(dicionario).fillna(df["prazo"])

        # Exibe prévia das alterações no terminal
        print("\n--- PRÉVIA DOS DADOS TRADUZIDOS ---")
        print(df[["id", "prazo", "prazo_traduzido"]].head(10))

        # Exportar para Excel
        print(f"\n💾 Salvando resultado em: {ARQUIVO_SAIDA}")
        df.to_excel(ARQUIVO_SAIDA, index=False)
        print("🎉 Processo concluído com sucesso!")

    except Exception as e:
        print(f"\n❌ Ocorreu um erro durante a execução: {e}")

if __name__ == "__main__":
    executar_traducao_sql()