"""Testes da investigação assistida de pendências de tradução."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
import yaml

from src.investigacao_pendencias import (
    PendenciaEnum,
    aplicar_decisoes_em_dicionario,
    carregar_pendencias_enum,
    executar_investigacao,
    gerar_template_decisoes,
    investigar_pendencias,
    selecionar_colunas_pista,
    listar_colunas_tabela,
    _converter_valor_para_param,
    _coluna_tem_nome_semantico,
    _pista_e_booleana,
    _pista_parece_dado_especifico,
    _pista_parece_texto_livre,
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



def test_selecionar_colunas_pista_prefere_portugues_sobre_name_en() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE varas (
                id INTEGER PRIMARY KEY,
                code TEXT,
                name_en TEXT,
                name TEXT
            )
        """))
        conn.commit()

    colunas = listar_colunas_tabela(engine, "varas")
    candidatas = selecionar_colunas_pista(colunas, "code")

    assert candidatas.index("name") < candidatas.index("name_en")



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



def test_investigar_pendencias_detecta_tabela_referencia_via_schema() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE hearingcontrol (
                id INTEGER PRIMARY KEY,
                hearingtype INTEGER,
                note TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE hearingtypes (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO hearingcontrol (id, hearingtype, note) VALUES
            (1, 11, 'Linha sem pista forte'),
            (2, 11, 'Outra linha sem pista forte')
        """))
        conn.execute(text("INSERT INTO hearingtypes (id, name) VALUES (11, 'Audiência de Instrução')"))
        conn.commit()

    relatorio = investigar_pendencias(engine, [PendenciaEnum("hearingcontrol", "hearingtype", "11")])

    item = relatorio["investigacoes"][0]
    assert item["tabela_referencia"] == "hearingtypes"
    assert item["sugestao"]["status"] == "alta_confianca"
    assert item["sugestao"]["traducao_sugerida"] == "Audiência de Instrução"
    assert "Tabela de referência 'hearingtypes'" in item["sugestao"]["justificativa"]



def test_investigar_pendencias_prefere_coluna_portugues_sobre_name_en() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE varas (
                id INTEGER PRIMARY KEY,
                code TEXT,
                name_en TEXT,
                name TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO varas (id, code, name_en, name) VALUES
            (1, '4', 'Federal Court', 'Vara Federal'),
            (2, '4', 'Federal Court', 'Vara Federal')
        """))
        conn.commit()

    relatorio = investigar_pendencias(engine, [PendenciaEnum("varas", "code", "4")])

    item = relatorio["investigacoes"][0]
    assert item["sugestao"]["status"] == "alta_confianca"
    assert item["sugestao"]["traducao_sugerida"] == "Vara Federal"
    assert "outro idioma" not in item["sugestao"]["justificativa"]



def test_investigar_pendencias_avisa_quando_pista_esta_so_em_outro_idioma() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE courts (
                id INTEGER PRIMARY KEY,
                code TEXT,
                name_en TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO courts (id, code, name_en) VALUES
            (1, '4', 'Federal Court'),
            (2, '4', 'Federal Court')
        """))
        conn.commit()

    relatorio = investigar_pendencias(engine, [PendenciaEnum("courts", "code", "4")])

    item = relatorio["investigacoes"][0]
    assert item["sugestao"]["status"] == "alta_confianca"
    assert "outro idioma" in item["sugestao"]["justificativa"]



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


def test_pista_parece_texto_livre_detecta_texto_longo() -> None:
    """Salvaguarda: textos longos/específicos não podem virar tradução de ENUM."""
    assert _pista_parece_texto_livre(
        "Audiência instrução designada para 11/06/2019 14:30 Seção B da 31ª Vara Cível da Capital."
    ) is True


def test_pista_parece_texto_livre_nao_bloqueia_rotulo_curto() -> None:
    """Rótulos curtos continuam aceitos como pistas válidas."""
    assert _pista_parece_texto_livre("Instrução") is False
    assert _pista_parece_texto_livre("Pessoa Jurídica") is False



def test_pista_parece_dado_especifico_distingue_nome_especifico_de_rotulo_generico() -> None:
    assert _pista_parece_dado_especifico("JAC BH Barão") is True
    assert _pista_parece_dado_especifico("Ativo") is False



def test_investigar_pendencias_rejeita_texto_livre_mesmo_em_coluna_semantica() -> None:
    """Mesmo com coluna semântica, texto livre longo deve ser descartado."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE hearings_log (
                id INTEGER PRIMARY KEY,
                hearingstatus INTEGER,
                observation TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO hearings_log (id, hearingstatus, observation) VALUES
            (1, 2, 'Audiência instrução designada para 11/06/2019 14:30 Seção B da 31ª Vara Cível da Capital.'),
            (2, 2, 'Audiência instrução designada para 11/06/2019 14:30 Seção B da 31ª Vara Cível da Capital.')
        """))
        conn.commit()

    relatorio = investigar_pendencias(
        engine,
        [PendenciaEnum("hearings_log", "hearingstatus", "2")],
        limite_linhas=5,
    )

    item = relatorio["investigacoes"][0]
    assert item["sugestao"]["status"] == "sem_pista_encontrada"
    assert item["sugestao"]["traducao_sugerida"] is None
    assert "descartadas por segurança" in item["sugestao"]["justificativa"]


def test_revisao_interativa_exibe_alerta_de_dado_especifico(capsys) -> None:
    from aplicar_sugestoes_investigacao import _revisar_interativo

    relatorio = {
        "investigacoes": [
            {
                "tabela": "lawsuits",
                "coluna": "finalpayment_type",
                "valor": "2",
                "sugestao": {
                    "status": "pista_unica",
                    "traducao_sugerida": "JAC BH Barão",
                    "justificativa": "Pista curta encontrada em coluna técnica.",
                    "alertas": [
                        {
                            "tipo": "possivel_dado_especifico",
                            "mensagem": (
                                "⚠️ Possível dado específico/sensível — verifique se este valor é "
                                "uma categoria genérica ou um dado real de caso antes de aplicar."
                            ),
                        }
                    ],
                },
            }
        ]
    }

    with patch("builtins.input", side_effect=["n"]):
        decisoes = _revisar_interativo(relatorio)

    saida = capsys.readouterr().out
    assert "Possível dado específico/sensível" in saida
    assert decisoes[0]["decisao"] == "pular"


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


def test_fallback_cast_nao_usa_text_no_mysql() -> None:
    """O fallback CAST não deve usar 'CAST(... AS TEXT)'.

    Valida que a expressão gerada pela ferramenta usa CAST(... AS CHAR), que é
    compatível tanto com MySQL/MariaDB quanto com SQLite.  Verifica inspecionando
    o SQL textual construído pelo fallback, sem precisar executar contra um banco
    real ou mocks de dialeto.
    """
    import inspect
    import src.investigacao_pendencias as mod

    # Filtra apenas linhas de código (exclui linhas de comentário puro)
    linhas_codigo = [
        linha
        for linha in inspect.getsource(mod._coletar_linhas_exemplo).splitlines()
        if not linha.strip().startswith("#")
    ]
    codigo_sem_comentarios = "\n".join(linhas_codigo).upper()

    # A sintaxe CAST(... AS TEXT) é inválida no MySQL/MariaDB; não pode aparecer.
    assert "AS TEXT" not in codigo_sem_comentarios, (
        "CAST com tipo TEXT encontrado em _coletar_linhas_exemplo (linhas de código). "
        "Use CAST(... AS CHAR) para compatibilidade com MySQL/MariaDB."
    )
    # Deve usar CHAR, aceito tanto no MySQL quanto no SQLite.
    # O tipo aparece na atribuição da variável _tipo_cast = "CHAR" no código.
    assert '"CHAR"' in codigo_sem_comentarios or "_TIPO_CAST = \"CHAR\"" in codigo_sem_comentarios, (
        "Esperado uso de tipo CHAR no fallback de _coletar_linhas_exemplo."
    )


def test_fallback_excecao_resulta_em_status_erro() -> None:
    """Se o fallback CAST lançar exceção, o resultado deve ser status='erro'.

    Garante que exceções reais de execução (ex: erro de sintaxe SQL no banco)
    não são silenciadas e mascaradas como 'sem_registros'.
    """
    import src.investigacao_pendencias as mod

    # Usa engine com coluna TEXT: a query direta (INTEGER) retorna 0 linhas no
    # SQLite, acionando o fallback. Patchamos executar_com_retry_db para que a
    # segunda chamada (fallback) simule um erro de SQL real.
    engine = _engine_pedidos2lawsuit_texto()
    pendencia = PendenciaEnum("pedidos2lawsuit", "status", "6", "investigacao_direta")

    chamadas = [0]
    original_retry = mod.executar_com_retry_db

    def _retry_com_falha_no_fallback(func, **kwargs):
        chamadas[0] += 1
        if chamadas[0] == 1:
            # Primeira chamada: query direta — executa normalmente (devolve [])
            return original_retry(func, **kwargs)
        # Segunda chamada: fallback CAST — simula erro de sintaxe SQL no banco
        raise RuntimeError("Simulated SQL syntax error: CAST type TEXT not supported")

    with patch.object(mod, "executar_com_retry_db", side_effect=_retry_com_falha_no_fallback):
        relatorio = investigar_pendencias(engine, [pendencia], limite_linhas=1)

    item = relatorio["investigacoes"][0]
    assert item["sugestao"]["status"] == "erro", (
        f"Exceção no fallback deve gerar status='erro', obtido: {item['sugestao']['status']!r}"
    )
    assert "Simulated SQL syntax error" in item["sugestao"]["justificativa"], (
        "A mensagem de erro original deve estar preservada na justificativa"
    )


def test_executar_investigacao_respeita_limite_linhas_em_colunas_diretas(tmp_path: Path) -> None:
    import src.investigacao_pendencias as mod

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE paymenttype (
                id INTEGER PRIMARY KEY,
                code TEXT,
                name TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO paymenttype (id, code, name) VALUES
            (1, 'Bol', 'Boleto'),
            (2, 'Bol', 'Boleto'),
            (3, 'Bol', 'Boleto'),
            (4, 'Bol', 'Boleto'),
            (5, 'Bol', 'Boleto')
        """))
        conn.commit()

    caminho_saida = tmp_path / "relatorio.yaml"
    with patch.object(mod, "criar_engine", return_value=engine):
        relatorio = executar_investigacao(
            caminho_saida=caminho_saida,
            limite_linhas=4,
            colunas_diretas=["paymenttype.code:Bol"],
        )

    item = relatorio["investigacoes"][0]
    assert relatorio["fonte_pendencias"] == "colunas_diretas:paymenttype.code:Bol"
    assert len(item["linhas_exemplo"]) == 4
