"""Funções de investigação assistida de pendências de tradução de códigos/ENUM."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import re
import unicodedata
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
import yaml

from src.db import criar_engine, executar_com_retry_db

ARQUIVO_AUDITORIA_PADRAO = "relatorio_auditoria_traducoes.yaml"
ARQUIVO_RELATORIO_INVESTIGACAO_PADRAO = "relatorio_investigacao_pendencias.yaml"
ARQUIVO_DICIONARIOS_PADRAO = "dicionarios.yaml"
ARQUIVO_PENDENCIAS_MARKDOWN_PADRAO = "PENDENCIAS_TRADUCAO_HUMANA.md"

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

_TEXTO_LIVRE_COMPRIMENTO_MIN = 50
_EXTENSOES_ARQUIVO_IGNORADAS = (
    ".yaml",
    ".yml",
    ".md",
    ".py",
    ".xlsx",
    ".json",
    ".diff",
    ".txt",
)

# Nomes de colunas de observação/texto-livre usadas como contexto complementar.
# Quando a coluna investigada não obtém tradução de alta confiança, a ferramenta
# agrega os valores dessas colunas correlacionadas para ajudar o usuário a inferir
# manualmente o significado do código.
_COLUNAS_OBSERVACAO_PADRAO: tuple[str, ...] = (
    "prazoobs",
    "obs",
    "observacao",
    "observacoes",
    "observacoesadv",
    "remarks",
    "comentario",
    "comentarios",
    "notas",
    "nota",
    "descricao",
    "anotacao",
    "anotacoes",
)

_SUFIXOS_OUTRO_IDIOMA = {
    "_english": "english",
    "_en": "en",
    "_es": "es",
}
_SUFIXOS_PORTUGUES = ("_pt", "_br")
_COLUNAS_CODIGO = ("code", "codigo", "status", "phase", "fase", "type", "tipo", "nature", "natureza", "link")
_GRUPOS_TABELAS_IRMAS = (
    ("pzphase", ("prazos_log", "prazo2publication", "lawsuitdocsmetadata")),
    ("finishtype", ("prazos_log", "prazo2publication", "lawsuitdocsmetadata")),
)


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


def _deduplicar_pendencias(pendencias: list[PendenciaEnum]) -> list[PendenciaEnum]:
    """Remove pendências repetidas, mantendo a ordem da primeira ocorrência."""
    vistos: set[tuple[str, str, str]] = set()
    return [
        item for item in pendencias
        if not ((chave := (item.tabela, item.coluna, item.valor)) in vistos or vistos.add(chave))
    ]


def _normalizar_celula_markdown(celula: str) -> str:
    """Normaliza uma célula de cabeçalho Markdown para comparação estrutural."""
    sem_acentos = "".join(
        char
        for char in unicodedata.normalize("NFKD", celula.lower())
        if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", "", sem_acentos)


def _extrair_identificadores_markdown(celula: str) -> list[str]:
    """Extrai identificadores entre crases, ignorando nomes de arquivo."""
    identificadores: list[str] = []
    for token in re.findall(r"`([^`]+)`", celula):
        token = token.strip()
        if token.lower().endswith(_EXTENSOES_ARQUIVO_IGNORADAS):
            continue
        if re.fullmatch(r"[A-Za-z_][\w]*", token):
            identificadores.append(token)
    return identificadores


def _extrair_valores_markdown(celula: str) -> list[str]:
    """Extrai valores documentados em uma célula de domínio Markdown."""
    valores: list[str] = []
    if ".." in celula or "–" in celula:
        return []
    grupos = re.findall(r"\{([^}]*)\}", celula)
    if grupos:
        candidatos = [valor for grupo in grupos for valor in grupo.split(",")]
    else:
        candidatos = re.findall(r"`([^`]+)`", celula)

    for candidato in candidatos:
        valor = candidato.strip()
        if not valor or ".." in valor or "–" in valor:
            continue
        if valor.lower().endswith(_EXTENSOES_ARQUIVO_IGNORADAS):
            continue
        valores.append(valor)
    return valores


def _cabecalho_tabela_pendencia_enum(celulas: list[str]) -> bool:
    """Indica se o cabeçalho descreve pendências de valores/ENUM."""
    if len(celulas) < 3:
        return False
    terceira = _normalizar_celula_markdown(celulas[2])
    return (
        _normalizar_celula_markdown(celulas[0]) == "tabela"
        and _normalizar_celula_markdown(celulas[1]) == "coluna"
        and ("valor" in terceira or "dominio" in terceira)
    )


def carregar_pendencias_markdown(caminho_markdown: str | Path) -> list[PendenciaEnum]:
    """Extrai pendências documentadas em tabelas Markdown estruturadas.

    Apenas tabelas em seções de pendências cujo cabeçalho começa com ``Tabela``
    e ``Coluna`` são consideradas. Exemplos em texto corrido, comandos entre
    crases e blocos de código são ignorados para evitar falsos positivos como
    nomes de arquivo.
    """
    caminho = Path(caminho_markdown)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo de pendências não encontrado: {caminho}")
    resultado: list[PendenciaEnum] = []

    dentro_bloco_codigo = False
    tabela_pendencias = False
    secao_pendencias = False
    nivel_secao_pendencias = 0
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if linha.lstrip().startswith("```"):
            dentro_bloco_codigo = not dentro_bloco_codigo
            tabela_pendencias = False
            continue
        if dentro_bloco_codigo:
            continue
        cabecalho = re.match(r"^(#{2,6})\s+(.+)$", linha.strip())
        if cabecalho:
            nivel = len(cabecalho.group(1))
            titulo = cabecalho.group(2).lower()
            if "pend" in titulo:
                secao_pendencias = True
                nivel_secao_pendencias = nivel
            elif secao_pendencias and nivel <= nivel_secao_pendencias:
                secao_pendencias = False
                nivel_secao_pendencias = 0
            tabela_pendencias = False
            continue
        if not linha.lstrip().startswith("|"):
            tabela_pendencias = False
            continue
        if not secao_pendencias:
            continue
        celulas = [celula.strip() for celula in linha.strip().strip("|").split("|")]
        if len(celulas) < 2:
            tabela_pendencias = False
            continue
        if set("".join(celulas)) <= {"-", ":", " "}:
            continue
        if _cabecalho_tabela_pendencia_enum(celulas):
            tabela_pendencias = True
            continue
        if not tabela_pendencias:
            continue

        tabelas = _extrair_identificadores_markdown(celulas[0])
        colunas = _extrair_identificadores_markdown(celulas[1])
        if not tabelas or not colunas:
            continue
        dominio = _extrair_valores_markdown(celulas[2] if len(celulas) > 2 else "") or ["*"]
        for tabela in tabelas:
            for coluna in colunas:
                resultado.extend(
                    PendenciaEnum(tabela, coluna, valor, "pendencia_documentada")
                    for valor in dominio
                )
    return _deduplicar_pendencias(resultado)



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


def _valores_distintos_coluna(
    engine: Engine,
    tabela: str,
    coluna: str,
    *,
    limite: int = 20,
) -> list[str]:
    """Obtém valores curtos distintos de uma coluna, sem coletar texto livre."""
    tabela_sql = _identificador(tabela, engine.dialect.name)
    coluna_sql = _identificador(coluna, engine.dialect.name)
    sql = text(
        f"SELECT CAST({coluna_sql} AS CHAR) AS valor FROM {tabela_sql} "
        f"WHERE {coluna_sql} IS NOT NULL "
        f"AND TRIM(CAST({coluna_sql} AS CHAR)) <> '' "
        f"GROUP BY CAST({coluna_sql} AS CHAR) "
        f"LIMIT {int(limite) + 1}"
    )
    with engine.connect() as conn:
        valores = [str(row[0]).strip() for row in conn.execute(sql).fetchall()]
    return valores if len(valores) <= limite else []


def _coluna_parece_codigo(coluna: ColunaTabela) -> bool:
    """Indica se uma coluna é candidata conservadora a código/ENUM curto."""
    nome = coluna.nome.lower()
    return _tipo_textual(coluna.tipo) or any(chave in nome for chave in _COLUNAS_CODIGO)


def descobrir_pendencias_schema(engine: Engine, dicionarios: dict[str, Any]) -> list[PendenciaEnum]:
    """Descobre códigos curtos sem tradução diretamente por introspecção do schema."""
    resultado: list[PendenciaEnum] = []
    for tabela in inspect(engine).get_table_names():
        traducoes_tabela = dicionarios.get(tabela, {})
        if not isinstance(traducoes_tabela, dict):
            traducoes_tabela = {}
        for coluna in listar_colunas_tabela(engine, tabela):
            if not _coluna_parece_codigo(coluna):
                continue
            traducoes_coluna = traducoes_tabela.get(coluna.nome, {})
            if not isinstance(traducoes_coluna, dict):
                traducoes_coluna = {}
            for valor in _valores_distintos_coluna(engine, tabela, coluna.nome):
                if len(valor) > 40 or _pista_parece_texto_livre(valor):
                    continue
                if valor not in traducoes_coluna:
                    resultado.append(PendenciaEnum(tabela, coluna.nome, valor, "descoberta_schema"))
    return _deduplicar_pendencias(resultado)


def expandir_pendencias_com_dominio(engine: Engine, pendencias: list[PendenciaEnum]) -> list[PendenciaEnum]:
    """Expande o sentinela ``*`` nos valores distintos observados no banco.

    Pendências vindas do Markdown são validadas por introspecção leve antes da
    primeira consulta de domínio. Tabelas ou colunas inexistentes são descartadas
    para que referências obsoletas/falsos positivos não interrompam o lote.
    """
    resultado: list[PendenciaEnum] = []
    insp = inspect(engine)
    tabelas_por_lower = {tabela.lower(): tabela for tabela in insp.get_table_names()}
    colunas_por_tabela: dict[str, dict[str, str]] = {}

    for pendencia in pendencias:
        tabela_real = tabelas_por_lower.get(pendencia.tabela.lower())
        if not tabela_real:
            continue
        if tabela_real not in colunas_por_tabela:
            colunas_por_tabela[tabela_real] = {
                str(coluna.get("name", "")).lower(): str(coluna.get("name", ""))
                for coluna in insp.get_columns(tabela_real)
            }
        coluna_real = colunas_por_tabela[tabela_real].get(pendencia.coluna.lower())
        if not coluna_real:
            continue

        if pendencia.valor == "*":
            resultado.extend(
                PendenciaEnum(tabela_real, coluna_real, valor, pendencia.motivo)
                for valor in _valores_distintos_coluna(engine, tabela_real, coluna_real)
            )
        else:
            resultado.append(PendenciaEnum(tabela_real, coluna_real, pendencia.valor, pendencia.motivo))
    return _deduplicar_pendencias(resultado)



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
    candidatas = [nome for _, _, nome in pontuadas[:limite]]
    return _reordenar_colunas_pista_por_idioma(candidatas, [coluna.nome for coluna in colunas])



def _normalizar_token_schema(valor: str) -> str:
    """Normaliza nomes de tabela/coluna para comparação heurística."""
    return re.sub(r"[^a-z0-9]+", "", valor.lower())



def _coluna_em_outro_idioma(nome: str) -> tuple[str, str] | None:
    """Retorna (base, idioma) quando a coluna aparenta estar em idioma não-PT."""
    nome_lower = nome.lower()
    for sufixo, idioma in _SUFIXOS_OUTRO_IDIOMA.items():
        if nome_lower.endswith(sufixo) and len(nome_lower) > len(sufixo):
            return nome_lower[: -len(sufixo)], idioma
    return None



def _gerar_colunas_portugues_irmas(nome: str) -> list[str]:
    """Gera possíveis nomes de coluna irmã em português para uma coluna estrangeira."""
    info = _coluna_em_outro_idioma(nome)
    if not info:
        return []
    base, _idioma = info
    candidatas = [base]
    candidatas.extend(f"{base}{sufixo}" for sufixo in _SUFIXOS_PORTUGUES)
    if base == "name":
        candidatas.append("nome")
    if base == "description":
        candidatas.append("descricao")
    if base == "title":
        candidatas.append("titulo")
    return candidatas



def _tem_coluna_irma_portuguesa(nome: str, nomes_disponiveis: list[str]) -> bool:
    """Indica se existe coluna irmã em português para a pista fornecida."""
    nomes_normalizados = {item.lower() for item in nomes_disponiveis}
    return any(candidata.lower() in nomes_normalizados for candidata in _gerar_colunas_portugues_irmas(nome))



def _reordenar_colunas_pista_por_idioma(candidatas: list[str], nomes_disponiveis: list[str]) -> list[str]:
    """Prefere colunas em português quando existir coluna irmã em outro idioma."""
    if not candidatas:
        return candidatas

    resultado = list(candidatas)
    nomes_reais = {nome.lower(): nome for nome in nomes_disponiveis}
    for coluna in list(candidatas):
        irmas = _gerar_colunas_portugues_irmas(coluna)
        if not irmas:
            continue
        for irma in irmas:
            irma_real = nomes_reais.get(irma.lower())
            if irma_real in resultado:
                idx_coluna = resultado.index(coluna)
                idx_irma = resultado.index(irma_real)
                if idx_irma > idx_coluna:
                    resultado.insert(idx_coluna, resultado.pop(idx_irma))
                break
    return resultado



# Mapeamentos de prefixos abreviados para formas completas usadas no SaidJur.
# A chave é o prefixo abreviado; o valor é a expansão semântica equivalente.
# Estrutura extensível: adicione novas entradas conforme novos prefixos abreviados
# forem identificados no banco de dados jurídico.
_PREFIXOS_ABREVIADOS: dict[str, str] = {
    "pz": "prazo",
    "pub": "publicacao",
    "doc": "documento",
    "emp": "employee",
    "cli": "cliente",
    "proc": "processo",
    "aud": "audiencia",
}

# Sufixos semânticos que identificam campos de tipo/estado/fase.
# Usado para remover o sufixo e expor o radical da entidade.
_SUFIXOS_SEMANTICOS = (
    "_type", "_tipo", "type", "tipo",
    "_status", "status",
    "_phase", "phase", "_fase", "fase",
    "_nature", "nature", "_natureza", "natureza",
    "_link", "link", "_kind", "kind",
)

# Prefixos que identificam campos de tipo/estado/fase.
_PREFIXOS_SEMANTICOS = (
    "type_", "tipo_", "status_", "phase_", "fase_", "code_", "codigo_", "id_",
    "nature_", "natureza_",
)


def _extrair_radicais_coluna(nome_coluna: str) -> list[str]:
    """Extrai radicais úteis do nome da coluna para buscar tabelas de referência.

    Inclui expansão de prefixos abreviados do domínio jurídico brasileiro
    (ex: ``pz`` → ``prazo``) para ampliar a cobertura da busca por tabelas
    de catálogo com nomes completos.
    """
    nome = nome_coluna.lower()
    termos: list[str] = []

    def _adicionar(valor: str) -> None:
        normalizado = _normalizar_token_schema(valor)
        if len(normalizado) >= 3 and normalizado not in termos:
            termos.append(normalizado)

    _adicionar(nome)
    for token in re.split(r"[_\W]+", nome):
        _adicionar(token)
        # Para cada token, verificar se começa com prefixo abreviado
        for prefixo_abrev, expansao in _PREFIXOS_ABREVIADOS.items():
            if token.startswith(prefixo_abrev) and len(token) > len(prefixo_abrev):
                sufixo = token[len(prefixo_abrev):]
                _adicionar(sufixo)
                _adicionar(expansao + sufixo)
                _adicionar(expansao + "_" + sufixo)

    for prefixo in _PREFIXOS_SEMANTICOS:
        if nome.startswith(prefixo):
            _adicionar(nome[len(prefixo):])
    for sufixo in _SUFIXOS_SEMANTICOS:
        if nome.endswith(sufixo):
            _adicionar(nome[: -len(sufixo)])

    # Expansão de prefixos abreviados no nome completo
    for prefixo_abrev, expansao in _PREFIXOS_ABREVIADOS.items():
        if nome.startswith(prefixo_abrev) and len(nome) > len(prefixo_abrev):
            parte = nome[len(prefixo_abrev):]
            _adicionar(parte)
            _adicionar(expansao)
            _adicionar(expansao + parte)
            _adicionar(expansao + "_" + parte)

    return termos


def _gerar_nomes_candidatos_tabela(
    nome_tabela_origem: str,
    nome_coluna: str,
) -> list[str]:
    """Gera nomes explícitos de tabela candidata a catálogo para a coluna.

    Complementa a heurística de pontuação com variantes específicas do
    domínio jurídico brasileiro, cobrindo padrões de nomenclatura como:
    - prefixo ``pz`` expandido para ``prazo``
    - combinações do nome da tabela de origem com o nome da coluna
    - variantes de tipo/contrato/fase em português e inglês

    A lista ``_VARIANTES_SUFIXO_TABELA`` é extensível: adicione novas entradas
    para cobrir novos padrões de nomenclatura identificados no banco.
    """
    # Sufixos de tabela de catálogo comuns (em ordem de prioridade)
    _VARIANTES_SUFIXO_TABELA: list[str] = [
        "s", "es", "_ref", "_type", "_types", "_tipo", "_tipos",
        "_status", "_phase", "_phases", "_fase", "_fases",
        "types", "tipos", "phases", "fases",
    ]

    coluna = nome_coluna.lower()
    tabela_raw = nome_tabela_origem.lower()
    # Remover no máximo um sufixo 's' ou 'es' (plural) do nome da tabela de origem
    # para obter a raiz da entidade. Usar removesuffix() (Python 3.9+) em vez de
    # rstrip() que poderia remover múltiplos caracteres.
    if tabela_raw.endswith("es"):
        tabela = tabela_raw.removesuffix("es").rstrip("_")
    elif tabela_raw.endswith("s"):
        tabela = tabela_raw.removesuffix("s").rstrip("_")
    else:
        tabela = tabela_raw.rstrip("_")

    radicais = _extrair_radicais_coluna(coluna)
    candidatos: list[str] = []

    seen: set[str] = set()

    def _add(nome: str) -> None:
        n = nome.strip("_").lower()
        if n and n not in seen and len(n) >= 3:
            seen.add(n)
            candidatos.append(n)

    # Variantes a partir dos radicais com sufixos de tabela de catálogo
    for radical in radicais:
        _add(radical)
        for suf in _VARIANTES_SUFIXO_TABELA:
            _add(radical + suf)
        # Combinação tabela_origem + radical
        _add(tabela + radical)
        _add(tabela + "_" + radical)

    # Variantes de contrato
    if "contract" in coluna or "contrat" in coluna:
        for v in ("contracttypes", "contract_types", "tipos_contrato",
                  "tipocontrato", "tipos_contratos", "tiposcontrato"):
            _add(v)

    # Variantes de tipo de publicação
    if "pub" in coluna or "publicac" in coluna or "publication" in coluna:
        for v in ("pubtypes", "pub_types", "publicationtypes",
                  "publication_types", "tipos_publicacao",
                  "tipospublicacao", "tipopublicacao"):
            _add(v)

    # Variantes de tipo de pessoa
    if "person" in coluna or "pessoa" in coluna:
        for v in ("persontypes", "persontype_ref", "tipos_pessoa", "tipopessoa"):
            _add(v)

    # Variantes de link/vínculo
    if "link" in coluna or "vinculo" in coluna:
        for v in ("linktypes", "link_types", "tipos_vinculo", "tipovinculo"):
            _add(v)

    return candidatos



def _pontuar_tabela_referencia(nome_tabela: str, radicais: list[str]) -> int:
    """Pontua o quão provável uma tabela é ser catálogo do código investigado."""
    normalizado = _normalizar_token_schema(nome_tabela)
    score = 0
    for radical in radicais:
        if normalizado == radical:
            score = max(score, 12)
        if normalizado in {f"{radical}s", f"{radical}es"}:
            score = max(score, 11)
        if normalizado.endswith(radical) or normalizado.startswith(radical):
            score = max(score, 8)
        if radical in normalizado:
            score = max(score, 6)
    return score



def _selecionar_coluna_codigo_referencia(colunas: list[ColunaTabela], coluna_origem: str) -> str | None:
    """Escolhe a coluna-código mais provável em uma tabela de catálogo."""
    radicais = _extrair_radicais_coluna(coluna_origem)
    candidatos: list[tuple[int, str]] = []
    for coluna in colunas:
        nome = coluna.nome.lower()
        score = 0
        if nome == coluna_origem.lower():
            score += 10
        if nome in {"id", "code", "codigo"}:
            score += 9
        if nome.endswith("_id") or nome.endswith("id"):
            score += 4
        if nome.endswith("_code") or nome.endswith("code") or "codigo" in nome:
            score += 4
        if any(radical and radical in _normalizar_token_schema(nome) for radical in radicais):
            score += 2
        if score > 0:
            candidatos.append((score, coluna.nome))
    if not candidatos:
        return None
    candidatos.sort(key=lambda item: (-item[0], item[1]))
    return candidatos[0][1]



def _selecionar_coluna_rotulo_referencia(colunas: list[ColunaTabela]) -> str | None:
    """Escolhe a coluna de rótulo mais provável em uma tabela de catálogo."""
    pontuadas: list[tuple[int, str]] = []
    nomes_disponiveis = [coluna.nome for coluna in colunas]
    for coluna in colunas:
        nome = coluna.nome.lower()
        if not _tipo_textual(coluna.tipo):
            continue
        score = 0
        if any(chave in nome for chave in _CHAVES_PISTA):
            score += 8
        if nome in {"name", "nome", "description", "descricao", "title", "titulo", "label"}:
            score += 3
        if _tem_coluna_irma_portuguesa(coluna.nome, nomes_disponiveis):
            score -= 2
        if score > 0:
            pontuadas.append((score, coluna.nome))
    if not pontuadas:
        return None
    pontuadas.sort(key=lambda item: (-item[0], item[1]))
    return _reordenar_colunas_pista_por_idioma([nome for _, nome in pontuadas], nomes_disponiveis)[0]



def _buscar_em_tabela_referencia(engine: Engine, pendencia: PendenciaEnum) -> dict[str, Any] | None:
    """Busca tradução em tabela de referência/catálogo detectada via schema.

    Combina duas estratégias:
    1. Pontuação por radical: pontua todas as tabelas do banco pelo grau de
       similaridade semântica com o nome da coluna investigada.
    2. Candidatos explícitos: lista de nomes derivados diretamente do nome da
       coluna e da tabela de origem, cobrindo padrões específicos do domínio
       jurídico brasileiro (ex: prefixo ``pz``, variantes de contrato/fase).
    """
    insp = inspect(engine)
    todas_tabelas = set(insp.get_table_names())
    radicais = _extrair_radicais_coluna(pendencia.coluna)

    # --- Estratégia 1: pontuação por radical ---
    candidatas: list[tuple[int, str]] = []
    for tabela in todas_tabelas:
        if tabela.lower() == pendencia.tabela.lower():
            continue
        score = _pontuar_tabela_referencia(tabela, radicais)
        if score > 0:
            candidatas.append((score, tabela))

    candidatas.sort(key=lambda item: (-item[0], item[1]))

    # --- Estratégia 2: candidatos explícitos por nome ---
    nomes_explicitos = _gerar_nomes_candidatos_tabela(pendencia.tabela, pendencia.coluna)
    ja_em_candidatas = {t.lower() for _, t in candidatas}
    for nome_expl in nomes_explicitos:
        # Encontrar a tabela real com nome case-insensitive
        real = next((t for t in todas_tabelas if t.lower() == nome_expl.lower()), None)
        if real and real.lower() != pendencia.tabela.lower() and real.lower() not in ja_em_candidatas:
            candidatas.append((5, real))
            ja_em_candidatas.add(real.lower())

    for _score, tabela_ref in candidatas:
        colunas_ref = listar_colunas_tabela(engine, tabela_ref)
        coluna_codigo = _selecionar_coluna_codigo_referencia(colunas_ref, pendencia.coluna)
        coluna_rotulo = _selecionar_coluna_rotulo_referencia(colunas_ref)
        if not coluna_codigo or not coluna_rotulo:
            continue

        tabela_sql = _identificador(tabela_ref, engine.dialect.name)
        coluna_codigo_sql = _identificador(coluna_codigo, engine.dialect.name)
        coluna_rotulo_sql = _identificador(coluna_rotulo, engine.dialect.name)
        sql = text(
            f"SELECT {coluna_codigo_sql} AS codigo, {coluna_rotulo_sql} AS rotulo "
            f"FROM {tabela_sql} "
            f"WHERE CAST({coluna_codigo_sql} AS CHAR) = CAST(:valor AS CHAR) "
            "LIMIT 5"
        )

        def _executar() -> list[dict[str, Any]]:
            with engine.connect() as conn:
                res = conn.execute(sql, {"valor": str(pendencia.valor)})
                return [dict(row._mapping) for row in res.fetchall()]

        linhas = executar_com_retry_db(
            _executar,
            descricao=f"Investigar catálogo {tabela_ref} para {pendencia.tabela}.{pendencia.coluna}",
        )
        rotulos = []
        for linha in linhas:
            valor_rotulo = linha.get("rotulo")
            # Rejeitar explicitamente valores nulos/vazios: None, string vazia ou
            # string que, após strip, resulte em "" — nunca converter None para "None".
            if valor_rotulo is None:
                continue
            rotulo = str(valor_rotulo).strip()
            if not rotulo:
                continue
            rotulos.append(rotulo)
        distintos = sorted(set(rotulos))
        if len(distintos) != 1:
            # Se há linhas mas todos os rótulos eram nulos/vazios, registramos
            # que a tabela foi encontrada mas não tinha rótulo válido e continuamos
            # tentando outras candidatas.
            continue

        traducao = distintos[0]
        coluna_outro_idioma = _coluna_em_outro_idioma(coluna_rotulo) is not None
        justificativa = (
            f"Tabela de referência '{tabela_ref}' detectada via schema; "
            f"coluna '{coluna_codigo}' mapeou o código '{pendencia.valor}' "
            f"para '{traducao}' usando o rótulo '{coluna_rotulo}'."
        )
        if coluna_outro_idioma and not _tem_coluna_irma_portuguesa(
            coluna_rotulo,
            [coluna.nome for coluna in colunas_ref],
        ):
            justificativa += (
                " A pista veio de coluna em outro idioma; revise/traduza manualmente "
                "antes de aplicar ao dicionário em português."
            )

        return {
            "tabela_referencia": tabela_ref,
            "coluna_codigo_referencia": coluna_codigo,
            "coluna_rotulo_referencia": coluna_rotulo,
            "linhas_referencia": linhas,
            "sugestao": _enriquecer_sugestao_com_alertas(
                {
                    "status": "alta_confianca",
                    "traducao_sugerida": traducao,
                    "justificativa": justificativa,
                    "pistas": [
                        {
                            "coluna": f"{tabela_ref}.{coluna_rotulo}",
                            "valores_frequentes": [{"valor": traducao, "ocorrencias": len(rotulos)}],
                            "valores_distintos": 1,
                            "ocorrencias_total": len(rotulos),
                        }
                    ],
                    "fonte": "tabela_referencia",
                }
            ),
        }
    return None



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



def _contar_linhas_com_valor(
    engine: Engine,
    pendencia: PendenciaEnum,
    *,
    param_valor: Any,
) -> int:
    """Retorna a contagem de linhas onde coluna = valor na tabela.

    Usado como diagnóstico para distinguir "tabela/coluna sem rows com esse valor"
    de "query retornou vazio por problema de tipo/nome".  Retorna -1 se a query
    falhar (erro de SQL ou conexão).
    """
    tabela_sql = _identificador(pendencia.tabela, engine.dialect.name)
    coluna_sql = _identificador(pendencia.coluna, engine.dialect.name)
    sql = text(
        f"SELECT COUNT(*) FROM {tabela_sql} WHERE {coluna_sql} = :valor"
    )
    try:
        with engine.connect() as conn:
            resultado = conn.execute(sql, {"valor": param_valor})
            row = resultado.fetchone()
            return int(row[0]) if row else 0
    except Exception:
        return -1



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

    linhas = executar_com_retry_db(_executar, descricao=f"Investigar {pendencia.tabela}.{pendencia.coluna}")

    # Diagnóstico: se a query principal não retornou linhas mas o valor é numérico,
    # tenta também comparar como string para capturar colunas TEXT que armazenam
    # inteiros como texto (ex: '6' em vez de 6).  Isso ocorre principalmente em
    # SQLite onde a comparação de tipo é estrita.
    #
    # Nota de compatibilidade: usa CAST(... AS CHAR) que é válido tanto no MySQL/
    # MariaDB quanto no SQLite (onde TEXT, CHAR e VARCHAR são equivalentes).
    # CAST(... AS TEXT) é aceito apenas pelo SQLite e causa erro de sintaxe no MySQL.
    if not linhas and isinstance(param_valor, int):
        _tipo_cast = "CHAR"
        sql_str = text(
            f"SELECT {colunas_sql} "
            f"FROM {tabela_sql} "
            f"WHERE CAST({coluna_sql} AS {_tipo_cast}) = CAST(:valor AS {_tipo_cast}) "
            f"LIMIT {int(limite_linhas)}"
        )

        def _executar_str() -> list[dict[str, Any]]:
            with engine.connect() as conn:
                res = conn.execute(sql_str, {"valor": str(param_valor)})
                return [dict(row._mapping) for row in res.fetchall()]

        # Qualquer exceção aqui (ex: erro de sintaxe SQL no banco alvo) é
        # propagada ao chamador para ser registrada como status "erro" em vez
        # de ser silenciada e mascarada como "sem_registros".
        linhas = executar_com_retry_db(
            _executar_str,
            descricao=f"Investigar (fallback texto) {pendencia.tabela}.{pendencia.coluna}",
        )

    return linhas



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


def _pista_parece_texto_livre(valor: str) -> bool:
    """Heurística para detectar texto livre longo/específico em pistas.

    Traduções válidas de ENUM tendem a ser rótulos curtos. Conteúdos longos
    (>=50 caracteres), com muitas palavras ou pontuação de texto corrido
    normalmente são dados de registros específicos e não devem ser sugeridos
    automaticamente.
    """
    texto = valor.strip()
    if not texto:
        return False

    if len(texto) >= _TEXTO_LIVRE_COMPRIMENTO_MIN:
        return True

    palavras = [p for p in re.split(r"\s+", texto) if p]
    if len(palavras) >= 10:
        return True

    pontuacoes = sum(texto.count(p) for p in (".", ";", ":", "!", "?", ","))
    if pontuacoes >= 2 and len(texto) >= 35 and len(palavras) >= 6:
        return True

    return False



def _pista_parece_dado_especifico(valor: str) -> bool:
    """Heurística para sinalizar nomes curtos que parecem entidade específica."""
    texto = valor.strip()
    if not texto or _pista_parece_texto_livre(texto):
        return False

    palavras = re.findall(r"[A-Za-zÀ-ÿ0-9]+", texto)
    if len(palavras) < 2:
        return False

    acronimos = [p for p in palavras if re.fullmatch(r"[A-Z]{2,4}", p)]
    capitalizadas = [
        p for p in palavras if re.fullmatch(r"[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][a-záàâãéêíóôõúç]+", p)
    ]
    return len(acronimos) >= 2 and len(acronimos) + len(capitalizadas) == len(palavras)



def _enriquecer_sugestao_com_alertas(sugestao: dict[str, Any]) -> dict[str, Any]:
    """Acrescenta alertas não bloqueantes à sugestão."""
    resultado = dict(sugestao)
    alertas: list[dict[str, str]] = []
    traducao = resultado.get("traducao_sugerida")
    if isinstance(traducao, str) and _pista_parece_dado_especifico(traducao):
        alertas.append(
            {
                "tipo": "possivel_dado_especifico",
                "mensagem": (
                    "⚠️ Possível dado específico/sensível — verifique se este valor é "
                    "uma categoria genérica ou um dado real de caso antes de aplicar."
                ),
            }
        )
    resultado["alertas"] = alertas
    return resultado



def _analisar_pistas(
    pendencia: PendenciaEnum,
    linhas: list[dict[str, Any]],
    colunas_pista: list[str],
) -> dict[str, Any]:
    if not linhas:
        return _enriquecer_sugestao_com_alertas({
            "status": "sem_registros",
            "traducao_sugerida": None,
            "justificativa": "Nenhuma linha encontrada para este valor.",
            "pistas": [],
        })

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
        return _enriquecer_sugestao_com_alertas({
            "status": "sem_pista_encontrada",
            "traducao_sugerida": None,
            "justificativa": "Foram encontradas linhas, mas sem pista textual clara.",
            "pistas": [],
        })

    # Alta confiança só quando o indício textual é único e consistente em
    # múltiplas linhas E a coluna-pista tem nome semanticamente relacionado a
    # rótulos/descrições (pista forte). Colunas booleanas (valores só 0/1) ou
    # com nomes puramente técnicos (pista fraca) não são suficientes para alta
    # confiança, pois qualquer amostra pequena terá valor constante nesses campos.
    descartou_texto_livre = False
    evidencias_por_rotulo: dict[str, list[dict[str, Any]]] = {}
    for pista in pistas:
        if pista["valores_distintos"] != 1:
            continue
        unico = pista["valores_frequentes"][0]["valor"]
        if (
            _pista_parece_texto_livre(unico)
            or _pista_e_booleana(pista["valores_frequentes"])
            or not _coluna_tem_nome_semantico(pista["coluna"])
        ):
            continue
        evidencias_por_rotulo.setdefault(unico, []).append(pista)

    for rotulo, evidencias in evidencias_por_rotulo.items():
        ocorrencias = sum(pista["ocorrencias_total"] for pista in evidencias)
        if len(evidencias) >= 2 and ocorrencias >= 2:
            return _enriquecer_sugestao_com_alertas({
                "status": "alta_confianca",
                "traducao_sugerida": rotulo,
                "justificativa": (
                    f"Múltiplas colunas-pista ({', '.join(p['coluna'] for p in evidencias)}) "
                    f"concordaram com '{rotulo}' em {ocorrencias} evidência(s) para o código "
                    f"'{pendencia.valor}'."
                ),
                "pistas": pistas,
                "fonte": "multiplas_pistas",
            })

    for pista in pistas:
        if pista["valores_distintos"] != 1 or pista["ocorrencias_total"] < 2:
            continue
        unico = pista["valores_frequentes"][0]["valor"]
        if _pista_parece_texto_livre(unico):
            descartou_texto_livre = True
            continue
        tem_nome_semantico = _coluna_tem_nome_semantico(pista["coluna"])
        e_booleana = _pista_e_booleana(pista["valores_frequentes"])
        if tem_nome_semantico and not e_booleana:
            justificativa = (
                f"Coluna '{pista['coluna']}' (pista forte — nome semântico) "
                f"apresentou valor único e consistente "
                f"em múltiplas linhas para o código '{pendencia.valor}'."
            )
            if _coluna_em_outro_idioma(pista["coluna"]) and not _tem_coluna_irma_portuguesa(
                pista["coluna"],
                colunas_pista,
            ):
                justificativa += (
                    " A pista veio de coluna em outro idioma; revise/traduza manualmente "
                    "antes de aplicar ao dicionário em português."
                )
            return _enriquecer_sugestao_com_alertas({
                "status": "alta_confianca",
                "traducao_sugerida": unico,
                "justificativa": justificativa,
                "pistas": pistas,
            })

    for pista in pistas:
        # "pista_unica" só é usada quando existe apenas um indício textual
        # disponível. Se houver múltiplos valores distintos nas pistas, não há
        # confiança suficiente para sugerir tradução automática.
        # Pistas fracas (colunas booleanas ou sem nome semântico) com valor único
        # em múltiplas linhas também caem aqui em vez de alta_confianca.
        if pista["valores_distintos"] == 1 and pista["ocorrencias_total"] >= 1:
            unico = pista["valores_frequentes"][0]["valor"]
            if _pista_parece_texto_livre(unico):
                descartou_texto_livre = True
                continue
            e_booleana = _pista_e_booleana(pista["valores_frequentes"])
            tem_nome_semantico = _coluna_tem_nome_semantico(pista["coluna"])
            if e_booleana or not tem_nome_semantico:
                justificativa = (
                    f"Coluna '{pista['coluna']}' (pista fraca — "
                    + ("coluna booleana" if e_booleana else "nome sem relação semântica")
                    + f") apresentou valor único '{unico}' nas linhas de exemplo, "
                    "mas isso não é evidência suficiente do significado do código. "
                    "Revise manualmente antes de aplicar."
                )
                if _coluna_em_outro_idioma(pista["coluna"]) and not _tem_coluna_irma_portuguesa(
                    pista["coluna"],
                    colunas_pista,
                ):
                    justificativa += (
                        " A pista veio de coluna em outro idioma; traduza/valide manualmente "
                        "antes de aplicar."
                    )
                return _enriquecer_sugestao_com_alertas({
                    "status": "pista_unica",
                    "traducao_sugerida": unico,
                    "justificativa": justificativa,
                    "pistas": pistas,
                })
            justificativa = (
                f"Coluna '{pista['coluna']}' (pista forte) tem apenas uma ocorrência "
                f"de exemplo para o código '{pendencia.valor}'. "
                "Sugestão útil para revisão, mas sem confiança alta (amostra pequena)."
            )
            if _coluna_em_outro_idioma(pista["coluna"]) and not _tem_coluna_irma_portuguesa(
                pista["coluna"],
                colunas_pista,
            ):
                justificativa += (
                    " A pista veio de coluna em outro idioma; traduza/valide manualmente "
                    "antes de aplicar."
                )
            return _enriquecer_sugestao_com_alertas({
                "status": "pista_unica",
                "traducao_sugerida": unico,
                "justificativa": justificativa,
                "pistas": pistas,
            })

    justificativa_final = "Há pistas textuais, mas sem consistência suficiente para alta confiança."
    if descartou_texto_livre:
        justificativa_final = (
            "As pistas disponíveis tinham aparência de texto livre específico "
            "(conteúdo de registro real) e foram descartadas por segurança."
        )

    return _enriquecer_sugestao_com_alertas({
        "status": "sem_pista_encontrada",
        "traducao_sugerida": None,
        "justificativa": justificativa_final,
        "pistas": pistas,
    })



def _coletar_contexto_coluna_obs(
    engine: Engine,
    pendencia: PendenciaEnum,
    colunas_disponiveis: list[ColunaTabela],
    *,
    limite_linhas: int = 20,
) -> dict[str, Any] | None:
    """Coleta distribuição de valores de coluna de observação correlacionada.

    Quando a investigação principal não encontra tradução de alta confiança, esta
    função busca colunas de observação/texto-livre (ex: ``prazoobs``) na mesma
    tabela e agrega os valores correlacionados com o código investigado.  O
    resultado é incluído no relatório como contexto adicional para ajudar o
    usuário a inferir manualmente o significado do código — sem gerar sugestão
    automática.

    Retorna ``None`` se não houver coluna de observação ou se não houver linhas
    com valores não-nulos correlacionadas ao código investigado.
    """
    nomes_disponiveis = {col.nome.lower() for col in colunas_disponiveis}
    coluna_obs_nome: str | None = None
    for candidata in _COLUNAS_OBSERVACAO_PADRAO:
        if candidata.lower() in nomes_disponiveis:
            # Recuperar o nome real (com capitalização original)
            coluna_obs_nome = next(
                col.nome for col in colunas_disponiveis if col.nome.lower() == candidata.lower()
            )
            break

    if not coluna_obs_nome:
        return None

    tabela_sql = _identificador(pendencia.tabela, engine.dialect.name)
    coluna_sql = _identificador(pendencia.coluna, engine.dialect.name)
    coluna_obs_sql = _identificador(coluna_obs_nome, engine.dialect.name)
    param_valor = _converter_valor_para_param(pendencia.valor)

    # Usa GROUP BY para obter contagens reais diretamente no banco, evitando
    # que o LIMIT distorça a distribuição de frequência quando há muitas linhas.
    sql = text(
        f"SELECT {coluna_obs_sql} AS obs_valor, COUNT(*) AS ocorrencias "
        f"FROM {tabela_sql} "
        f"WHERE {coluna_sql} = :valor "
        f"AND {coluna_obs_sql} IS NOT NULL "
        f"AND TRIM(CAST({coluna_obs_sql} AS CHAR)) <> '' "
        f"GROUP BY {coluna_obs_sql} "
        f"ORDER BY ocorrencias DESC "
        f"LIMIT {int(limite_linhas)}"
    )

    def _executar() -> list[dict[str, Any]]:
        with engine.connect() as conn:
            res = conn.execute(sql, {"valor": param_valor})
            return [dict(row._mapping) for row in res.fetchall()]

    try:
        linhas = executar_com_retry_db(
            _executar,
            descricao=f"Contexto obs {pendencia.tabela}.{coluna_obs_nome} para {pendencia.coluna}={pendencia.valor}",
        )
    except Exception:
        return None

    amostras = [
        {"valor": str(linha.get("obs_valor", "")).strip(), "ocorrencias": int(linha.get("ocorrencias", 1))}
        for linha in linhas
        if linha.get("obs_valor") is not None and str(linha.get("obs_valor", "")).strip()
    ]

    if not amostras:
        return None

    total_ocorrencias = sum(a["ocorrencias"] for a in amostras)
    valores_distintos = len(amostras)

    return {
        "coluna_obs": coluna_obs_nome,
        "total_ocorrencias": total_ocorrencias,
        "valores_distintos": valores_distintos,
        "amostras": amostras[:5],
        "nota": (
            "Valores de coluna de observação correlacionados com o código investigado. "
            "Use como pista manual — não é tradução automática."
        ),
    }


def _coletar_distribuicao_codigo(engine: Engine, pendencia: PendenciaEnum) -> dict[str, Any] | None:
    """Resume o domínio do código como sinal auxiliar, sem inferir um rótulo."""
    tabela_sql = _identificador(pendencia.tabela, engine.dialect.name)
    coluna_sql = _identificador(pendencia.coluna, engine.dialect.name)
    sql = text(
        f"SELECT CAST({coluna_sql} AS CHAR) AS valor, COUNT(*) AS ocorrencias "
        f"FROM {tabela_sql} WHERE {coluna_sql} IS NOT NULL "
        f"GROUP BY CAST({coluna_sql} AS CHAR) ORDER BY ocorrencias DESC LIMIT 21"
    )
    with engine.connect() as conn:
        linhas = [dict(row._mapping) for row in conn.execute(sql).fetchall()]
    if not linhas or len(linhas) > 20:
        return None
    total = sum(int(linha["ocorrencias"]) for linha in linhas)
    alvo = next((int(linha["ocorrencias"]) for linha in linhas if str(linha["valor"]) == pendencia.valor), 0)
    classificacao = "enum_poucos_estados" if len(linhas) <= 5 else "dominio_amplo"
    if len(linhas) == 2 and total and 0.2 <= alvo / total <= 0.8:
        classificacao = "binario_balanceado"
    return {
        "valores_distintos": len(linhas),
        "ocorrencias_total": total,
        "ocorrencias_valor": alvo,
        "classificacao": classificacao,
        "valores_frequentes": [
            {"valor": str(linha["valor"]), "ocorrencias": int(linha["ocorrencias"])}
            for linha in linhas[:5]
        ],
    }


def _propagar_entre_tabelas_irmas(investigacoes: list[dict[str, Any]]) -> None:
    """Propaga rótulo de alta confiança entre tabelas irmãs explicitamente conhecidas."""
    for coluna, tabelas in _GRUPOS_TABELAS_IRMAS:
        for destino in investigacoes:
            if destino["coluna"].lower() != coluna or destino["tabela"].lower() not in tabelas:
                continue
            if destino["sugestao"]["status"] == "alta_confianca":
                continue
            origem = next(
                (
                    item for item in investigacoes
                    if item["tabela"].lower() in tabelas
                    and item["coluna"].lower() == coluna
                    and item["valor"] == destino["valor"]
                    and item["sugestao"]["status"] == "alta_confianca"
                    and item["sugestao"].get("traducao_sugerida")
                ),
                None,
            )
            if origem is None:
                continue
            destino["sugestao"] = _enriquecer_sugestao_com_alertas({
                "status": "alta_confianca",
                "traducao_sugerida": origem["sugestao"]["traducao_sugerida"],
                "justificativa": (
                    f"Tradução propagada da tabela irmã '{origem['tabela']}.{origem['coluna']}' "
                    "para o mesmo código no grupo de tabelas relacionadas."
                ),
                "pistas": origem["sugestao"].get("pistas", []),
                "fonte": "tabela_irma",
                "origem_tabela_irma": f"{origem['tabela']}.{origem['coluna']}",
            })


def _agrupar_investigacoes(investigacoes: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    """Organiza itens por confiança e tabela para revisão em lote."""
    resultado: dict[str, dict[str, list[str]]] = {}
    for item in investigacoes:
        status = item["sugestao"]["status"]
        resultado.setdefault(status, {}).setdefault(item["tabela"], []).append(
            f"{item['coluna']}:{item['valor']}"
        )
    return resultado


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
            lookup = _buscar_em_tabela_referencia(engine, pendencia)
            if lookup:
                investigacoes.append(
                    {
                        "tabela": pendencia.tabela,
                        "coluna": pendencia.coluna,
                        "valor": pendencia.valor,
                        "motivo_pendencia": pendencia.motivo,
                        "colunas_pista": [lookup["coluna_rotulo_referencia"]],
                        "linhas_exemplo": lookup["linhas_referencia"],
                        "sugestao": lookup["sugestao"],
                        "tabela_referencia": lookup["tabela_referencia"],
                        **(
                            {"distribuicao_codigo": distribuicao}
                            if (distribuicao := _coletar_distribuicao_codigo(engine, pendencia)) is not None
                            else {}
                        ),
                    }
                )
                continue

            colunas = executar_com_retry_db(
                lambda tabela=pendencia.tabela, engine_ref=engine: listar_colunas_tabela(
                    engine_ref, tabela
                ),
                descricao=f"Listar colunas de {pendencia.tabela}",
            )
            colunas_pista = selecionar_colunas_pista(colunas, pendencia.coluna)
            if not colunas_pista:
                item_sem_pista: dict[str, Any] = {
                    "tabela": pendencia.tabela,
                    "coluna": pendencia.coluna,
                    "valor": pendencia.valor,
                    "motivo_pendencia": pendencia.motivo,
                    "colunas_pista": [],
                    "linhas_exemplo": [],
                    "sugestao": {
                        **_enriquecer_sugestao_com_alertas(
                            {
                                "status": "sem_pista_encontrada",
                                "traducao_sugerida": None,
                                "justificativa": "Nenhuma coluna vizinha candidata a pista foi identificada.",
                                "pistas": [],
                            }
                        ),
                    },
                }
                contexto_obs = _coletar_contexto_coluna_obs(
                    engine, pendencia, colunas, limite_linhas=limite_linhas * 4
                )
                distribuicao = _coletar_distribuicao_codigo(engine, pendencia)
                if distribuicao is not None:
                    item_sem_pista["distribuicao_codigo"] = distribuicao
                if contexto_obs is not None:
                    item_sem_pista["contexto_obs"] = contexto_obs
                investigacoes.append(item_sem_pista)
                continue

            linhas = _coletar_linhas_exemplo(
                engine,
                pendencia,
                colunas_pista,
                limite_linhas=limite_linhas,
            )
            sugestao = _analisar_pistas(pendencia, linhas, colunas_pista)

            # Diagnóstico adicional: quando sem_registros, verifica via COUNT se
            # existe alguma linha com esse valor (pode indicar problema de tipo ou
            # de nome de coluna/tabela que a query de amostra não capturou).
            if sugestao["status"] == "sem_registros":
                param_valor = _converter_valor_para_param(pendencia.valor)
                contagem = _contar_linhas_com_valor(engine, pendencia, param_valor=param_valor)
                if contagem > 0:
                    sugestao = dict(sugestao)
                    sugestao["justificativa"] = (
                        f"A query de amostragem retornou 0 linhas, mas COUNT(*) encontrou "
                        f"{contagem} linha(s) com {pendencia.coluna} = {pendencia.valor!r}. "
                        "Possível incompatibilidade de tipo ou coluna com nome diferente do esperado. "
                        "Verifique o tipo real da coluna no schema (ex: TEXT vs INT)."
                    )
                    sugestao["contagem_real"] = contagem

            item: dict[str, Any] = {
                "tabela": pendencia.tabela,
                "coluna": pendencia.coluna,
                "valor": pendencia.valor,
                "motivo_pendencia": pendencia.motivo,
                "colunas_pista": colunas_pista,
                "linhas_exemplo": linhas,
                "sugestao": sugestao,
            }
            distribuicao = _coletar_distribuicao_codigo(engine, pendencia)
            if distribuicao is not None:
                item["distribuicao_codigo"] = distribuicao
            if sugestao["status"] != "alta_confianca":
                contexto_obs = _coletar_contexto_coluna_obs(
                    engine, pendencia, colunas, limite_linhas=limite_linhas * 4
                )
                if contexto_obs is not None:
                    item["contexto_obs"] = contexto_obs
            investigacoes.append(item)
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
                        **_enriquecer_sugestao_com_alertas(
                            {
                                "status": "erro",
                                "traducao_sugerida": None,
                                "justificativa": f"Falha ao investigar: {exc}",
                                "pistas": [],
                            }
                        ),
                    },
                }
            )

    _propagar_entre_tabelas_irmas(investigacoes)
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
        "agrupado_por_confianca_e_tabela": _agrupar_investigacoes(investigacoes),
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
    caminho_pendencias_markdown: str | Path | None = None,
    descobrir_schema: bool = False,
    caminho_dicionarios: str | Path = ARQUIVO_DICIONARIOS_PADRAO,
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
    elif caminho_pendencias_markdown or descobrir_schema:
        pendencias = []
        fontes = []
        if caminho_pendencias_markdown:
            pendencias.extend(carregar_pendencias_markdown(caminho_pendencias_markdown))
            fontes.append(str(caminho_pendencias_markdown))
        fontes.append("schema" if descobrir_schema else "")
        fonte = ",".join(fonte for fonte in fontes if fonte)
    else:
        pendencias = carregar_pendencias_enum(caminho_relatorio_auditoria)
        fonte = str(caminho_relatorio_auditoria)

    engine = criar_engine()
    try:
        if caminho_pendencias_markdown:
            pendencias = expandir_pendencias_com_dominio(engine, pendencias)
        if descobrir_schema:
            pendencias.extend(descobrir_pendencias_schema(engine, carregar_yaml(caminho_dicionarios)))
        pendencias = _deduplicar_pendencias(pendencias)
        relatorio = investigar_pendencias(engine, pendencias, limite_linhas=limite_linhas)
        relatorio["fonte_pendencias"] = fonte
        salvar_yaml(relatorio, caminho_saida)
        return relatorio
    finally:
        engine.dispose()
