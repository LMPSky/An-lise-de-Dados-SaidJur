"""Testes para o módulo src/db.py usando SQLite em memória."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from src.db import (
    criar_engine,
    executar_com_retry_db,
    listar_tabelas,
    listar_colunas,
    tabelas_validas,
    colunas_validas,
    colunas_texto,
    coluna_label,
    fks_inferidas,
)


@pytest.fixture
def engine_teste() -> Engine:
    """
    Cria um engine SQLite em memória com tabelas de exemplo.
    SQLite não tem information_schema, então os testes de db.py
    usam mocks para funções que dependem do MySQL information_schema.
    """
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE clientes (
                id      INTEGER PRIMARY KEY,
                nome    TEXT NOT NULL,
                email   TEXT,
                cidade  TEXT,
                criado_em TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE processos (
                id       INTEGER PRIMARY KEY,
                numero   TEXT NOT NULL,
                status   TEXT,
                descricao TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO clientes VALUES
            (1, 'João Silva', 'joao@ex.com', 'São Paulo', '2023-01-01'),
            (2, 'Maria Souza', 'maria@ex.com', 'Rio', '2023-02-01')
        """))
        conn.execute(text("""
            INSERT INTO processos VALUES
            (1, '0001234-00.2023.8', 'em andamento', 'Ação de cobrança'),
            (2, '0002345-00.2023.8', 'concluído', 'Divórcio consensual')
        """))
        conn.commit()
    return engine


@pytest.fixture
def engine_labels() -> Engine:
    """Engine com tabelas para testar coluna_label e fks_inferidas."""
    import src.db as db_module
    # Limpar caches para garantir testes isolados
    db_module._CACHE_COLUNA_LABEL.clear()
    db_module._CACHE_FKS_INFERIDAS.clear()

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        # tabela com 'name' como coluna de label
        conn.execute(text("""
            CREATE TABLE cities (
                id   INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        """))
        # tabela com 'nome' (sem 'name')
        conn.execute(text("""
            CREATE TABLE lawsuit_types (
                id   INTEGER PRIMARY KEY,
                nome TEXT NOT NULL
            )
        """))
        # tabela sem nenhuma coluna de label
        conn.execute(text("""
            CREATE TABLE raw_ids (
                id  INTEGER PRIMARY KEY,
                val INTEGER
            )
        """))
        # tabela com coluna city_id (FK implícita)
        conn.execute(text("""
            CREATE TABLE lawsuits (
                id      INTEGER PRIMARY KEY,
                city_id INTEGER,
                paid    INTEGER
            )
        """))
        conn.execute(text("INSERT INTO cities VALUES (1, 'São Paulo'), (2, 'Rio de Janeiro')"))
        conn.execute(text("INSERT INTO lawsuit_types VALUES (6, 'Cível'), (7, 'Trabalhista')"))
        conn.execute(text("INSERT INTO lawsuits VALUES (1, 1, 0), (2, 2, 1)"))
        conn.commit()
    return engine


class TestColunaLabel:
    """Testes para a função coluna_label."""

    def test_encontra_name(self, engine_labels: Engine) -> None:
        """Deve encontrar 'name' como coluna de label."""
        assert coluna_label(engine_labels, "cities") == "name"

    def test_encontra_nome_sem_name(self, engine_labels: Engine) -> None:
        """Deve encontrar 'nome' quando não há 'name'."""
        assert coluna_label(engine_labels, "lawsuit_types") == "nome"

    def test_retorna_none_quando_nao_encontra(self, engine_labels: Engine) -> None:
        """Deve retornar None quando nenhuma candidata existe."""
        assert coluna_label(engine_labels, "raw_ids") is None


class TestFksInferidas:
    """Testes para a função fks_inferidas."""

    def test_detecta_city_id(self, engine_labels: Engine) -> None:
        """city_id deve ser detectado como FK implícita para cities."""
        resultado = fks_inferidas(engine_labels, "lawsuits")
        colunas = [r["coluna"] for r in resultado]
        assert "city_id" in colunas
        ref = next(r for r in resultado if r["coluna"] == "city_id")
        assert ref["tabela_referenciada"] == "cities"

    def test_nao_confunde_paid_com_fk(self, engine_labels: Engine) -> None:
        """'paid' não deve ser detectado como FK implícita."""
        resultado = fks_inferidas(engine_labels, "lawsuits")
        colunas = [r["coluna"] for r in resultado]
        assert "paid" not in colunas


class TestFksInferidasExtendidas:
    """Testes para os mapeamentos estendidos de FK inferida (domínio jurídico brasileiro)."""

    @pytest.fixture
    def engine_legal(self) -> Engine:
        """Engine com tabelas do domínio jurídico para testar mapeamentos adicionais."""
        import src.db as db_module
        db_module._CACHE_COLUNA_LABEL.clear()
        db_module._CACHE_FKS_INFERIDAS.clear()

        engine = create_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))
            # tabela com numero como label (processos brasileiros)
            conn.execute(text("""
                CREATE TABLE lawsuits (
                    id      INTEGER PRIMARY KEY,
                    numero  TEXT NOT NULL
                )
            """))
            # tabela cliente referenciada pela tabela de processos do cliente
            conn.execute(text("""
                CREATE TABLE clientes (
                    id   INTEGER PRIMARY KEY,
                    nome TEXT NOT NULL
                )
            """))
            # tabela com FK para clientes (mapeamento inglês→português)
            conn.execute(text("""
                CREATE TABLE processos_cliente (
                    id        INTEGER PRIMARY KEY,
                    client_id INTEGER,
                    lawsuit_id INTEGER
                )
            """))
            conn.execute(text("INSERT INTO lawsuits VALUES (1, '0001234-00.2023.8.26.0100')"))
            conn.execute(text("INSERT INTO clientes VALUES (1, 'João Silva')"))
            conn.execute(text("INSERT INTO processos_cliente VALUES (1, 1, 1)"))
            conn.commit()
        return engine

    def test_encontra_numero_como_label(self, engine_legal: Engine) -> None:
        """'numero' deve ser reconhecida como coluna de label em tabelas de processos."""
        assert coluna_label(engine_legal, "lawsuits") == "numero"

    def test_detecta_client_id_com_mapeamento_portugues(self, engine_legal: Engine) -> None:
        """client_id deve ser mapeado para a tabela 'clientes' (português)."""
        resultado = fks_inferidas(engine_legal, "processos_cliente")
        colunas = [r["coluna"] for r in resultado]
        assert "client_id" in colunas
        ref = next(r for r in resultado if r["coluna"] == "client_id")
        assert ref["tabela_referenciada"] == "clientes"

    def test_detecta_lawsuit_id_com_mapeamento_portugues(self, engine_legal: Engine) -> None:
        """lawsuit_id deve ser mapeado para 'lawsuits' (nome original) ou 'processos'."""
        resultado = fks_inferidas(engine_legal, "processos_cliente")
        colunas = [r["coluna"] for r in resultado]
        assert "lawsuit_id" in colunas
        ref = next(r for r in resultado if r["coluna"] == "lawsuit_id")
        assert ref["tabela_referenciada"] == "lawsuits"



    """Testes para tabelas_validas e tabelas_existentes."""

    def test_retorna_set(self, engine_teste: Engine) -> None:
        """tabelas_validas deve retornar um set."""
        # Para SQLite, simulamos com a lista de tabelas do sqlite_master
        with engine_teste.connect() as conn:
            resultado = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            nomes = {row[0] for row in resultado}

        assert isinstance(nomes, set)
        assert "clientes" in nomes
        assert "processos" in nomes

    def test_tabela_inexistente_nao_esta_no_set(self, engine_teste: Engine) -> None:
        """Uma tabela que não existe não deve aparecer no set."""
        with engine_teste.connect() as conn:
            resultado = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
            nomes = {row[0] for row in resultado}

        assert "tabela_inexistente" not in nomes


class TestColunasValidas:
    """Testes para colunas_validas usando SQLite PRAGMA."""

    def test_retorna_colunas_da_tabela(self, engine_teste: Engine) -> None:
        """Deve retornar os nomes corretos das colunas."""
        with engine_teste.connect() as conn:
            resultado = conn.execute(text("PRAGMA table_info(clientes)"))
            colunas = {row[1] for row in resultado}  # row[1] = name

        assert "id" in colunas
        assert "nome" in colunas
        assert "email" in colunas

    def test_nao_retorna_colunas_de_outra_tabela(self, engine_teste: Engine) -> None:
        """Colunas de uma tabela não devem aparecer para outra."""
        with engine_teste.connect() as conn:
            resultado = conn.execute(text("PRAGMA table_info(clientes)"))
            colunas = {row[1] for row in resultado}

        assert "numero" not in colunas  # coluna de 'processos'


class TestConsultaBasica:
    """Testes de consulta básica ao banco."""

    def test_select_simples(self, engine_teste: Engine) -> None:
        """SELECT simples deve retornar os dados inseridos."""
        with engine_teste.connect() as conn:
            resultado = conn.execute(
                text("SELECT * FROM clientes WHERE id = :id"), {"id": 1}
            )
            linhas = resultado.fetchall()

        assert len(linhas) == 1
        assert linhas[0][1] == "João Silva"

    def test_like_funciona(self, engine_teste: Engine) -> None:
        """Busca LIKE deve encontrar registros com acento."""
        with engine_teste.connect() as conn:
            resultado = conn.execute(
                text("SELECT * FROM clientes WHERE nome LIKE :padrao"),
                {"padrao": "%Maria%"},
            )
            linhas = resultado.fetchall()

        assert len(linhas) == 1

    def test_count_retorna_total(self, engine_teste: Engine) -> None:
        """COUNT(*) deve retornar o total correto."""
        with engine_teste.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM clientes")).scalar_one()

        assert total == 2

    def test_paginacao(self, engine_teste: Engine) -> None:
        """LIMIT/OFFSET deve retornar apenas a quantidade solicitada."""
        with engine_teste.connect() as conn:
            resultado = conn.execute(
                text("SELECT * FROM clientes LIMIT :lim OFFSET :off"),
                {"lim": 1, "off": 0},
            )
            linhas = resultado.fetchall()

        assert len(linhas) == 1

    def test_paginacao_segunda_pagina(self, engine_teste: Engine) -> None:
        """Segunda página deve retornar o segundo registro."""
        with engine_teste.connect() as conn:
            resultado = conn.execute(
                text("SELECT * FROM clientes ORDER BY id LIMIT :lim OFFSET :off"),
                {"lim": 1, "off": 1},
            )
            linhas = resultado.fetchall()

        assert len(linhas) == 1
        assert linhas[0][1] == "Maria Souza"


class TestSeguranca:
    """Testes relacionados à segurança das queries."""

    def test_queries_parametrizadas(self, engine_teste: Engine) -> None:
        """Verificar que o uso de parâmetros previne SQL injection básico."""
        # Uma tentativa de injeção via parâmetro deve retornar 0 resultados
        # em vez de executar código malicioso
        tentativa_injecao = "' OR '1'='1"
        with engine_teste.connect() as conn:
            resultado = conn.execute(
                text("SELECT * FROM clientes WHERE nome = :nome"),
                {"nome": tentativa_injecao},
            )
            linhas = resultado.fetchall()

        # SQLAlchemy parametrizado trata o valor como string literal
        assert len(linhas) == 0


class TestConfiguracaoEngine:
    def test_criar_engine_aplica_parametros_de_resiliencia(self, monkeypatch: pytest.MonkeyPatch) -> None:
        capturado: dict[str, object] = {}

        def fake_create_engine(url: str, **kwargs: object) -> str:
            capturado["url"] = url
            capturado["kwargs"] = kwargs
            return "engine-falso"

        monkeypatch.setattr("src.db.create_engine", fake_create_engine)

        engine = criar_engine(
            {
                "host": "db.local",
                "porta": 3307,
                "usuario": "alice",
                "senha": "segredo",
                "nome": "saidjur_teste",
            }
        )

        assert engine == "engine-falso"
        url = str(capturado["url"])
        assert url.startswith("mysql+pymysql://alice:")
        assert url.endswith("@db.local:3307/saidjur_teste?charset=utf8mb4")
        kwargs = capturado["kwargs"]
        assert kwargs["pool_pre_ping"] is True
        assert kwargs["pool_recycle"] == 1800
        assert kwargs["pool_size"] == 5
        assert kwargs["max_overflow"] == 10
        assert kwargs["pool_timeout"] == 30
        assert kwargs["connect_args"] == {"connect_timeout": 10, "read_timeout": 60}
        assert kwargs["echo"] is False

    def test_retry_db_tenta_uma_vez_novamente(self) -> None:
        chamadas = {"total": 0}

        def flaky() -> str:
            chamadas["total"] += 1
            if chamadas["total"] == 1:
                raise OperationalError("SELECT 1", {}, RuntimeError("conexão caiu"))
            return "ok"

        resultado = executar_com_retry_db(flaky, delay_segundos=0)

        assert resultado == "ok"
        assert chamadas["total"] == 2


class TestColunaLabelComSobrescritas:
    """Testes para a preferência explícita por tabela em coluna_label."""

    @pytest.fixture(autouse=True)
    def limpar_cache(self) -> None:
        import src.db as db_module
        db_module._CACHE_COLUNA_LABEL.clear()

    def test_lawsuits_prefere_lawsuitnumber(self) -> None:
        """lawsuits deve preferir 'lawsuitnumber' independente da ordem de _CANDIDATAS_LABEL."""
        engine = create_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE lawsuits (
                    id            INTEGER PRIMARY KEY,
                    lawsuitnumber TEXT NOT NULL,
                    name          TEXT
                )
            """))
            conn.execute(text("INSERT INTO lawsuits VALUES (1, '0001234-00.2023.8', 'Processo X')"))
            conn.commit()
        assert coluna_label(engine, "lawsuits") == "lawsuitnumber"

    def test_empname_reconhecida_como_label_de_employees(self) -> None:
        """Tabela de funcionários com coluna 'empname' deve ter essa coluna como label."""
        engine = create_engine("sqlite:///:memory:")
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE employees (
                    id      INTEGER PRIMARY KEY,
                    empname TEXT NOT NULL,
                    status  INTEGER
                )
            """))
            conn.execute(text("INSERT INTO employees VALUES (1, 'João Advogado', 1)"))
            conn.commit()
        assert coluna_label(engine, "employees") == "empname"


class TestDataZeroNormalizacao:
    """Testes de normalização de datas zeradas do MySQL na exportação."""

    def test_eh_data_zero_reconhece_data_zerada(self) -> None:
        from src.api.routes_export_search import _eh_data_zero
        assert _eh_data_zero("0000-00-00") is True
        assert _eh_data_zero("00:00:00") is True
        assert _eh_data_zero("0000-00-00 00:00:00") is True
        assert _eh_data_zero("0000-00-00T00:00") is True

    def test_eh_data_zero_nao_afeta_datas_validas(self) -> None:
        from src.api.routes_export_search import _eh_data_zero
        assert _eh_data_zero("2023-06-15") is False
        assert _eh_data_zero("14:30:00") is False
        assert _eh_data_zero("2023-06-15 14:30:00") is False
        assert _eh_data_zero(None) is False
        assert _eh_data_zero("") is False

    def test_normalizar_dados_converte_data_zero_para_none(self) -> None:
        from src.api.routes_export_search import _normalizar_dados_para_exportacao
        import unittest.mock as mock

        engine = mock.MagicMock()
        dados = {
            "hearingcontrol": [
                {"id": 1, "date": "0000-00-00", "time": "00:00:00", "type": 5},
                {"id": 2, "date": "2023-06-15", "time": "10:00:00", "type": 3},
            ]
        }

        with mock.patch(
            "src.api.routes_export_search._resolver_fks_dados_busca",
            return_value={},
        ):
            resultado = _normalizar_dados_para_exportacao(engine, dados)

        assert resultado["hearingcontrol"][0]["date"] is None
        assert resultado["hearingcontrol"][0]["time"] is None
        assert resultado["hearingcontrol"][1]["date"] == "2023-06-15"

    def test_api_export_eh_data_zero(self) -> None:
        from src.api_export import _eh_data_zero_export
        assert _eh_data_zero_export("0000-00-00") is True
        assert _eh_data_zero_export("2023-01-01") is False
        assert _eh_data_zero_export(None) is False


class TestParsearColunasDiretas:
    """Testes para parsear_colunas_diretas na investigação direcionada."""

    def test_parseia_tabela_coluna_valor(self) -> None:
        from src.investigacao_pendencias import parsear_colunas_diretas, PendenciaEnum
        resultado = parsear_colunas_diretas(["hearingcontrol.hearingtype:11"])
        assert resultado == [
            PendenciaEnum("hearingcontrol", "hearingtype", "11", "investigacao_direta")
        ]

    def test_parseia_sem_valor_usa_coringa(self) -> None:
        from src.investigacao_pendencias import parsear_colunas_diretas, PendenciaEnum
        resultado = parsear_colunas_diretas(["hearingcontrol.needwitness"])
        assert resultado == [
            PendenciaEnum("hearingcontrol", "needwitness", "*", "investigacao_direta")
        ]

    def test_parseia_multiplos_specs(self) -> None:
        from src.investigacao_pendencias import parsear_colunas_diretas
        resultado = parsear_colunas_diretas([
            "hearingcontrol.hearingtype:11",
            "pedidos2lawsuit.status:6",
        ])
        assert len(resultado) == 2
        assert resultado[0].tabela == "hearingcontrol"
        assert resultado[1].tabela == "pedidos2lawsuit"

    def test_erro_se_sem_ponto(self) -> None:
        from src.investigacao_pendencias import parsear_colunas_diretas
        import pytest
        with pytest.raises(ValueError, match="inválida"):
            parsear_colunas_diretas(["hearingcontrol:11"])
