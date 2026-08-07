"""Funções de investigação assistida de pendências de tradução de códigos/ENUM."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
import yaml

from src.db import criar_engine, executar_com_retry_db

ARQUIVO_AUDITORIA_PADRAO = "relatorio_auditoria_traducoes.yaml"
ARQUIVO_RELATORIO_INVESTIGACAO_PADRAO = "relatorio_investigacao_pendencias.yaml"
ARQUIVO_DICIONARIOS_PADRAO = "dicionarios.yaml"

_TIPOS_TEXTUAIS = ("char", "text", "enum", "set", "json", "clob")
_CHAVES_PISTA = (
    "name",
    "nome",
    "desc",
    "descricao",
    "description",
    "title",
    "titulo",
    "label",
    "text",
    "obs",
    "observacao",
)
# Palavras-chave que indicam coluna com nome semanticamente relacionado a
# rótulos/descrições — usadas para diferenciar "pista forte" de "pista fraca".
_CHAVES_SEMANTICAS = _CHAVES_PISTA


@dataclass(frozen=True)
class PendenciaEnum:
    """Representa uma pendência de tradução de valor de ENUM/código."""

    tabela: str
    coluna: str
    valor: str
    motivo: str = "sem_entrada_no_dicionario"


@dataclass(frozen=True)
class ColunaTabela:
    """Metadados simplificados de uma coluna de tabela."""

    nome: str
    tipo: str
    posicao: int



def _identificador(nome: str, dialect_name: str) -> str:
    if dialect_name == "mysql":
        return f"`{nome.replace('`', '``')}`"
    return f'"{nome.replace("\"", "\"\"")}"'



def _tipo_textual(tipo: str) -> bool:
    tipo_limpo = tipo.lower()
    return any(chave in tipo_limpo for chave in _TIPOS_TEXTUAIS)



def parsear_colunas_diretas(specs: list[str]) -> list[PendenciaEnum]:
    """Converte especificações ``tabela.coluna`` (ou ``tabela.coluna:valor``) em PendenciaEnum.

    Formato aceito:
    - ``tabela.coluna`` — investiga todos os valores pendentes (usa valor sentinela ``*``).
    - ``tabela.coluna:valor`` — investiga apenas o valor informado.

    Exemplo::

        parsear_colunas_diretas([
            "hearingcontrol.hearingtype:11",
            "pedidos2lawsuit.status:6",
            "hearingcontrol.needwitness",
        ])
    """
    resultado: list[PendenciaEnum] = []
    for spec in specs:
        spec = spec.strip()
        if not spec:
            continue
        # Separa "valor" do restante, se houver ":"
        if ":" in spec:
            parte_tabela_coluna, valor = spec.rsplit(":", 1)
        else:
            parte_tabela_coluna, valor = spec, "*"

        if "." not in parte_tabela_coluna:
            raise ValueError(
                f"Especificação inválida: '{spec}'. Use o formato 'tabela.coluna' ou 'tabela.coluna:valor'."
            )
        tabela, coluna = parte_tabela_coluna.split(".", 1)
        tabela = tabela.strip()
        coluna = coluna.strip()
        valor = valor.strip()

        if not tabela or not coluna:
            raise ValueError(f"Especificação inválida: '{spec}'. Tabela e coluna não podem ser vazias.")

        resultado.append(
            PendenciaEnum(
                tabela=tabela,
                coluna=coluna,
                valor=valor,
                motivo="investigacao_direta",
            )
        )
    return resultado



def carregar_pendencias_enum(caminho_relatorio: str | Path) -> list[PendenciaEnum]:
    """Carrega pendências ENUM/código do relatório YAML de auditoria."""
    caminho = Path(caminho_relatorio)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo de auditoria não encontrado: {caminho}")

    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    pendencias = dados.get("pendencias", {})

    resultado: list[PendenciaEnum] = []
    for tabela, bloco_tabela in pendencias.items():
        if not isinstance(bloco_tabela, dict):
            continue
        enums = bloco_tabela.get("enums", [])
        for bloco_enum in enums:
            coluna = str(bloco_enum.get("coluna", "")).strip()
            if not coluna:
                continue
            for item in bloco_enum.get("valores_pendentes", []):
                valor = str(item.get("valor", "")).strip()
                if not valor:
                    continue
                motivo = str(item.get("motivo", "sem_entrada_no_dicionario"))
                resultado.append(PendenciaEnum(tabela=str(tabela), coluna=coluna, valor=valor, motivo=motivo))

    # Dedup mantendo ordem
    vistos: set[tuple[str, str, str]] = set()
    dedup: list[PendenciaEnum] = []
    for item in resultado:
        chave = (item.tabela, item.coluna, item.valor)
        if chave in vistos:
            continue
        vistos.add(chave)
        dedup.append(item)
    return dedup



def listar_colunas_tabela(engine: Engine, tabela: str) -> list[ColunaTabela]:
    """Lista colunas da tabela com tipo e posição ordinal."""
    insp = inspect(engine)
    colunas = insp.get_columns(tabela)
    return [
        ColunaTabela(
            nome=str(coluna.get("name", "")),
            tipo=str(coluna.get("type", "")).lower(),
            posicao=indice,
        )
        for indice, coluna in enumerate(colunas)
    ]



def selecionar_colunas_pista(
    colunas: list[ColunaTabela],
    coluna_codigo: str,
    *,
    limite: int = 6,
) -> list[str]:
    """Seleciona colunas vizinhas candidatas a pista textual."""
    if not colunas:
        return []

    indice_alvo = next((c.posicao for c in colunas if c.nome.lower() == coluna_codigo.lower()), None)
    if indice_alvo is None:
        return []

    pontuadas: list[tuple[int, int, str]] = []
    for coluna in colunas:
        nome = coluna.nome.lower()
        if nome == coluna_codigo.lower():
            continue

        score = 0
        if _tipo_textual(coluna.tipo):
            score += 3
        if any(chave in nome for chave in _CHAVES_PISTA):
            score += 5
        if nome in {"id", "created_at", "updated_at"}:
            score -= 2

        if score <= 0:
            continue

        distancia = abs(coluna.posicao - indice_alvo)
        # score desc, distancia asc
        pontuadas.append((-score, distancia, coluna.nome))

    pontuadas.sort()
    return [nome for _, _, nome in pontuadas[:limite]]



def _converter_valor_para_param(valor: str) -> Any:
    """Converte o valor string para int quando for numérico.

    Isso garante que comparações com colunas inteiras no MySQL e SQLite
    funcionem corretamente (evita falso negativo por incompatibilidade de tipo).
    Usa correspondência de padrão estrita para evitar false positives com
    caracteres Unicode ou strings como '--3'.
    """
    if re.fullmatch(r"-?\d+", valor):
        try:
            return int(valor)
        except ValueError:
            pass
    return valor



def _coletar_linhas_exemplo(
    engine: Engine,
    pendencia: PendenciaEnum,
    colunas_pista: list[str],
    *,
    limite_linhas: int,
) -> list[dict[str, Any]]:
    tabela_sql = _identificador(pendencia.tabela, engine.dialect.name)
    coluna_sql = _identificador(pendencia.coluna, engine.dialect.name)
    colunas_sql = ", ".join(_identificador(col, engine.dialect.name) for col in colunas_pista)

    sql = text(
        f"SELECT {colunas_sql} "
        f"FROM {tabela_sql} "
        f"WHERE {coluna_sql} = :valor "
        f"LIMIT {int(limite_linhas)}"
    )

    # Converte para int quando numérico para compatibilidade com colunas
    # inteiras no MySQL, evitando falso negativo por diferença de tipo.
    param_valor = _converter_valor_para_param(pendencia.valor)

    def _executar() -> list[dict[str, Any]]:
        with engine.connect() as conn:
            res = conn.execute(sql, {"valor": param_valor})
            return [dict(row._mapping) for row in res.fetchall()]

    return executar_com_retry_db(_executar, descricao=f"Investigar {pendencia.tabela}.{pendencia.coluna}")



def _coluna_tem_nome_semantico(nome: str) -> bool:
    """Retorna True quando o nome da coluna sugere que ela é um rótulo/descrição.

    Colunas com nomes como ``name``, ``descricao``, ``title`` etc. são candidatas
    a conter texto descritivo do código investigado — são "pistas fortes".
    Colunas puramente booleanas/numéricas (ex: ``hearingfile``, ``dispensed``)
    são "pistas fracas" que não indicam o significado semântico do código.
    """
    nome_lower = nome.lower()
    return any(chave in nome_lower for chave in _CHAVES_SEMANTICAS)



def _pista_e_booleana(valores_frequentes: list[dict[str, Any]]) -> bool:
    """Retorna True quando todos os valores observados são exclusivamente '0' ou '1'.

    Isso identifica colunas booleanas, que costumam ter valor constante em qualquer
    amostra pequena e não revelam o significado semântico do código investigado.
    """
    vals = {str(item["valor"]).strip() for item in valores_frequentes}
    return vals.issubset({"0", "1"})



def _analisar_pistas(
    pendencia: PendenciaEnum,
    linhas: list[dict[str, Any]],
    colunas_pista: list[str],
) -> dict[str, Any]:
    if not linhas:
        return {
            "status": "sem_registros",
            "traducao_sugerida": None,
            "justificativa": "Nenhuma linha encontrada para este valor.",
            "pistas": [],
        }

    pistas: list[dict[str, Any]] = []
    for coluna in colunas_pista:
        valores = []
        for linha in linhas:
            valor = linha.get(coluna)
            if valor is None:
                continue
            texto = str(valor).strip()
            if not texto:
                continue
            if texto.lower() == pendencia.valor.lower():
                continue
            valores.append(texto)

        if not valores:
            continue

        contagem = Counter(valores)
        pistas.append(
            {
                "coluna": coluna,
                "valores_frequentes": [
                    {"valor": valor, "ocorrencias": qtd}
                    for valor, qtd in contagem.most_common(3)
                ],
                "valores_distintos": len(contagem),
                "ocorrencias_total": sum(contagem.values()),
            }
        )

    if not pistas:
        return {
            "status": "sem_pista_encontrada",
            "traducao_sugerida": None,
            "justificativa": "Foram encontradas linhas, mas sem pista textual clara.",
            "pistas": [],
        }

    # Alta confiança só quando o indício textual é único e consistente em
    # múltiplas linhas E a coluna-pista tem nome semanticamente relacionado a
    # rótulos/descrições (pista forte). Colunas booleanas (valores só 0/1) ou
    # com nomes puramente técnicos (pista fraca) não são suficientes para alta
    # confiança, pois qualquer amostra pequena terá valor constante nesses campos.
    for pista in pistas:
        if pista["valores_distintos"] != 1 or pista["ocorrencias_total"] < 2:
            continue
        unico = pista["valores_frequentes"][0]["valor"]
        tem_nome_semantico = _coluna_tem_nome_semantico(pista["coluna"])
        e_booleana = _pista_e_booleana(pista["valores_frequentes"])
        if tem_nome_semantico and not e_booleana:
            return {
                "status": "alta_confianca",
                "traducao_sugerida": unico,
                "justificativa": (
                    f"Coluna '{pista['coluna']}' (pista forte — nome semântico) "
                    f"apresentou valor único e consistente "
                    f"em múltiplas linhas para o código '{pendencia.valor}'."
                ),
                "pistas": pistas,
            }

    for pista in pistas:
        # "pista_unica" só é usada quando existe apenas um indício textual
        # disponível. Se houver múltiplos valores distintos nas pistas, não há
        # confiança suficiente para sugerir tradução automática.
        # Pistas fracas (colunas booleanas ou sem nome semântico) com valor único
        # em múltiplas linhas também caem aqui em vez de alta_confianca.
        if pista["valores_distintos"] == 1 and pista["ocorrencias_total"] >= 1:
            unico = pista["valores_frequentes"][0]["valor"]
            e_booleana = _pista_e_booleana(pista["valores_frequentes"])
            tem_nome_semantico = _coluna_tem_nome_semantico(pista["coluna"])
            if e_booleana or not tem_nome_semantico:
                return {
                    "status": "pista_unica",
                    "traducao_sugerida": unico,
                    "justificativa": (
                        f"Coluna '{pista['coluna']}' (pista fraca — "
                        + ("coluna booleana" if e_booleana else "nome sem relação semântica")
                        + f") apresentou valor único '{unico}' nas linhas de exemplo, "
                        "mas isso não é evidência suficiente do significado do código. "
                        "Revise manualmente antes de aplicar."
                    ),
                    "pistas": pistas,
                }
            return {
                "status": "pista_unica",
                "traducao_sugerida": unico,
                "justificativa": (
                    f"Coluna '{pista['coluna']}' (pista forte) tem apenas uma ocorrência "
                    f"de exemplo para o código '{pendencia.valor}'. "
                    "Sugestão útil para revisão, mas sem confiança alta (amostra pequena)."
                ),
                "pistas": pistas,
            }

    return {
        "status": "sem_pista_encontrada",
        "traducao_sugerida": None,
        "justificativa": "Há pistas textuais, mas sem consistência suficiente para alta confiança.",
        "pistas": pistas,
    }



def investigar_pendencias(
    engine: Engine,
    pendencias: list[PendenciaEnum],
    *,
    limite_linhas: int = 5,
) -> dict[str, Any]:
    """Investiga pendências de código/ENUM consultando exemplos reais no banco."""
    limite_linhas = max(2, int(limite_linhas))
    investigacoes: list[dict[str, Any]] = []

    for pendencia in pendencias:
        try:
            colunas = executar_com_retry_db(
                lambda tabela=pendencia.tabela, engine_ref=engine: listar_colunas_tabela(
                    engine_ref, tabela
                ),
                descricao=f"Listar colunas de {pendencia.tabela}",
            )
            colunas_pista = selecionar_colunas_pista(colunas, pendencia.coluna)
            if not colunas_pista:
                investigacoes.append(
                    {
                        "tabela": pendencia.tabela,
                        "coluna": pendencia.coluna,
                        "valor": pendencia.valor,
                        "motivo_pendencia": pendencia.motivo,
                        "colunas_pista": [],
                        "linhas_exemplo": [],
                        "sugestao": {
                            "status": "sem_pista_encontrada",
                            "traducao_sugerida": None,
                            "justificativa": "Nenhuma coluna vizinha candidata a pista foi identificada.",
                            "pistas": [],
                        },
                    }
                )
                continue

            linhas = _coletar_linhas_exemplo(
                engine,
                pendencia,
                colunas_pista,
                limite_linhas=limite_linhas,
            )
            sugestao = _analisar_pistas(pendencia, linhas, colunas_pista)

            investigacoes.append(
                {
                    "tabela": pendencia.tabela,
                    "coluna": pendencia.coluna,
                    "valor": pendencia.valor,
                    "motivo_pendencia": pendencia.motivo,
                    "colunas_pista": colunas_pista,
                    "linhas_exemplo": linhas,
                    "sugestao": sugestao,
                }
            )
        except Exception as exc:
            investigacoes.append(
                {
                    "tabela": pendencia.tabela,
                    "coluna": pendencia.coluna,
                    "valor": pendencia.valor,
                    "motivo_pendencia": pendencia.motivo,
                    "colunas_pista": [],
                    "linhas_exemplo": [],
                    "sugestao": {
                        "status": "erro",
                        "traducao_sugerida": None,
                        "justificativa": f"Falha ao investigar: {exc}",
                        "pistas": [],
                    },
                }
            )

    resumo = {
        "total_pendencias": len(investigacoes),
        "alta_confianca": sum(1 for i in investigacoes if i["sugestao"]["status"] == "alta_confianca"),
        "pista_unica": sum(1 for i in investigacoes if i["sugestao"]["status"] == "pista_unica"),
        "sem_pista_encontrada": sum(
            1 for i in investigacoes if i["sugestao"]["status"] == "sem_pista_encontrada"
        ),
        "sem_registros": sum(1 for i in investigacoes if i["sugestao"]["status"] == "sem_registros"),
        "erros": sum(1 for i in investigacoes if i["sugestao"]["status"] == "erro"),
    }

    return {
        "gerado_em_utc": datetime.now(UTC).isoformat(),
        "resumo": resumo,
        "investigacoes": investigacoes,
    }



def salvar_yaml(dados: dict[str, Any], caminho: str | Path) -> None:
    """Salva estrutura em YAML mantendo unicode e ordenação original."""
    Path(caminho).write_text(
        yaml.safe_dump(dados, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )



def carregar_yaml(caminho: str | Path) -> dict[str, Any]:
    """Carrega um arquivo YAML em dicionário."""
    conteudo = yaml.safe_load(Path(caminho).read_text(encoding="utf-8"))
    return conteudo if isinstance(conteudo, dict) else {}



def gerar_template_decisoes(relatorio: dict[str, Any]) -> dict[str, Any]:
    """Gera template de decisões para modo não interativo."""
    itens = []
    for item in relatorio.get("investigacoes", []):
        sugestao = item.get("sugestao", {})
        itens.append(
            {
                "tabela": item.get("tabela"),
                "coluna": item.get("coluna"),
                "valor": item.get("valor"),
                "status_sugestao": sugestao.get("status"),
                "traducao_sugerida": sugestao.get("traducao_sugerida"),
                "decisao": "pendente",  # aplicar | pular
                "traducao_final": None,
            }
        )
    return {"decisoes": itens}



def aplicar_decisoes_em_dicionario(
    dicionarios: dict[str, Any],
    decisoes: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Aplica decisões aprovadas na estrutura de dicionários em memória."""
    aplicadas: list[dict[str, str]] = []

    for item in decisoes:
        if str(item.get("decisao", "")).lower() != "aplicar":
            continue

        tabela = str(item.get("tabela", "")).strip()
        coluna = str(item.get("coluna", "")).strip()
        valor = str(item.get("valor", "")).strip()
        traducao = item.get("traducao_final") or item.get("traducao_sugerida")
        traducao = str(traducao).strip() if traducao is not None else ""

        if not tabela or not coluna or not valor or not traducao:
            continue

        tabela_dict = dicionarios.setdefault(tabela, {})
        if not isinstance(tabela_dict, dict):
            continue
        coluna_dict = tabela_dict.setdefault(coluna, {})
        if not isinstance(coluna_dict, dict):
            continue

        coluna_dict[valor] = traducao
        aplicadas.append(
            {
                "tabela": tabela,
                "coluna": coluna,
                "valor": valor,
                "traducao": traducao,
            }
        )

    return dicionarios, aplicadas



def executar_investigacao(
    caminho_relatorio_auditoria: str | Path = ARQUIVO_AUDITORIA_PADRAO,
    caminho_saida: str | Path = ARQUIVO_RELATORIO_INVESTIGACAO_PADRAO,
    *,
    limite_linhas: int = 5,
    colunas_diretas: list[str] | None = None,
) -> dict[str, Any]:
    """Fluxo completo de investigação via banco real configurado em src.config.

    Parâmetros
    ----------
    caminho_relatorio_auditoria:
        Arquivo YAML de auditoria (ignorado quando ``colunas_diretas`` é fornecido).
    caminho_saida:
        Arquivo YAML de saída.
    limite_linhas:
        Máximo de linhas de exemplo por pendência.
    colunas_diretas:
        Quando informada, ignora o relatório de auditoria e investiga apenas as
        especificações fornecidas no formato ``"tabela.coluna"`` ou
        ``"tabela.coluna:valor"``.  Exemplo::

            executar_investigacao(colunas_diretas=[
                "hearingcontrol.hearingtype:11",
                "pedidos2lawsuit.status:6",
            ])
    """
    if colunas_diretas:
        pendencias = parsear_colunas_diretas(colunas_diretas)
        fonte = "colunas_diretas:" + ",".join(colunas_diretas)
    else:
        pendencias = carregar_pendencias_enum(caminho_relatorio_auditoria)
        fonte = str(caminho_relatorio_auditoria)

    engine = criar_engine()
    try:
        relatorio = investigar_pendencias(engine, pendencias, limite_linhas=limite_linhas)
        relatorio["fonte_pendencias"] = fonte
        salvar_yaml(relatorio, caminho_saida)
        return relatorio
    finally:
        engine.dispose()
