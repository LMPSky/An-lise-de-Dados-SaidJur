"""Fluxo de investigação assistida para nomes de colunas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
import yaml

from src.db import (
    criar_engine,
    executar_com_retry_db,
    fks_inferidas,
    listar_chaves_estrangeiras,
)
from src.traducoes_colunas import (
    TRADUCOES_COLUNAS,
    _traduzir_coluna_relacional,
    traduzir_nome_coluna,
)

ARQUIVO_RELATORIO_COLUNAS_PADRAO = "relatorio_investigacao_colunas.yaml"
ARQUIVO_DECISOES_BOOLEANOS_PADRAO = "colunas_booleanas_confirmadas.yaml"
TABELAS_PRIORITARIAS_BOOLEANOS = (
    "lawsuits",
    "persons",
    "hearingcontrol",
    "prazos_log",
    "employees",
    "users",
)
LIMITE_DISTINTOS_BOOLEANO = 64
_COLUNAS_PK_CACHE: dict[Engine, dict[str, set[str]]] = {}
_COLUNAS_FK_CACHE: dict[Engine, dict[str, set[str]]] = {}
_CACHE_BOOLEANOS_LOCK = Lock()


@dataclass(frozen=True)
class ColunaSchema:
    """Representa uma coluna existente no schema."""

    tabela: str
    coluna: str
    tipo: str


def carregar_yaml(caminho: str | Path) -> dict[str, Any]:
    """Carrega um arquivo YAML, retornando dicionário vazio quando ausente."""
    caminho_path = Path(caminho)
    if not caminho_path.exists():
        return {}
    dados = yaml.safe_load(caminho_path.read_text(encoding="utf-8"))
    return dados if isinstance(dados, dict) else {}


def _chave_tabela_coluna(tabela: str, coluna: str) -> str:
    """Normaliza a chave composta ``tabela.coluna`` usada nas decisões."""
    return f"{tabela.strip().lower()}.{coluna.strip().lower()}"


def normalizar_tabela_coluna(tabela: str, coluna: str) -> str:
    """Expõe a normalização pública de chaves ``tabela.coluna``."""
    return _chave_tabela_coluna(tabela, coluna)


def _estrutura_decisoes_booleanos_padrao() -> dict[str, Any]:
    """Retorna a estrutura mínima do arquivo de decisões de booleanos."""
    return {
        "confirmadas": {},
        "rejeitadas": {},
    }


def carregar_decisoes_booleanos(caminho: str | Path = ARQUIVO_DECISOES_BOOLEANOS_PADRAO) -> dict[str, Any]:
    """Carrega decisões manuais de revisão de colunas booleanas."""
    dados = carregar_yaml(caminho)
    estrutura = _estrutura_decisoes_booleanos_padrao()

    for secao in ("confirmadas", "rejeitadas"):
        bloco = dados.get(secao, {})
        if not isinstance(bloco, dict):
            bloco = {}
        normalizado: dict[str, Any] = {}
        for chave, valor in bloco.items():
            if not isinstance(valor, dict):
                valor = {}
            tabela = str(valor.get("tabela") or str(chave).split(".", 1)[0]).strip()
            coluna = str(valor.get("coluna") or str(chave).split(".", 1)[-1]).strip()
            if not tabela or not coluna:
                continue
            normalizado[_chave_tabela_coluna(tabela, coluna)] = {
                "tabela": tabela,
                "coluna": coluna,
                **valor,
            }
        estrutura[secao] = normalizado

    return estrutura


def salvar_decisoes_booleanos(
    dados: dict[str, Any],
    caminho: str | Path = ARQUIVO_DECISOES_BOOLEANOS_PADRAO,
) -> None:
    """Salva o arquivo de decisões manuais de booleanos."""
    payload = {
        "atualizado_em": datetime.now(UTC).isoformat(),
        "confirmadas": dict(sorted((dados.get("confirmadas") or {}).items())),
        "rejeitadas": dict(sorted((dados.get("rejeitadas") or {}).items())),
    }
    salvar_yaml(payload, caminho)


def registrar_decisao_booleana(
    dados: dict[str, Any],
    tabela: str,
    coluna: str,
    decisao: str,
    *,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Registra uma decisão manual de confirmação/rejeição para uma coluna."""
    decisao_normalizada = decisao.strip().lower()
    if decisao_normalizada not in {"confirmado", "rejeitado"}:
        raise ValueError(f"Decisão inválida: {decisao}")

    chave = _chave_tabela_coluna(tabela, coluna)
    instante = timestamp or datetime.now(UTC).isoformat()
    dados.setdefault("confirmadas", {})
    dados.setdefault("rejeitadas", {})
    dados["confirmadas"].pop(chave, None)
    dados["rejeitadas"].pop(chave, None)

    payload = {
        "tabela": tabela,
        "coluna": coluna,
    }
    if decisao_normalizada == "confirmado":
        payload["confirmado_em"] = instante
        dados["confirmadas"][chave] = payload
    else:
        payload["rejeitado_em"] = instante
        dados["rejeitadas"][chave] = payload

    return dados


def colunas_rejeitadas_booleanos(dados: dict[str, Any]) -> set[str]:
    """Extrai o conjunto normalizado de colunas rejeitadas manualmente."""
    rejeitadas = dados.get("rejeitadas", {})
    if not isinstance(rejeitadas, dict):
        return set()
    return set(rejeitadas)


def lista_colunas_booleanas_confirmadas(
    caminho: str | Path | None = None,
) -> list[dict[str, str]]:
    """Retorna lista de colunas confirmadas como booleanas para exibição no frontend.

    Cada item da lista contém ``tabela`` e ``coluna``.  Quando o arquivo de
    decisões ainda não existe (antes de qualquer execução de
    ``revisar_booleanos.py``), retorna lista vazia sem lançar exceção.

    Quando ``caminho`` não é informado, o caminho padrão é resolvido em
    tempo de chamada a partir de ``ARQUIVO_DECISOES_BOOLEANOS_PADRAO``, e não
    fixado em tempo de definição da função, permitindo que o valor seja
    sobrescrito dinamicamente (por exemplo, em testes).
    """
    dados = carregar_decisoes_booleanos(
        caminho if caminho is not None else ARQUIVO_DECISOES_BOOLEANOS_PADRAO
    )
    confirmadas = dados.get("confirmadas", {})
    if not isinstance(confirmadas, dict):
        return []
    return [
        {"tabela": info["tabela"], "coluna": info["coluna"]}
        for info in confirmadas.values()
        if isinstance(info, dict) and info.get("tabela") and info.get("coluna")
    ]


def sincronizar_decisoes_booleanos_relatorio(
    relatorio: dict[str, Any],
    dados_decisoes: dict[str, Any],
) -> dict[str, Any]:
    """Anota no relatório as decisões manuais já persistidas."""
    confirmadas = dados_decisoes.get("confirmadas", {})
    rejeitadas = dados_decisoes.get("rejeitadas", {})

    for item in relatorio.get("investigacoes", []):
        chave = _chave_tabela_coluna(str(item.get("tabela", "")), str(item.get("coluna", "")))
        for campo in (
            "confirmado_manualmente",
            "rejeitado_manualmente",
            "revisao_booleano_manual",
            "revisado_booleano_em",
        ):
            item.pop(campo, None)

        if chave in confirmadas:
            item["confirmado_manualmente"] = True
            item["revisao_booleano_manual"] = "confirmado"
            item["revisado_booleano_em"] = confirmadas[chave].get("confirmado_em")
        elif chave in rejeitadas:
            item["rejeitado_manualmente"] = True
            item["revisao_booleano_manual"] = "rejeitado"
            item["revisado_booleano_em"] = rejeitadas[chave].get("rejeitado_em")

    return relatorio



def _fallback_trivial(nome_coluna: str) -> str:
    """Retorna a capitalização trivial usada como baseline heurístico."""
    return " ".join(parte.capitalize() for parte in nome_coluna.lower().split("_"))



def _identificador(nome: str, dialect_name: str) -> str:
    """Escapa identificadores de tabela/coluna conforme o dialeto."""
    if dialect_name == "mysql":
        return f"`{nome.replace('`', '``')}`"
    return f'"{nome.replace("\"", "\"\"")}"'



def _listar_tabelas_validas(engine: Engine) -> list[str]:
    """Lista tabelas reais, ignorando artefatos internos do SQLite."""
    insp = inspect(engine)
    return [
        nome
        for nome in sorted(insp.get_table_names())
        if not (engine.dialect.name == "sqlite" and nome.startswith("sqlite_"))
    ]



def _parsear_colunas_diretas(specs: list[str]) -> list[tuple[str, str]]:
    """Converte especificações ``tabela.coluna`` em pares utilizáveis."""
    alvos: list[tuple[str, str]] = []
    for spec in specs:
        spec_limpa = spec.strip()
        if not spec_limpa or "." not in spec_limpa:
            raise ValueError(
                f"Especificação inválida: '{spec}'. Use o formato 'tabela.coluna'."
            )
        tabela, coluna = spec_limpa.split(".", 1)
        tabela = tabela.strip()
        coluna = coluna.strip()
        if not tabela or not coluna:
            raise ValueError(
                f"Especificação inválida: '{spec}'. Tabela e coluna não podem ser vazias."
            )
        alvos.append((tabela, coluna))
    return alvos



def classificar_estado_traducao(nome_coluna: str) -> str:
    """Classifica o estado atual de tradução de uma coluna."""
    nome = nome_coluna.lower()
    if nome in TRADUCOES_COLUNAS:
        return "traduzida_manual"
    if _traduzir_coluna_relacional(nome) is not None:
        return "traduzida_heuristica"
    traducao = traduzir_nome_coluna(nome)
    fallback_trivial = _fallback_trivial(nome)
    if traducao != fallback_trivial and traducao != nome and traducao != nome.capitalize():
        return "traduzida_heuristica"
    return "nao_traduzida"



def listar_colunas_schema(engine: Engine, tabela: str | None = None) -> list[dict[str, str]]:
    """Inspeciona o schema e lista colunas com estado de tradução."""
    insp = inspect(engine)
    tabelas = [tabela] if tabela else _listar_tabelas_validas(engine)
    resultado: list[dict[str, str]] = []

    for nome_tabela in tabelas:
        for coluna_info in insp.get_columns(nome_tabela):
            nome_coluna = str(coluna_info.get("name", ""))
            tipo_coluna = str(coluna_info.get("type", ""))
            resultado.append(
                {
                    "tabela": nome_tabela,
                    "coluna": nome_coluna,
                    "tipo": tipo_coluna,
                    "estado": classificar_estado_traducao(nome_coluna),
                    "traducao_atual": traduzir_nome_coluna(nome_coluna),
                }
            )
    return resultado



def _classificar_tipo_dado(tipo: str) -> dict[str, str] | None:
    """Produz uma pista descritiva a partir do tipo SQL da coluna."""
    tipo_limpo = tipo.lower().strip()
    if not tipo_limpo:
        return None

    if "tinyint(1)" in tipo_limpo or tipo_limpo == "boolean" or "bool" in tipo_limpo:
        valor = "Campo booleano/indicador (sim/não)"
    elif any(chave in tipo_limpo for chave in ("date", "datetime", "timestamp", "time")):
        valor = "Campo de data/hora"
    elif any(chave in tipo_limpo for chave in ("int", "decimal", "numeric", "float", "double", "real")):
        valor = "Campo numérico/código"
    elif any(chave in tipo_limpo for chave in ("char", "text", "clob", "json")):
        valor = "Campo textual"
    else:
        valor = f"Tipo de dado: {tipo}"

    return {"fonte": "tipo_dado", "valor": valor, "confianca": "baixa"}


def _tipo_compativel_booleano(tipo: str) -> bool:
    """Retorna True para tipos compatíveis com armazenamento booleano."""
    tipo_limpo = tipo.lower().strip()
    if not tipo_limpo:
        return False
    if "tinyint(1)" in tipo_limpo or tipo_limpo == "boolean" or "bool" in tipo_limpo:
        return True
    return tipo_limpo.split("(", 1)[0].strip() in {"tinyint", "int", "integer", "smallint", "bigint"}


def _normalizar_valor_booleano(valor: Any) -> str | None:
    """Normaliza valor observado para '0' ou '1' quando possível."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        return "1" if valor else "0"
    valor_limpo = str(valor).strip().lower()
    if valor_limpo in {"0", "1"}:
        return valor_limpo
    return None


def _colunas_pk_tabela(engine: Engine, tabela: str) -> set[str]:
    """Retorna (em cache) o conjunto de colunas PK da tabela."""
    with _CACHE_BOOLEANOS_LOCK:
        cache_engine = _COLUNAS_PK_CACHE.setdefault(engine, {})
        tabela_normalizada = tabela.lower()
        if tabela_normalizada not in cache_engine:
            try:
                pk_constraint = inspect(engine).get_pk_constraint(tabela)
                pk_cols = pk_constraint.get("constrained_columns") or []
                cache_engine[tabela_normalizada] = {str(coluna).lower() for coluna in pk_cols}
            except Exception:
                cache_engine[tabela_normalizada] = set()
        return cache_engine[tabela_normalizada]


def _colunas_fk_tabela(engine: Engine, tabela: str) -> set[str]:
    """Retorna (em cache) o conjunto de colunas FK declaradas/inferidas da tabela."""
    with _CACHE_BOOLEANOS_LOCK:
        cache_engine = _COLUNAS_FK_CACHE.setdefault(engine, {})
        tabela_normalizada = tabela.lower()
        if tabela_normalizada not in cache_engine:
            try:
                declaradas = {str(fk["coluna"]).lower() for fk in listar_chaves_estrangeiras(engine, tabela)}
            except Exception:
                declaradas = set()
            try:
                inferidas = {str(fk["coluna"]).lower() for fk in fks_inferidas(engine, tabela)}
            except Exception:
                inferidas = set()
            cache_engine[tabela_normalizada] = declaradas | inferidas
        return cache_engine[tabela_normalizada]


def _coluna_auditoria_usuario(nome_coluna: str) -> bool:
    """Identifica colunas de auditoria de usuário que nunca devem ser booleanas."""
    return nome_coluna.lower().endswith("userid")


def _clausula_limite_um(dialect_name: str) -> str:
    """Retorna cláusula de limitação de 1 linha conforme o dialeto."""
    if dialect_name in {"mysql", "sqlite", "postgresql"}:
        return " LIMIT 1"
    if dialect_name == "oracle":
        return " FETCH FIRST 1 ROWS ONLY"
    return ""


def _tipo_texto_cast(dialect_name: str) -> str:
    """Retorna tipo textual para CAST compatível com o dialeto."""
    if dialect_name == "mysql":
        return "CHAR"
    if dialect_name == "mssql":
        return "VARCHAR(64)"
    if dialect_name == "oracle":
        return "VARCHAR2(64)"
    return "TEXT"


def _motivo_exclusao_booleano(
    engine: Engine,
    tabela: str,
    coluna: str,
    *,
    colunas_rejeitadas: set[str] | None = None,
) -> str | None:
    """Retorna o motivo de exclusão da coluna na classificação booleana."""
    nome_coluna = coluna.lower()
    if colunas_rejeitadas and _chave_tabela_coluna(tabela, coluna) in colunas_rejeitadas:
        return "rejeitada_manualmente"
    if nome_coluna in _colunas_pk_tabela(engine, tabela):
        return "chave_primaria"
    if nome_coluna in _colunas_fk_tabela(engine, tabela):
        return "chave_estrangeira"
    if _coluna_auditoria_usuario(nome_coluna):
        return "auditoria_usuario"
    return None


def _existe_valor_fora_booleano(engine: Engine, tabela: str, coluna: str) -> bool:
    """Verifica se existe algum valor não nulo fora do domínio 0/1."""
    dialect_name = engine.dialect.name
    tabela_sql = _identificador(tabela, dialect_name)
    coluna_sql = _identificador(coluna, dialect_name)
    cast_texto = f"CAST({coluna_sql} AS {_tipo_texto_cast(dialect_name)})"
    where_clause = (
        f"WHERE {coluna_sql} IS NOT NULL "
        f"AND TRIM(LOWER({cast_texto})) NOT IN ('0', '1')"
    )
    if dialect_name == "mssql":
        sql = text(f"SELECT TOP 1 1 FROM {tabela_sql} {where_clause}")
    else:
        sql = text(f"SELECT 1 FROM {tabela_sql} {where_clause}{_clausula_limite_um(dialect_name)}")
    with engine.connect() as conn:
        return conn.execute(sql).fetchone() is not None


def _existe_valor_nulo(engine: Engine, tabela: str, coluna: str) -> bool:
    """Verifica se a coluna possui pelo menos um valor NULL."""
    dialect_name = engine.dialect.name
    tabela_sql = _identificador(tabela, dialect_name)
    coluna_sql = _identificador(coluna, dialect_name)
    if dialect_name == "mssql":
        sql = text(f"SELECT TOP 1 1 FROM {tabela_sql} WHERE {coluna_sql} IS NULL")
    else:
        sql = text(
            f"SELECT 1 FROM {tabela_sql} WHERE {coluna_sql} IS NULL{_clausula_limite_um(dialect_name)}"
        )
    with engine.connect() as conn:
        return conn.execute(sql).fetchone() is not None


def _valores_distintos_coluna(
    engine: Engine,
    tabela: str,
    coluna: str,
    *,
    limite: int = LIMITE_DISTINTOS_BOOLEANO,
) -> list[Any]:
    """Coleta uma amostra de valores distintos não nulos de uma coluna."""
    tabela_sql = _identificador(tabela, engine.dialect.name)
    coluna_sql = _identificador(coluna, engine.dialect.name)
    sql = text(
        f"SELECT DISTINCT {coluna_sql} AS valor "
        f"FROM {tabela_sql} "
        f"WHERE {coluna_sql} IS NOT NULL "
        f"LIMIT :limite"
    )

    with engine.connect() as conn:
        return [row[0] for row in conn.execute(sql, {"limite": limite}).fetchall()]


def _pista_provavel_booleano(
    engine: Engine,
    tabela: str,
    coluna: str,
    tipo: str,
    *,
    colunas_rejeitadas: set[str] | None = None,
) -> dict[str, Any] | None:
    """Detecta colunas cujo domínio observado é restrito a 0/1, ignorando NULL."""
    if _motivo_exclusao_booleano(
        engine,
        tabela,
        coluna,
        colunas_rejeitadas=colunas_rejeitadas,
    ):
        return None

    if not _tipo_compativel_booleano(tipo):
        return None

    try:
        distintos = _valores_distintos_coluna(engine, tabela, coluna)
    except Exception:
        return None

    if not distintos:
        return None

    normalizados = {_normalizar_valor_booleano(valor) for valor in distintos}
    if None in normalizados:
        return None

    try:
        if _existe_valor_fora_booleano(engine, tabela, coluna):
            return None
    except Exception:
        return None

    try:
        possui_nulos = _existe_valor_nulo(engine, tabela, coluna)
    except Exception:
        possui_nulos = False

    return {
        "fonte": "provavel_booleano",
        "valor": (
            "Domínio sem valores fora de 0/1 e amostra de distintos "
            f"(limite={LIMITE_DISTINTOS_BOOLEANO}) restrita a 0/1; tipo compatível: {tipo}."
        ),
        "confianca": "media",
        "categoria": "provavel_booleano",
        "valores_observados": sorted(normalizados),
        "nulos_observados": possui_nulos,
        "amostra_distintos": [str(valor) for valor in distintos],
    }



def _compartilha_padrao_nome(alvo: str, candidato: str) -> bool:
    """Retorna True quando duas colunas compartilham prefixo/sufixo relevante."""
    alvo_tokens = [parte for parte in alvo.lower().split("_") if parte]
    candidato_tokens = [parte for parte in candidato.lower().split("_") if parte]
    if alvo_tokens and candidato_tokens:
        if len(alvo_tokens) > 1 and len(candidato_tokens) > 1:
            if alvo_tokens[0] == candidato_tokens[0] or alvo_tokens[-1] == candidato_tokens[-1]:
                return True
        comum = set(alvo_tokens) & set(candidato_tokens)
        if comum:
            return True

    tamanho = min(len(alvo), len(candidato), 5)
    prefixo = alvo[:tamanho]
    sufixo = alvo[-tamanho:]
    prefixo_util = len(prefixo.strip("_")) >= 3 and candidato.startswith(prefixo)
    sufixo_util = len(sufixo.strip("_")) >= 3 and candidato.endswith(sufixo)
    return prefixo_util or sufixo_util



def _pistas_colunas_irmas(engine: Engine, tabela: str, coluna: str) -> list[dict[str, str]]:
    """Busca colunas irmãs já traduzidas manualmente na mesma tabela."""
    candidatas = listar_colunas_schema(engine, tabela)
    pistas: list[dict[str, str]] = []

    for candidata in candidatas:
        nome_candidata = candidata["coluna"]
        if nome_candidata.lower() == coluna.lower():
            continue
        if candidata["estado"] != "traduzida_manual":
            continue
        if not _compartilha_padrao_nome(coluna, nome_candidata):
            continue

        pistas.append(
            {
                "fonte": "colunas_irmas",
                "valor": (
                    f"Coluna irmã '{nome_candidata}' já traduzida manualmente como "
                    f"'{candidata['traducao_atual']}'."
                ),
                "confianca": "media",
                "coluna_relacionada": nome_candidata,
                "traducao_relacionada": candidata["traducao_atual"],
            }
        )

    return pistas[:3]



def _base_relacional(nome_coluna: str) -> str | None:
    """Extrai a entidade-base de um nome relacional."""
    nome = nome_coluna.lower()
    if nome.endswith("_id") and len(nome) > 3:
        return nome[:-3]
    if nome.endswith("id") and nome != "id" and len(nome) > 2:
        return nome[:-2].rstrip("_")
    return None



def _inferir_tabela_relacionada(engine: Engine, tabela: str, coluna: str) -> str | None:
    """Infere tabela relacionada via FK explícita ou heurística de nome."""
    insp = inspect(engine)

    for fk in insp.get_foreign_keys(tabela):
        colunas = [str(item).lower() for item in fk.get("constrained_columns") or []]
        if coluna.lower() in colunas:
            tabela_ref = fk.get("referred_table")
            if tabela_ref:
                return str(tabela_ref)

    base = _base_relacional(coluna)
    if not base:
        return None

    tabelas = {nome.lower(): nome for nome in _listar_tabelas_validas(engine)}
    candidatas = [
        base,
        f"{base}s",
        f"{base}es",
        base.rstrip("s"),
    ]
    for candidata in candidatas:
        if candidata.lower() in tabelas:
            return tabelas[candidata.lower()]
    return None



def _pista_fk_referencia(engine: Engine, tabela: str, coluna: str) -> dict[str, str] | None:
    """Cria pista quando a coluna aparenta referenciar outra tabela."""
    tabela_ref = _inferir_tabela_relacionada(engine, tabela, coluna)
    if not tabela_ref:
        return None

    base = _base_relacional(coluna) or tabela_ref.rstrip("s")
    sugestao = None
    traducao_base = traduzir_nome_coluna(base)
    if traducao_base != _fallback_trivial(base):
        sugestao = _traduzir_coluna_relacional(f"{base}_id") or traducao_base

    pista: dict[str, str] = {
        "fonte": "fk_referencia",
        "valor": f"Possível referência à tabela '{tabela_ref}'.",
        "confianca": "media",
        "tabela_referencia": tabela_ref,
    }
    if sugestao:
        pista["sugestao"] = sugestao
    return pista



def _pista_column_comment(engine: Engine, tabela: str, coluna: str) -> dict[str, str] | None:
    """Consulta COLUMN_COMMENT quando disponível no banco alvo."""
    sql = text(
        "SELECT COLUMN_COMMENT FROM information_schema.COLUMNS "
        "WHERE TABLE_NAME=:t AND COLUMN_NAME=:c"
    )

    def _executar() -> dict[str, str] | None:
        with engine.connect() as conn:
            resultado = conn.execute(sql, {"t": tabela, "c": coluna})
            row = resultado.fetchone()
            if row and row[0]:
                return {
                    "fonte": "column_comment",
                    "valor": str(row[0]),
                    "confianca": "alta_confianca",
                    "sugestao": str(row[0]),
                }
            return None

    try:
        return executar_com_retry_db(
            _executar,
            descricao=f"Consultar comment de {tabela}.{coluna}",
        )
    except Exception:
        return None



def coletar_pistas_coluna(
    engine: Engine,
    tabela: str,
    coluna: str,
    tipo: str,
    *,
    colunas_rejeitadas: set[str] | None = None,
) -> dict[str, Any]:
    """Coleta pistas estruturais para entender o significado de uma coluna."""
    pistas: list[dict[str, str]] = []

    pista_comment = _pista_column_comment(engine, tabela, coluna)
    if pista_comment:
        pistas.append(pista_comment)

    pista_booleana = _pista_provavel_booleano(
        engine,
        tabela,
        coluna,
        tipo,
        colunas_rejeitadas=colunas_rejeitadas,
    )
    if pista_booleana:
        pistas.append(pista_booleana)

    pista_tipo = _classificar_tipo_dado(tipo)
    if pista_tipo:
        pistas.append(pista_tipo)

    pistas.extend(_pistas_colunas_irmas(engine, tabela, coluna))

    pista_fk = _pista_fk_referencia(engine, tabela, coluna)
    if pista_fk:
        pistas.append(pista_fk)

    return {"pistas": pistas}



def _determinar_confianca_nome(
    estado: str,
    traducao_atual: str,
    coluna: str,
    pistas: list[dict[str, Any]],
) -> tuple[str, str | None]:
    """Determina a confiança da tradução do nome, independente do domínio de valores."""
    sugestao_candidata: str | None = None
    nivel_confianca_nome = "sem_pista"

    if estado == "traduzida_manual":
        sugestao_candidata = traducao_atual
        nivel_confianca_nome = "traduzida_manual"
    else:
        pista_alta = next((p for p in pistas if p["confianca"] == "alta_confianca"), None)
        pista_media = next((p for p in pistas if p["confianca"] == "media"), None)

        if pista_alta is not None:
            sugestao_candidata = pista_alta.get("sugestao") or pista_alta["valor"]
            nivel_confianca_nome = "alta_confianca"
        elif _traduzir_coluna_relacional(coluna.lower()) is not None:
            sugestao_candidata = traducao_atual
            nivel_confianca_nome = "alta_confianca"
        elif estado == "traduzida_heuristica":
            sugestao_candidata = traducao_atual
            nivel_confianca_nome = "pista_parcial"
        elif pista_media is not None:
            sugestao_candidata = pista_media.get("sugestao") or pista_media.get("traducao_relacionada")
            nivel_confianca_nome = "pista_parcial"

    return nivel_confianca_nome, sugestao_candidata



def investigar_coluna(
    engine: Engine,
    tabela: str,
    coluna: str,
    *,
    colunas_rejeitadas: set[str] | None = None,
    decisoes_booleanos: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Executa a investigação completa de uma coluna específica."""
    colunas = listar_colunas_schema(engine, tabela)
    alvo = next((item for item in colunas if item["coluna"].lower() == coluna.lower()), None)
    if not alvo:
        raise ValueError(f"Coluna não encontrada: {tabela}.{coluna}")

    estado = alvo["estado"]
    traducao_atual = alvo["traducao_atual"]
    pistas = coletar_pistas_coluna(
        engine,
        tabela,
        alvo["coluna"],
        alvo["tipo"],
        colunas_rejeitadas=colunas_rejeitadas,
    )["pistas"]
    pista_booleana = next((p for p in pistas if p.get("categoria") == "provavel_booleano"), None)
    nivel_confianca_nome, sugestao_candidata = _determinar_confianca_nome(
        estado,
        traducao_atual,
        alvo["coluna"],
        pistas,
    )

    resultado = {
        "tabela": tabela,
        "coluna": alvo["coluna"],
        "tipo": alvo["tipo"],
        "estado": estado,
        "traducao_atual": traducao_atual,
        "pistas": pistas,
        "sugestao_candidata": sugestao_candidata,
        "nivel_confianca": nivel_confianca_nome,
        "nivel_confianca_nome": nivel_confianca_nome,
        "classificacao_valores": "provavel_booleano" if pista_booleana is not None else None,
        "provavel_booleano": pista_booleana is not None,
    }
    if decisoes_booleanos:
        sincronizar_decisoes_booleanos_relatorio(
            {"investigacoes": [resultado]},
            decisoes_booleanos,
        )
    return resultado



def investigar_tabela(
    engine: Engine,
    tabela: str,
    *,
    colunas_rejeitadas: set[str] | None = None,
    decisoes_booleanos: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Investiga todas as colunas de uma tabela."""
    return [
        investigar_coluna(
            engine,
            tabela,
            coluna["coluna"],
            colunas_rejeitadas=colunas_rejeitadas,
            decisoes_booleanos=decisoes_booleanos,
        )
        for coluna in listar_colunas_schema(engine, tabela)
    ]



def salvar_yaml(dados: dict[str, Any], caminho: str | Path) -> None:
    """Salva o relatório em YAML preservando unicode."""
    Path(caminho).write_text(
        yaml.safe_dump(dados, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _agrupar_colunas_booleanas(investigacoes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Agrupa as colunas marcadas como provável booleano por tabela."""
    resultado: dict[str, list[dict[str, Any]]] = {}

    for item in investigacoes:
        if not item.get("provavel_booleano"):
            continue
        pista = next(
            (p for p in item.get("pistas", []) if p.get("categoria") == "provavel_booleano"),
            None,
        )
        resultado.setdefault(str(item["tabela"]), []).append(
            {
                "coluna": item["coluna"],
                "tipo": item["tipo"],
                "valores_observados": [] if pista is None else pista.get("valores_observados", []),
                "nulos_observados": False if pista is None else bool(pista.get("nulos_observados")),
            }
        )

    return resultado


def executar_investigacao_colunas(
    engine: Engine | None = None,
    tabela: str | None = None,
    colunas_diretas: list[str] | None = None,
    caminho_saida: str = ARQUIVO_RELATORIO_COLUNAS_PADRAO,
    caminho_decisoes_booleanos: str | None = ARQUIVO_DECISOES_BOOLEANOS_PADRAO,
) -> dict[str, Any]:
    """Executa o fluxo completo de investigação de nomes de coluna."""
    engine_local = engine or criar_engine()
    criou_engine = engine is None

    try:
        with _CACHE_BOOLEANOS_LOCK:
            _COLUNAS_PK_CACHE.pop(engine_local, None)
            _COLUNAS_FK_CACHE.pop(engine_local, None)
        investigacoes: list[dict[str, Any]] = []
        decisoes_booleanos = (
            carregar_decisoes_booleanos(caminho_decisoes_booleanos)
            if caminho_decisoes_booleanos
            else _estrutura_decisoes_booleanos_padrao()
        )
        rejeitadas = colunas_rejeitadas_booleanos(decisoes_booleanos)

        if colunas_diretas:
            for tabela_alvo, coluna_alvo in _parsear_colunas_diretas(colunas_diretas):
                investigacoes.append(
                    investigar_coluna(
                        engine_local,
                        tabela_alvo,
                        coluna_alvo,
                        colunas_rejeitadas=rejeitadas,
                        decisoes_booleanos=decisoes_booleanos,
                    )
                )
        elif tabela:
            investigacoes.extend(
                investigar_tabela(
                    engine_local,
                    tabela,
                    colunas_rejeitadas=rejeitadas,
                    decisoes_booleanos=decisoes_booleanos,
                )
            )
        else:
            for nome_tabela in _listar_tabelas_validas(engine_local):
                investigacoes.extend(
                    investigar_tabela(
                        engine_local,
                        nome_tabela,
                        colunas_rejeitadas=rejeitadas,
                        decisoes_booleanos=decisoes_booleanos,
                    )
                )

        resumo_nome = {
            "traduzidas_manual": sum(
                1 for item in investigacoes if item["nivel_confianca_nome"] == "traduzida_manual"
            ),
            "alta_confianca": sum(
                1 for item in investigacoes if item["nivel_confianca_nome"] == "alta_confianca"
            ),
            "pista_parcial": sum(
                1 for item in investigacoes if item["nivel_confianca_nome"] == "pista_parcial"
            ),
            "sem_pista": sum(1 for item in investigacoes if item["nivel_confianca_nome"] == "sem_pista"),
        }
        resumo = {
            "total_investigadas": len(investigacoes),
            "provavel_booleano": sum(1 for item in investigacoes if item["provavel_booleano"]),
            "classificacao_nomes": resumo_nome,
            # Chaves planas mantidas por compatibilidade retroativa com consumidores
            # que ainda esperam o formato anterior do resumo no YAML/CLI.
            "traduzidas_manual": resumo_nome["traduzidas_manual"],
            "alta_confianca": resumo_nome["alta_confianca"],
            "pista_parcial": resumo_nome["pista_parcial"],
            "sem_pista": resumo_nome["sem_pista"],
        }

        relatorio = {
            "gerado_em": datetime.now(UTC).isoformat(),
            "resumo": resumo,
            "colunas_booleanas_provaveis": _agrupar_colunas_booleanas(investigacoes),
            "investigacoes": investigacoes,
        }
        sincronizar_decisoes_booleanos_relatorio(relatorio, decisoes_booleanos)
        salvar_yaml(relatorio, caminho_saida)
        return relatorio
    finally:
        if criou_engine:
            engine_local.dispose()
