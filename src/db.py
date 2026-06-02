"""Módulo de banco de dados: engine SQLAlchemy e funções de introspecção."""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.config import CONFIG

# Tipos de coluna considerados "textuais" para busca global
_TIPOS_TEXTO = frozenset(
    {"char", "varchar", "tinytext", "text", "mediumtext", "longtext", "json", "enum", "set"}
)


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
    """
    Cria e retorna o engine SQLAlchemy configurado para MySQL via PyMySQL.

    Args:
        cfg: Dicionário com configurações do banco. Se None, usa CONFIG global.
    """
    url = _url_banco(cfg)
    return create_engine(
        url,
        pool_pre_ping=True,       # testa conexão antes de usar
        pool_recycle=3600,        # reconecta após 1 hora (evita timeout MySQL)
        echo=False,
    )


def listar_tabelas(engine: Engine) -> list[dict[str, Any]]:
    """
    Retorna todas as tabelas do banco com contagem aproximada e tamanho em MB.

    Usa information_schema.TABLES para evitar COUNT(*) completo em tabelas grandes.
    """
    sql = text("""
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
    """)
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
    """
    Retorna as colunas de uma tabela com tipo, nulidade e chave.

    Args:
        engine: Engine SQLAlchemy.
        nome_tabela: Nome da tabela (já validado contra whitelist).
    """
    sql = text("""
        SELECT
            COLUMN_NAME   AS nome,
            COLUMN_TYPE   AS tipo,
            IS_NULLABLE   AS nulo,
            COLUMN_KEY    AS chave
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME   = :tabela
        ORDER BY ORDINAL_POSITION
    """)
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


def tabelas_validas(engine: Engine) -> set[str]:
    """Retorna o conjunto de nomes de tabelas existentes no banco."""
    return {t["nome"] for t in listar_tabelas(engine)}


def colunas_validas(engine: Engine, nome_tabela: str) -> set[str]:
    """Retorna o conjunto de nomes de colunas de uma tabela."""
    return {c["nome"] for c in listar_colunas(engine, nome_tabela)}


def colunas_texto(engine: Engine, nome_tabela: str) -> list[str]:
    """
    Retorna os nomes das colunas textuais de uma tabela.

    Considera: CHAR, VARCHAR, TEXT (todos os tamanhos), JSON, ENUM, SET.
    """
    colunas = listar_colunas(engine, nome_tabela)
    resultado = []
    for col in colunas:
        tipo_base = col["tipo"].split("(")[0].lower().strip()
        if tipo_base in _TIPOS_TEXTO:
            resultado.append(col["nome"])
    return resultado
