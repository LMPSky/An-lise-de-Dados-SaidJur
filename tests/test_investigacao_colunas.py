"""Testes do fluxo de investigação de nomes de coluna."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
import yaml

from aplicar_sugestoes_colunas import _revisar_interativo, aplicar_traducoes_no_arquivo
from src.investigacao_colunas import (
    classificar_estado_traducao,
    coletar_pistas_coluna,
    executar_investigacao_colunas,
    investigar_coluna,
    listar_colunas_schema,
    _pista_provavel_booleano,
)



def test_classificar_estado_traduzida_manual() -> None:
    assert classificar_estado_traducao("created_at") == "traduzida_manual"



def test_classificar_estado_traduzida_heuristica(monkeypatch) -> None:
    from src import investigacao_colunas as modulo

    monkeypatch.setitem(modulo.TRADUCOES_COLUNAS, "processo", "Processo")
    assert classificar_estado_traducao("processo_id") == "traduzida_heuristica"



def test_classificar_estado_nao_traduzida() -> None:
    assert classificar_estado_traducao("xyzabc123") == "nao_traduzida"



def test_listar_colunas_schema_tabela() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE teste (id INTEGER PRIMARY KEY, nome TEXT, xyzabc123 TEXT)"))
        conn.commit()

    colunas = listar_colunas_schema(engine, "teste")

    assert [item["coluna"] for item in colunas] == ["id", "nome", "xyzabc123"]
    assert colunas[1]["tabela"] == "teste"



def test_column_comment_alta_confianca(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE teste (id INTEGER PRIMARY KEY, pzphase TEXT)"))
        conn.commit()

    class ResultadoFake:
        def fetchone(self):
            return ("Fase do prazo",)

    conexao_real = engine.connect

    class ConexaoFake:
        def __init__(self):
            self._conn = conexao_real()

        def __enter__(self):
            self._conn.__enter__()
            return self

        def __exit__(self, exc_type, exc, tb):
            return self._conn.__exit__(exc_type, exc, tb)

        def execute(self, statement, *args, **kwargs):
            if "information_schema.COLUMNS" in str(statement):
                return ResultadoFake()
            return self._conn.execute(statement, *args, **kwargs)

        def close(self):
            return self._conn.close()

        def __getattr__(self, name):
            return getattr(self._conn, name)

    monkeypatch.setattr(engine, "connect", lambda: ConexaoFake())

    pistas = coletar_pistas_coluna(engine, "teste", "pzphase", "TEXT")["pistas"]

    assert any(
        pista["fonte"] == "column_comment" and pista["confianca"] == "alta_confianca"
        for pista in pistas
    )



def test_tipo_dado_booleano() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE teste (ativo INTEGER)"))
        conn.commit()

    pistas = coletar_pistas_coluna(engine, "teste", "ativo", "TINYINT(1)")["pistas"]

    assert any("booleano" in pista["valor"].lower() for pista in pistas if pista["fonte"] == "tipo_dado")


def test_pista_provavel_booleano_aceita_zero_um_e_null() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE teste (ativo INTEGER)"))
        conn.execute(text("INSERT INTO teste (ativo) VALUES (1), (0), (NULL), ('1')"))
        conn.commit()

    pista = _pista_provavel_booleano(engine, "teste", "ativo", "INTEGER")

    assert pista is not None
    assert pista["categoria"] == "provavel_booleano"
    assert pista["valores_observados"] == ["0", "1"]


def test_pista_provavel_booleano_rejeita_valor_fora_do_dominio() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE teste (status INTEGER)"))
        conn.execute(text("INSERT INTO teste (status) VALUES (0), (1), (2)"))
        conn.commit()

    pista = _pista_provavel_booleano(engine, "teste", "status", "INTEGER")

    assert pista is None


def test_pista_provavel_booleano_rejeita_coluna_pk() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE country (id INTEGER PRIMARY KEY, nome TEXT)"))
        conn.execute(text("INSERT INTO country (id, nome) VALUES (0, 'A'), (1, 'B')"))
        conn.commit()

    pista = _pista_provavel_booleano(engine, "country", "id", "INTEGER")

    assert pista is None


def test_pista_provavel_booleano_rejeita_coluna_fk() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE accounts (id INTEGER PRIMARY KEY, nome TEXT)"))
        conn.execute(text("CREATE TABLE controlpanel2accounts (account_id INTEGER, remote INTEGER)"))
        conn.execute(text("INSERT INTO controlpanel2accounts (account_id, remote) VALUES (0, 0), (1, 1), (NULL, NULL)"))
        conn.commit()

    pista_fk = _pista_provavel_booleano(engine, "controlpanel2accounts", "account_id", "INTEGER")
    pista_bool = _pista_provavel_booleano(engine, "controlpanel2accounts", "remote", "INTEGER")

    assert pista_fk is None
    assert pista_bool is not None
    assert pista_bool["categoria"] == "provavel_booleano"


def test_pista_provavel_booleano_rejeita_coluna_auditoria_userid() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE config_prazo_emails (created_at_userid INTEGER)"))
        conn.execute(text("INSERT INTO config_prazo_emails (created_at_userid) VALUES (0), (1), (NULL)"))
        conn.commit()

    pista = _pista_provavel_booleano(engine, "config_prazo_emails", "created_at_userid", "INTEGER")

    assert pista is None


def test_pista_provavel_booleano_rejeita_amostra_enviesada_com_valor_posterior() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE eventos (id INTEGER PRIMARY KEY, codigo_multiplo INTEGER)"))
        conn.execute(
            text(
                "INSERT INTO eventos (id, codigo_multiplo) VALUES "
                "(1, 0), (2, 1), (3, 0), (4, 1), (5, 2)"
            )
        )
        conn.commit()

    pista = _pista_provavel_booleano(engine, "eventos", "codigo_multiplo", "INTEGER")

    assert pista is None


def test_colunas_irmas_sugestao() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE documentos (prazo_status TEXT, prazo_id INTEGER, nome TEXT)"))
        conn.commit()

    pistas = coletar_pistas_coluna(engine, "documentos", "prazo_status", "TEXT")["pistas"]

    assert any(
        pista["fonte"] == "colunas_irmas" and pista.get("coluna_relacionada") == "prazo_id"
        for pista in pistas
    )



def test_investigar_coluna_individual(monkeypatch) -> None:
    from src import investigacao_colunas as modulo

    monkeypatch.setitem(modulo.TRADUCOES_COLUNAS, "processo", "Processo")
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE documentos (processo_id INTEGER, observacao TEXT)"))
        conn.commit()

    resultado = investigar_coluna(engine, "documentos", "processo_id")

    assert resultado["estado"] == "traduzida_heuristica"
    assert resultado["sugestao_candidata"] == "ID do Processo"
    assert resultado["nivel_confianca"] == "alta_confianca"


def test_investigar_coluna_marca_provavel_booleano() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, flag_binaria INTEGER)"))
        conn.execute(text("INSERT INTO usuarios (flag_binaria) VALUES (0), (1), (NULL)"))
        conn.commit()

    resultado = investigar_coluna(engine, "usuarios", "flag_binaria")

    assert resultado["nivel_confianca"] == "pista_parcial"
    assert resultado["nivel_confianca_nome"] == "pista_parcial"
    assert resultado["classificacao_valores"] == "provavel_booleano"
    assert resultado["provavel_booleano"] is True
    assert resultado["sugestao_candidata"] is None


def test_investigar_coluna_traduzida_manual_tambem_marca_provavel_booleano(monkeypatch) -> None:
    from src import investigacao_colunas as modulo

    monkeypatch.setitem(modulo.TRADUCOES_COLUNAS, "ativo", "Ativo")
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE prazos_log (ativo INTEGER)"))
        conn.execute(text("INSERT INTO prazos_log (ativo) VALUES (0), (1), (NULL), (1)"))
        conn.commit()

    resultado = investigar_coluna(engine, "prazos_log", "ativo")

    assert resultado["estado"] == "traduzida_manual"
    assert resultado["nivel_confianca"] == "traduzida_manual"
    assert resultado["nivel_confianca_nome"] == "traduzida_manual"
    assert resultado["classificacao_valores"] == "provavel_booleano"
    assert resultado["provavel_booleano"] is True
    assert resultado["sugestao_candidata"] == "Ativo"


def test_aplicar_sugestoes_nao_sobrescreve_manual(monkeypatch, tmp_path: Path) -> None:
    relatorio = {
        "investigacoes": [
            {
                "tabela": "teste",
                "coluna": "created_at",
                "estado": "traduzida_manual",
                "traducao_atual": "Data de Criação",
                "nivel_confianca": "traduzida_manual",
                "sugestao_candidata": "Outra Tradução",
                "pistas": [],
            }
        ]
    }

    respostas = iter(["s", "n"])
    monkeypatch.setattr("builtins.input", lambda *_args: next(respostas))
    decisoes = _revisar_interativo(relatorio)

    assert decisoes[0]["decisao"] == "pular"
    assert decisoes[0]["traducao_final"] is None

    arquivo = tmp_path / "traducoes_colunas.py"
    arquivo.write_text(
        "TRADUCOES_COLUNAS = {\n    'created_at': 'Data de Criação',\n}\n",
        encoding="utf-8",
    )

    aplicadas = aplicar_traducoes_no_arquivo(arquivo, decisoes)
    assert aplicadas == []
    assert "Outra Tradução" not in arquivo.read_text(encoding="utf-8")



def test_executar_investigacao_colunas_gera_relatorio(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE teste (id INTEGER PRIMARY KEY, xyzabc123 TEXT)"))
        conn.commit()

    saida = tmp_path / "relatorio.yaml"
    relatorio = executar_investigacao_colunas(engine=engine, tabela="teste", caminho_saida=str(saida))

    assert relatorio["resumo"]["total_investigadas"] == 2
    dados = yaml.safe_load(saida.read_text(encoding="utf-8"))
    assert dados["investigacoes"][1]["coluna"] == "xyzabc123"


def test_executar_investigacao_colunas_agrupar_booleanos_no_relatorio(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, ativo INTEGER, status INTEGER)"))
        conn.execute(text("INSERT INTO users (ativo, status) VALUES (0, 0), (1, 2), (NULL, 1)"))
        conn.commit()

    saida = tmp_path / "relatorio_booleanos.yaml"
    relatorio = executar_investigacao_colunas(engine=engine, tabela="users", caminho_saida=str(saida))

    assert relatorio["resumo"]["provavel_booleano"] == 1
    assert relatorio["resumo"]["classificacao_nomes"]["traduzidas_manual"] == 2
    assert relatorio["resumo"]["classificacao_nomes"]["pista_parcial"] == 1
    assert relatorio["colunas_booleanas_provaveis"]["users"] == [
        {
            "coluna": "ativo",
            "tipo": "INTEGER",
            "valores_observados": ["0", "1"],
            "nulos_observados": True,
        }
    ]


def test_executar_investigacao_colunas_separa_resumo_nome_e_booleano(monkeypatch, tmp_path: Path) -> None:
    from src import investigacao_colunas as modulo

    monkeypatch.setitem(modulo.TRADUCOES_COLUNAS, "ativo", "Ativo")
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE prazos_log (ativo INTEGER, observacao TEXT)"))
        conn.execute(text("INSERT INTO prazos_log (ativo, observacao) VALUES (0, 'a'), (1, 'b'), (NULL, 'c')"))
        conn.commit()

    saida = tmp_path / "relatorio_prazos.yaml"
    relatorio = executar_investigacao_colunas(engine=engine, tabela="prazos_log", caminho_saida=str(saida))

    investigacao_ativo = next(item for item in relatorio["investigacoes"] if item["coluna"] == "ativo")
    assert investigacao_ativo["nivel_confianca_nome"] == "traduzida_manual"
    assert investigacao_ativo["provavel_booleano"] is True
    assert relatorio["resumo"]["provavel_booleano"] == 1
    assert relatorio["resumo"]["classificacao_nomes"]["traduzidas_manual"] == 1


def test_relatorio_exemplo_nao_inclui_falsos_positivos_pk_fk_userid(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE accounts (id INTEGER PRIMARY KEY, nome TEXT)"))
        conn.execute(text("CREATE TABLE country (id INTEGER PRIMARY KEY, nome TEXT)"))
        conn.execute(
            text(
                "CREATE TABLE controlpanel2accounts ("
                "controlpanel2accounts_id INTEGER PRIMARY KEY, "
                "account_id INTEGER, "
                "remote INTEGER)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE config_prazo_emails ("
                "id INTEGER PRIMARY KEY, "
                "created_at_userid INTEGER, "
                "ativo INTEGER)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO controlpanel2accounts (controlpanel2accounts_id, account_id, remote) VALUES "
                "(0, 0, 0), (1, 1, 1), (2, 7, 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO config_prazo_emails (id, created_at_userid, ativo) VALUES "
                "(0, 0, 0), (1, 1, 1), (2, 8, NULL)"
            )
        )
        conn.commit()

    saida = tmp_path / "relatorio_investigacao_colunas.yaml"
    relatorio = executar_investigacao_colunas(engine=engine, caminho_saida=str(saida))
    booleanas = {
        f"{item['tabela']}.{item['coluna']}"
        for item in relatorio["investigacoes"]
        if item.get("provavel_booleano")
    }

    assert "country.id" not in booleanas
    assert "controlpanel2accounts.controlpanel2accounts_id" not in booleanas
    assert "controlpanel2accounts.account_id" not in booleanas
    assert "config_prazo_emails.created_at_userid" not in booleanas
    assert "controlpanel2accounts.remote" in booleanas
    assert "config_prazo_emails.ativo" in booleanas

    dados_yaml = yaml.safe_load(saida.read_text(encoding="utf-8"))
    booleanas_yaml = {
        f"{item['tabela']}.{item['coluna']}"
        for item in dados_yaml["investigacoes"]
        if item.get("provavel_booleano")
    }
    assert "config_prazo_emails.created_at_userid" not in booleanas_yaml


def test_pista_provavel_booleano_rejeita_todos_casos_fk_reportados(tmp_path: Path) -> None:
    """Colunas *_id que a heurística de FK reconhece como referência a outra tabela
    não devem ser classificadas como provavel_booleano, mesmo com valores {0,1,NULL}.

    Cobre exatamente os 6 casos de falsos positivos reportados pelo usuário:
    account_id, sub_judicial_area_id, coligada_id, jobrole_id, busunit_id, paymentlimit_id.
    """
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        # Tabelas de referência necessárias para que a heurística de FK reconheça
        # cada coluna como FK válida (nomes gerados por _candidatos_para).
        conn.execute(text("CREATE TABLE accounts (id INTEGER PRIMARY KEY, nome TEXT)"))
        conn.execute(text("CREATE TABLE sub_judicial_areas (id INTEGER PRIMARY KEY, nome TEXT)"))
        conn.execute(text("CREATE TABLE coligadas (id INTEGER PRIMARY KEY, nome TEXT)"))
        conn.execute(text("CREATE TABLE jobroles (id INTEGER PRIMARY KEY, nome TEXT)"))
        conn.execute(text("CREATE TABLE busunits (id INTEGER PRIMARY KEY, nome TEXT)"))
        conn.execute(text("CREATE TABLE paymentlimits (id INTEGER PRIMARY KEY, nome TEXT)"))

        # Tabela de testes com todos os casos reportados como FK + colunas
        # genuinamente booleanas para validar que não há regressão.
        conn.execute(
            text(
                "CREATE TABLE casos_reportados ("
                "id INTEGER PRIMARY KEY, "
                "account_id INTEGER, "
                "sub_judicial_area_id INTEGER, "
                "coligada_id INTEGER, "
                "jobrole_id INTEGER, "
                "busunit_id INTEGER, "
                "paymentlimit_id INTEGER, "
                "ativo INTEGER, "
                "remote INTEGER)"
            )
        )
        # Inserir valores {0,1,NULL} em todas as colunas para simular o cenário
        # que causava os falsos positivos.
        conn.execute(
            text(
                "INSERT INTO casos_reportados "
                "(account_id, sub_judicial_area_id, coligada_id, jobrole_id, busunit_id, paymentlimit_id, ativo, remote) "
                "VALUES (0, 0, 0, 0, 0, 0, 0, 0), "
                "(1, 1, 1, 1, 1, 1, 1, 1), "
                "(NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)"
            )
        )
        conn.commit()

    fks_reportadas = [
        "account_id",
        "sub_judicial_area_id",
        "coligada_id",
        "jobrole_id",
        "busunit_id",
        "paymentlimit_id",
    ]

    # Nenhuma coluna FK deve ser classificada como booleana.
    for coluna in fks_reportadas:
        pista = _pista_provavel_booleano(engine, "casos_reportados", coluna, "INTEGER")
        assert pista is None, (
            f"Coluna FK '{coluna}' foi incorretamente classificada como provavel_booleano"
        )

    # Colunas genuinamente booleanas continuam sendo detectadas (sem regressão).
    for coluna_bool in ("ativo", "remote"):
        pista = _pista_provavel_booleano(engine, "casos_reportados", coluna_bool, "INTEGER")
        assert pista is not None, (
            f"Coluna booleana '{coluna_bool}' deixou de ser detectada como provavel_booleano"
        )
        assert pista["categoria"] == "provavel_booleano"

    # Verificar também via executar_investigacao_colunas (relatório completo).
    saida = tmp_path / "relatorio_casos_fk.yaml"
    relatorio = executar_investigacao_colunas(
        engine=engine, tabela="casos_reportados", caminho_saida=str(saida)
    )
    booleanas = {
        item["coluna"]
        for item in relatorio["investigacoes"]
        if item.get("provavel_booleano")
    }
    for coluna in fks_reportadas:
        assert coluna not in booleanas, (
            f"Coluna FK '{coluna}' apareceu como provavel_booleano no relatório completo"
        )
    assert "ativo" in booleanas
    assert "remote" in booleanas
