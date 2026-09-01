import pandas as pd
import yaml

# 1. Caminho do seu arquivo Excel com o De/Para
ARQUIVO_EXCEL = "D:/SaidJur/prazos_traduzidos.xlsx"  # Altere para o nome real do seu Excel
ARQUIVO_YAML_SAIDA = "d:/SaidJur/dicionario_traducoes.yaml"

# Nomes exatos das colunas no seu Excel
COLUNA_DE = "prazo"           # Coluna com o texto original
COLUNA_PARA = "prazo_traduzido" # Coluna com o texto novo

def converter_excel_para_yaml():
    try:
        print("📖 Lendo planilha Excel...")
        df = pd.read_excel(ARQUIVO_EXCEL)

        # Remove linhas em branco e duplicadas
        df = df.dropna(subset=[COLUNA_DE, COLUNA_PARA])
        
        # Cria o dicionário { "TEXTO_ANTIGO": "TEXTO_NOVO" }
        dicionario = dict(zip(df[COLUNA_DE].astype(str), df[COLUNA_PARA].astype(str)))

        # Salva em formato YAML
        print(f"💾 Gerando {ARQUIVO_YAML_SAIDA}...")
        with open(ARQUIVO_YAML_SAIDA, "w", encoding="utf-8") as file:
            yaml.dump(dicionario, file, allow_unicode=True, default_flow_style=False, sort_keys=False)

        print(f"🎉 Sucesso! {len(dicionario)} mapeamentos salvos no YAML.")

    except Exception as e:
        print(f"❌ Erro ao converter: {e}")

if __name__ == "__main__":
    converter_excel_para_yaml()