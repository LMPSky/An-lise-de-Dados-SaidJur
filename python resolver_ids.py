"""
Script utilitário para resolver IDs em registros legíveis.

Uso:
    python resolver_ids.py

Edite a lista CONSULTAS abaixo com (tabela_referenciada, coluna_id, valor_id)
e rode o script. Ele imprime a linha inteira da tabela referenciada para
cada ID, incluindo qualquer coluna de "nome"/"descrição" que exista,
para você confirmar visualmente o que aquele número representa.

Não faz nenhuma escrita no banco — apenas SELECTs.
"""

from __future__ import annotations

import pymysql

from src.config import CONFIG


# ── Edite aqui as consultas que você quer resolver ──────────────────────────
# Cada item é: (tabela, coluna_pk, valor_do_id)
CONSULTAS = [
    ("client_publication_search_terms", "client_id", 2267),          # "ID do Cliente = 2267"
    ("pedidos2lawsuit", "id", 27185),               # "ID do Processo = 27185" (pedidos2lawsuit)
    ("lawsuits", "id", 2332),                # "ID do Processo = 2332" (hearingcontrol)
    ("lawsuits", "id", 2325),                # "ID do Processo = 2325"
    ("lawsuits", "id", 5808),                # "ID do Processo = 5808"
    ("client_publication_search_terms", "id", 12),  # "ID do Termo de Busca = 12"
    # Adicione mais linhas conforme precisar, por exemplo:
    # ("employees", "emp_id", 426),          # "Responsável da Audiência = 426"
    # ("hearingtype", "hearingtype_id", 11), # "Tipo de Audiência = 11"
]


def _conectar() -> pymysql.connections.Connection:
    cfg = CONFIG.get("banco", {})
    return pymysql.connect(
        host=cfg.get("host", "127.0.0.1"),
        user=cfg.get("usuario", "root"),
        passwd=cfg.get("senha", "Acd9854Yui2026!"),
        database=cfg.get("nome", "saidjur"),
        port=int(cfg.get("porta", 3306)),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def _identificador(nome: str) -> str:
    return f"`{nome.replace('`', '``')}`"


def resolver(conn: pymysql.connections.Connection, tabela: str, coluna_pk: str, valor: int) -> None:
    """Busca e imprime a linha completa referenciada por um ID."""
    tabela_sql = _identificador(tabela)
    coluna_sql = _identificador(coluna_pk)

    sql = f"SELECT * FROM {tabela_sql} WHERE {coluna_sql} = %s LIMIT 1"

    print(f"\n{'=' * 70}")
    print(f"🔎 Tabela: {tabela}  |  {coluna_pk} = {valor}")
    print("=" * 70)

    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, (valor,))
            row = cursor.fetchone()
    except Exception as exc:
        print(f"❌ Erro ao consultar: {exc}")
        return

    if not row:
        print("⚠️  Nenhum registro encontrado com esse ID.")
        return

    # Imprime todas as colunas da linha encontrada.
    largura_max = max(len(k) for k in row.keys())
    for chave, valor_coluna in row.items():
        texto = "" if valor_coluna is None else str(valor_coluna)
        # Trunca valores muito longos para não poluir o console.
        if len(texto) > 200:
            texto = texto[:200] + "... (truncado)"
        print(f"  {chave.ljust(largura_max)} : {texto}")


def main() -> None:
    print("🔍 Resolvendo IDs configurados em CONSULTAS...")
    conn = _conectar()
    try:
        for tabela, coluna_pk, valor in CONSULTAS:
            resolver(conn, tabela, coluna_pk, valor)
    finally:
        conn.close()

    print(f"\n{'=' * 70}")
    print("✅ Concluído.")


if __name__ == "__main__":
    main()