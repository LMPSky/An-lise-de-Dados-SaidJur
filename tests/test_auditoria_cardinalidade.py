"""Testes unitários para a auditoria de cobertura por cardinalidade real de coluna."""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy import create_engine, text

from src.auditoria_cardinalidade import (
    CARDINALIDADE_MAXIMA_PADRAO,
    _coletar_valores_distintos,
    _coluna_elegivel_cardinalidade,
    _coluna_parece_identificadora,
    _contar_valores_distintos,
    auditar_cobertura_por_cardinalidade,
)
from src.investigacao_pendencias import ColunaTabela


def _popular_tabela_tipos_documento(engine, total_tipos: int = 30) -> None:
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE lawsuitdocs (id INTEGER, doctype TEXT)"))
        for indice in range(total_tipos):
            conn.execute(
                text("INSERT INTO lawsuitdocs (id, doctype) VALUES (:id, :doctype)"),
                {"id": indice, "doctype": f"tipo_{indice}"},
            )
        conn.commit()


def test_contar_valores_distintos_sem_subselecao() -> None:
    engine = create_engine("sqlite:///:memory:")
    _popular_tabela_tipos_documento(engine, total_tipos=30)

    assert _contar_valores_distintos(engine, "lawsuitdocs", "doctype") == 30


def test_coletar_valores_distintos_retorna_todos_sem_teto_de_vinte() -> None:
    """Diferente da descoberta via schema (teto de 20), coleta todos os valores."""
    engine = create_engine("sqlite:///:memory:")
    _popular_tabela_tipos_documento(engine, total_tipos=30)

    valores = _coletar_valores_distintos(engine, "lawsuitdocs", "doctype", cardinalidade_maxima=30)

    assert len(valores) == 30
    assert set(valores) == {f"tipo_{i}" for i in range(30)}


def test_auditoria_encontra_coluna_com_mais_de_vinte_valores_sem_dicionario() -> None:
    """Caso central: coluna com >20 valores distintos, invisível às outras ferramentas."""
    engine = create_engine("sqlite:///:memory:")
    _popular_tabela_tipos_documento(engine, total_tipos=30)

    with patch("src.auditoria_cardinalidade.dicionario_de_coluna", return_value={}):
        relatorio = auditar_cobertura_por_cardinalidade(engine)

    assert relatorio["resumo"]["colunas_auditadas"] >= 1
    pendencia = next(
        p for p in relatorio["pendencias"] if p["tabela"] == "lawsuitdocs" and p["coluna"] == "doctype"
    )
    assert pendencia["cardinalidade"] == 30
    assert len(pendencia["valores_pendentes"]) == 30


def test_auditoria_ignora_coluna_ja_totalmente_traduzida() -> None:
    engine = create_engine("sqlite:///:memory:")
    _popular_tabela_tipos_documento(engine, total_tipos=5)

    dicionario_completo = {f"tipo_{i}": f"Tipo {i}" for i in range(5)}
    with patch("src.auditoria_cardinalidade.dicionario_de_coluna", return_value=dicionario_completo):
        relatorio = auditar_cobertura_por_cardinalidade(engine)

    tabelas_com_pendencia = {p["tabela"] for p in relatorio["pendencias"]}
    assert "lawsuitdocs" not in tabelas_com_pendencia


def test_auditoria_ignora_coluna_fora_da_faixa_de_cardinalidade() -> None:
    """Coluna com cardinalidade acima do teto configurado é ignorada (provável texto livre)."""
    engine = create_engine("sqlite:///:memory:")
    _popular_tabela_tipos_documento(engine, total_tipos=10)

    with patch("src.auditoria_cardinalidade.dicionario_de_coluna", return_value={}):
        relatorio = auditar_cobertura_por_cardinalidade(engine, cardinalidade_maxima=5)

    tabelas_com_pendencia = {p["tabela"] for p in relatorio["pendencias"]}
    assert "lawsuitdocs" not in tabelas_com_pendencia
    assert relatorio["resumo"]["colunas_fora_do_intervalo_cardinalidade"] >= 1


def test_auditoria_falha_isolada_em_coluna_nao_interrompe_demais() -> None:
    import src.auditoria_cardinalidade as mod

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE a (code TEXT)"))
        conn.execute(text("CREATE TABLE b (status TEXT)"))
        conn.execute(text("INSERT INTO a (code) VALUES ('x'), ('y')"))
        conn.execute(text("INSERT INTO b (status) VALUES ('novo'), ('antigo')"))
        conn.commit()

    original = mod._contar_valores_distintos

    def _falha_para_a_code(engine_, tabela, coluna, **kwargs):
        if tabela == "a" and coluna == "code":
            raise TimeoutError("Lost connection to MySQL server during query (timed out)")
        return original(engine_, tabela, coluna, **kwargs)

    with (
        patch.object(mod, "_contar_valores_distintos", side_effect=_falha_para_a_code),
        patch.object(mod, "dicionario_de_coluna", return_value={}),
    ):
        relatorio = mod.auditar_cobertura_por_cardinalidade(engine)

    assert relatorio["resumo"]["total_colunas_com_falha"] == 1
    assert relatorio["resumo"]["colunas_com_falha"][0]["tabela_coluna"] == "a.code"
    tabelas_com_pendencia = {p["tabela"] for p in relatorio["pendencias"]}
    assert "b" in tabelas_com_pendencia


def test_cardinalidade_maxima_padrao_bem_acima_do_teto_das_outras_ferramentas() -> None:
    """A faixa padrão deve ser maior que o teto de 20 das outras ferramentas."""
    assert CARDINALIDADE_MAXIMA_PADRAO > 20


def test_coluna_parece_identificadora_reconhece_convencoes_de_fk() -> None:
    for nome in ["account_id", "userid", "busunitid", "client_id", "id_tipo"]:
        assert _coluna_parece_identificadora(nome), f"{nome} deveria parecer identificador"


def test_coluna_parece_identificadora_ignora_falsos_positivos_de_sufixo() -> None:
    """Palavras que terminam em 'id' mas não são FK (lista de exceções de src.db)."""
    for nome in ["valid", "paid", "said", "void"]:
        assert not _coluna_parece_identificadora(nome), f"{nome} nao deveria parecer identificador"


def test_coluna_elegivel_cardinalidade_exclui_coluna_identificadora() -> None:
    coluna = ColunaTabela(nome="account_id", tipo="int(11)", posicao=1)
    assert not _coluna_elegivel_cardinalidade(coluna)


def test_coluna_elegivel_cardinalidade_exclui_denylist_estrutural() -> None:
    for nome in ["lft", "rgt", "level", "name", "path", "reason"]:
        coluna = ColunaTabela(nome=nome, tipo="varchar(255)", posicao=1)
        assert not _coluna_elegivel_cardinalidade(coluna), f"{nome} deveria ser excluida"


def test_coluna_elegivel_cardinalidade_aceita_codigo_legitimo() -> None:
    coluna = ColunaTabela(nome="doctype", tipo="varchar(60)", posicao=1)
    assert _coluna_elegivel_cardinalidade(coluna)


def test_auditoria_ignora_coluna_fk_mesmo_com_cardinalidade_moderada() -> None:
    """Reproduz o falso positivo real: accounts.account_id (56 ids, 1..650)."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE accounts (id INTEGER, account_id INTEGER)"))
        for indice in range(1, 57):
            conn.execute(
                text("INSERT INTO accounts (id, account_id) VALUES (:id, :account_id)"),
                {"id": indice, "account_id": indice},
            )
        conn.commit()

    with patch("src.auditoria_cardinalidade.dicionario_de_coluna", return_value={}):
        relatorio = auditar_cobertura_por_cardinalidade(engine)

    tabelas_com_pendencia = {p["tabela"] for p in relatorio["pendencias"]}
    assert "accounts" not in tabelas_com_pendencia


def test_coluna_elegivel_cardinalidade_exclui_flag_de_permissao_por_nome() -> None:
    for nome in ["read_users", "write_clients", "approve_contracts", "del_lawsuit"]:
        coluna = ColunaTabela(nome=nome, tipo="tinyint(1)", posicao=1)
        assert not _coluna_elegivel_cardinalidade(coluna), f"{nome} deveria ser excluida"


def test_coluna_elegivel_cardinalidade_exclui_duplicata_em_ingles() -> None:
    for nome in ["name_en", "subject_en", "motive_en"]:
        coluna = ColunaTabela(nome=nome, tipo="varchar(255)", posicao=1)
        assert not _coluna_elegivel_cardinalidade(coluna), f"{nome} deveria ser excluida"


def test_coluna_elegivel_cardinalidade_substring_cobre_variantes_do_denylist() -> None:
    """Comparação por substring deve cobrir `markup_observation`/`non_agreement_reason`."""
    for nome in ["markup_observation", "non_agreement_reason", "acordo_amount", "totalsentenceamount"]:
        coluna = ColunaTabela(nome=nome, tipo="varchar(255)", posicao=1)
        assert not _coluna_elegivel_cardinalidade(coluna), f"{nome} deveria ser excluida"


def test_auditoria_ignora_flag_booleana_sem_prefixo_reconhecido() -> None:
    """Checagem factual: coluna com valores exatamente {'0', '1'} é descartada."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE usertasks (id INTEGER, finishtype TEXT)"))
        for indice in range(500):
            conn.execute(
                text("INSERT INTO usertasks (id, finishtype) VALUES (:id, :finishtype)"),
                {"id": indice, "finishtype": "1" if indice % 3 == 0 else "0"},
            )
        conn.commit()

    with patch("src.auditoria_cardinalidade.dicionario_de_coluna", return_value={}):
        relatorio = auditar_cobertura_por_cardinalidade(engine)

    tabelas_com_pendencia = {p["tabela"] for p in relatorio["pendencias"]}
    assert "usertasks" not in tabelas_com_pendencia
