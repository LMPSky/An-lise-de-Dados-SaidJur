"""Módulo de banco de dados: engine SQLAlchemy e funções de introspecção."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.config import CONFIG

# Tipos de coluna considerados "textuais" para busca global
_TIPOS_TEXTO_BASE = frozenset({"char", "varchar", "tinytext", "text", "json", "enum", "set"})
_TIPOS_TEXTO_GRANDE = frozenset({"mediumtext", "longtext"})

_CACHE_STATS: dict[tuple[str, str], tuple[datetime, dict[str, Any]]] = {}
_CACHE_TTL = timedelta(minutes=5)


def _quote_ident(nome: str) -> str:
    """Protege identificadores SQL com aspas invertidas."""
    return "`" + nome.replace("`", "``") + "`"


def _url_banco(cfg: dict[str, Any] | None = None) -> str:
    """Constrói a URL de conexão com o banco de dados."""
    if cfg is None:
        cfg = CONFIG["banco"]
    usuario = cfg.get("usuario", "root")
    senha = cfg.get("senha", "")
    host = cfg.get("host", "127.0.0.1")
    porta = cfg.get("porta", 3306)
    nome = cfg.get("nome", "saidjur")
    # PyMySQL puro Python — mais fácil de instalar no Windows
    return f"mysql+pymysql://{usuario}:{senha}@{host}:{porta}/{nome}?charset=utf8mb4"


def criar_engine(cfg: dict[str, Any] | None = None) -> Engine:
    """Cria e retorna o engine SQLAlchemy configurado para MySQL via PyMySQL."""
    url = _url_banco(cfg)
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False,
    )


def listar_tabelas(engine: Engine) -> list[dict[str, Any]]:
    """Retorna todas as tabelas com contagem aproximada de linhas e tamanho em MB."""
    if engine.dialect.name == "sqlite":
        with engine.connect() as conn:
            resultado = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            )
            tabelas: list[dict[str, Any]] = []
            for row in resultado:
                nome = row[0]
                total = conn.execute(text(f"SELECT COUNT(*) FROM {_quote_ident(nome)}")).scalar_one()
                tabelas.append({"nome": nome, "linhas_aprox": int(total), "tamanho_mb": 0.0})
            return tabelas

    sql = text(
        """
        SELECT
            TABLE_NAME                                          AS nome,
            COALESCE(TABLE_ROWS, 0)                            AS linhas_aprox,
            ROUND(
                COALESCE(DATA_LENGTH + INDEX_LENGTH, 0) / 1048576, 2
            )                                                  AS tamanho_mb
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
    """
    )
    with engine.connect() as conn:
        resultado = conn.execute(sql)
        return [
            {
                "nome": row.nome,
                "linhas_aprox": int(row.linhas_aprox),
                "tamanho_mb": float(row.tamanho_mb),
            }
            for row in resultado
        ]


def listar_colunas(engine: Engine, nome_tabela: str) -> list[dict[str, Any]]:
    """Retorna as colunas de uma tabela com tipo, nulidade e chave."""
    if engine.dialect.name == "sqlite":
        with engine.connect() as conn:
            resultado = conn.execute(text(f"PRAGMA table_info({_quote_ident(nome_tabela)})"))
            return [
                {
                    "nome": row[1],
                    "tipo": row[2],
                    "nulo": row[3] == 0,
                    "chave": "PRI" if row[5] == 1 else "",
                }
                for row in resultado
            ]

    sql = text(
        """
        SELECT
            COLUMN_NAME   AS nome,
            COLUMN_TYPE   AS tipo,
            IS_NULLABLE   AS nulo,
            COLUMN_KEY    AS chave
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME   = :tabela
        ORDER BY ORDINAL_POSITION
    """
    )
    with engine.connect() as conn:
        resultado = conn.execute(sql, {"tabela": nome_tabela})
        return [
            {
                "nome": row.nome,
                "tipo": row.tipo,
                "nulo": row.nulo == "YES",
                "chave": row.chave,
            }
            for row in resultado
        ]


def listar_chaves_estrangeiras(engine: Engine, nome_tabela: str) -> list[dict[str, str]]:
    """Retorna FKs da tabela informada."""
    if engine.dialect.name == "sqlite":
        with engine.connect() as conn:
            resultado = conn.execute(
                text(f"PRAGMA foreign_key_list({_quote_ident(nome_tabela)})")
            )
            return [
                {
                    "coluna": row[3],
                    "tabela_referenciada": row[2],
                    "coluna_referenciada": row[4],
                }
                for row in resultado
            ]

    sql = text(
        """
        SELECT
            COLUMN_NAME AS coluna,
            REFERENCED_TABLE_NAME AS tabela_referenciada,
            REFERENCED_COLUMN_NAME AS coluna_referenciada
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = :tabela
          AND REFERENCED_TABLE_NAME IS NOT NULL
        ORDER BY ORDINAL_POSITION
    """
    )
    with engine.connect() as conn:
        resultado = conn.execute(sql, {"tabela": nome_tabela})
        return [dict(row._mapping) for row in resultado]


def tabelas_validas(engine: Engine) -> set[str]:
    """Retorna o conjunto de nomes de tabelas existentes no banco."""
    return {t["nome"] for t in listar_tabelas(engine)}


def colunas_validas(engine: Engine, nome_tabela: str) -> set[str]:
    """Retorna o conjunto de nomes de colunas de uma tabela."""
    return {c["nome"] for c in listar_colunas(engine, nome_tabela)}


def colunas_texto(
    engine: Engine,
    nome_tabela: str,
    incluir_colunas_grandes: bool = False,
) -> list[str]:
    """Retorna os nomes das colunas textuais de uma tabela."""
    tipos = set(_TIPOS_TEXTO_BASE)
    if incluir_colunas_grandes:
        tipos |= _TIPOS_TEXTO_GRANDE

    colunas = listar_colunas(engine, nome_tabela)
    return [
        col["nome"]
        for col in colunas
        if col["tipo"].split("(")[0].lower().strip() in tipos
    ]


def dados_dashboard(engine: Engine) -> dict[str, Any]:
    """Agrega métricas da tela inicial."""
    tabelas = listar_tabelas(engine)
    total_tabelas = len(tabelas)
    total_registros = sum(int(t.get("linhas_aprox") or 0) for t in tabelas)
    tamanho_total_mb = round(sum(float(t.get("tamanho_mb") or 0) for t in tabelas), 2)
    top_tabelas = sorted(tabelas, key=lambda t: int(t.get("linhas_aprox") or 0), reverse=True)[:10]

    return {
        "estatisticas": {
            "total_tabelas": total_tabelas,
            "total_registros": total_registros,
            "tamanho_total_mb": tamanho_total_mb,
        },
        "maiores_tabelas": top_tabelas,
    }


def _limpar_comentarios_sql(sql: str) -> str:
    sem_bloco = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sem_linha = re.sub(r"--.*?$", " ", sem_bloco, flags=re.MULTILINE)
    sem_hash = re.sub(r"#.*?$", " ", sem_linha, flags=re.MULTILINE)
    return sem_hash.strip()


def validar_sql_somente_leitura(query: str) -> str:
    """Valida SQL para permitir somente SELECT/WITH de leitura."""
    limpa = _limpar_comentarios_sql(query)
    if not limpa:
        raise ValueError("Query vazia.")

    inicio = limpa.lstrip().lower()
    if not (inicio.startswith("select") or inicio.startswith("with")):
        raise ValueError("Apenas queries SELECT ou WITH são permitidas.")

    corpo = limpa.rstrip()
    if ";" in corpo[:-1] or (corpo.endswith(";") and ";" in corpo[:-1]):
        raise ValueError("Apenas uma query é permitida por execução.")

    bloqueados = re.compile(
        r"\b(insert|update|delete|drop|alter|create|truncate|replace|grant|revoke|call|execute|set)\b",
        flags=re.IGNORECASE,
    )
    if bloqueados.search(corpo):
        raise ValueError("Comandos de alteração de dados/estrutura não são permitidos.")

    return limpa


def executar_sql_somente_leitura(
    engine: Engine,
    query: str,
    limite: int = 5000,
    timeout_segundos: int = 30,
) -> dict[str, Any]:
    """Executa query somente leitura com timeout e limite de linhas."""
    limpa = validar_sql_somente_leitura(query)

    sql_final = f"SELECT * FROM ({limpa.rstrip(';')}) _q LIMIT {int(limite)}"

    with engine.connect() as conn:
        try:
            conn.execute(
                text("SET SESSION max_execution_time=:ms"),
                {"ms": int(timeout_segundos) * 1000},
            )
        except Exception:
            pass

        resultado = conn.execute(text(sql_final))
        colunas = list(resultado.keys())
        linhas = [dict(zip(colunas, row)) for row in resultado]

    return {
        "colunas": colunas,
        "linhas": linhas,
        "total": len(linhas),
        "limite": limite,
    }


def estatisticas_coluna(engine: Engine, tabela: str, coluna: str) -> dict[str, Any]:
    """Retorna estatísticas rápidas para uma coluna, com cache de 5 minutos."""
    chave_cache = (tabela, coluna)
    agora = datetime.utcnow()
    if chave_cache in _CACHE_STATS:
        ts, valor = _CACHE_STATS[chave_cache]
        if agora - ts < _CACHE_TTL:
            return {**valor, "cache": True}

    q_tabela = _quote_ident(tabela)
    q_coluna = _quote_ident(coluna)

    with engine.connect() as conn:
        total_aprox = conn.execute(text(f"SELECT COUNT(*) FROM {q_tabela}")).scalar_one()

        fonte = f"{q_tabela}"
        amostrado = False
        tamanho_amostra = 200000
        if int(total_aprox) > 1_000_000:
            fonte = f"(SELECT {q_coluna} FROM {q_tabela} LIMIT {tamanho_amostra}) amostra"
            amostrado = True

        base_sql = text(
            f"""
            SELECT
                COUNT({q_coluna}) AS nao_nulos,
                COUNT(DISTINCT {q_coluna}) AS distintos,
                MIN({q_coluna}) AS minimo,
                MAX({q_coluna}) AS maximo
            FROM {fonte}
        """
        )
        base = conn.execute(base_sql).mappings().one()

        top_sql = text(
            f"""
            SELECT {q_coluna} AS valor, COUNT(*) AS quantidade
            FROM {fonte}
            WHERE {q_coluna} IS NOT NULL
            GROUP BY {q_coluna}
            ORDER BY quantidade DESC
            LIMIT 5
        """
        )
        top5 = [dict(r) for r in conn.execute(top_sql).mappings()]

    dados = {
        "nao_nulos": int(base["nao_nulos"] or 0),
        "distintos": int(base["distintos"] or 0),
        "minimo": base["minimo"],
        "maximo": base["maximo"],
        "top_5": top5,
        "amostrado": amostrado,
        "total_referencia": int(total_aprox or 0),
        "cache": False,
    }

    _CACHE_STATS[chave_cache] = (agora, dados)
    return dados
