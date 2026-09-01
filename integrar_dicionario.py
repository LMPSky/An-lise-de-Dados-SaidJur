import csv
import yaml

# Caminhos dos arquivos
CSV_PATH = 'C:/Users/lucas.paim/Desktop/dicionario_prazos.csv'
YAML_PATH = 'D:/SaidJur/dicionarios.yaml'  # Altere para o nome real do seu YAML

# 1. Carrega os dados extraídos do CSV
novos_prazos = {}
with open(CSV_PATH, mode='r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Garante a conversão do ID para string ou inteiro conforme o padrão
        novos_prazos[int(row['ID'])] = row['Descrição']

# 2. Carrega o YAML existente
try:
    with open(YAML_PATH, mode='r', encoding='utf-8') as f:
        dicionario = yaml.safe_load(f) or {}
except FileNotFoundError:
    dicionario = {}

# 3. Integra na estrutura (Ajuste o caminho da chave se necessário)
if 'prazotype' not in dicionario:
    dicionario['prazotype'] = {}

# Atualiza com as centenas de novos itens
dicionario['prazotype'].update(novos_prazos)

# 4. Salva o dicionário atualizado
with open(YAML_PATH, mode='w', encoding='utf-8') as f:
    yaml.dump(dicionario, f, allow_unicode=True, sort_keys=False)

print("✅ Integração concluída com sucesso no arquivo YAML!")