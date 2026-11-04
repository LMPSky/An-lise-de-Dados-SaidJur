"""Testes unitários para a auditoria de cobertura por cardinalidade real de coluna."""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy import create_engine, text

from src.auditoria_cardinalidade import (
    CARDINALIDADE_MAXIMA_CATALOGOS_GRANDES,
    CARDINALIDADE_MAXIMA_PADRAO,
    CARDINALIDADE_MINIMA_CATALOGOS_GRANDES,
    _coletar_valores_distintos,
    _coluna_elegivel_cardinalidade,
    _coluna_parece_identificador_numerico_no_banco,
    _coluna_parece_identificadora,
    _coluna_parece_monetaria_no_banco,
    _coluna_parece_numero_edicao_no_banco,
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


def test_coluna_parece_identificadora_reconhece_id_sem_underscore() -> None:
    """``idcourt``/``idcourt_division``/``idcomarca``: 'id' seguido direto de letra."""
    for nome in ["idcourt", "idcourt_division", "idcomarca"]:
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


def test_coluna_elegivel_cardinalidade_exclui_numero_referencia_e_endereco() -> None:
    """Número de referência/identificador em formato livre e campos de endereço."""
    nomes = [
        "lawsuitnumber",
        "vara_number",
        "register_number",
        "stnumber",
        "address",
        "cep",
        "district",
        "compliment",
        "clientcode",
        "client_reference",
    ]
    for nome in nomes:
        coluna = ColunaTabela(nome=nome, tipo="varchar(255)", posicao=1)
        assert not _coluna_elegivel_cardinalidade(coluna), f"{nome} deveria ser excluida"


def test_coluna_elegivel_cardinalidade_exclui_remetente_e_descricao_livre() -> None:
    """E-mail/remetente e descrição livre longa não são código/ENUM."""
    nomes = ["sender", "instructions_sender", "client_receiver", "proof_object", "required_todo"]
    for nome in nomes:
        coluna = ColunaTabela(nome=nome, tipo="varchar(255)", posicao=1)
        assert not _coluna_elegivel_cardinalidade(coluna), f"{nome} deveria ser excluida"


def test_coluna_elegivel_cardinalidade_exclui_resp_by_e_horario() -> None:
    """Coluna 'responsável por'/'enviado por' e horário do dia não são código/ENUM."""
    nomes = ["hearing_resp", "instructions_resp", "closed_by", "login_time", "logout_time"]
    for nome in nomes:
        coluna = ColunaTabela(nome=nome, tipo="varchar(255)", posicao=1)
        assert not _coluna_elegivel_cardinalidade(coluna), f"{nome} deveria ser excluida"


def test_coluna_elegivel_cardinalidade_exclui_proposta_centro_custo_e_emissor() -> None:
    """Quarta rodada: proposta de acordo em texto livre, 'centro de custo' com nome
    de empresa e id numérico de emissor sem sufixo *_id."""
    nomes = ["final_agreement_proposal", "cost_center_1", "issuer"]
    for nome in nomes:
        coluna = ColunaTabela(nome=nome, tipo="varchar(255)", posicao=1)
        assert not _coluna_elegivel_cardinalidade(coluna), f"{nome} deveria ser excluida"


def test_coluna_elegivel_cardinalidade_exclui_oab_user_del_e_jurify_pasta() -> None:
    """Quarta rodada: registro profissional único, id de usuário e identificador de
    pasta (correspondência exata)."""
    nomes = ["oab", "user_del", "jurify_pasta"]
    for nome in nomes:
        coluna = ColunaTabela(nome=nome, tipo="varchar(255)", posicao=1)
        assert not _coluna_elegivel_cardinalidade(coluna), f"{nome} deveria ser excluida"


def test_coluna_elegivel_cardinalidade_oab_exato_preserva_oab_uf() -> None:
    """`oab_uf` (cardinalidade compatível com as 27 UFs do Brasil) não deve ser
    excluída pela exclusão exata de `oab`."""
    coluna = ColunaTabela(nome="oab_uf", tipo="varchar(10)", posicao=1)
    assert _coluna_elegivel_cardinalidade(coluna)


def test_auditoria_catalogo_grande_legitimo_nao_e_descartado_por_proporcao() -> None:
    """Catálogo real acima do teto padrão (ex: 600 tipos de documento, cada um
    repetido várias vezes numa tabela maior) deve ser encontrado: proporção
    baixa não aciona o filtro de identificador/texto livre."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE lawsuitdocs (id INTEGER, doctype TEXT)"))
        indice = 0
        for tipo in range(600):
            for _repeticao in range(20):
                conn.execute(
                    text("INSERT INTO lawsuitdocs (id, doctype) VALUES (:id, :doctype)"),
                    {"id": indice, "doctype": f"tipo_{tipo}"},
                )
                indice += 1
        conn.commit()

    # SQLite (usado nos testes) não tem TABLE_ROWS do information_schema, então
    # `_linhas_estimadas_tabela` sempre retorna 0 nesse dialeto — simula a
    # estimativa real (12.000 linhas) para exercitar o filtro de proporção.
    with (
        patch("src.auditoria_cardinalidade.dicionario_de_coluna", return_value={}),
        patch("src.auditoria_cardinalidade._linhas_estimadas_tabela", return_value=12_000),
    ):
        relatorio = auditar_cobertura_por_cardinalidade(
            engine,
            cardinalidade_minima=CARDINALIDADE_MINIMA_CATALOGOS_GRANDES,
            cardinalidade_maxima=CARDINALIDADE_MAXIMA_CATALOGOS_GRANDES,
        )

    pendencia = next(
        p for p in relatorio["pendencias"] if p["tabela"] == "lawsuitdocs" and p["coluna"] == "doctype"
    )
    assert pendencia["cardinalidade"] == 600


def test_auditoria_descarta_coluna_de_alta_cardinalidade_proxima_do_total_de_linhas() -> None:
    """Coluna acima do teto padrão com cardinalidade quase igual ao total de
    linhas (ex: identificador/texto livre não capturado por nome) é
    descartada mesmo dentro da faixa configurada, por proporção alta."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE lawsuitdocs (id INTEGER, doctype TEXT)"))
        for indice in range(600):
            conn.execute(
                text("INSERT INTO lawsuitdocs (id, doctype) VALUES (:id, :doctype)"),
                # Quase um valor distinto por linha (proporção ~99%).
                {"id": indice, "doctype": f"unico_{indice}"},
            )
        conn.commit()

    with (
        patch("src.auditoria_cardinalidade.dicionario_de_coluna", return_value={}),
        patch("src.auditoria_cardinalidade._linhas_estimadas_tabela", return_value=600),
    ):
        relatorio = auditar_cobertura_por_cardinalidade(
            engine,
            cardinalidade_minima=CARDINALIDADE_MINIMA_CATALOGOS_GRANDES,
            cardinalidade_maxima=CARDINALIDADE_MAXIMA_CATALOGOS_GRANDES,
        )

    tabelas_com_pendencia = {p["tabela"] for p in relatorio["pendencias"]}
    assert "lawsuitdocs" not in tabelas_com_pendencia
    assert relatorio["resumo"]["colunas_fora_do_intervalo_cardinalidade"] >= 1


def test_auditoria_faixa_padrao_2_500_nao_e_afetada_pelo_filtro_de_proporcao() -> None:
    """O filtro de proporção só vale acima de CARDINALIDADE_MAXIMA_PADRAO: uma
    coluna dentro da faixa 2-500 já revisada continua funcionando como antes,
    mesmo com proporção alta (poucas linhas, muitos valores distintos)."""
    engine = create_engine("sqlite:///:memory:")
    _popular_tabela_tipos_documento(engine, total_tipos=30)

    with patch("src.auditoria_cardinalidade.dicionario_de_coluna", return_value={}):
        relatorio = auditar_cobertura_por_cardinalidade(engine)

    pendencia = next(
        p for p in relatorio["pendencias"] if p["tabela"] == "lawsuitdocs" and p["coluna"] == "doctype"
    )
    assert pendencia["cardinalidade"] == 30


def test_coluna_elegivel_cardinalidade_colunas_texto_livre_confirmadas_sao_excluidas() -> None:
    """Nona rodada de ajuste: colunas confirmadas em produção como texto
    livre/identificador na faixa de catálogos grandes (cidade, documento,
    telefone, anotação, campo "outro, especifique", nome de vara manual)
    devem ser excluídas por nome, sem precisar de round-trip ao banco."""
    nomes_excluidos = [
        "city",
        "cidade",
        "cnpj",
        "cpf",
        "phone01",
        "telefone",
        "complement",
        "annotations",
        "agreement_viable_other",
        "lawsuit",
        "lawsuit_object",
        "vara_cartorio_manual",
        "agent",
    ]
    for nome in nomes_excluidos:
        coluna = ColunaTabela(nome=nome, tipo="varchar(255)", posicao=1)
        assert not _coluna_elegivel_cardinalidade(coluna), f"{nome} deveria ser excluído"


def test_coluna_elegivel_cardinalidade_lawsuit_type_nao_e_excluida_por_nome() -> None:
    """``lawsuit_type`` não segue a convenção de nome de identificador
    (*_id/id*), então a exclusão por nome não se aplica — é descartada à
    parte pela checagem factual de valores puramente numéricos."""
    coluna = ColunaTabela(nome="lawsuit_type", tipo="varchar(10)", posicao=1)
    assert _coluna_elegivel_cardinalidade(coluna)


def test_coluna_parece_identificador_numerico_no_banco_detecta_ids_sequenciais() -> None:
    """Confirmado em produção: ``lawsuits_log.lawsuit_type`` guarda ids
    sequenciais ('1', '2', ..., '884') sem seguir a convenção de nome de FK —
    a checagem factual sobre os valores reais deve detectar isso."""
    valores = [str(n) for n in [1, 2, 3, 11, 12, 15, 23, 24, 852, 884]]
    assert _coluna_parece_identificador_numerico_no_banco(valores)


def test_coluna_parece_identificador_numerico_no_banco_preserva_catalogo_legitimo() -> None:
    """Um catálogo real de código/ENUM (valores não puramente numéricos, ou
    com texto) não deve ser descartado por este filtro."""
    assert not _coluna_parece_identificador_numerico_no_banco(["ativo", "inativo", "pendente"])
    assert not _coluna_parece_identificador_numerico_no_banco(["R$ 100,00", "R$ 200,00"])


def test_auditoria_descarta_fk_numerica_sem_convencao_de_nome_na_faixa_de_catalogos_grandes() -> None:
    """Reprodução do caso real ``lawsuits_log.lawsuit_type``: ids sequenciais
    numéricos (sem convenção de nome *_id/id*) não devem virar pendência de
    tradução na faixa de catálogos grandes. Cada id é repetido 10 vezes
    (proporção cardinalidade/linhas baixa, ~0.1) para isolar o novo filtro
    factual de identificador numérico do filtro de proporção já existente."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE lawsuits_log (id INTEGER, lawsuit_type TEXT)"))
        indice = 0
        for tipo in range(600):
            for _repeticao in range(10):
                conn.execute(
                    text("INSERT INTO lawsuits_log (id, lawsuit_type) VALUES (:id, :lawsuit_type)"),
                    {"id": indice, "lawsuit_type": str(tipo + 1)},
                )
                indice += 1
        conn.commit()

    with (
        patch("src.auditoria_cardinalidade.dicionario_de_coluna", return_value={}),
        patch("src.auditoria_cardinalidade._linhas_estimadas_tabela", return_value=6_000),
    ):
        relatorio = auditar_cobertura_por_cardinalidade(
            engine,
            cardinalidade_minima=CARDINALIDADE_MINIMA_CATALOGOS_GRANDES,
            cardinalidade_maxima=CARDINALIDADE_MAXIMA_CATALOGOS_GRANDES,
        )

    tabelas_com_pendencia = {p["tabela"] for p in relatorio["pendencias"]}
    assert "lawsuits_log" not in tabelas_com_pendencia


def test_coluna_elegivel_cardinalidade_paper_e_excluida_por_nome() -> None:
    """Décima rodada de ajuste: ``publicationxml.paper`` guarda identificador
    de edição de diário oficial em formato "número/ano", não um código."""
    coluna = ColunaTabela(nome="paper", tipo="varchar(20)", posicao=1)
    assert not _coluna_elegivel_cardinalidade(coluna)


def test_coluna_parece_numero_edicao_no_banco_detecta_formato_numero_ano() -> None:
    """Confirmado em produção: ``publicationxml.paper`` tem 417 valores, todos
    no formato "número/ano" (``"2468/2018"``...)."""
    valores = ["2468/2018", "2470/2018", "2471/2018", "3/2019", "10/2020"]
    assert _coluna_parece_numero_edicao_no_banco(valores)


def test_coluna_parece_numero_edicao_no_banco_preserva_catalogo_legitimo() -> None:
    """Um catálogo real de código/ENUM (sem o formato "número/ano") não deve
    ser descartado por este filtro."""
    assert not _coluna_parece_numero_edicao_no_banco(["ativo", "inativo", "pendente"])
    assert not _coluna_parece_numero_edicao_no_banco(["1", "2", "3"])


def test_auditoria_descarta_numero_edicao_na_faixa_de_catalogos_grandes() -> None:
    """Reprodução do caso real ``publicationxml.paper``: identificador de
    edição "número/ano" não deve virar pendência de tradução, mesmo com
    proporção baixa (cada edição repetida várias vezes numa tabela maior)."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE publicationxml (id INTEGER, paper TEXT)"))
        indice = 0
        for edicao in range(600):
            for _repeticao in range(10):
                conn.execute(
                    text("INSERT INTO publicationxml (id, paper) VALUES (:id, :paper)"),
                    {"id": indice, "paper": f"{edicao + 1}/2018"},
                )
                indice += 1
        conn.commit()

    with (
        patch("src.auditoria_cardinalidade.dicionario_de_coluna", return_value={}),
        patch("src.auditoria_cardinalidade._linhas_estimadas_tabela", return_value=6_000),
    ):
        relatorio = auditar_cobertura_por_cardinalidade(
            engine,
            cardinalidade_minima=CARDINALIDADE_MINIMA_CATALOGOS_GRANDES,
            cardinalidade_maxima=CARDINALIDADE_MAXIMA_CATALOGOS_GRANDES,
        )

    tabelas_com_pendencia = {p["tabela"] for p in relatorio["pendencias"]}
    assert "publicationxml" not in tabelas_com_pendencia


def test_cardinalidade_catalogos_grandes_comeca_logo_apos_teto_padrao() -> None:
    """O piso da faixa de catálogos grandes não deve reabrir a faixa já revisada."""
    assert CARDINALIDADE_MINIMA_CATALOGOS_GRANDES == CARDINALIDADE_MAXIMA_PADRAO + 1
    assert CARDINALIDADE_MAXIMA_CATALOGOS_GRANDES > CARDINALIDADE_MAXIMA_PADRAO


def test_cli_auditar_cardinalidade_usa_faixa_de_catalogos_grandes_por_padrao() -> None:
    """Rodar o script sem flags não deve repetir a varredura da faixa 2-500 já
    revisada: o padrão passa a ser a faixa de catálogos grandes."""
    import auditar_cardinalidade

    args = auditar_cardinalidade._parser().parse_args([])

    assert args.cardinalidade_minima == CARDINALIDADE_MINIMA_CATALOGOS_GRANDES
    assert args.cardinalidade_maxima == CARDINALIDADE_MAXIMA_CATALOGOS_GRANDES


def test_coluna_elegivel_cardinalidade_idcourt_sem_underscore_e_excluido() -> None:
    """`idcourt`/`idcourt_division` guardam ids sequenciais, confirmados em produção."""
    for nome in ["idcourt", "idcourt_division"]:
        coluna = ColunaTabela(nome=nome, tipo="int(11)", posicao=1)
        assert not _coluna_elegivel_cardinalidade(coluna), f"{nome} deveria ser excluida"


def test_coluna_elegivel_cardinalidade_exclui_instrucoes_em_texto_livre() -> None:
    """Quinta rodada: instrução em texto livre não é código/ENUM."""
    nomes = ["instructions"]
    for nome in nomes:
        coluna = ColunaTabela(nome=nome, tipo="varchar(255)", posicao=1)
        assert not _coluna_elegivel_cardinalidade(coluna), f"{nome} deveria ser excluida"


def test_coluna_elegivel_cardinalidade_exclui_localizacao_titulo_e_vara_por_nome_exato() -> None:
    """Quinta rodada: descrição de localização de tribunal/cidade, título/objeto de
    tarefa em texto livre, campo concatenado de vara e id numérico de usuário que
    alterou o registro - todos por correspondência exata."""
    nomes = [
        "location",
        "current_location",
        "title",
        "object",
        "vara",
        "user_changed_lawsuit",
    ]
    for nome in nomes:
        coluna = ColunaTabela(nome=nome, tipo="varchar(255)", posicao=1)
        assert not _coluna_elegivel_cardinalidade(coluna), f"{nome} deveria ser excluida"


def test_coluna_elegivel_cardinalidade_exato_nao_afeta_protocol_location_e_objecttype() -> None:
    """`protocol_location`/`objecttype` não devem colidir com a exclusão exata de
    `location`/`object`."""
    for nome in ["protocol_location", "objecttype"]:
        coluna = ColunaTabela(nome=nome, tipo="varchar(255)", posicao=1)
        assert _coluna_elegivel_cardinalidade(coluna), f"{nome} deveria continuar elegivel"


def test_coluna_elegivel_cardinalidade_exclui_nome_de_pessoa_por_nome_exato() -> None:
    """Nome de pessoa/parte (correspondência exata, não substring)."""
    nomes = ["nd", "pta", "defendant", "plaintiff", "lawyer", "witness_1", "preposto_1"]
    for nome in nomes:
        coluna = ColunaTabela(nome=nome, tipo="varchar(255)", posicao=1)
        assert not _coluna_elegivel_cardinalidade(coluna), f"{nome} deveria ser excluida"


def test_coluna_elegivel_cardinalidade_nome_exato_nao_afeta_variante_categorica() -> None:
    """`defendant_classification`/`witness_performance` não colidem com o nome exato."""
    for nome in ["defendant_classification", "witness_performance"]:
        coluna = ColunaTabela(nome=nome, tipo="varchar(255)", posicao=1)
        assert _coluna_elegivel_cardinalidade(coluna), f"{nome} deveria continuar elegivel"


def test_coluna_parece_monetaria_no_banco_reconhece_formatos_de_moeda() -> None:
    """Valores como 'R$ 14.500,00'/'5000.00' são quantia monetária."""
    assert _coluna_parece_monetaria_no_banco(["5000.00", "0.00", "2234.39"])
    assert _coluna_parece_monetaria_no_banco(
        ["2000", "R$ 14.500,00", "14500,00", "4200,00", "R$ 10.000,00", "R$ 1.800,00"]
    )
    assert _coluna_parece_monetaria_no_banco(["0.00", "100.00", "29.50", "45.68", "10.85", "66.89"])


def test_coluna_parece_monetaria_no_banco_ignora_codigo_numerico() -> None:
    """Códigos numéricos (OAB, código de vara, filial) não são falsamente marcados."""
    assert not _coluna_parece_monetaria_no_banco(["228.659", "197766", "172.112", "53.748", "154381"])
    assert not _coluna_parece_monetaria_no_banco(["0001", "0002", "0003", "0024", "0004"])
    assert not _coluna_parece_monetaria_no_banco(["1205", "226", "1026", "1344", "1059", "1093"])


def test_auditoria_ignora_coluna_monetaria_sem_termo_reconhecido_no_nome() -> None:
    """Checagem factual: coluna com valores de quantia monetária é descartada mesmo
    sem termo reconhecido (amount/valor/total) no nome."""
    engine = create_engine("sqlite:///:memory:")
    valores = ["5000.00", "0.00", "2234.39"]
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE lawsuits (id INTEGER, legal_fees TEXT)"))
        for indice in range(100):
            conn.execute(
                text("INSERT INTO lawsuits (id, legal_fees) VALUES (:id, :legal_fees)"),
                {"id": indice, "legal_fees": valores[indice % len(valores)]},
            )
        conn.commit()

    with patch("src.auditoria_cardinalidade.dicionario_de_coluna", return_value={}):
        relatorio = auditar_cobertura_por_cardinalidade(engine)

    tabelas_com_pendencia = {p["tabela"] for p in relatorio["pendencias"]}
    assert "lawsuits" not in tabelas_com_pendencia
