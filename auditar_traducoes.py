"""Auditoria completa de traduções de colunas e ENUMs no banco MySQL real."""

from __future__ import annotations

from datetime import UTC, datetime
import re
import unicodedata
from typing import Any

import pymysql
import yaml

from src.config import CONFIG
from src.dicionarios import dicionario_de_coluna
from src.traducoes_colunas import TRADUCOES_COLUNAS, traduzir_nome_coluna

ARQUIVO_RELATORIO = "relatorio_auditoria_traducoes.yaml"
LIMITE_AMOSTRA_ENUM = 51
MAX_VALORES_ENUM = 20

_TIPOS_TEXTUAIS = frozenset({"char", "varchar", "tinytext", "text", "enum", "set"})
_TERMOS_INGLES_COMUNS = frozenset(
    {
        "active",
        "all",
        "closed",
        "created",
        "deleted",
        "disabled",
        "done",
        "employee",
        "file",
        "name",
        "none",
        "open",
        "path",
        "pending",
        "reason",
        "search",
        "state",
        "status",
        "term",
        "type",
        "updated",
        "user",
    }
)


def _normalizar_texto(texto: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(ch) != "Mn"
    )


def _tokenizar(texto: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _normalizar_texto(texto))


def _traducao_basica_do_nome(nome_coluna: str) -> str:
    partes = []
    for parte in nome_coluna.lower().split("_"):
        if parte == "id":
            partes.append("ID")
        else:
            partes.append(parte.capitalize())
    return " ".join(partes)


def classificar_traducao_coluna(nome_coluna: str, traducao: str | None = None) -> str:
    """Classifica qualidade da tradução de um nome de coluna."""
    if not nome_coluna:
        return "nao_traduzido"

    nome_coluna = nome_coluna.lower()
    traducao_atual = (traducao or traduzir_nome_coluna(nome_coluna) or "").strip()

    # Entradas explícitas no dicionário canônico são tratadas como traduzidas.
    if nome_coluna in TRADUCOES_COLUNAS:
        return "traduzido_corretamente"

    if _normalizar_texto(traducao_atual) == _normalizar_texto(_traducao_basica_do_nome(nome_coluna)):
        return "nao_traduzido"

    partes_originais = [p for p in _tokenizar(nome_coluna.replace("_", " ")) if p not in {"id"}]
    tokens_traducao = set(_tokenizar(traducao_atual))
    if any(parte in tokens_traducao for parte in partes_originais):
        return "parcialmente_traduzido"

    if any(token in _TERMOS_INGLES_COMUNS for token in tokens_traducao):
        return "parcialmente_traduzido"

    return "traduzido_corretamente"


def traducao_pendente_placeholder(valor_original: str, traducao: str | None) -> bool:
    """Retorna True quando a tradução é placeholder do tipo [valor]."""
    if traducao is None:
        return False
    traducao_limpa = str(traducao).strip()
    if not traducao_limpa:
        return False
    if traducao_limpa == f"[{valor_original}]":
        return True
    return bool(re.fullmatch(r"\[.+\]", traducao_limpa))


def traducao_parece_ingles(traducao: str | None) -> bool:
    """Heurística simples para detectar traduções ainda em inglês."""
    if traducao is None:
        return False
    tokens = _tokenizar(str(traducao))
    if not tokens:
        return False
    return any(token in _TERMOS_INGLES_COMUNS for token in tokens)


def avaliar_pendencias_enum(
    valores_amostra: list[str], dicionario_coluna: dict[str, str]
) -> list[dict[str, str]]:
    """Identifica pendências de tradução para valores de ENUM/código."""
    pendencias: list[dict[str, str]] = []
    for valor in valores_amostra:
        traducao = dicionario_coluna.get(valor)
        if traducao is None:
            pendencias.append(
                {
                    "valor": valor,
                    "traducao_atual": "",
                    "motivo": "sem_entrada_no_dicionario",
                }
            )
            continue

        if traducao_pendente_placeholder(valor, traducao):
            pendencias.append(
                {
                    "valor": valor,
                    "traducao_atual": str(traducao),
                    "motivo": "placeholder_pendente",
                }
            )
            continue

        if traducao_parece_ingles(traducao):
            pendencias.append(
                {
                    "valor": valor,
                    "traducao_atual": str(traducao),
                    "motivo": "traducao_possivelmente_em_ingles",
                }
            )

    return pendencias


def _identificador(nome: str) -> str:
    return f"`{nome.replace('`', '``')}`"


def _coletar_tabelas(conn: pymysql.connections.Connection, schema: str) -> list[str]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT TABLE_NAME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME
            """,
            (schema,),
        )
        return [str(row[0]) for row in cursor.fetchall()]


def _coletar_colunas(
    conn: pymysql.connections.Connection, schema: str, tabela: str
) -> list[tuple[str, str]]:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (schema, tabela),
        )
        return [(str(nome), str(tipo).lower()) for nome, tipo in cursor.fetchall()]


def _coletar_amostra_valores(
    conn: pymysql.connections.Connection, tabela: str, coluna: str
) -> list[str]:
    tabela_sql = _identificador(tabela)
    coluna_sql = _identificador(coluna)
    sql = (
        f"SELECT DISTINCT {coluna_sql} "
        f"FROM {tabela_sql} "
        f"WHERE {coluna_sql} IS NOT NULL "
        f"LIMIT {LIMITE_AMOSTRA_ENUM}"
    )
    with conn.cursor() as cursor:
        cursor.execute(sql)
        valores = []
        for row in cursor.fetchall():
            valor = row[0]
            if valor is None:
                continue
            texto = str(valor).strip()
            if texto:
                valores.append(texto)
        return valores


def _coluna_candidata_enum(coluna: str, tipo_dado: str) -> bool:
    if tipo_dado not in _TIPOS_TEXTUAIS:
        return False
    nome = coluna.lower()
    chaves = ("type", "tipo", "status", "nature", "natureza", "code", "codigo", "phase", "fase")
    return any(chave in nome for chave in chaves)


def _conectar_mysql() -> pymysql.connections.Connection:
    cfg = CONFIG.get("banco", {})
    return pymysql.connect(
        host=cfg.get("host", "127.0.0.1"),
        user=cfg.get("usuario", "root"),
        passwd=cfg.get("senha", ""),
        database=cfg.get("nome", "saidjur"),
        port=int(cfg.get("porta", 3306)),
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=10,
        read_timeout=60,
        write_timeout=60,
    )


def auditar_traducoes() -> dict[str, Any]:
    """Executa auditoria completa e retorna o relatório em memória."""
    resumo = {
        "tabelas_analisadas": 0,
        "colunas_total": 0,
        "colunas_traduzidas": 0,
        "colunas_parcialmente_traduzidas": 0,
        "colunas_nao_traduzidas": 0,
        "placeholders_enum_pendentes": 0,
        "valores_enum_sem_dicionario": 0,
        "valores_enum_possivelmente_ingles": 0,
        "tabelas_com_erro": 0,
    }

    relatorio: dict[str, Any] = {
        "gerado_em_utc": datetime.now(UTC).isoformat(),
        "banco": CONFIG.get("banco", {}).get("nome", "saidjur"),
        "resumo": resumo,
        "pendencias": {},
    }

    conn = _conectar_mysql()
    schema = CONFIG.get("banco", {}).get("nome", "saidjur")

    try:
        tabelas = _coletar_tabelas(conn, schema)
        for indice, tabela in enumerate(tabelas, start=1):
            print(f"[{indice}/{len(tabelas)}] 🔎 Auditando tabela: {tabela}")
            resumo["tabelas_analisadas"] += 1

            try:
                colunas = _coletar_colunas(conn, schema, tabela)
                pendencias_coluna: list[dict[str, str]] = []
                pendencias_enum: list[dict[str, Any]] = []

                for coluna, tipo_dado in colunas:
                    resumo["colunas_total"] += 1
                    traducao = traduzir_nome_coluna(coluna)
                    categoria = classificar_traducao_coluna(coluna, traducao)

                    if categoria == "traduzido_corretamente":
                        resumo["colunas_traduzidas"] += 1
                    elif categoria == "parcialmente_traduzido":
                        resumo["colunas_parcialmente_traduzidas"] += 1
                        pendencias_coluna.append(
                            {
                                "coluna": coluna,
                                "traducao_atual": traducao,
                                "categoria": categoria,
                            }
                        )
                    else:
                        resumo["colunas_nao_traduzidas"] += 1
                        pendencias_coluna.append(
                            {
                                "coluna": coluna,
                                "traducao_atual": traducao,
                                "categoria": categoria,
                            }
                        )

                    if not _coluna_candidata_enum(coluna, tipo_dado):
                        continue

                    valores_amostra = _coletar_amostra_valores(conn, tabela, coluna)
                    if not valores_amostra or len(set(valores_amostra)) > MAX_VALORES_ENUM:
                        continue

                    dicionario_coluna = dicionario_de_coluna(tabela, coluna)
                    pendencias_valores = avaliar_pendencias_enum(
                        list(dict.fromkeys(valores_amostra)),
                        dicionario_coluna,
                    )
                    if not pendencias_valores:
                        continue

                    for pendencia in pendencias_valores:
                        motivo = pendencia["motivo"]
                        if motivo == "placeholder_pendente":
                            resumo["placeholders_enum_pendentes"] += 1
                        elif motivo == "sem_entrada_no_dicionario":
                            resumo["valores_enum_sem_dicionario"] += 1
                        elif motivo == "traducao_possivelmente_em_ingles":
                            resumo["valores_enum_possivelmente_ingles"] += 1

                    pendencias_enum.append(
                        {
                            "coluna": coluna,
                            "valores_pendentes": pendencias_valores,
                        }
                    )

                if pendencias_coluna or pendencias_enum:
                    relatorio["pendencias"][tabela] = {}
                    if pendencias_coluna:
                        relatorio["pendencias"][tabela]["colunas"] = pendencias_coluna
                    if pendencias_enum:
                        relatorio["pendencias"][tabela]["enums"] = pendencias_enum

            except Exception as exc:
                resumo["tabelas_com_erro"] += 1
                relatorio["pendencias"][tabela] = {"erro": str(exc)}
                print(f"   ⚠️  Falha na tabela {tabela}: {exc}")
                continue

    finally:
        conn.close()

    return relatorio


def salvar_relatorio(relatorio: dict[str, Any], caminho: str = ARQUIVO_RELATORIO) -> None:
    with open(caminho, "w", encoding="utf-8") as arquivo:
        yaml.safe_dump(relatorio, arquivo, allow_unicode=True, sort_keys=False)


def imprimir_resumo(relatorio: dict[str, Any]) -> None:
    resumo = relatorio["resumo"]
    print("\n" + "=" * 72)
    print("✅ AUDITORIA DE TRADUÇÕES CONCLUÍDA")
    print("=" * 72)
    print(f"📊 Tabelas analisadas: {resumo['tabelas_analisadas']}")
    print(f"📋 Colunas totais: {resumo['colunas_total']}")
    print(f"✅ Colunas traduzidas: {resumo['colunas_traduzidas']}")
    print(f"🟡 Colunas parcialmente traduzidas: {resumo['colunas_parcialmente_traduzidas']}")
    print(f"🔴 Colunas não traduzidas: {resumo['colunas_nao_traduzidas']}")
    print(f"🧩 Placeholders ENUM pendentes: {resumo['placeholders_enum_pendentes']}")
    print(f"📚 Valores ENUM sem dicionário: {resumo['valores_enum_sem_dicionario']}")
    print(f"🌐 Valores ENUM possivelmente em inglês: {resumo['valores_enum_possivelmente_ingles']}")
    print(f"⚠️  Tabelas com erro: {resumo['tabelas_com_erro']}")
    print(f"📝 Relatório detalhado: {ARQUIVO_RELATORIO}")


def main() -> None:
    print("🔍 Iniciando auditoria completa de traduções...")
    print("ℹ️  Modo somente leitura (queries SELECT).")
    relatorio = auditar_traducoes()
    salvar_relatorio(relatorio)
    imprimir_resumo(relatorio)


if __name__ == "__main__":
    main()
