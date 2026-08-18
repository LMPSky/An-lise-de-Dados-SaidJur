"""Fluxo de investigação assistida para nomes de colunas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
import yaml

from src.db import criar_engine, executar_com_retry_db
from src.traducoes_colunas import (
    TRADUCOES_COLUNAS,
    _traduzir_coluna_relacional,
    traduzir_nome_coluna,
)

ARQUIVO_RELATORIO_COLUNAS_PADRAO = "relatorio_investigacao_colunas.yaml"
TABELAS_PRIORITARIAS_BOOLEANOS = (
    "lawsuits",
    "persons",
    "hearingcontrol",
    "prazos_log",
    "employees",
    "users",
)


@dataclass(frozen=True)
class ColunaSchema:
    """Representa uma coluna existente no schema."""

    tabela: str
    coluna: str
    tipo: str



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


def _valores_distintos_coluna(
    engine: Engine,
    tabela: str,
    coluna: str,
    *,
    limite: int = 10,
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
) -> dict[str, Any] | None:
    """Detecta colunas cujo domínio observado é restrito a 0/1/NULL."""
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

    return {
        "fonte": "provavel_booleano",
        "valor": (
            "Valores distintos observados restritos a 0/1/NULL; "
            f"tipo compatível: {tipo}."
        ),
        "confianca": "media",
        "categoria": "provavel_booleano",
        "valores_observados": sorted(normalizados),
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



def coletar_pistas_coluna(engine: Engine, tabela: str, coluna: str, tipo: str) -> dict[str, Any]:
    """Coleta pistas estruturais para entender o significado de uma coluna."""
    pistas: list[dict[str, str]] = []

    pista_comment = _pista_column_comment(engine, tabela, coluna)
    if pista_comment:
        pistas.append(pista_comment)

    pista_booleana = _pista_provavel_booleano(engine, tabela, coluna, tipo)
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



def investigar_coluna(engine: Engine, tabela: str, coluna: str) -> dict[str, Any]:
    """Executa a investigação completa de uma coluna específica."""
    colunas = listar_colunas_schema(engine, tabela)
    alvo = next((item for item in colunas if item["coluna"].lower() == coluna.lower()), None)
    if not alvo:
        raise ValueError(f"Coluna não encontrada: {tabela}.{coluna}")

    estado = alvo["estado"]
    traducao_atual = alvo["traducao_atual"]
    pistas = coletar_pistas_coluna(engine, tabela, alvo["coluna"], alvo["tipo"])["pistas"]

    sugestao_candidata: str | None = None
    nivel_confianca = "sem_pista"
    pista_booleana = next((p for p in pistas if p.get("categoria") == "provavel_booleano"), None)

    if pista_booleana is not None:
        nivel_confianca = "provavel_booleano"
    elif estado == "traduzida_manual":
        sugestao_candidata = traducao_atual
        nivel_confianca = "traduzida_manual"
    else:
        pista_alta = next((p for p in pistas if p["confianca"] == "alta_confianca"), None)
        pista_media = next((p for p in pistas if p["confianca"] == "media"), None)

        if pista_alta is not None:
            sugestao_candidata = pista_alta.get("sugestao") or pista_alta["valor"]
            nivel_confianca = "alta_confianca"
        elif _traduzir_coluna_relacional(alvo["coluna"].lower()) is not None:
            sugestao_candidata = traducao_atual
            nivel_confianca = "alta_confianca"
        elif estado == "traduzida_heuristica":
            sugestao_candidata = traducao_atual
            nivel_confianca = "pista_parcial"
        elif pista_media is not None:
            sugestao_candidata = pista_media.get("sugestao") or pista_media.get("traducao_relacionada")
            nivel_confianca = "pista_parcial"

    return {
        "tabela": tabela,
        "coluna": alvo["coluna"],
        "tipo": alvo["tipo"],
        "estado": estado,
        "traducao_atual": traducao_atual,
        "pistas": pistas,
        "sugestao_candidata": sugestao_candidata,
        "nivel_confianca": nivel_confianca,
        "provavel_booleano": pista_booleana is not None,
    }



def investigar_tabela(engine: Engine, tabela: str) -> list[dict[str, Any]]:
    """Investiga todas as colunas de uma tabela."""
    return [
        investigar_coluna(engine, tabela, coluna["coluna"])
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
        if item.get("nivel_confianca") != "provavel_booleano":
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
            }
        )

    return resultado


def executar_investigacao_colunas(
    engine: Engine | None = None,
    tabela: str | None = None,
    colunas_diretas: list[str] | None = None,
    caminho_saida: str = ARQUIVO_RELATORIO_COLUNAS_PADRAO,
) -> dict[str, Any]:
    """Executa o fluxo completo de investigação de nomes de coluna."""
    engine_local = engine or criar_engine()
    criou_engine = engine is None

    try:
        investigacoes: list[dict[str, Any]] = []

        if colunas_diretas:
            for tabela_alvo, coluna_alvo in _parsear_colunas_diretas(colunas_diretas):
                investigacoes.append(investigar_coluna(engine_local, tabela_alvo, coluna_alvo))
        elif tabela:
            investigacoes.extend(investigar_tabela(engine_local, tabela))
        else:
            for nome_tabela in _listar_tabelas_validas(engine_local):
                investigacoes.extend(investigar_tabela(engine_local, nome_tabela))

        # Os cinco grupos são mutuamente exclusivos e somam exatamente
        # ``total_investigadas``: cada item tem exatamente um ``nivel_confianca``.
        resumo = {
            "total_investigadas": len(investigacoes),
            "provavel_booleano": sum(1 for item in investigacoes if item["nivel_confianca"] == "provavel_booleano"),
            "traduzidas_manual": sum(1 for item in investigacoes if item["nivel_confianca"] == "traduzida_manual"),
            "alta_confianca": sum(1 for item in investigacoes if item["nivel_confianca"] == "alta_confianca"),
            "pista_parcial": sum(1 for item in investigacoes if item["nivel_confianca"] == "pista_parcial"),
            "sem_pista": sum(1 for item in investigacoes if item["nivel_confianca"] == "sem_pista"),
        }

        relatorio = {
            "gerado_em": datetime.now(UTC).isoformat(),
            "resumo": resumo,
            "colunas_booleanas_provaveis": _agrupar_colunas_booleanas(investigacoes),
            "investigacoes": investigacoes,
        }
        salvar_yaml(relatorio, caminho_saida)
        return relatorio
    finally:
        if criou_engine:
            engine_local.dispose()
