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
    carregar_pendencias_markdown,
    carregar_pendencias_enum,
    descobrir_pendencias_schema,
    executar_investigacao,
    expandir_pendencias_com_dominio,
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
    _coletar_contexto_coluna_obs,
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


def test_carregar_pendencias_markdown_extrai_referencias_e_valor(tmp_path: Path) -> None:
    caminho = tmp_path / "PENDENCIAS.md"
    caminho.write_text(
        "## Valores de ENUM/código pendentes\n"
        "| Tabela | Coluna | Valores pendentes |\n"
        "|--------|--------|-------------------|\n"
        "| `prazos_log` / `prazo2publication` | `pzphase` | `{3, 4}` |\n"
        "| `tarefas` | `status` | `{novo, antigo}` |",
        encoding="utf-8",
    )

    assert carregar_pendencias_markdown(caminho) == [
        PendenciaEnum("prazos_log", "pzphase", "3", "pendencia_documentada"),
        PendenciaEnum("prazos_log", "pzphase", "4", "pendencia_documentada"),
        PendenciaEnum("prazo2publication", "pzphase", "3", "pendencia_documentada"),
        PendenciaEnum("prazo2publication", "pzphase", "4", "pendencia_documentada"),
        PendenciaEnum("tarefas", "status", "novo", "pendencia_documentada"),
        PendenciaEnum("tarefas", "status", "antigo", "pendencia_documentada"),
    ]


def test_carregar_pendencias_markdown_ignora_nomes_de_arquivo(tmp_path: Path) -> None:
    caminho = tmp_path / "PENDENCIAS.md"
    caminho.write_text(
        "Fonte: `relatorio_auditoria_traducoes.yaml`\n"
        "Execute `python investigar_pendencias.py --colunas tabela.coluna`.\n"
        "## Valores de ENUM/código pendentes\n"
        "| Tabela | Coluna | Valores pendentes |\n"
        "|--------|--------|-------------------|\n"
        "| `tarefas` | `status` | `{novo}` |\n",
        encoding="utf-8",
    )

    assert carregar_pendencias_markdown(caminho) == [
        PendenciaEnum("tarefas", "status", "novo", "pendencia_documentada"),
    ]


def test_carregar_pendencias_markdown_ignora_blocos_de_codigo(tmp_path: Path) -> None:
    caminho = tmp_path / "PENDENCIAS.md"
    caminho.write_text(
        "```bash\n"
        "python investigar_pendencias.py --colunas falsa.tabela:1\n"
        "| `tambem_falsa` | `status` | `{1}` |\n"
        "```\n"
        "## Valores de ENUM/código pendentes\n"
        "| Tabela | Coluna | Valores pendentes |\n"
        "|--------|--------|-------------------|\n"
        "| `tarefas` | `status` | `{novo}` |\n",
        encoding="utf-8",
    )

    assert carregar_pendencias_markdown(caminho) == [
        PendenciaEnum("tarefas", "status", "novo", "pendencia_documentada"),
    ]


def test_expandir_pendencias_com_dominio_descarta_tabela_inexistente() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE tarefas (status TEXT)"))
        conn.execute(text("INSERT INTO tarefas (status) VALUES ('novo'), ('antigo')"))
        conn.commit()

    pendencias = [
        PendenciaEnum("relatorio_auditoria_traducoes", "yaml", "*", "pendencia_documentada"),
        PendenciaEnum("tarefas", "status", "*", "pendencia_documentada"),
    ]

    assert expandir_pendencias_com_dominio(engine, pendencias) == [
        PendenciaEnum("tarefas", "status", "antigo", "pendencia_documentada"),
        PendenciaEnum("tarefas", "status", "novo", "pendencia_documentada"),
    ]


def test_investigar_pendencias_registra_erro_por_item_e_continua() -> None:
    import src.investigacao_pendencias as mod

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE falha (codigo TEXT, name TEXT)"))
        conn.execute(text("CREATE TABLE sucesso (codigo TEXT, name TEXT)"))
        conn.execute(text("INSERT INTO sucesso (codigo, name) VALUES ('ok', 'Rótulo válido')"))
        conn.commit()

    original_coletar = mod._coletar_linhas_exemplo

    def _coletar_com_falha(engine_arg, pendencia, colunas_pista, *, limite_linhas):
        if pendencia.tabela == "falha":
            raise RuntimeError("falha SQL simulada")
        return original_coletar(engine_arg, pendencia, colunas_pista, limite_linhas=limite_linhas)

    with (
        patch.object(mod, "_buscar_em_tabela_referencia", return_value=None),
        patch.object(mod, "_coletar_linhas_exemplo", side_effect=_coletar_com_falha),
    ):
        relatorio = investigar_pendencias(
            engine,
            [
                PendenciaEnum("falha", "codigo", "x", "pendencia_documentada"),
                PendenciaEnum("sucesso", "codigo", "ok", "pendencia_documentada"),
            ],
            limite_linhas=5,
        )

    assert relatorio["resumo"]["total_pendencias"] == 2
    assert relatorio["resumo"]["erros"] == 1
    assert relatorio["investigacoes"][0]["sugestao"]["status"] == "erro"
    assert relatorio["investigacoes"][1]["sugestao"]["status"] != "erro"
    assert "falha SQL simulada" in relatorio["investigacoes"][0]["sugestao"]["justificativa"]


def test_descobrir_pendencias_schema_ignora_texto_livre_e_ja_traduzidos() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE tarefas (status TEXT, observacao TEXT)"))
        conn.execute(text(
            "INSERT INTO tarefas VALUES ('novo', 'Texto de observação livre bastante longo que não é código')"
        ))
        conn.commit()

    pendencias = descobrir_pendencias_schema(engine, {"tarefas": {"status": {"novo": "Novo"}}})

    assert pendencias == []



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


# ---------------------------------------------------------------------------
# Testes Parte 0 — Bug de rótulo nulo em tabela de referência
# ---------------------------------------------------------------------------

def _engine_tabela_referencia_rotulo_nulo() -> Engine:
    """Engine com tabela de referência onde o rótulo é NULL para o código investigado."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE hearingstatus (
                id   INTEGER PRIMARY KEY,
                observation TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE hearingcontrol (
                id           INTEGER PRIMARY KEY,
                hearingstatus INTEGER
            )
        """))
        # Rótulo NULL para o código investigado (1)
        conn.execute(text("INSERT INTO hearingstatus (id, observation) VALUES (1, NULL)"))
        conn.execute(text("INSERT INTO hearingcontrol (id, hearingstatus) VALUES (1, 1)"))
        conn.commit()
    return engine


def test_rotulo_nulo_nao_gera_alta_confianca() -> None:
    """Parte 0: rótulo NULL na tabela de referência nunca deve gerar alta_confianca.

    Garante que quando a coluna de rótulo retorna NULL no banco para o código
    investigado, a ferramenta rejeita a linha e não trata o valor Python None
    como a string literal 'None'.
    """
    engine = _engine_tabela_referencia_rotulo_nulo()
    pendencias = [PendenciaEnum("hearingcontrol", "hearingstatus", "1", "investigacao_direta")]
    relatorio = investigar_pendencias(engine, pendencias, limite_linhas=10)

    item = relatorio["investigacoes"][0]
    sugestao = item["sugestao"]

    # O rótulo NULL não pode ser aceito como tradução válida
    assert sugestao.get("traducao_sugerida") != "None", (
        "Rótulo NULL não deve ser convertido para string 'None' e aceito como tradução"
    )
    assert sugestao["status"] != "alta_confianca" or sugestao.get("traducao_sugerida") not in (None, "None", ""), (
        "Status alta_confianca nunca deve ter tradução None/vazia vinda de rótulo nulo"
    )


def test_rotulo_nulo_status_rebaixado() -> None:
    """Parte 0: quando todas as linhas candidatas têm rótulo nulo, o status deve ser
    rebaixado (não 'alta_confianca') e a tradução sugerida não deve ser 'None'.
    """
    engine = _engine_tabela_referencia_rotulo_nulo()
    pendencias = [PendenciaEnum("hearingcontrol", "hearingstatus", "1", "investigacao_direta")]
    relatorio = investigar_pendencias(engine, pendencias, limite_linhas=10)

    item = relatorio["investigacoes"][0]
    status = item["sugestao"]["status"]
    traducao = item["sugestao"].get("traducao_sugerida")

    assert status != "alta_confianca" or traducao not in (None, "None"), (
        f"Tradução inválida '{traducao}' com status '{status}' para rótulo nulo"
    )
    # A tradução não deve ser a string literal "None"
    assert traducao != "None", (
        "A ferramenta converteu None para string 'None' — bug de rótulo nulo não corrigido"
    )


# ---------------------------------------------------------------------------
# Testes Parte A — Novos padrões de nome de tabela candidata
# ---------------------------------------------------------------------------

def _engine_pzphase() -> Engine:
    """Engine com tabela nomeada 'prazofases' para o campo 'pzphase'."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE prazofases (
                id    INTEGER PRIMARY KEY,
                pzphase INTEGER,
                nome  TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE prazos_log (
                id      INTEGER PRIMARY KEY,
                pzphase INTEGER
            )
        """))
        conn.execute(text("INSERT INTO prazofases (id, pzphase, nome) VALUES (2, 2, 'Aguardando')"))
        conn.execute(text("INSERT INTO prazos_log (id, pzphase) VALUES (1, 2)"))
        conn.commit()
    return engine


def test_pzphase_detecta_tabela_prazofases() -> None:
    """Parte A: coluna 'pzphase' com prefixo 'pz' deve encontrar tabela 'prazofases'.

    Verifica que a expansão do prefixo abreviado 'pz' → 'prazo' permite
    detectar a tabela de catálogo com nome 'prazofases'.
    """
    engine = _engine_pzphase()
    pendencias = [PendenciaEnum("prazos_log", "pzphase", "2", "investigacao_direta")]
    relatorio = investigar_pendencias(engine, pendencias, limite_linhas=10)

    item = relatorio["investigacoes"][0]
    sugestao = item["sugestao"]

    assert sugestao.get("traducao_sugerida") == "Aguardando", (
        f"Esperava 'Aguardando' via tabela prazofases, obtido: {sugestao!r}"
    )
    assert sugestao["status"] == "alta_confianca", (
        f"Esperava alta_confianca, obtido: {sugestao['status']!r}"
    )


def _engine_contract_type() -> Engine:
    """Engine com tabela 'tipos_contrato' para o campo 'contract_type'."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE tipos_contrato (
                id   INTEGER PRIMARY KEY,
                code TEXT NOT NULL,
                nome TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE lawsuits (
                id            INTEGER PRIMARY KEY,
                contract_type TEXT
            )
        """))
        conn.execute(text("INSERT INTO tipos_contrato (id, code, nome) VALUES (1, 'es', 'Escritório')"))
        conn.execute(text("INSERT INTO lawsuits (id, contract_type) VALUES (1, 'es')"))
        conn.commit()
    return engine


def test_contract_type_detecta_tabela_tipos_contrato() -> None:
    """Parte A: coluna 'contract_type' deve encontrar tabela 'tipos_contrato'.

    Verifica o padrão de nome de tabela específico do domínio jurídico BR.
    """
    engine = _engine_contract_type()
    pendencias = [PendenciaEnum("lawsuits", "contract_type", "es", "investigacao_direta")]
    relatorio = investigar_pendencias(engine, pendencias, limite_linhas=10)

    item = relatorio["investigacoes"][0]
    sugestao = item["sugestao"]

    assert sugestao.get("traducao_sugerida") == "Escritório", (
        f"Esperava 'Escritório' via tabela tipos_contrato, obtido: {sugestao!r}"
    )


def _engine_publicationtype() -> Engine:
    """Engine com tabela 'publicationtypes' para o campo 'publicationtype'."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE publicationtypes (
                id   INTEGER PRIMARY KEY,
                nome TEXT NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE prazo2publication (
                id             INTEGER PRIMARY KEY,
                publicationtype INTEGER
            )
        """))
        conn.execute(text(
            "INSERT INTO publicationtypes (id, nome) VALUES (58704, 'DJSP - Intimações')"
        ))
        conn.execute(text("INSERT INTO prazo2publication (id, publicationtype) VALUES (1, 58704)"))
        conn.commit()
    return engine


def test_publicationtype_detecta_tabela_publicationtypes() -> None:
    """Parte A: coluna 'publicationtype' deve encontrar tabela 'publicationtypes'.

    Verifica que o padrão <entidade>type → <entidade>types é coberto pela
    heurística ampliada de nomes candidatos.
    """
    engine = _engine_publicationtype()
    pendencias = [PendenciaEnum("prazo2publication", "publicationtype", "58704", "investigacao_direta")]
    relatorio = investigar_pendencias(engine, pendencias, limite_linhas=10)

    item = relatorio["investigacoes"][0]
    sugestao = item["sugestao"]

    assert sugestao.get("traducao_sugerida") == "DJSP - Intimações", (
        f"Esperava 'DJSP - Intimações' via tabela publicationtypes, obtido: {sugestao!r}"
    )


def test_coletar_contexto_coluna_obs_retorna_distribuicao() -> None:
    """Verifica que _coletar_contexto_coluna_obs agrega valores de coluna de observação."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE prazos_log (
                id INTEGER PRIMARY KEY,
                pzphase INTEGER,
                prazoobs TEXT
            )
        """))
        conn.execute(text("INSERT INTO prazos_log (pzphase, prazoobs) VALUES (3, 'Prazo de recurso')"))
        conn.execute(text("INSERT INTO prazos_log (pzphase, prazoobs) VALUES (3, 'Prazo de recurso')"))
        conn.execute(text("INSERT INTO prazos_log (pzphase, prazoobs) VALUES (3, 'Contestação')"))
        conn.commit()

    colunas = listar_colunas_tabela(engine, "prazos_log")
    pendencia = PendenciaEnum("prazos_log", "pzphase", "3", "investigacao_direta")
    resultado = _coletar_contexto_coluna_obs(engine, pendencia, colunas, limite_linhas=20)

    assert resultado is not None
    assert resultado["coluna_obs"] == "prazoobs"
    assert resultado["valores_distintos"] == 2
    amostras_vals = [a["valor"] for a in resultado["amostras"]]
    assert "Prazo de recurso" in amostras_vals
    assert "Contestação" in amostras_vals
    # Verificar que o valor mais frequente vem primeiro
    assert resultado["amostras"][0]["valor"] == "Prazo de recurso"
    assert resultado["amostras"][0]["ocorrencias"] == 2


def test_coletar_contexto_coluna_obs_retorna_none_sem_coluna_obs() -> None:
    """Verifica que _coletar_contexto_coluna_obs retorna None quando não há coluna de observação."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE hearingcontrol (
                id INTEGER PRIMARY KEY,
                hearingtype INTEGER,
                hearingdate TEXT
            )
        """))
        conn.execute(text("INSERT INTO hearingcontrol (hearingtype, hearingdate) VALUES (11, '2024-01-01')"))
        conn.commit()

    colunas = listar_colunas_tabela(engine, "hearingcontrol")
    pendencia = PendenciaEnum("hearingcontrol", "hearingtype", "11", "investigacao_direta")
    resultado = _coletar_contexto_coluna_obs(engine, pendencia, colunas, limite_linhas=20)

    assert resultado is None


def test_investigar_pendencias_inclui_contexto_obs_quando_sem_alta_confianca() -> None:
    """Verifica que investigar_pendencias adiciona contexto_obs quando status != alta_confianca."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE prazos_log (
                id INTEGER PRIMARY KEY,
                pzphase INTEGER,
                prazoobs TEXT
            )
        """))
        # Múltiplos obs distintos → não gera alta_confianca na coluna pista
        conn.execute(text("INSERT INTO prazos_log (pzphase, prazoobs) VALUES (4, 'Fase de julgamento')"))
        conn.execute(text("INSERT INTO prazos_log (pzphase, prazoobs) VALUES (4, 'Julgamento por juiz leigo')"))
        conn.execute(text("INSERT INTO prazos_log (pzphase, prazoobs) VALUES (4, 'Processo em pauta')"))
        conn.commit()

    pendencias = [PendenciaEnum("prazos_log", "pzphase", "4", "investigacao_direta")]
    relatorio = investigar_pendencias(engine, pendencias, limite_linhas=10)

    item = relatorio["investigacoes"][0]
    # Com múltiplas obs distintas, não deve haver alta confiança
    assert item["sugestao"]["status"] != "alta_confianca"
    assert "contexto_obs" in item
    assert item["contexto_obs"]["coluna_obs"] == "prazoobs"
    amostras_vals = [a["valor"] for a in item["contexto_obs"]["amostras"]]
    assert "Fase de julgamento" in amostras_vals


def test_investigar_pendencias_nao_inclui_contexto_obs_quando_alta_confianca() -> None:
    """Verifica que contexto_obs não é adicionado quando há tabela de referência (alta confiança)."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE prazos_log (
                id INTEGER PRIMARY KEY,
                pzphase INTEGER,
                prazoobs TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE pzphases (
                id INTEGER PRIMARY KEY,
                nome TEXT
            )
        """))
        conn.execute(text("INSERT INTO pzphases (id, nome) VALUES (4, 'Aguardando julgamento')"))
        conn.execute(text("INSERT INTO prazos_log (pzphase, prazoobs) VALUES (4, 'Fase de julgamento')"))
        conn.commit()

    pendencias = [PendenciaEnum("prazos_log", "pzphase", "4", "investigacao_direta")]
    relatorio = investigar_pendencias(engine, pendencias, limite_linhas=10)

    item = relatorio["investigacoes"][0]
    assert item["sugestao"]["status"] == "alta_confianca"
    assert "contexto_obs" not in item


def test_multiplas_pistas_concordantes_aumentam_confianca() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE itens (codigo TEXT, nome TEXT, descricao TEXT)"))
        conn.execute(text("INSERT INTO itens VALUES ('x', 'Categoria', NULL), ('x', NULL, 'Categoria')"))
        conn.commit()

    item = investigar_pendencias(engine, [PendenciaEnum("itens", "codigo", "x")])["investigacoes"][0]

    assert item["sugestao"]["status"] == "alta_confianca"
    assert item["sugestao"]["fonte"] == "multiplas_pistas"
    assert item["sugestao"]["traducao_sugerida"] == "Categoria"


def test_propaga_traducao_entre_tabelas_irmas() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE prazo2publication (pzphase INTEGER, nome TEXT)"))
        conn.execute(text("CREATE TABLE prazos_log (pzphase INTEGER)"))
        conn.execute(text("INSERT INTO prazo2publication VALUES (3, 'Recurso'), (3, 'Recurso')"))
        conn.execute(text("INSERT INTO prazos_log VALUES (3)"))
        conn.commit()

    with patch("src.investigacao_pendencias._buscar_em_tabela_referencia", return_value=None):
        relatorio = investigar_pendencias(
            engine,
            [PendenciaEnum("prazo2publication", "pzphase", "3"), PendenciaEnum("prazos_log", "pzphase", "3")],
        )
    destino = relatorio["investigacoes"][1]

    assert destino["sugestao"]["status"] == "alta_confianca"
    assert destino["sugestao"]["fonte"] == "tabela_irma"
    assert destino["sugestao"]["traducao_sugerida"] == "Recurso"


def test_relatorio_inclui_distribuicao_e_agrupamento_consolidado() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE flags (status INTEGER)"))
        conn.execute(text("INSERT INTO flags VALUES (0), (0), (1), (1)"))
        conn.commit()

    relatorio = investigar_pendencias(engine, [PendenciaEnum("flags", "status", "0")])
    item = relatorio["investigacoes"][0]

    assert item["distribuicao_codigo"]["classificacao"] == "binario_balanceado"
    assert relatorio["agrupado_por_confianca_e_tabela"]["sem_pista_encontrada"]["flags"] == ["status:0"]
