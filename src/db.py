"""Módulo de banco de dados: engine SQLAlchemy e funções de introspecção."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import MetaData, Table, create_engine, func, inspect, select, text
from sqlalchemy.engine import Engine

from src.config import CONFIG

# Tipos de coluna considerados "textuais" para busca global
_TIPOS_TEXTO_BASE = frozenset({"char", "varchar", "tinytext", "text", "json", "enum", "set"})
_TIPOS_TEXTO_GRANDE = frozenset({"mediumtext", "longtext"})

_CACHE_STATS: dict[tuple[str, str], tuple[datetime, dict[str, Any]]] = {}
_CACHE_TTL = timedelta(minutes=5)

# ── Caches para label resolution ─────────────────────────────────────────────
# cache permanente: tabela → coluna de label (None se não encontrada)
_CACHE_COLUNA_LABEL: dict[str, str | None] = {}
# cache de FKs inferidas: tabela → (timestamp, lista)
_CACHE_FKS_INFERIDAS: dict[str, tuple[datetime, list[dict[str, str]]]] = {}
_CACHE_FKS_INFERIDAS_TTL = timedelta(hours=1)
# cache LRU simples para labels: "tabela:id" → label
_CACHE_LABELS: dict[str, str] = {}
_CACHE_LABELS_MAX = 10_000

# Candidatos de colunas de label, em ordem de preferência
_CANDIDATAS_LABEL = (
    "name", "nome", "descricao", "description", "title",
    "titulo", "label", "display_name", "displayname",
    "razao_social", "fantasia",
)

# Tipos numéricos reconhecidos para heurística de FK inferida
_TIPOS_NUMERICOS = frozenset({
    "int", "bigint", "mediumint", "smallint", "tinyint",
    "integer",
})


def _url_banco(cfg: dict[str, Any] | None = None) -> str:
    """Constrói a URL de conexão com o banco de dados."""
    if cfg is None:
        cfg = CONFIG["banco"]
    usuario = cfg.get("usuario", "root")
    senha = cfg.get("senha", "")
    host = cfg.get("host", "127.0.0.1")
    porta = cfg.get("porta", 3306)
    nome = cfg.get("nome", "saidjur")
    return f"mysql+pymysql://{usuario}:{senha}@{host}:{porta}/{nome}?charset=utf8mb4"


def criar_engine(cfg: dict[str, Any] | None = None) -> Engine:
    """Cria e retorna o engine SQLAlchemy configurado para MySQL via PyMySQL."""
    url = _url_banco(cfg)
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600, echo=False)


def listar_tabelas(engine: Engine) -> list[dict[str, Any]]:
    """Retorna todas as tabelas com contagem aproximada de linhas e tamanho em MB."""
    if engine.dialect.name == "sqlite":
        insp = inspect(engine)
        meta = MetaData()
        tabelas: list[dict[str, Any]] = []
        with engine.connect() as conn:
            for nome in sorted(insp.get_table_names()):
                if nome.startswith("sqlite_"):
                    continue
                tbl = Table(nome, meta, autoload_with=engine)
                total = conn.execute(select(func.count()).select_from(tbl)).scalar_one()
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
        insp = inspect(engine)
        pk_cols = set(insp.get_pk_constraint(nome_tabela).get("constrained_columns", []))
        colunas = []
        for c in insp.get_columns(nome_tabela):
            tipo = str(c.get("type", ""))
            colunas.append(
                {
                    "nome": c["name"],
                    "tipo": tipo,
                    "nulo": bool(c.get("nullable", True)),
                    "chave": "PRI" if c["name"] in pk_cols else "",
                }
            )
        return colunas

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
        insp = inspect(engine)
        resultado: list[dict[str, str]] = []
        for fk in insp.get_foreign_keys(nome_tabela):
            colunas = fk.get("constrained_columns") or []
            ref_colunas = fk.get("referred_columns") or []
            if not colunas or not ref_colunas:
                continue
            resultado.append(
                {
                    "coluna": colunas[0],
                    "tabela_referenciada": fk.get("referred_table") or "",
                    "coluna_referenciada": ref_colunas[0],
                }
            )
        return resultado

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


def coluna_label(engine: Engine, nome_tabela: str) -> str | None:
    """Retorna o nome da coluna mais adequada como label para a tabela dada.

    Tenta as candidatas em ordem de preferência. Resultado em cache permanente.
    Retorna None se nenhuma candidata existir.
    """
    if nome_tabela in _CACHE_COLUNA_LABEL:
        return _CACHE_COLUNA_LABEL[nome_tabela]

    try:
        cols = {c["nome"].lower() for c in listar_colunas(engine, nome_tabela)}
    except Exception:
        _CACHE_COLUNA_LABEL[nome_tabela] = None
        return None

    for candidata in _CANDIDATAS_LABEL:
        if candidata in cols:
            _CACHE_COLUNA_LABEL[nome_tabela] = candidata
            return candidata

    _CACHE_COLUNA_LABEL[nome_tabela] = None
    return None


def _candidatos_para(coluna: str) -> list[str]:
    """Gera nomes de tabela candidatas para uma coluna FK implícita."""
    base = re.sub(r"(_id|id|_pk)$", "", coluna, flags=re.IGNORECASE).lower()
    base = base.rstrip("_")
    if not base:
        return []

    # Pluralização simples em inglês
    if base.endswith("y"):
        plural = base[:-1] + "ies"
    elif base.endswith(("s", "x", "z", "ch", "sh")):
        plural = base + "es"
    else:
        plural = base + "s"

    candidates = [
        base,
        plural,
        base + "es",
        base.replace("user", "usuario"),
        base.replace("users", "usuarios"),
        base.replace("city", "cidade"),
        base.replace("cities", "cidades"),
        base.replace("type", "tipo"),
        base.replace("types", "tipos"),
    ]
    # deduplicate preservando ordem
    seen: set[str] = set()
    result = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            result.append(c)
    return result


# Colunas a ignorar na heurística — palavras comuns que terminam em "id"
# mas não são FKs (ex: "paid", "said", "valid").
_COLUNAS_FK_IGNORADAS = frozenset({"paid", "said", "laid", "void", "fluid", "rapid", "valid", "acid"})


def fks_inferidas(engine: Engine, nome_tabela: str) -> list[dict[str, str]]:
    """Detecta FKs implícitas (não declaradas) por heurística de nomes de coluna.

    Resultado em cache de 1h.
    Retorna lista no mesmo formato que listar_chaves_estrangeiras.
    """
    agora = datetime.now(UTC)
    if nome_tabela in _CACHE_FKS_INFERIDAS:
        ts, valor = _CACHE_FKS_INFERIDAS[nome_tabela]
        if agora - ts < _CACHE_FKS_INFERIDAS_TTL:
            return valor

    try:
        todas_tabelas = tabelas_validas(engine)
        colunas = listar_colunas(engine, nome_tabela)
    except Exception:
        return []

    # FKs já declaradas — não duplicar
    try:
        fks_declaradas = {fk["coluna"] for fk in listar_chaves_estrangeiras(engine, nome_tabela)}
    except Exception:
        fks_declaradas = set()

    resultado: list[dict[str, str]] = []
    for col in colunas:
        nome_col = col["nome"]
        tipo_col = col["tipo"].lower().split("(")[0].strip()

        if nome_col in fks_declaradas:
            continue
        if nome_col.lower() in _COLUNAS_FK_IGNORADAS:
            continue
        if tipo_col not in _TIPOS_NUMERICOS:
            continue
        # deve terminar em _id, id, _pk ou começar com id_
        if not re.search(r"(_id|id|_pk)$", nome_col, flags=re.IGNORECASE) and \
                not re.match(r"^id_", nome_col, flags=re.IGNORECASE):
            continue
        # não é só "id" sozinho (PK da própria tabela)
        if nome_col.lower() == "id":
            continue

        candidatos = _candidatos_para(nome_col)
        tabela_ref = next((c for c in candidatos if c in todas_tabelas), None)
        if not tabela_ref:
            continue

        # tabela referenciada deve ter coluna "id"
        try:
            cols_ref = {c["nome"].lower() for c in listar_colunas(engine, tabela_ref)}
        except Exception:
            continue
        if "id" not in cols_ref:
            continue

        resultado.append({
            "coluna": nome_col,
            "tabela_referenciada": tabela_ref,
            "coluna_referenciada": "id",
        })

    _CACHE_FKS_INFERIDAS[nome_tabela] = (agora, resultado)
    return resultado


def resolver_labels(
    engine: Engine,
    resolucoes: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    """Resolve IDs em labels para múltiplas tabelas em um único request.

    Parâmetro resolucoes: lista de dicts com chaves 'tabela', 'coluna_chave', 'ids'.
    Retorna dict: tabela → {str(id): label}.
    Usa cache LRU de até _CACHE_LABELS_MAX entradas.
    """
    resposta: dict[str, dict[str, str]] = {}

    for pedido in resolucoes:
        tabela = pedido.get("tabela", "")
        coluna_chave = pedido.get("coluna_chave", "id")
        ids = pedido.get("ids", [])

        if not tabela or not ids:
            continue

        col_label = coluna_label(engine, tabela)
        mapa: dict[str, str] = {}

        ids_pendentes = []
        for id_val in ids:
            cache_key = f"{tabela}:{id_val}"
            if cache_key in _CACHE_LABELS:
                mapa[str(id_val)] = _CACHE_LABELS[cache_key]
            else:
                ids_pendentes.append(id_val)

        if ids_pendentes:
            try:
                meta = MetaData()
                tbl = Table(tabela, meta, autoload_with=engine)
                if col_label and col_label in {c.name for c in tbl.columns}:
                    col_ref = tbl.c[coluna_chave]
                    col_lbl = tbl.c[col_label]
                    stmt = select(col_ref, col_lbl).where(col_ref.in_(ids_pendentes))
                    with engine.connect() as conn:
                        for row in conn.execute(stmt):
                            id_str = str(row[0])
                            lbl = str(row[1]) if row[1] is not None else id_str
                            # truncar labels longos
                            if len(lbl) > 60:
                                lbl = lbl[:57] + "..."
                            mapa[id_str] = lbl
                            cache_key = f"{tabela}:{row[0]}"
                            # manter cache dentro do limite
                            if len(_CACHE_LABELS) >= _CACHE_LABELS_MAX:
                                try:
                                    del _CACHE_LABELS[next(iter(_CACHE_LABELS))]
                                except StopIteration:
                                    pass
                            _CACHE_LABELS[cache_key] = lbl
            except Exception:
                pass

        if mapa:
            resposta[tabela] = mapa

    return resposta


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
    """Remove comentários SQL de forma linear (evita regex ReDoS)."""
    out: list[str] = []
    i = 0
    n = len(sql)
    em_string: str | None = None

    while i < n:
        ch = sql[i]
        prox = sql[i + 1] if i + 1 < n else ""

        if em_string:
            out.append(ch)
            if ch == em_string:
                em_string = None
            elif ch == "\\" and i + 1 < n:
                i += 1
                out.append(sql[i])
            i += 1
            continue

        if ch in {"'", '"'}:
            em_string = ch
            out.append(ch)
            i += 1
            continue

        if ch == "/" and prox == "*":
            i += 2
            while i + 1 < n and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i += 2 if i + 1 <= n else 1
            out.append(" ")
            continue

        if ch == "-" and prox == "-":
            i += 2
            while i < n and sql[i] not in "\r\n":
                i += 1
            out.append(" ")
            continue

        if ch == "#":
            i += 1
            while i < n and sql[i] not in "\r\n":
                i += 1
            out.append(" ")
            continue

        out.append(ch)
        i += 1

    return "".join(out).strip()


def validar_sql_somente_leitura(query: str) -> str:
    """Valida SQL para permitir somente SELECT/WITH de leitura."""
    limpa = _limpar_comentarios_sql(query)
    if not limpa:
        raise ValueError("Query vazia.")

    inicio = limpa.lstrip().lower()
    if not (inicio.startswith("select") or inicio.startswith("with")):
        raise ValueError("Apenas queries SELECT ou WITH são permitidas.")

    corpo = limpa.rstrip()
    if ";" in corpo[:-1]:
        raise ValueError("Apenas uma query é permitida por execução.")

    bloqueados = [
        "insert", "update", "delete", "drop", "alter", "create", "truncate",
        "replace", "grant", "revoke", "call", "execute", "set",
    ]
    palavras = {token.lower() for token in corpo.replace("(", " ").replace(")", " ").split()}
    if any(cmd in palavras for cmd in bloqueados):
        raise ValueError("Comandos de alteração de dados/estrutura não são permitidos.")

    return limpa


def executar_sql_somente_leitura(
    engine: Engine,
    query: str,
    limite: int = 5000,
    timeout_segundos: int = 30,
) -> dict[str, Any]:
    """Executa query somente leitura com timeout e limite de linhas."""
    limpa = validar_sql_somente_leitura(query).rstrip(";")

    with engine.connect() as conn:
        try:
            conn.execute(
                text("SET SESSION max_execution_time=:ms"),
                {"ms": int(timeout_segundos) * 1000},
            )
        except Exception:
            pass

        resultado = conn.execute(text(limpa))
        colunas = list(resultado.keys())
        linhas = [dict(zip(colunas, row)) for row in resultado.fetchmany(int(limite))]

    return {
        "colunas": colunas,
        "linhas": linhas,
        "total": len(linhas),
        "limite": limite,
    }


def estatisticas_coluna(engine: Engine, tabela: str, coluna: str) -> dict[str, Any]:
    """Retorna estatísticas rápidas para uma coluna, com cache de 5 minutos."""
    chave_cache = (tabela, coluna)
    agora = datetime.now(UTC)
    if chave_cache in _CACHE_STATS:
        ts, valor = _CACHE_STATS[chave_cache]
        if agora - ts < _CACHE_TTL:
            return {**valor, "cache": True}

    meta = MetaData()
    tbl = Table(tabela, meta, autoload_with=engine)
    col = tbl.c[coluna]

    with engine.connect() as conn:
        total_aprox = conn.execute(select(func.count()).select_from(tbl)).scalar_one()

        amostrado = int(total_aprox) > 1_000_000
        if amostrado:
            fonte = select(col.label("valor")).select_from(tbl).limit(200000).subquery("amostra")
            col_ref = fonte.c.valor
        else:
            fonte = tbl
            col_ref = col

        base_stmt = select(
            func.count(col_ref).label("nao_nulos"),
            func.count(func.distinct(col_ref)).label("distintos"),
            func.min(col_ref).label("minimo"),
            func.max(col_ref).label("maximo"),
        ).select_from(fonte)
        base = conn.execute(base_stmt).mappings().one()

        top_stmt = (
            select(col_ref.label("valor"), func.count().label("quantidade"))
            .select_from(fonte)
            .where(col_ref.is_not(None))
            .group_by(col_ref)
            .order_by(func.count().desc())
            .limit(5)
        )
        top5 = [dict(r) for r in conn.execute(top_stmt).mappings()]

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
