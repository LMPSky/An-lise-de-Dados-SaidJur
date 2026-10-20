"""Auditoria de cobertura de tradução por cardinalidade (sem teto de 20 valores).

As duas ferramentas de descoberta já existentes (``auditar_traducoes.py`` e
``src.investigacao_pendencias.descobrir_pendencias_schema``, usada por
``investigar_pendencias.py``/``listar_traducoes_faltantes.py``) descartam por
completo qualquer coluna cujos valores distintos amostrados ultrapassem um
teto fixo pequeno (``MAX_VALORES_ENUM = 20`` na auditoria, ``limite = 20`` na
descoberta via schema). Isso é necessário para não tratar colunas de texto
livre genuíno como código/ENUM, mas tem um efeito colateral real: qualquer
coluna de código/ENUM legítima com **mais de 20 valores distintos** (ex: um
catálogo de ~40-100 tipos de documento) nunca aparece em nenhum dos dois
relatórios — fica permanentemente fora do radar, mesmo rodando ``--completo``.

Este módulo implementa uma terceira estratégia, complementar às anteriores:
em vez de buscar uma amostra de valores e descartá-la se ultrapassar o teto,
primeiro **estima a cardinalidade real da coluna** via
``COUNT(DISTINCT coluna)`` (ou uma subseleção limitada, para tabelas
colossais) e só então decide se a coluna é "categórica" (cardinalidade dentro
de uma faixa configurável, por padrão 2–500). Colunas aprovadas têm **todos**
os seus valores distintos (não apenas os primeiros 20) comparados ao
``dicionarios.yaml``, usando a mesma classificação de pendência de
``auditar_traducoes.avaliar_pendencias_enum`` (sem entrada no dicionário,
placeholder ``[valor]`` pendente, ou tradução que parece estar em inglês).

A elegibilidade de coluna parte de
``src.investigacao_pendencias._coluna_elegivel_para_descoberta_completa``
(mesma lista enxuta de exclusões: ``BLOB``, tipos temporais, ``id`` e colunas
sensíveis de credenciais), mas — diferente da primeira versão deste módulo —
soma vários filtros adicionais, necessários porque a cardinalidade sozinha
não diferencia "código/ENUM" de "coluna identificadora", "flag booleana de
permissão" ou "texto livre/valor monetário curto por coincidência de
amostra":

1. **Colunas identificadoras (FK/PK)**: qualquer coluna cujo nome pareça
   referenciar outra linha (``account_id``, ``userid``, ``busunitid``,
   ``client_id``...) é excluída, mesmo sem exceder 500 valores distintos —
   um ``*_id`` com 56 valores distintos é só uma tabela pequena sendo
   referenciada, não uma categoria a traduzir. Constatado em produção: a
   primeira versão deste módulo sugeriu ``accounts.account_id`` (ids 1, 2,
   3... 650) como "pendência de tradução".
2. **Flags booleanas de permissão/ação** (``read_users``, ``write_clients``,
   ``approve_contracts``...): seguem a mesma convenção de prefixo já
   detectada em ``src.investigacao_pendencias._coluna_parece_flag_de_acao``
   e, de fato, no primeiro relatório real pós-filtro de FK/ID, **226 das 264
   colunas com cardinalidade 2** eram flags ``{'0', '1'}`` sem nenhuma
   entrada no dicionário — a maior fonte isolada de falso positivo
   remanescente. Reforçado por uma checagem factual (qualquer coluna cujos
   valores coletados sejam exatamente ``{'0', '1'}`` é descartada, mesmo sem
   prefixo reconhecido por nome).
3. **Colunas estruturais/texto-livre/monetárias conhecidas**: nomes que
   indicam nested set (``lft``/``rgt``/``level``), texto livre curto
   (``name``/``path``/``reason``/``motive``...) ou valores numéricos/
   monetários (``amount``/``total``/``rate``...) — comparação por
   substring, no mesmo padrão de
   ``_NOMES_COLUNA_TEXTO_LIVRE_DESCOBERTA_SCHEMA`` (ex: ``obs`` já cobre
   ``markup_observation``).
4. **Colunas ``_en`` (duplicata em inglês de outra coluna)**: ``name_en``,
   ``subject_en``, ``motive_en``... são a própria tradução de uma coluna
   irmã, não um código a traduzir.
5. **Número de referência/identificador em formato livre, endereço, e-mail
   e nome de pessoa/parte**: constatado em um segundo relatório real (já com
   os filtros 1-4 aplicados), o grupo dominante de falso positivo
   remanescente era este: números de processo/conta/registro
   (``lawsuitnumber``, ``register_number``, ``num_acc``...), campos de
   endereço (``address``/``cep``/``district``), e-mail/remetente
   (``emails.sender``), e nome de pessoa/parte
   (``defendant``/``plaintiff``/``witness_1``/``preposto_1``) — exclusão por
   substring (``number``, ``address``, ``sender``...) ou, quando o termo é
   curto demais para substring sem colidir com coluna legítima (ex: ``nd``
   dentro de ``fundamento``, ``witness`` dentro de
   ``witness_performance`` que é uma nota numérica categórica), por
   correspondência exata de nome
   (``_NOMES_COLUNA_EXATOS_SEMPRE_EXCLUIDOS_CARDINALIDADE``).
6. **Valor monetário sem termo reconhecido no nome da coluna**: colunas como
   ``lawsuits.legal_fees`` ou ``lawsuits_log.buyer_resp``/``seller_resp``
   guardam valores como ``"5000.00"``/``"R$ 14.500,00"`` sem que o nome
   contenha ``amount``/``valor``/``total`` — checagem factual complementar
   (``_coluna_parece_monetaria_no_banco``), no mesmo espírito da checagem de
   flag booleana.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from auditar_traducoes import avaliar_pendencias_enum
from src.db import _COLUNAS_FK_IGNORADAS, conectar_com_timeout, fks_inferidas, listar_chaves_estrangeiras
from src.dicionarios import dicionario_de_coluna
from src.investigacao_pendencias import (
    ColunaTabela,
    _coluna_elegivel_para_descoberta_completa,
    _coluna_parece_flag_de_acao,
    _identificador,
    _linhas_estimadas_tabela,
    _NOMES_COLUNA_TEXTO_LIVRE_DESCOBERTA_SCHEMA,
    _pista_parece_texto_livre,
    listar_colunas_tabela,
)
from src.tabelas_grandes import (
    LIMITE_LINHAS_TABELA_COLOSSAL,
    LIMITE_MINIMO_SUBSELECAO_TABELA_COLOSSAL,
    LIMITE_SUBSELECAO_TABELA_COLOSSAL,
    LIMITE_SUBSELECAO_TABELA_COLOSSAL_MODO_COMPLETO,
)

ARQUIVO_AUDITORIA_CARDINALIDADE_PADRAO = "relatorio_auditoria_cardinalidade.yaml"

# Faixa padrão de cardinalidade considerada "categórica" (código/ENUM).
# O piso de 2 descarta colunas com um único valor constante (nunca precisam
# de tradução) e o teto de 500 é generoso o bastante para cobrir catálogos
# grandes (ex: tipos de documento, fases processuais) sem degenerar em texto
# livre de alta cardinalidade (nomes, descrições, timestamps formatados).
CARDINALIDADE_MINIMA_PADRAO = 2
CARDINALIDADE_MAXIMA_PADRAO = 500

# Tamanho máximo de valor individual ainda considerado rótulo curto (mesmo
# critério de `descobrir_pendencias_schema`): acima disso, mesmo com poucos
# valores distintos, provavelmente não é um código/ENUM de verdade.
_TAMANHO_MAXIMO_VALOR = 60

# Acima deste número de linhas estimadas (mas ainda abaixo do limiar de
# tabela colossal), a tabela já pode ser grande o bastante para um
# `COUNT(DISTINCT)`/`DISTINCT` sem índice travar — constatado em produção
# com `publications_duplicate_info` (ordinária, não colossal). Mesmo valor
# usado em `auditar_traducoes.py` para a mesma decisão.
LIMITE_LINHAS_TABELA_GRANDE = 500_000

# Padrão de nome de coluna identificadora (FK/PK por convenção): termina em
# "id"/"_id"/"_pk" ou começa com "id_" (mesma convenção usada em
# `src.db.fks_inferidas`). Aplicado independente do tipo da coluna e mesmo
# quando a tabela referenciada não é encontrada por nome (ex: `idcomarca`,
# `busunitid`) — o nome já é evidência suficiente de que o valor identifica
# uma linha de outra tabela, não uma categoria.
_PADRAO_COLUNA_IDENTIFICADORA = re.compile(r"(?:_id|_pk|id)$|^id_", re.IGNORECASE)

# Dois únicos valores possíveis para uma coluna booleana — qualquer coluna
# cujo conjunto de valores coletados seja exatamente este é descartada da
# auditoria: um flag "ativo/inativo" sem entrada no dicionário não é uma
# pendência de tradução de código/ENUM no mesmo sentido de um catálogo real
# (mesmo raciocínio de `_coluna_e_booleana_no_banco`, reaproveitado aqui sem
# consulta extra pois os valores já foram coletados).
_VALORES_BOOLEANOS = frozenset({"0", "1"})

# Nomes de coluna estrutural (nested set, ordenação), texto livre curto ou
# valor numérico/monetário que, na prática, não são código/ENUM mesmo com
# poucos valores distintos na amostra — complementa
# `_NOMES_COLUNA_TEXTO_LIVRE_DESCOBERTA_SCHEMA` (que já cobre texto livre
# longo como `body`/`observacao`, com o mesmo critério de substring) com
# termos mais curtos observados em produção (`accounts.lft/rgt/level/path`,
# `description`, `name`, `reason`, `amount`...).
_NOMES_COLUNA_SEMPRE_EXCLUIDOS_CARDINALIDADE: tuple[str, ...] = (
    "lft",
    "rgt",
    "level",
    "nivel",
    "path",
    "caminho",
    "position",
    "posicao",
    "ordem",
    "order",
    "name",
    "nome",
    "reason",
    "motivo",
    "motive",
    "justification",
    "amount",
    "valor",
    "total",
    "quantidade",
    "search",
    "busca",
    "rate",
    "salary",
    "invoice_number",
    "index_value",
    "email",
    "pwd",
    # Terceira rodada de ajuste (relatório real pós-flags booleanas): número
    # de referência/identificador em formato livre (``lawsuitnumber``,
    # ``vara_number``, ``register_number``, ``stnumber``) — sempre um valor
    # único por registro, nunca um código/ENUM.
    "number",
    # Campos de endereço (``persons.address/cep/district/compliment``).
    "address",
    "cep",
    "district",
    "compliment",
    # Referência interna em texto livre, não um código (``lawsuits_log.clientcode``:
    # valores como "Proc. 888"; ``lawsuits_additional_info.client_reference``:
    # nome do cliente/empresa).
    "clientcode",
    "reference",
    # Nome de pessoa/remetente em campo de e-mail ou de quem enviou/recebeu
    # (``emails.sender``, ``expedients.instructions_sender``,
    # ``lawsuits_additional_info.client_receiver``).
    "sender",
    "receiver",
    # Descrição livre longa, não categórica, mesmo com poucos valores na
    # amostra (``hearingcontrol.proof_object``/``required_todo``).
    "proof_object",
    "required_todo",
    # Quantidade numérica (``projectevents.hours``), não código/ENUM.
    "hours",
    "horas",
    # Valor monetário calculado (``lawsuits_calculos.*_calcs``).
    "calcs",
    # Coluna "responsável por"/"enviado por": guarda id de funcionário/usuário
    # (``hearing_resp``, ``instructions_resp``, ``lawsuit_resp``) ou valor
    # monetário (``buyer_resp``/``seller_resp``), nunca um código/ENUM.
    "_resp",
    "_by",
    # Número de conta/agência/banco (``persons.num_acc/num_ag/num_bank``).
    "num_acc",
    "num_ag",
    "num_bank",
    # Horário do dia (``usertasks.login_time/logout_time``), não um código.
    "_time",
)

# Nomes de coluna excluídos por correspondência EXATA (não substring): termos
# curtos demais para substring sem colidir com colunas legítimas (ex: ``nd``
# apareceria dentro de ``fundamento``) ou nomes de pessoa/parte que têm uma
# variante irmã legítima e categórica (ex: ``witness_performance`` guarda uma
# nota numérica, não o nome da testemunha, então ``witness`` não pode ser
# substring — só ``witness_1``/``witness_2`` são excluídos).
_NOMES_COLUNA_EXATOS_SEMPRE_EXCLUIDOS_CARDINALIDADE: tuple[str, ...] = (
    "nd",
    "pta",
    "defendant",
    "plaintiff",
    "lawyer",
    "cartoriosmax",
    "witness_1",
    "witness_2",
    "preposto_1",
    "legal_assistant",
)

# Valor com cara de quantia monetária (``R$ 14.500,00``, ``14500,00``,
# ``5000.00``): colunas como ``lawsuits.legal_fees`` ou
# ``lawsuits_log.buyer_resp``/``seller_resp`` guardam esse tipo de valor sem
# que o nome contenha um termo monetário reconhecido (``amount``/``valor``/
# ``total``) — checagem factual complementar à exclusão por nome, no mesmo
# espírito de `_VALORES_BOOLEANOS`.
_PADRAO_VALOR_MONETARIO = re.compile(
    r"^-?(r\$\s*)?\d+(\.\d{3})*,\d{2}$|^-?\d+\.\d{2}$",
    re.IGNORECASE,
)


def _coluna_parece_monetaria_no_banco(valores: list[str]) -> bool:
    """Indica se a maioria dos valores coletados parece quantia monetária."""
    valores_nao_vazios = [valor for valor in valores if valor.strip()]
    if not valores_nao_vazios:
        return False
    quantidade_monetaria = sum(
        1 for valor in valores_nao_vazios if _PADRAO_VALOR_MONETARIO.match(valor.strip())
    )
    return quantidade_monetaria / len(valores_nao_vazios) >= 0.5


def _coluna_parece_duplicata_em_ingles(nome: str) -> bool:
    """Indica se a coluna é a duplicata em inglês de outra (ex: ``name_en``)."""
    return nome.endswith("_en")


def _coluna_parece_identificadora(nome: str) -> bool:
    """Indica se o nome da coluna parece um identificador (FK/PK), não um código."""
    nome_lower = nome.strip().lower()
    if nome_lower in _COLUNAS_FK_IGNORADAS:
        return False
    return bool(_PADRAO_COLUNA_IDENTIFICADORA.search(nome_lower))


def _coluna_elegivel_cardinalidade(coluna: ColunaTabela) -> bool:
    """Elegibilidade de coluna para a auditoria de cardinalidade.

    Parte da elegibilidade ampliada do modo completo
    (``_coluna_elegivel_para_descoberta_completa``) e soma a exclusão de
    colunas identificadoras (FK/PK por nome), flags booleanas de
    permissão/ação por nome e nomes estruturais/texto-livre/monetários
    conhecidos (comparação por substring, igual a
    ``_NOMES_COLUNA_TEXTO_LIVRE_DESCOBERTA_SCHEMA``) — ver docstring do
    módulo para o raciocínio completo por trás de cada filtro.
    """
    if not _coluna_elegivel_para_descoberta_completa(coluna):
        return False
    nome = coluna.nome.strip().lower()
    if _coluna_parece_identificadora(nome):
        return False
    if _coluna_parece_flag_de_acao(nome):
        return False
    if _coluna_parece_duplicata_em_ingles(nome):
        return False
    if any(chave in nome for chave in _NOMES_COLUNA_TEXTO_LIVRE_DESCOBERTA_SCHEMA):
        return False
    if any(chave in nome for chave in _NOMES_COLUNA_SEMPRE_EXCLUIDOS_CARDINALIDADE):
        return False
    if nome in _NOMES_COLUNA_EXATOS_SEMPRE_EXCLUIDOS_CARDINALIDADE:
        return False
    return True


@dataclass
class PendenciaCardinalidade:
    """Pendência de tradução descoberta pela auditoria de cardinalidade."""

    tabela: str
    coluna: str
    cardinalidade: int
    valores_pendentes: list[dict[str, str]] = field(default_factory=list)


def _contar_valores_distintos(
    engine: Engine,
    tabela: str,
    coluna: str,
    *,
    limite_subselecao: int | None = None,
    limite_minimo_subselecao: int = LIMITE_MINIMO_SUBSELECAO_TABELA_COLOSSAL,
) -> int:
    """Estima a cardinalidade de uma coluna via ``COUNT(DISTINCT ...)``.

    Para tabelas colossais, evita o ``COUNT(DISTINCT)`` na tabela inteira
    (mesmo risco de timeout já documentado em
    ``src.investigacao_pendencias._valores_distintos_coluna``) e conta sobre
    uma subseleção limitada por ``LIMIT``, com o mesmo retry decrescente até
    ``limite_minimo_subselecao`` em caso de falha.
    """
    tabela_sql = _identificador(tabela, engine.dialect.name)
    coluna_sql = _identificador(coluna, engine.dialect.name)

    if limite_subselecao is None:
        sql = text(
            f"SELECT COUNT(DISTINCT {coluna_sql}) FROM {tabela_sql} "
            f"WHERE {coluna_sql} IS NOT NULL"
        )
        with conectar_com_timeout(engine) as conn:
            resultado = conn.execute(sql).scalar()
        return int(resultado or 0)

    limite_atual = int(limite_subselecao)
    while True:
        sql = text(
            f"SELECT COUNT(DISTINCT valor) FROM ("
            f"SELECT {coluna_sql} AS valor FROM {tabela_sql} "
            f"WHERE {coluna_sql} IS NOT NULL "
            f"LIMIT {limite_atual}"
            f") AS amostra"
        )
        try:
            with conectar_com_timeout(engine) as conn:
                resultado = conn.execute(sql).scalar()
            return int(resultado or 0)
        except Exception:  # noqa: BLE001 - decide entre reduzir o LIMIT ou propagar
            if limite_atual <= limite_minimo_subselecao:
                raise
            limite_atual = max(limite_minimo_subselecao, limite_atual // 2)


def _coletar_valores_distintos(
    engine: Engine,
    tabela: str,
    coluna: str,
    *,
    cardinalidade_maxima: int,
    limite_subselecao: int | None = None,
    limite_minimo_subselecao: int = LIMITE_MINIMO_SUBSELECAO_TABELA_COLOSSAL,
) -> list[str]:
    """Coleta todos os valores distintos de uma coluna já confirmada como categórica."""
    tabela_sql = _identificador(tabela, engine.dialect.name)
    coluna_sql = _identificador(coluna, engine.dialect.name)
    # Pequena folga sobre a cardinalidade estimada: COUNT(DISTINCT) e a
    # consulta de valores podem divergir levemente se o banco mudar entre as
    # duas consultas (linhas inseridas/removidas concorrentemente).
    limite_valores = cardinalidade_maxima + 50

    if limite_subselecao is None:
        sql = text(
            f"SELECT DISTINCT CAST({coluna_sql} AS CHAR) AS valor FROM {tabela_sql} "
            f"WHERE {coluna_sql} IS NOT NULL "
            f"AND TRIM(CAST({coluna_sql} AS CHAR)) <> '' "
            f"LIMIT {limite_valores}"
        )
        with conectar_com_timeout(engine) as conn:
            return [str(row[0]).strip() for row in conn.execute(sql).fetchall()]

    limite_atual = int(limite_subselecao)
    while True:
        sql = text(
            f"SELECT DISTINCT valor FROM ("
            f"SELECT TRIM(CAST({coluna_sql} AS CHAR)) AS valor FROM {tabela_sql} "
            f"WHERE {coluna_sql} IS NOT NULL "
            f"LIMIT {limite_atual}"
            f") AS amostra "
            f"WHERE valor <> '' "
            f"LIMIT {limite_valores}"
        )
        try:
            with conectar_com_timeout(engine) as conn:
                return [str(row[0]).strip() for row in conn.execute(sql).fetchall()]
        except Exception:  # noqa: BLE001 - decide entre reduzir o LIMIT ou propagar
            if limite_atual <= limite_minimo_subselecao:
                raise
            limite_atual = max(limite_minimo_subselecao, limite_atual // 2)


def auditar_cobertura_por_cardinalidade(
    engine: Engine,
    *,
    cardinalidade_minima: int = CARDINALIDADE_MINIMA_PADRAO,
    cardinalidade_maxima: int = CARDINALIDADE_MAXIMA_PADRAO,
    limite_subselecao_colossal: int = LIMITE_SUBSELECAO_TABELA_COLOSSAL_MODO_COMPLETO,
) -> dict[str, Any]:
    """Audita todas as colunas elegíveis do banco por cardinalidade real.

    Retorna um relatório estruturado (pendências + resumo), no mesmo espírito
    de ``src.investigacao_pendencias.descobrir_pendencias_schema``, mas usando
    cardinalidade real (``COUNT(DISTINCT)``) em vez de nome de coluna ou teto
    fixo de amostra para decidir elegibilidade.
    """
    pendencias: list[PendenciaCardinalidade] = []
    colunas_auditadas = 0
    colunas_fora_do_intervalo = 0
    colunas_com_falha: list[dict[str, str]] = []
    tabelas_colossais: list[str] = []

    for tabela in inspect(engine).get_table_names():
        try:
            linhas_estimadas = _linhas_estimadas_tabela(engine, tabela)
        except Exception as exc:  # noqa: BLE001 - falha isolada não pode derrubar o lote
            linhas_estimadas = 0
            print(f"⚠️  Falha ao estimar linhas de {tabela}, tratando como tabela normal: {exc}")

        tabela_colossal = linhas_estimadas > LIMITE_LINHAS_TABELA_COLOSSAL
        tabela_grande = linhas_estimadas > LIMITE_LINHAS_TABELA_GRANDE
        if tabela_colossal:
            tabelas_colossais.append(tabela)
            limite_subselecao = limite_subselecao_colossal
            print(
                f"ℹ️  Tabela colossal '{tabela}' (~{linhas_estimadas:,} linhas): "
                f"estimando cardinalidade sobre amostra de até {limite_subselecao:,} linhas."
            )
        elif tabela_grande:
            limite_subselecao = LIMITE_SUBSELECAO_TABELA_COLOSSAL
            print(
                f"ℹ️  Tabela grande '{tabela}' (~{linhas_estimadas:,} linhas): "
                f"estimando cardinalidade sobre amostra de até {limite_subselecao:,} linhas."
            )
        else:
            limite_subselecao = None

        # Colunas FK declaradas/inferidas por convenção: referenciam outra
        # linha, não são código/ENUM. Reforça (não substitui) a exclusão por
        # nome em `_coluna_parece_identificadora`, cobrindo também FKs
        # declaradas no schema cujo nome não segue a convenção *id/_id.
        try:
            colunas_fk = {fk["coluna"] for fk in listar_chaves_estrangeiras(engine, tabela)}
            colunas_fk |= {fk["coluna"] for fk in fks_inferidas(engine, tabela)}
        except Exception:  # noqa: BLE001 - detecção de FK é best-effort
            colunas_fk = set()

        colunas: list[ColunaTabela] = listar_colunas_tabela(engine, tabela)
        for coluna in colunas:
            if not _coluna_elegivel_cardinalidade(coluna):
                continue
            if coluna.nome in colunas_fk:
                continue

            try:
                cardinalidade = _contar_valores_distintos(
                    engine, tabela, coluna.nome, limite_subselecao=limite_subselecao
                )
            except Exception as exc:  # noqa: BLE001 - falha isolada não pode derrubar o lote
                colunas_com_falha.append(
                    {"tabela_coluna": f"{tabela}.{coluna.nome}", "etapa": "cardinalidade", "erro": str(exc)}
                )
                print(f"⚠️  Falha ao estimar cardinalidade de {tabela}.{coluna.nome}: {exc}")
                continue

            if cardinalidade < cardinalidade_minima or cardinalidade > cardinalidade_maxima:
                colunas_fora_do_intervalo += 1
                continue

            colunas_auditadas += 1
            try:
                valores = _coletar_valores_distintos(
                    engine,
                    tabela,
                    coluna.nome,
                    cardinalidade_maxima=cardinalidade,
                    limite_subselecao=limite_subselecao,
                )
            except Exception as exc:  # noqa: BLE001 - falha isolada não pode derrubar o lote
                colunas_com_falha.append(
                    {"tabela_coluna": f"{tabela}.{coluna.nome}", "etapa": "valores", "erro": str(exc)}
                )
                print(f"⚠️  Falha ao coletar valores de {tabela}.{coluna.nome}: {exc}")
                continue

            # Checagem factual complementar à exclusão por nome
            # (_coluna_parece_flag_de_acao): mesmo sem prefixo verbal
            # reconhecido, uma coluna cujos únicos valores reais são '0'/'1'
            # é um flag booleano, não um código/ENUM — mesmo raciocínio de
            # `_coluna_e_booleana_no_banco`, sem round-trip extra ao banco
            # pois os valores já foram coletados acima.
            if set(valores) == _VALORES_BOOLEANOS:
                continue

            # Checagem factual complementar à exclusão por nome
            # (amount/valor/total/calcs/_resp): valores como "R$ 14.500,00"
            # ou "5000.00" são quantia monetária mesmo quando o nome da
            # coluna não contém um termo monetário reconhecido.
            if _coluna_parece_monetaria_no_banco(valores):
                continue

            valores_curtos = [
                valor
                for valor in dict.fromkeys(valores)
                if len(valor) <= _TAMANHO_MAXIMO_VALOR and not _pista_parece_texto_livre(valor)
            ]
            if not valores_curtos:
                continue

            dicionario_coluna = dicionario_de_coluna(tabela, coluna.nome)
            valores_pendentes = avaliar_pendencias_enum(valores_curtos, dicionario_coluna)
            if valores_pendentes:
                pendencias.append(
                    PendenciaCardinalidade(
                        tabela=tabela,
                        coluna=coluna.nome,
                        cardinalidade=cardinalidade,
                        valores_pendentes=valores_pendentes,
                    )
                )

    pendencias.sort(key=lambda p: (p.tabela, p.coluna))

    resumo = {
        "colunas_auditadas": colunas_auditadas,
        "colunas_fora_do_intervalo_cardinalidade": colunas_fora_do_intervalo,
        "colunas_com_falha": colunas_com_falha,
        "total_colunas_com_falha": len(colunas_com_falha),
        "tabelas_colossais_amostradas": tabelas_colossais,
        "total_tabelas_colossais_amostradas": len(tabelas_colossais),
        "total_colunas_com_pendencia": len(pendencias),
        "total_valores_pendentes": sum(len(p.valores_pendentes) for p in pendencias),
        "cardinalidade_minima": cardinalidade_minima,
        "cardinalidade_maxima": cardinalidade_maxima,
    }

    return {
        "gerado_em_utc": datetime.now(UTC).isoformat(),
        "resumo": resumo,
        "pendencias": [
            {
                "tabela": p.tabela,
                "coluna": p.coluna,
                "cardinalidade": p.cardinalidade,
                "valores_pendentes": p.valores_pendentes,
            }
            for p in pendencias
        ],
    }
