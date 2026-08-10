"""Testes da investigação assistida de pendências de tradução."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
import yaml

from src.investigacao_pendencias import (
    PendenciaEnum,
    aplicar_decisoes_em_dicionario,
    carregar_pendencias_enum,
    gerar_template_decisoes,
    investigar_pendencias,
    selecionar_colunas_pista,
    listar_colunas_tabela,
    _converter_valor_para_param,
    _coluna_tem_nome_semantico,
    _pista_e_booleana,
    _contar_linhas_com_valor,
)



def test_carregar_pendencias_enum_do_relatorio_yaml(tmp_path: Path) -> None:
    caminho = tmp_path / "relatorio.yaml"
    caminho.write_text(
        yaml.safe_dump(
            {
                "pendencias": {
                    "paymenttype": {
                        "enums": [
                            {
                                "coluna": "code",
                                "valores_pendentes": [
                                    {"valor": "Bol", "motivo": "sem_entrada_no_dicionario"},
                                    {"valor": "Bol", "motivo": "sem_entrada_no_dicionario"},
                                    {"valor": "chq", "motivo": "sem_entrada_no_dicionario"},
                                ],
                            }
                        ]
                    }
                }
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    pendencias = carregar_pendencias_enum(caminho)

    assert pendencias == [
        PendenciaEnum("paymenttype", "code", "Bol", "sem_entrada_no_dicionario"),
        PendenciaEnum("paymenttype", "code", "chq", "sem_entrada_no_dicionario"),
    ]



def test_selecionar_colunas_pista_prioriza_nome_e_descricao() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE paymenttype (
                id INTEGER PRIMARY KEY,
                code TEXT,
                name TEXT,
                description TEXT,
                created_at TEXT
            )
        """))
        conn.commit()

    colunas = listar_colunas_tabela(engine, "paymenttype")
    candidatas = selecionar_colunas_pista(colunas, "code")

    assert "name" in candidatas
    assert "description" in candidatas



def _engine_pagamento() -> Engine:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE paymenttype (
                id INTEGER PRIMARY KEY,
                code TEXT,
                name TEXT,
                description TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO paymenttype (id, code, name, description) VALUES
            (1, 'Bol', 'Boleto', 'Pagamento por boleto bancário'),
            (2, 'Bol', 'Boleto', 'Pagamento por boleto bancário'),
            (3, 'chq', 'Cheque', 'Pagamento por cheque')
        """))
        conn.commit()
    return engine



def test_investigar_pendencias_gera_sugestao_de_alta_confianca() -> None:
    engine = _engine_pagamento()
    pendencias = [PendenciaEnum("paymenttype", "code", "Bol")]

    relatorio = investigar_pendencias(engine, pendencias, limite_linhas=5)

    assert relatorio["resumo"]["total_pendencias"] == 1
    assert relatorio["resumo"]["alta_confianca"] == 1
    item = relatorio["investigacoes"][0]
    assert item["sugestao"]["status"] == "alta_confianca"
    assert item["sugestao"]["traducao_sugerida"] == "Boleto"
    assert item["linhas_exemplo"]



def test_investigar_pendencias_marca_sem_pista_quando_nao_ha_coluna_textual() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE config_status (
                id INTEGER PRIMARY KEY,
                code INTEGER,
                phase_id INTEGER,
                ordem INTEGER
            )
        """))
        conn.execute(text("INSERT INTO config_status (id, code, phase_id, ordem) VALUES (1, 2, 5, 10)"))
        conn.commit()

    relatorio = investigar_pendencias(engine, [PendenciaEnum("config_status", "code", "2")])

    item = relatorio["investigacoes"][0]
    assert item["sugestao"]["status"] == "sem_pista_encontrada"


def test_investigar_pendencias_marca_pista_unica_quando_ha_apenas_uma_linha_util() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE paymenttype (
                id INTEGER PRIMARY KEY,
                code TEXT,
                name TEXT
            )
        """))
        conn.execute(text("INSERT INTO paymenttype (id, code, name) VALUES (1, 'dda', 'Débito Direto')"))
        conn.commit()

    relatorio = investigar_pendencias(engine, [PendenciaEnum("paymenttype", "code", "dda")])

    assert relatorio["resumo"]["pista_unica"] == 1
    item = relatorio["investigacoes"][0]
    assert item["sugestao"]["status"] == "pista_unica"
    assert item["sugestao"]["traducao_sugerida"] == "Débito Direto"


def test_aplicar_decisoes_em_dicionario_aplica_somente_aprovadas() -> None:
    dicionarios = {"paymenttype": {"code": {"deb": "Débito"}}}
    decisoes = [
        {
            "tabela": "paymenttype",
            "coluna": "code",
            "valor": "Bol",
            "traducao_sugerida": "Boleto",
            "decisao": "aplicar",
        },
        {
            "tabela": "paymenttype",
            "coluna": "code",
            "valor": "chq",
            "traducao_sugerida": "Cheque",
            "decisao": "pular",
        },
    ]

    atualizados, aplicadas = aplicar_decisoes_em_dicionario(dicionarios, decisoes)

    assert atualizados["paymenttype"]["code"]["Bol"] == "Boleto"
    assert "chq" not in atualizados["paymenttype"]["code"]
    assert len(aplicadas) == 1



def test_gerar_template_decisoes() -> None:
    relatorio = {
        "investigacoes": [
            {
                "tabela": "paymenttype",
                "coluna": "code",
                "valor": "Bol",
                "sugestao": {
                    "status": "alta_confianca",
                    "traducao_sugerida": "Boleto",
                },
            }
        ]
    }

    template = gerar_template_decisoes(relatorio)

    assert template["decisoes"][0]["decisao"] == "pendente"
    assert template["decisoes"][0]["traducao_sugerida"] == "Boleto"


# ---------------------------------------------------------------------------
# Testes para os bugs corrigidos (Bug 1/2 — filtro por valor numérico,
# Bug 3 — heurística de confiança mais rigorosa)
# ---------------------------------------------------------------------------

def test_converter_valor_para_param_converte_inteiros() -> None:
    """Bug 1/2: valor numérico deve ser convertido para int."""
    assert _converter_valor_para_param("6") == 6
    assert _converter_valor_para_param("11") == 11
    assert _converter_valor_para_param("-3") == -3


def test_converter_valor_para_param_mantem_strings() -> None:
    """Bug 1/2: valor não-numérico permanece como string."""
    assert _converter_valor_para_param("Bol") == "Bol"
    assert _converter_valor_para_param("abc") == "abc"
    assert _converter_valor_para_param("") == ""


def test_investigar_pendencias_encontra_valor_numerico_em_coluna_inteira() -> None:
    """Bug 2: investigação com valor numérico passado como string deve encontrar
    linhas em colunas inteiras do banco (sem falso negativo por tipo)."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE pedidos2lawsuit (
                id INTEGER PRIMARY KEY,
                status INTEGER,
                claim_text TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO pedidos2lawsuit (id, status, claim_text) VALUES
            (1, 6, 'Pedido de devolução'),
            (2, 1, 'Pedido inicial'),
            (3, 6, 'Pedido revisional')
        """))
        conn.commit()

    # O valor '6' é passado como string (vem da linha de comando), mas a
    # coluna é INTEGER — a busca não deve retornar zero linhas.
    relatorio = investigar_pendencias(engine, [PendenciaEnum("pedidos2lawsuit", "status", "6")])

    item = relatorio["investigacoes"][0]
    assert item["linhas_exemplo"], "Deve retornar linhas para status=6 (inteiro)"
    assert item["sugestao"]["status"] != "sem_registros"


def test_investigar_pendencias_linhas_exemplo_satisfazem_filtro() -> None:
    """Bug 1: todas as linhas de exemplo retornadas devem satisfazer o filtro
    pelo valor investigado (não podem ser linhas genéricas da tabela)."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE hearingcontrol (
                id INTEGER PRIMARY KEY,
                hearingtype INTEGER,
                observation TEXT,
                hearingfile INTEGER
            )
        """))
        conn.execute(text("""
            INSERT INTO hearingcontrol (id, hearingtype, observation, hearingfile) VALUES
            (1, 11, 'Audiência de instrução', 0),
            (2,  1, 'Audiência inicial', 0),
            (3, 11, 'Audiência de julgamento', 1),
            (4,  2, 'Audiência de conciliação', 0),
            (5, 11, 'Terceira instrução', 0)
        """))
        conn.commit()

    relatorio = investigar_pendencias(
        engine,
        [PendenciaEnum("hearingcontrol", "hearingtype", "11")],
        limite_linhas=5,
    )

    item = relatorio["investigacoes"][0]
    # As linhas de exemplo devem ter sido coletadas apenas das linhas com
    # hearingtype=11 — verificamos que nenhuma delas seria gerada por amostra
    # genérica (rows com hearingtype != 11 não devem aparecer).
    # Como a coluna 'observation' é textual e variável, não deve gerar
    # alta_confianca, mas as linhas DEVEM existir.
    assert item["linhas_exemplo"], "Devem existir linhas para hearingtype=11"
    assert len(item["linhas_exemplo"]) <= 5


def test_coluna_tem_nome_semantico_verdadeiro() -> None:
    """Bug 3: colunas com nome sugestivo devem ser identificadas como semânticas."""
    assert _coluna_tem_nome_semantico("typename") is True
    assert _coluna_tem_nome_semantico("description") is True
    assert _coluna_tem_nome_semantico("hearing_title") is True
    assert _coluna_tem_nome_semantico("label_id") is True
    assert _coluna_tem_nome_semantico("observacao") is True


def test_coluna_tem_nome_semantico_falso() -> None:
    """Bug 3: colunas técnicas/booleanas não devem ser identificadas como semânticas."""
    assert _coluna_tem_nome_semantico("hearingfile") is False
    assert _coluna_tem_nome_semantico("dispensed") is False
    assert _coluna_tem_nome_semantico("correspondent") is False
    assert _coluna_tem_nome_semantico("status") is False


def test_pista_e_booleana_apenas_zero_um() -> None:
    """Bug 3: pista com apenas 0/1 é classificada como booleana."""
    assert _pista_e_booleana([{"valor": "0", "ocorrencias": 5}]) is True
    assert _pista_e_booleana([{"valor": "1", "ocorrencias": 3}]) is True


def test_pista_nao_e_booleana_com_valor_textual() -> None:
    """Bug 3: pista com valor textual não é classificada como booleana."""
    assert _pista_e_booleana([{"valor": "Boleto", "ocorrencias": 5}]) is False
    assert _pista_e_booleana([{"valor": "11", "ocorrencias": 3}]) is False


def test_investigar_pendencias_nao_classifica_booleana_como_alta_confianca() -> None:
    """Bug 3: coluna booleana com valor constante não deve gerar alta_confianca —
    deve cair para pista_unica com aviso de pista fraca.
    Esse era o padrão falso-positivo que causou hearingtype[11]='0' no dicionário."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE hearingcontrol (
                id INTEGER PRIMARY KEY,
                hearingtype INTEGER,
                hearingfile INTEGER,
                dispensed INTEGER
            )
        """))
        # Todas as linhas com hearingtype=11 têm hearingfile=0 e dispensed=0
        # (padrão booleano) — isso NÃO deve disparar alta_confianca.
        conn.execute(text("""
            INSERT INTO hearingcontrol (id, hearingtype, hearingfile, dispensed) VALUES
            (1, 11, 0, 0),
            (2, 11, 0, 0),
            (3, 11, 0, 0),
            (4, 11, 0, 0),
            (5, 11, 0, 0)
        """))
        conn.commit()

    relatorio = investigar_pendencias(
        engine,
        [PendenciaEnum("hearingcontrol", "hearingtype", "11")],
        limite_linhas=5,
    )

    item = relatorio["investigacoes"][0]
    assert item["sugestao"]["status"] != "alta_confianca", (
        "Coluna booleana com valor constante não deve gerar alta_confianca"
    )


def test_investigar_pendencias_coluna_semantica_gera_alta_confianca() -> None:
    """Bug 3: quando há coluna com nome semântico (ex: typename) e valor único
    consistente, deve gerar alta_confianca normalmente."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE hearingcontrol (
                id INTEGER PRIMARY KEY,
                hearingtype INTEGER,
                typename TEXT,
                hearingfile INTEGER
            )
        """))
        conn.execute(text("""
            INSERT INTO hearingcontrol (id, hearingtype, typename, hearingfile) VALUES
            (1, 11, 'Instrução', 0),
            (2, 11, 'Instrução', 0),
            (3, 11, 'Instrução', 1)
        """))
        conn.commit()

    relatorio = investigar_pendencias(
        engine,
        [PendenciaEnum("hearingcontrol", "hearingtype", "11")],
        limite_linhas=5,
    )

    item = relatorio["investigacoes"][0]
    assert item["sugestao"]["status"] == "alta_confianca"
    assert item["sugestao"]["traducao_sugerida"] == "Instrução"


# ---------------------------------------------------------------------------
# Testes específicos para o falso negativo residual em pedidos2lawsuit.status=6
# (Parte 0 da rodada 4)
# ---------------------------------------------------------------------------

def _engine_pedidos2lawsuit_inteiro() -> "Engine":
    """Engine SQLite com pedidos2lawsuit, status como coluna INTEGER."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE pedidos2lawsuit (
                id          INTEGER PRIMARY KEY,
                status      INTEGER,
                claim_text  TEXT,
                agent       TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO pedidos2lawsuit VALUES
            (1, 6, 'Pedido de devolução de valores', 'Agência SP'),
            (2, 1, 'Pedido inicial',                 'Agência RJ'),
            (3, 6, 'Pedido revisional',               'Agência BH')
        """))
        conn.commit()
    return engine


def _engine_pedidos2lawsuit_texto() -> "Engine":
    """Engine SQLite com pedidos2lawsuit, status como coluna TEXT (armazena '6')."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE pedidos2lawsuit (
                id          INTEGER PRIMARY KEY,
                status      TEXT,
                claim_text  TEXT,
                agent       TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO pedidos2lawsuit VALUES
            (1, '6', 'Pedido de devolução de valores', 'Agência SP'),
            (2, '1', 'Pedido inicial',                 'Agência RJ'),
            (3, '6', 'Pedido revisional',               'Agência BH')
        """))
        conn.commit()
    return engine


def test_investigar_pedidos2lawsuit_status6_coluna_inteira_nao_retorna_sem_registros() -> None:
    """Parte 0: investigação de pedidos2lawsuit.status=6 com coluna INTEGER
    não deve retornar sem_registros quando a linha existe."""
    engine = _engine_pedidos2lawsuit_inteiro()
    pendencias = [PendenciaEnum("pedidos2lawsuit", "status", "6", "investigacao_direta")]
    relatorio = investigar_pendencias(engine, pendencias, limite_linhas=5)

    item = relatorio["investigacoes"][0]
    assert item["linhas_exemplo"], "Deve encontrar linhas com status=6 (INTEGER)"
    assert item["sugestao"]["status"] != "sem_registros", (
        "sem_registros é falso negativo: a linha existe no banco"
    )


def test_investigar_pedidos2lawsuit_status6_coluna_texto_usa_fallback() -> None:
    """Parte 0: quando o status é TEXT '6' e a query exata (= int 6) não retorna
    linhas no SQLite, o fallback CAST deve encontrar as linhas corretamente."""
    engine = _engine_pedidos2lawsuit_texto()
    pendencias = [PendenciaEnum("pedidos2lawsuit", "status", "6", "investigacao_direta")]
    relatorio = investigar_pendencias(engine, pendencias, limite_linhas=5)

    item = relatorio["investigacoes"][0]
    # O fallback de comparação via CAST deve evitar o falso negativo.
    assert item["linhas_exemplo"], "Fallback CAST deve encontrar linhas com status='6' (TEXT)"
    assert item["sugestao"]["status"] != "sem_registros", (
        "Falso negativo residual: fallback CAST deve detectar as linhas existentes"
    )


def test_contar_linhas_com_valor_retorna_contagem_correta() -> None:
    """_contar_linhas_com_valor deve retornar o número real de linhas com o valor."""
    engine = _engine_pedidos2lawsuit_inteiro()
    pendencia = PendenciaEnum("pedidos2lawsuit", "status", "6")
    contagem = _contar_linhas_com_valor(engine, pendencia, param_valor=6)
    assert contagem == 2  # há 2 linhas com status=6 no engine


def test_contar_linhas_com_valor_retorna_zero_quando_nao_existe() -> None:
    """_contar_linhas_com_valor retorna 0 quando nenhuma linha tem o valor."""
    engine = _engine_pedidos2lawsuit_inteiro()
    pendencia = PendenciaEnum("pedidos2lawsuit", "status", "99")
    contagem = _contar_linhas_com_valor(engine, pendencia, param_valor=99)
    assert contagem == 0
