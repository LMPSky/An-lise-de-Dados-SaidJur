import yaml

with open("relatorio_investigacao_colunas.yaml", encoding="utf-8") as f:
    d = yaml.safe_load(f)

bools = [i for i in d["investigacoes"] if i.get("provavel_booleano")]
for i in bools:
    print(f"{i['tabela']}.{i['coluna']}")

print(f"\nTotal: {len(bools)}")