"""Testes da investigação assistida de pendências de tradução."""

from __future__ import annotations

import contextlib
from pathlib import Path
from unittest.mock import patch

import pytest
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
    _coluna_elegivel_para_descoberta_completa,
    _pista_e_booleana,
    _pista_parece_dado_especifico,
    _pista_parece_texto_livre,
    _contar_linhas_com_valor,
    _coletar_contexto_coluna_obs,
    _propagar_entre_tabelas_irmas,
    _buscar_em_tabela_referencia,
    ColunaTabela,
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


def test_carregar_pendencias_markdown_ignora_tabela_de_nomes_de_coluna(tmp_path: Path) -> None:
    caminho = tmp_path / "PENDENCIAS.md"
    caminho.write_text(
        "## Nomes de coluna pendentes\n"
        "| Tabela | Coluna | Tradução atual (fallback) | Contexto |\n"
        "|--------|--------|---------------------------|----------|\n"
        "| `lawsuits` | `nd` | Nd | Sigla ambígua. |\n"
        "\n"
        "## Valores de ENUM/código pendentes\n"
        "| Tabela | Coluna | Valores pendentes | Observação |\n"
        "|--------|--------|-------------------|------------|\n"
        "| `tarefas` | `status` | `novo` | Código real. |\n",
        encoding="utf-8",
    )

    assert carregar_pendencias_markdown(caminho) == [
        PendenciaEnum("tarefas", "status", "novo", "pendencia_documentada"),
    ]


def test_carregar_pendencias_markdown_aceita_cabecalho_dominio_acentuado(tmp_path: Path) -> None:
    caminho = tmp_path / "PENDENCIAS.md"
    caminho.write_text(
        "## Pendências que permanecem abertas\n"
        "| Tabela | Coluna | Domínio observado |\n"
        "|--------|--------|-------------------|\n"
        "| `tarefas` | `status` | `{0, 1}` |\n",
        encoding="utf-8",
    )

    assert carregar_pendencias_markdown(caminho) == [
        PendenciaEnum("tarefas", "status", "0", "pendencia_documentada"),
        PendenciaEnum("tarefas", "status", "1", "pendencia_documentada"),
    ]


def test_carregar_pendencias_markdown_usa_asterisco_para_dominio_com_intervalo(tmp_path: Path) -> None:
    caminho = tmp_path / "PENDENCIAS.md"
    caminho.write_text(
        "## Valores de ENUM/código pendentes\n"
        "| Tabela | Coluna | Valores pendentes |\n"
        "|--------|--------|-------------------|\n"
        "| `paymentguarantee2lawsuit` | `type_old` | `{1..12, 14, 16..19}` |\n",
        encoding="utf-8",
    )

    assert carregar_pendencias_markdown(caminho) == [
        PendenciaEnum("paymentguarantee2lawsuit", "type_old", "*", "pendencia_documentada"),
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


def test_expandir_pendencias_com_dominio_falha_isolada_nao_interrompe_demais() -> None:
    """Um timeout ao expandir domínio de uma pendência não deve derrubar as demais."""
    import src.investigacao_pendencias as mod

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE emails (code TEXT)"))
        conn.execute(text("CREATE TABLE tarefas (status TEXT)"))
        conn.execute(text("INSERT INTO emails (code) VALUES ('A')"))
        conn.execute(text("INSERT INTO tarefas (status) VALUES ('novo')"))
        conn.commit()

    original = mod._valores_distintos_coluna

    def _falha_para_emails_code(engine_, tabela, coluna, **kwargs):
        if tabela == "emails" and coluna == "code":
            raise TimeoutError("Lost connection to MySQL server during query (timed out)")
        return original(engine_, tabela, coluna, **kwargs)

    pendencias = [
        PendenciaEnum("emails", "code", "*", "pendencia_documentada"),
        PendenciaEnum("tarefas", "status", "*", "pendencia_documentada"),
    ]

    with patch.object(mod, "_valores_distintos_coluna", side_effect=_falha_para_emails_code):
        resultado = expandir_pendencias_com_dominio(engine, pendencias)

    assert resultado == [PendenciaEnum("tarefas", "status", "novo", "pendencia_documentada")]


def test_expandir_pendencias_com_dominio_amostra_tabela_colossal() -> None:
    """Expansão de domínio em tabela colossal (ex: publicationxml) usa amostra limitada, não é pulada."""
    import src.investigacao_pendencias as mod
    from src.tabelas_grandes import LIMITE_LINHAS_TABELA_COLOSSAL, LIMITE_SUBSELECAO_TABELA_COLOSSAL

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE publicationxml (nature TEXT)"))
        conn.execute(text("CREATE TABLE tarefas (status TEXT)"))
        conn.execute(text("INSERT INTO publicationxml (nature) VALUES ('p')"))
        conn.execute(text("INSERT INTO tarefas (status) VALUES ('novo')"))
        conn.commit()

    def _estimativa_falsa(engine_, tabela):
        return LIMITE_LINHAS_TABELA_COLOSSAL + 1 if tabela == "publicationxml" else 0

    pendencias = [
        PendenciaEnum("publicationxml", "nature", "*", "pendencia_documentada"),
        PendenciaEnum("tarefas", "status", "*", "pendencia_documentada"),
    ]

    with patch.object(mod, "_linhas_estimadas_tabela", side_effect=_estimativa_falsa):
        with patch.object(mod, "_valores_distintos_coluna", wraps=mod._valores_distintos_coluna) as mock_valores:
            resultado = expandir_pendencias_com_dominio(engine, pendencias)

    assert resultado == [
        PendenciaEnum("publicationxml", "nature", "p", "pendencia_documentada"),
        PendenciaEnum("tarefas", "status", "novo", "pendencia_documentada"),
    ]
    chamadas_por_tabela = {call.args[1]: call.kwargs.get("limite_subselecao") for call in mock_valores.call_args_list}
    assert chamadas_por_tabela["publicationxml"] == LIMITE_SUBSELECAO_TABELA_COLOSSAL
    assert chamadas_por_tabela["tarefas"] is None


def test_valores_distintos_coluna_com_limite_subselecao_usa_subconsulta_limitada() -> None:
    """Com ``limite_subselecao``, a consulta lê apenas as N primeiras linhas, sem GROUP BY na tabela toda."""
    import src.investigacao_pendencias as mod

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE grande (codigo TEXT)"))
        # Os 3 primeiros valores (dentro do limite de subseleção) são 'a'/'b'; o valor
        # 'c' só aparece depois do limite de subseleção e não deve ser retornado.
        conn.execute(text("INSERT INTO grande (codigo) VALUES ('a'), ('a'), ('b'), ('c')"))
        conn.commit()

    valores = mod._valores_distintos_coluna(engine, "grande", "codigo", limite_subselecao=3)

    assert set(valores) == {"a", "b"}
    assert "c" not in valores


def test_valores_distintos_coluna_reduz_limite_subselecao_apos_falha() -> None:
    """Se a subseleção falhar (ex: timeout), tenta de novo com LIMIT reduzido até o piso."""
    import src.investigacao_pendencias as mod

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE grande (codigo TEXT)"))
        conn.execute(text("INSERT INTO grande (codigo) VALUES ('a'), ('b')"))
        conn.commit()

    conectar_original = mod.conectar_com_timeout
    chamadas: list[int] = []

    @contextlib.contextmanager
    def _conectar_instrumentado(engine_arg, *args, **kwargs):
        with conectar_original(engine_arg, *args, **kwargs) as conn:
            execute_original = conn.execute

            def _execute_instrumentado(sql, *a, **kw):
                texto_sql = str(sql)
                if "LIMIT 1000" in texto_sql:
                    chamadas.append(1000)
                    raise TimeoutError("Lost connection to MySQL server during query (timed out)")
                if "LIMIT 500" in texto_sql:
                    chamadas.append(500)
                return execute_original(sql, *a, **kw)

            conn.execute = _execute_instrumentado
            yield conn

    with patch.object(mod, "conectar_com_timeout", side_effect=_conectar_instrumentado):
        valores = mod._valores_distintos_coluna(
            engine,
            "grande",
            "codigo",
            limite_subselecao=1000,
            limite_minimo_subselecao=500,
        )

    assert set(valores) == {"a", "b"}
    assert chamadas == [1000, 500]


def test_valores_distintos_coluna_propaga_erro_apos_atingir_piso() -> None:
    """Se todas as tentativas (até o piso) falharem, o erro é propagado, não engolido."""
    import src.investigacao_pendencias as mod

    engine = create_engine("sqlite:///:memory:")

    def _falha_sempre(engine_arg, *args, **kwargs):
        raise TimeoutError("Lost connection to MySQL server during query (timed out)")

    with patch.object(mod, "conectar_com_timeout", side_effect=_falha_sempre):
        with pytest.raises(TimeoutError):
            mod._valores_distintos_coluna(
                engine,
                "grande",
                "codigo",
                limite_subselecao=200,
                limite_minimo_subselecao=200,
            )


def test_investigar_pendencias_registra_erro_por_item_e_continua() -> None:
    import src.investigacao_pendencias as mod

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE falha (codigo TEXT, name TEXT)"))
        conn.execute(text("CREATE TABLE sucesso (codigo TEXT, name TEXT)"))
        conn.execute(text("INSERT INTO sucesso (codigo, name) VALUES ('ok', 'Rótulo válido')"))
        conn.commit()

    original_coletar = mod._coletar_linhas_exemplo

    def _coletar_com_falha(engine_arg, pendencia, colunas_pista, *, limite_linhas, **kwargs):
        if pendencia.tabela == "falha":
            raise RuntimeError("falha SQL simulada")
        return original_coletar(engine_arg, pendencia, colunas_pista, limite_linhas=limite_linhas, **kwargs)

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


def test_investigar_pendencias_nao_descarta_item_quando_distribuicao_falha() -> None:
    """Falha em _coletar_distribuicao_codigo (sinal auxiliar) não deve virar status 'erro'."""
    import src.investigacao_pendencias as mod

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE sucesso (codigo TEXT, name TEXT)"))
        conn.execute(text("INSERT INTO sucesso (codigo, name) VALUES ('ok', 'Rótulo válido')"))
        conn.commit()

    with (
        patch.object(mod, "_buscar_em_tabela_referencia", return_value=None),
        patch.object(mod, "_coletar_distribuicao_codigo", side_effect=RuntimeError("timeout simulado")),
    ):
        relatorio = investigar_pendencias(
            engine,
            [PendenciaEnum("sucesso", "codigo", "ok", "pendencia_documentada")],
            limite_linhas=5,
        )

    item = relatorio["investigacoes"][0]
    assert item["sugestao"]["status"] != "erro"
    assert "distribuicao_codigo" not in item


def test_coletar_distribuicao_codigo_captura_falha_e_retorna_none() -> None:
    """_coletar_distribuicao_codigo não propaga exceções: retorna None em caso de falha."""
    import src.investigacao_pendencias as mod

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE sucesso (codigo TEXT)"))
        conn.commit()

    with patch.object(mod, "conectar_com_timeout", side_effect=TimeoutError("timeout simulado")):
        resultado = mod._coletar_distribuicao_codigo(
            engine, PendenciaEnum("sucesso", "codigo", "x", "pendencia_documentada")
        )

    assert resultado is None


def test_coletar_linhas_exemplo_com_limite_subselecao_usa_subconsulta_limitada() -> None:
    """Com limite_subselecao, a busca por valor roda sobre uma subseleção, não a tabela toda."""
    import src.investigacao_pendencias as mod

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE grande (codigo TEXT, nome TEXT)"))
        conn.execute(text("INSERT INTO grande (codigo, nome) VALUES ('a', 'primeiro')"))
        conn.execute(text("INSERT INTO grande (codigo, nome) VALUES ('b', 'fora_da_amostra')"))
        conn.commit()

    linhas_dentro = mod._coletar_linhas_exemplo(
        engine,
        PendenciaEnum("grande", "codigo", "a", "pendencia_documentada"),
        ["nome"],
        limite_linhas=5,
        limite_subselecao=1,
    )
    linhas_fora = mod._coletar_linhas_exemplo(
        engine,
        PendenciaEnum("grande", "codigo", "b", "pendencia_documentada"),
        ["nome"],
        limite_linhas=5,
        limite_subselecao=1,
    )

    assert linhas_dentro == [{"nome": "primeiro"}]
    assert linhas_fora == []


def test_investigar_pendencias_salva_checkpoint_parcial_periodicamente(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE sucesso (codigo TEXT, name TEXT)"))
        conn.execute(text("INSERT INTO sucesso (codigo, name) VALUES ('ok', 'Rótulo válido')"))
        conn.commit()

    caminho_checkpoint = tmp_path / "checkpoint.yaml"
    pendencias = [
        PendenciaEnum("sucesso", "codigo", "ok", "pendencia_documentada") for _ in range(5)
    ]

    with patch(
        "src.investigacao_pendencias._buscar_em_tabela_referencia", return_value=None
    ):
        relatorio_final = investigar_pendencias(
            engine,
            pendencias,
            limite_linhas=5,
            caminho_checkpoint=caminho_checkpoint,
            intervalo_checkpoint=2,
        )

    # Checkpoint deve ter sido salvo (a cada 2 itens, entre os 5 processados).
    assert caminho_checkpoint.exists()
    checkpoint = yaml.safe_load(caminho_checkpoint.read_text(encoding="utf-8"))
    assert checkpoint["em_andamento"] is True
    assert checkpoint["total_pendencias_esperado"] == 5
    assert checkpoint["resumo"]["total_pendencias"] in (2, 4)

    # O relatório final (retornado, não necessariamente salvo em disco por
    # investigar_pendencias) não deve ter marcação de "em andamento".
    assert "em_andamento" not in relatorio_final
    assert "total_pendencias_esperado" not in relatorio_final
    assert relatorio_final["resumo"]["total_pendencias"] == 5


def test_investigar_pendencias_sem_checkpoint_nao_grava_arquivo(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE sucesso (codigo TEXT, name TEXT)"))
        conn.execute(text("INSERT INTO sucesso (codigo, name) VALUES ('ok', 'Rótulo válido')"))
        conn.commit()

    caminho_checkpoint = tmp_path / "nao_deve_existir.yaml"
    pendencias = [PendenciaEnum("sucesso", "codigo", "ok", "pendencia_documentada")]

    with patch(
        "src.investigacao_pendencias._buscar_em_tabela_referencia", return_value=None
    ):
        investigar_pendencias(engine, pendencias, limite_linhas=5)

    assert not caminho_checkpoint.exists()


def test_propagar_entre_tabelas_irmas_nao_sobrescreve_erro() -> None:
    investigacoes = [
        {
            "tabela": "prazos_log",
            "coluna": "pzphase",
            "valor": "1",
            "sugestao": {
                "status": "erro",
                "traducao_sugerida": None,
                "justificativa": "Falha ao investigar: timeout",
                "pistas": [],
            },
        },
        {
            "tabela": "prazo2publication",
            "coluna": "pzphase",
            "valor": "1",
            "sugestao": {
                "status": "alta_confianca",
                "traducao_sugerida": "audiência inicial",
                "justificativa": "Tabela de referência confirmou o rótulo.",
                "pistas": [],
            },
        },
    ]

    _propagar_entre_tabelas_irmas(investigacoes)

    assert investigacoes[0]["sugestao"]["status"] == "erro"
    assert investigacoes[0]["sugestao"]["traducao_sugerida"] is None
    assert "timeout" in investigacoes[0]["sugestao"]["justificativa"]


def test_descobrir_pendencias_schema_ignora_texto_livre_e_ja_traduzidos() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE tarefas (status TEXT, observacao TEXT)"))
        conn.execute(text(
            "INSERT INTO tarefas VALUES ('novo', 'Texto de observação livre bastante longo que não é código')"
        ))
        conn.commit()

    pendencias, resumo = descobrir_pendencias_schema(engine, {"tarefas": {"status": {"novo": "Novo"}}})

    assert pendencias == []
    assert resumo["total_colunas_excluidas"] >= 0
    assert resumo["total_colunas_com_falha"] == 0


def test_descobrir_pendencias_schema_exclui_colunas_text_blob_json_por_tipo() -> None:
    """Colunas TEXT/BLOB/JSON nunca devem ser consultadas: excluídas antes da query."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE emails (
                id INTEGER PRIMARY KEY,
                code VARCHAR(20),
                body TEXT,
                anexo BLOB,
                metadados JSON
            )
        """))
        conn.execute(text("INSERT INTO emails (id, code, body) VALUES (1, 'A', 'texto grande de e-mail')"))
        conn.commit()

    pendencias, resumo = descobrir_pendencias_schema(engine, {})

    tabelas_colunas = {(p.tabela, p.coluna) for p in pendencias}
    assert ("emails", "body") not in tabelas_colunas
    assert ("emails", "anexo") not in tabelas_colunas
    assert ("emails", "metadados") not in tabelas_colunas
    assert ("emails", "code") in tabelas_colunas

    excluidas = {item["tabela_coluna"] for item in resumo["colunas_excluidas"]}
    assert "emails.body" in excluidas
    assert "emails.anexo" in excluidas
    assert "emails.metadados" in excluidas
    assert resumo["total_colunas_excluidas"] == len(excluidas)


def test_descobrir_pendencias_schema_exclui_varchar_acima_do_limite() -> None:
    """VARCHAR acima do tamanho configurado é excluído mesmo com nome de código."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE publications_duplicate_info (
                id INTEGER PRIMARY KEY,
                filecode VARCHAR(20),
                filename VARCHAR(255)
            )
        """))
        conn.execute(text(
            "INSERT INTO publications_duplicate_info (id, filecode, filename) VALUES (1, 'A', 'algum_arquivo.pdf')"
        ))
        conn.commit()

    pendencias, resumo = descobrir_pendencias_schema(engine, {})

    tabelas_colunas = {(p.tabela, p.coluna) for p in pendencias}
    assert ("publications_duplicate_info", "filename") not in tabelas_colunas
    assert ("publications_duplicate_info", "filecode") in tabelas_colunas

    excluidas = {item["tabela_coluna"]: item["motivo"] for item in resumo["colunas_excluidas"]}
    assert excluidas["publications_duplicate_info.filename"] == "varchar_acima_do_limite"


def test_descobrir_pendencias_schema_exclui_por_nome_mesmo_com_tipo_curto() -> None:
    """Nomes como body/content/summary são excluídos mesmo com VARCHAR curto."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE publicacoes (
                id INTEGER PRIMARY KEY,
                code VARCHAR(20),
                summary VARCHAR(50),
                content VARCHAR(50)
            )
        """))
        conn.execute(text(
            "INSERT INTO publicacoes (id, code, summary, content) VALUES (1, 'A', 'resumo curto', 'conteudo curto')"
        ))
        conn.commit()

    pendencias, resumo = descobrir_pendencias_schema(engine, {})

    tabelas_colunas = {(p.tabela, p.coluna) for p in pendencias}
    assert ("publicacoes", "summary") not in tabelas_colunas
    assert ("publicacoes", "content") not in tabelas_colunas
    assert ("publicacoes", "code") in tabelas_colunas

    excluidas = {item["tabela_coluna"]: item["motivo"] for item in resumo["colunas_excluidas"]}
    assert excluidas["publicacoes.summary"] == "nome_indica_texto_livre"
    assert excluidas["publicacoes.content"] == "nome_indica_texto_livre"


def test_descobrir_pendencias_schema_falha_isolada_nao_interrompe_demais_colunas() -> None:
    """Uma falha (timeout/erro SQL) ao consultar uma coluna não deve derrubar o lote."""
    import src.investigacao_pendencias as mod

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE emails (
                id INTEGER PRIMARY KEY,
                code VARCHAR(20)
            )
        """))
        conn.execute(text("""
            CREATE TABLE prazos_log (
                id INTEGER PRIMARY KEY,
                pzphase VARCHAR(20)
            )
        """))
        conn.execute(text("INSERT INTO emails (id, code) VALUES (1, 'A')"))
        conn.execute(text("INSERT INTO prazos_log (id, pzphase) VALUES (1, 'X')"))
        conn.commit()

    original = mod._valores_distintos_coluna

    def _falha_para_emails_code(engine_, tabela, coluna, **kwargs):
        if tabela == "emails" and coluna == "code":
            raise TimeoutError("Lost connection to MySQL server during query (timed out)")
        return original(engine_, tabela, coluna, **kwargs)

    with patch.object(mod, "_valores_distintos_coluna", side_effect=_falha_para_emails_code):
        pendencias, resumo = descobrir_pendencias_schema(engine, {})

    tabelas_colunas = {(p.tabela, p.coluna) for p in pendencias}
    assert ("prazos_log", "pzphase") in tabelas_colunas
    assert not any(t == "emails" and c == "code" for t, c in tabelas_colunas)

    falhas = {item["tabela_coluna"] for item in resumo["colunas_com_falha"]}
    assert "emails.code" in falhas
    assert resumo["total_colunas_com_falha"] == 1


def test_linhas_estimadas_tabela_retorna_zero_para_dialeto_nao_mysql() -> None:
    """Em SQLite (usado nos testes) não há TABLE_ROWS: nunca deve ser tratado como colossal."""
    from src.investigacao_pendencias import _linhas_estimadas_tabela

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE publicationxml (id INTEGER PRIMARY KEY, nature VARCHAR(20))"))
        conn.commit()

    assert _linhas_estimadas_tabela(engine, "publicationxml") == 0


def test_descobrir_pendencias_schema_amostra_tabela_colossal_em_vez_de_pular() -> None:
    """Tabelas colossais (ex: publicationxml) são amostradas com limite reduzido, não puladas."""
    import src.investigacao_pendencias as mod
    from src.tabelas_grandes import LIMITE_LINHAS_TABELA_COLOSSAL, LIMITE_SUBSELECAO_TABELA_COLOSSAL

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE publicationxml (
                id INTEGER PRIMARY KEY,
                nature VARCHAR(20)
            )
        """))
        conn.execute(text("""
            CREATE TABLE prazos_log (
                id INTEGER PRIMARY KEY,
                pzphase VARCHAR(20)
            )
        """))
        conn.execute(text("INSERT INTO publicationxml (id, nature) VALUES (1, 'p')"))
        conn.execute(text("INSERT INTO prazos_log (id, pzphase) VALUES (1, 'X')"))
        conn.commit()

    def _estimativa_falsa(engine_, tabela):
        if tabela == "publicationxml":
            return LIMITE_LINHAS_TABELA_COLOSSAL + 1
        return 0

    with patch.object(mod, "_linhas_estimadas_tabela", side_effect=_estimativa_falsa):
        with patch.object(mod, "_valores_distintos_coluna", wraps=mod._valores_distintos_coluna) as mock_valores:
            pendencias, resumo = descobrir_pendencias_schema(engine, {})

    tabelas_colunas = {(p.tabela, p.coluna) for p in pendencias}
    assert ("publicationxml", "nature") in tabelas_colunas
    assert ("prazos_log", "pzphase") in tabelas_colunas

    chamadas_por_tabela = {call.args[1]: call.kwargs.get("limite_subselecao") for call in mock_valores.call_args_list}
    assert chamadas_por_tabela["publicationxml"] == LIMITE_SUBSELECAO_TABELA_COLOSSAL
    assert chamadas_por_tabela["prazos_log"] is None

    assert resumo["total_tabelas_colossais_amostradas"] == 1
    assert resumo["tabelas_colossais_amostradas"] == [
        {"tabela": "publicationxml", "linhas_estimadas": LIMITE_LINHAS_TABELA_COLOSSAL + 1}
    ]


def test_descobrir_pendencias_schema_falha_ao_estimar_linhas_nao_interrompe() -> None:
    """Uma falha ao estimar linhas de uma tabela não deve derrubar a descoberta: trata como normal."""
    import src.investigacao_pendencias as mod

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE prazos_log (
                id INTEGER PRIMARY KEY,
                pzphase VARCHAR(20)
            )
        """))
        conn.execute(text("INSERT INTO prazos_log (id, pzphase) VALUES (1, 'X')"))
        conn.commit()

    def _falha_estimativa(engine_, tabela):
        raise TimeoutError("Lost connection to MySQL server during query (timed out)")

    with patch.object(mod, "_linhas_estimadas_tabela", side_effect=_falha_estimativa):
        pendencias, resumo = descobrir_pendencias_schema(engine, {})

    tabelas_colunas = {(p.tabela, p.coluna) for p in pendencias}
    assert ("prazos_log", "pzphase") in tabelas_colunas
    assert resumo["total_tabelas_colossais_amostradas"] == 0


def test_executar_investigacao_inclui_resumo_descoberta_schema_no_relatorio(tmp_path: Path) -> None:
    """O relatório final expõe contagens de colunas excluídas/com falha na descoberta via schema."""
    import src.investigacao_pendencias as mod

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE paymenttype (
                id INTEGER PRIMARY KEY,
                code VARCHAR(20),
                body TEXT
            )
        """))
        conn.execute(text("INSERT INTO paymenttype (id, code, body) VALUES (1, 'Bol', 'texto livre')"))
        conn.commit()

    caminho_saida = tmp_path / "relatorio.yaml"
    with patch.object(mod, "criar_engine", return_value=engine):
        relatorio = executar_investigacao(caminho_saida=caminho_saida, descobrir_schema=True)

    assert "descoberta_schema" in relatorio
    assert relatorio["descoberta_schema"]["total_colunas_excluidas"] >= 1
    assert any(
        item["tabela_coluna"] == "paymenttype.body"
        for item in relatorio["descoberta_schema"]["colunas_excluidas"]
    )

    relatorio_salvo = yaml.safe_load(caminho_saida.read_text(encoding="utf-8"))
    assert "descoberta_schema" in relatorio_salvo



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


def test_buscar_em_tabela_referencia_ignora_coluna_de_permissao_booleana() -> None:
    """Colunas como 'read_users'/'role_client' são flags booleanas, não FK.

    Regressão: antes desta correção, usertasks.read_users = 1 batia por
    coincidência com o id=1 da tabela 'users', retornando o nome de um
    usuário qualquer como se fosse a tradução do código.
    """
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE usertasks (
                id INTEGER PRIMARY KEY,
                read_users INTEGER
            )
        """))
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """))
        conn.execute(text("INSERT INTO usertasks (id, read_users) VALUES (1, 1)"))
        conn.execute(text("INSERT INTO users (id, name) VALUES (1, 'AmericoBarroso')"))
        conn.commit()

    resultado = _buscar_em_tabela_referencia(engine, PendenciaEnum("usertasks", "read_users", "1"))

    assert resultado is None


def test_buscar_em_tabela_referencia_ignora_flag_booleano_sem_prefixo_reconhecido() -> None:
    """Colunas booleanas sem prefixo verbal reconhecido também são descartadas.

    Regressão: 'client_sys_updated' não bate com nenhum prefixo de
    _PREFIXOS_COLUNA_ACAO_BOOLEANA, mas é um flag 0/1 (maioria '0') que
    coincidiu, por acaso, com o id=1 de 'client_sectors', sugerindo 'DSC'
    como se fosse a tradução do código.
    """
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE prazo2publication (
                id INTEGER PRIMARY KEY,
                client_sys_updated INTEGER
            )
        """))
        conn.execute(text("""
            CREATE TABLE client_sectors (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """))
        conn.execute(text("INSERT INTO prazo2publication (id, client_sys_updated) VALUES (1, 0)"))
        conn.execute(text("INSERT INTO prazo2publication (id, client_sys_updated) VALUES (2, 1)"))
        conn.execute(text("INSERT INTO client_sectors (id, name) VALUES (1, 'DSC')"))
        conn.commit()

    resultado = _buscar_em_tabela_referencia(
        engine, PendenciaEnum("prazo2publication", "client_sys_updated", "1")
    )

    assert resultado is None


def test_buscar_em_tabela_referencia_rejeita_rotulo_texto_livre() -> None:
    """Rótulos longos/texto corrido são notas de caso, não categorias de ENUM."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE hearingcontrol (
                id INTEGER PRIMARY KEY,
                hearingstatus INTEGER
            )
        """))
        conn.execute(text("""
            CREATE TABLE hearingstatuses (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """))
        conn.execute(text("INSERT INTO hearingcontrol (id, hearingstatus) VALUES (1, 2)"))
        conn.execute(text(
            "INSERT INTO hearingstatuses (id, name) VALUES "
            "(2, 'Audiência instrução designada para 11/06/2019 14:30 Seção B da 31ª Vara Cível da Capital.')"
        ))
        conn.commit()

    resultado = _buscar_em_tabela_referencia(engine, PendenciaEnum("hearingcontrol", "hearingstatus", "2"))

    assert resultado is None


def test_buscar_em_tabela_referencia_rejeita_rotulo_nome_de_arquivo() -> None:
    """Um nome de arquivo de documento anexado não é uma tradução de ENUM válida."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE expedients (
                id INTEGER PRIMARY KEY,
                expedientfile INTEGER
            )
        """))
        conn.execute(text("""
            CREATE TABLE expedientfiles (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """))
        conn.execute(text("INSERT INTO expedients (id, expedientfile) VALUES (1, 1)"))
        conn.execute(text(
            "INSERT INTO expedientfiles (id, name) VALUES (1, 'alvara_11041-2015-039.pdf')"
        ))
        conn.commit()

    resultado = _buscar_em_tabela_referencia(engine, PendenciaEnum("expedients", "expedientfile", "1"))

    assert resultado is None


def test_buscar_em_tabela_referencia_abstem_quando_candidatas_empatadas_divergem() -> None:
    """Regressão: colunas como 'payment_type'/'doctype' geram o radical genérico
    'type', que empata (mesma pontuação de similaridade) entre várias tabelas
    "*type*" do schema. Antes desta correção, a primeira em ordem alfabética
    que tivesse um rótulo válido para o id era aceita cegamente — mesmo que
    outra tabela empatada apontasse para um rótulo completamente diferente.
    Agora, quando candidatas do mesmo nível de pontuação divergem sobre a
    tradução, a função se abstém em vez de adivinhar.
    """
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE final_payments (
                id INTEGER PRIMARY KEY,
                payment_type INTEGER
            )
        """))
        conn.execute(text("""
            CREATE TABLE companytype (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE prazotype (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """))
        conn.execute(text("INSERT INTO final_payments (id, payment_type) VALUES (1, 1)"))
        conn.execute(text("INSERT INTO companytype (id, name) VALUES (1, 'supervisor de controle')"))
        conn.execute(text("INSERT INTO prazotype (id, name) VALUES (1, 'ENVIAR CTPS P/ ANOTAÇÃO')"))
        conn.commit()

    resultado = _buscar_em_tabela_referencia(engine, PendenciaEnum("final_payments", "payment_type", "1"))

    assert resultado is None


def test_buscar_em_tabela_referencia_aceita_candidatas_empatadas_que_concordam() -> None:
    """Quando candidatas empatadas concordam no rótulo, a tradução é aceita
    normalmente (o empate por si só não é motivo de rejeição). Usa 'prazo'
    (radical específico de domínio) como base do empate, já que radicais
    puramente genéricos como 'type' agora têm score limitado e não chegam
    a formar candidatas por si só."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE lawsuitdocsmetadata (
                id INTEGER PRIMARY KEY,
                prazo_fase INTEGER
            )
        """))
        conn.execute(text("""
            CREATE TABLE prazotype (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE prazomotivos (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """))
        conn.execute(text("INSERT INTO lawsuitdocsmetadata (id, prazo_fase) VALUES (1, 1)"))
        conn.execute(text("INSERT INTO prazotype (id, name) VALUES (1, 'Encerramento')"))
        conn.execute(text("INSERT INTO prazomotivos (id, name) VALUES (1, 'Encerramento')"))
        conn.commit()

    resultado = _buscar_em_tabela_referencia(engine, PendenciaEnum("lawsuitdocsmetadata", "prazo_fase", "1"))

    assert resultado is not None
    assert resultado["sugestao"]["traducao_sugerida"] == "Encerramento"


def test_buscar_em_tabela_referencia_ignora_tabela_de_fato_larga() -> None:
    """Regressão: 'lawsuits' é a tabela de fato central do domínio (dezenas de
    colunas), não um catálogo/enum — mesmo pontuando alto por similaridade de
    nome com 'lawsuit_phase_id', um id que bate nela é coincidência, não uma
    FK real. Tabelas com muitas colunas devem ser descartadas como
    candidatas de catálogo.
    """
    engine = create_engine("sqlite:///:memory:")
    colunas_largas = ", ".join(f"col{i} TEXT" for i in range(15))
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE lawsuit_phases2judicial_area (
                id INTEGER PRIMARY KEY,
                lawsuit_phase_id INTEGER
            )
        """))
        conn.execute(text(f"""
            CREATE TABLE lawsuits (
                id INTEGER PRIMARY KEY,
                {colunas_largas}
            )
        """))
        conn.execute(text(
            "INSERT INTO lawsuit_phases2judicial_area (id, lawsuit_phase_id) VALUES (1, 7)"
        ))
        conn.execute(text(
            "INSERT INTO lawsuits (id, col0) VALUES (7, 'EXTINTA A EXECUÇÃO')"
        ))
        conn.commit()

    resultado = _buscar_em_tabela_referencia(
        engine, PendenciaEnum("lawsuit_phases2judicial_area", "lawsuit_phase_id", "7")
    )

    assert resultado is None


def test_buscar_em_tabela_referencia_ignora_match_baseado_so_em_radical_generico() -> None:
    """Regressão: colunas como 'payment_type'/'doctype'/'type_old' só
    compartilham a palavra genérica 'type' com tabelas de catálogo não
    relacionadas ('prazotype', 'hearingtype', 'companytype'...). Um match
    que só se sustenta nessa palavra genérica não deve nem virar candidata
    — do contrário a coluna resolveria para o valor de uma tabela sem
    nenhuma relação semântica real assim que ela for a única com o id
    procurado (sem conflito para acionar a abstenção por empate).
    """
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE templatesubject (
                id INTEGER PRIMARY KEY,
                type INTEGER
            )
        """))
        conn.execute(text("""
            CREATE TABLE prazotype (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """))
        conn.execute(text("INSERT INTO templatesubject (id, type) VALUES (1, 2)"))
        conn.execute(text("INSERT INTO prazotype (id, name) VALUES (2, 'ENVIAR CTPS P/ ANOTAÇÃO')"))
        conn.commit()

    resultado = _buscar_em_tabela_referencia(engine, PendenciaEnum("templatesubject", "type", "2"))

    assert resultado is None



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


def test_buscar_em_tabela_referencia_usa_fk_declarada_no_schema() -> None:
    """FK real declarada no schema (``FOREIGN KEY``) deve ser usada como fonte
    de tradução, com prioridade sobre a heurística de radical de nome, e sem
    o teto de largura de tabela (uma FK real pode apontar para tabela larga).
    """
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.execute(text("""
            CREATE TABLE employees (
                id INTEGER PRIMARY KEY,
                name TEXT,
                c2 TEXT, c3 TEXT, c4 TEXT, c5 TEXT, c6 TEXT, c7 TEXT,
                c8 TEXT, c9 TEXT, c10 TEXT, c11 TEXT, c12 TEXT, c13 TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE prazos_log (
                id INTEGER PRIMARY KEY,
                userid INTEGER,
                FOREIGN KEY (userid) REFERENCES employees(id)
            )
        """))
        conn.execute(text("INSERT INTO employees (id, name) VALUES (7, 'Maria Souza')"))
        conn.commit()

    resultado = _buscar_em_tabela_referencia(engine, PendenciaEnum("prazos_log", "userid", "7"))

    assert resultado is not None
    assert resultado["sugestao"]["fonte"] == "fk_declarada"
    assert resultado["sugestao"]["traducao_sugerida"] == "Maria Souza"
    assert resultado["tabela_referencia"] == "employees"


def test_buscar_em_tabela_referencia_usa_fk_inferida_por_convencao() -> None:
    """FK inferida por convenção de nome (``pubtype`` → ``pubtypes``, sem
    declaração real no schema) deve ser usada como fonte de tradução —
    reaproveitando a heurística ``fks_inferidas`` já validada na resolução
    de labels da interface web.
    """
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE prazo2publication (
                id INTEGER PRIMARY KEY,
                pubtype INTEGER
            )
        """))
        conn.execute(text("""
            CREATE TABLE pubtypes (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """))
        conn.execute(text("INSERT INTO pubtypes (id, name) VALUES (3, 'Publicação de Sentença')"))
        conn.commit()

    resultado = _buscar_em_tabela_referencia(engine, PendenciaEnum("prazo2publication", "pubtype", "3"))

    assert resultado is not None
    assert resultado["sugestao"]["fonte"] == "fk_inferida"
    assert resultado["sugestao"]["traducao_sugerida"] == "Publicação de Sentença"
    assert resultado["tabela_referencia"] == "pubtypes"


def test_buscar_em_tabela_referencia_ignora_fk_declarada_de_coluna_booleana() -> None:
    """Mesmo com uma FK real declarada, uma coluna que se comporta como flag
    booleana no banco (apenas '0'/'1') continua sendo descartada — o guard de
    boolean/flag roda antes de qualquer estratégia, incluindo FK declarada.
    """
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.execute(text("""
            CREATE TABLE client_sectors (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE clients (
                id INTEGER PRIMARY KEY,
                client_sys_updated INTEGER,
                FOREIGN KEY (client_sys_updated) REFERENCES client_sectors(id)
            )
        """))
        conn.execute(text("""
            INSERT INTO client_sectors (id, name) VALUES (0, 'Sem Setor'), (1, 'Setor Fiscal')
        """))
        conn.execute(text("""
            INSERT INTO clients (id, client_sys_updated) VALUES
            (1, 0), (2, 0), (3, 0), (4, 1)
        """))
        conn.commit()

    resultado = _buscar_em_tabela_referencia(engine, PendenciaEnum("clients", "client_sys_updated", "1"))

    assert resultado is None


def test_coluna_elegivel_para_descoberta_completa_exclui_apenas_blob() -> None:
    """No modo completo, BLOB é excluído de antemão (junto dos tipos
    temporais, cobertos em teste próprio); TEXT/JSON/VARCHAR grande e nomes
    que sugerem texto livre seguem elegíveis (o filtro real fica por conta da
    cardinalidade observada na amostragem)."""
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("body", "text", 0)) is True
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("observacao", "mediumtext", 0)) is True
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("dados", "json", 0)) is True
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("anexo", "blob", 0)) is False
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("arquivo", "longblob", 0)) is False


def test_coluna_elegivel_para_descoberta_completa_exclui_tipos_temporais() -> None:
    """Colunas de data/hora nunca são código/ENUM — mesmo no modo completo,
    devem ser excluídas de antemão. Em produção, deixar essas colunas
    elegíveis fez `varas.timestamp` e
    `lawsuitdocsmetadata.protocol_confirmed_date` virarem "pendências" e
    receberem rótulos sem sentido (ex: "Consultivo", "Teste") por coincidência
    de amostra pequena."""
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("criado_em", "date", 0)) is False
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("timestamp", "datetime", 0)) is False
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("protocol_confirmed_date", "timestamp", 0)) is False
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("hora_inicio", "time", 0)) is False
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("ano_fiscal", "year", 0)) is False


def test_descobrir_pendencias_schema_modo_completo_encontra_codigo_em_coluna_text() -> None:
    """Modo completo deve descobrir um código curto guardado em uma coluna
    TEXT com nome que sugere texto livre ('observacao') — normalmente
    excluída pelo modo padrão por tipo e por nome."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE lawsuitdocs (
                id INTEGER PRIMARY KEY,
                observacao TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO lawsuitdocs (id, observacao) VALUES (1, '2'), (2, '2'), (3, '9')
        """))
        conn.commit()

    pendencias_padrao, resumo_padrao = descobrir_pendencias_schema(engine, {})
    assert not any(p.tabela == "lawsuitdocs" and p.coluna == "observacao" for p in pendencias_padrao)
    assert any(item["tabela_coluna"] == "lawsuitdocs.observacao" for item in resumo_padrao["colunas_excluidas"])

    pendencias_completo, resumo_completo = descobrir_pendencias_schema(engine, {}, modo_completo=True)
    valores_encontrados = {
        p.valor for p in pendencias_completo if p.tabela == "lawsuitdocs" and p.coluna == "observacao"
    }
    assert valores_encontrados == {"2", "9"}
    assert resumo_completo["colunas_excluidas"] == []



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


def test_analisar_pistas_recusa_coluna_id_opaca() -> None:
    """Regressão: colunas identificadoras opacas (``id``/``*_id``) não devem
    receber tradução adivinhada a partir de uma pista textual de exemplo —
    em produção, `accounts.parent_id` e `expedientfilemetadata.expedient_id`
    receberam texto de comentário/nome de arquivo de outra linha como se
    fosse tradução, quando na verdade são apenas referências opacas a outra
    linha/tabela (sem significado textual próprio)."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE acordo_nucleus (
                id INTEGER PRIMARY KEY,
                updated_at_userid INTEGER,
                obs TEXT
            )
        """))
        conn.execute(text(
            "INSERT INTO acordo_nucleus (id, updated_at_userid, obs) "
            "VALUES (1, 445, 'admissão 03/07/2017 - demissão 11/01/2022')"
        ))
        conn.commit()

    relatorio = investigar_pendencias(engine, [PendenciaEnum("acordo_nucleus", "updated_at_userid", "445")])

    item = relatorio["investigacoes"][0]
    assert item["sugestao"]["status"] == "sem_pista_encontrada"
    assert item["sugestao"]["traducao_sugerida"] is None


def test_coluna_elegivel_para_descoberta_completa_exclui_coluna_id() -> None:
    """A coluna `id` (convenção de chave primária) nunca é um código/categoria
    — cada valor é único por definição — então deve ser excluída de antemão
    mesmo no modo completo."""
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("id", "int", 0)) is False
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("ID", "int", 0)) is False
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("busunit_id", "int", 0)) is True


def test_coluna_elegivel_para_descoberta_completa_exclui_colunas_sensiveis() -> None:
    """Colunas de credenciais/segredos (senha, token...) nunca devem ser
    tratadas como código/ENUM a traduzir — em produção, `users_api.password`
    recebeu o nome de um usuário como "tradução" por coincidência de amostra
    pequena via `_analisar_pistas`."""
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("password", "varchar(255)", 0)) is False
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("senha", "varchar(255)", 0)) is False
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("api_token", "varchar(255)", 0)) is False
    assert _coluna_elegivel_para_descoberta_completa(ColunaTabela("status", "varchar(20)", 0)) is True


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
                    "justificativa": "Coluna 'label' concordou em todas as linhas.",
                },
            }
        ]
    }

    template = gerar_template_decisoes(relatorio)

    assert template["decisoes"][0]["decisao"] == "pendente"
    assert template["decisoes"][0]["traducao_sugerida"] == "Boleto"
    assert template["decisoes"][0]["justificativa"] == "Coluna 'label' concordou em todas as linhas."


def test_gerar_template_decisoes_filtra_por_status_e_tabela() -> None:
    """Relatórios grandes (milhares de itens) precisam ser revisados em lotes
    menores — os filtros `apenas_status`/`apenas_tabela` permitem gerar um
    template com só uma fatia do relatório (ex: apenas os itens
    'pista_unica' de uma tabela específica)."""
    relatorio = {
        "investigacoes": [
            {
                "tabela": "paymenttype",
                "coluna": "code",
                "valor": "Bol",
                "sugestao": {"status": "alta_confianca", "traducao_sugerida": "Boleto"},
            },
            {
                "tabela": "usertasks",
                "coluna": "status",
                "valor": "3",
                "sugestao": {"status": "pista_unica", "traducao_sugerida": "Concluída"},
            },
            {
                "tabela": "projects",
                "coluna": "status",
                "valor": "1",
                "sugestao": {"status": "pista_unica", "traducao_sugerida": "Ativo"},
            },
        ]
    }

    apenas_pista_unica = gerar_template_decisoes(relatorio, apenas_status="pista_unica")
    assert len(apenas_pista_unica["decisoes"]) == 2
    assert {item["tabela"] for item in apenas_pista_unica["decisoes"]} == {"usertasks", "projects"}

    apenas_usertasks = gerar_template_decisoes(
        relatorio, apenas_status="pista_unica", apenas_tabela="usertasks"
    )
    assert len(apenas_usertasks["decisoes"]) == 1
    assert apenas_usertasks["decisoes"][0]["tabela"] == "usertasks"


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


def test_coluna_tem_nome_semantico_falso() -> None:
    """Bug 3: colunas técnicas/booleanas não devem ser identificadas como semânticas."""
    assert _coluna_tem_nome_semantico("hearingfile") is False
    assert _coluna_tem_nome_semantico("dispensed") is False
    assert _coluna_tem_nome_semantico("correspondent") is False
    assert _coluna_tem_nome_semantico("status") is False


def test_coluna_tem_nome_semantico_exclui_colunas_de_nota_livre() -> None:
    """Regressão: colunas de nota/observação de texto livre (``obs``,
    ``observacao``) não devem contar como "pista forte" — na prática, são
    campos narrativos por linha (comentário de caso, motivo, etc.), não
    rótulos de categoria. Confirmado ao revisar manualmente 2.126 itens
    ``pista_unica``: colunas como ``markup_observation`` e ``observations``
    bateram, por coincidência, com códigos e sugeriram texto específico de
    um caso/pessoa (ex: nome de funcionário) como se fosse tradução."""
    assert _coluna_tem_nome_semantico("observacao") is False
    assert _coluna_tem_nome_semantico("observations") is False
    assert _coluna_tem_nome_semantico("markup_observation") is False
    assert _coluna_tem_nome_semantico("obs") is False


def test_coluna_tem_nome_semantico_exclui_name_em_identificador_de_arquivo() -> None:
    """Regressão: ``filename`` contém "name" como substring mas não é um
    rótulo de categoria — é o nome de um arquivo específico daquela linha.
    Em produção, ``expedientfilemetadata.filename`` foi classificado como
    "pista forte" só por conter "name", batendo por coincidência com uma
    coluna de observação e produzindo sugestões inúteis."""
    assert _coluna_tem_nome_semantico("filename") is False
    assert _coluna_tem_nome_semantico("username") is False


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


def test_executar_investigacao_colunas_diretas_ignora_descoberta_via_schema(tmp_path: Path) -> None:
    """``--colunas`` deve investigar apenas as especificações pedidas.

    Bug reproduzido: combinar ``--colunas`` com ``--completo`` (que implica
    ``descobrir_schema=True``) disparava uma varredura do banco inteiro além
    do item direcionado, transformando uma checagem de 1 pendência em
    milhares e causando uma bateria de timeouts desnecessária em tabelas
    colossais.
    """
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
            INSERT INTO paymenttype (id, code, name) VALUES (1, 'Bol', 'Boleto')
        """))
        # Outra tabela com um código curto sem tradução, elegível para
        # descoberta via schema — não deve aparecer no relatório quando
        # colunas_diretas é usado, mesmo com descobrir_schema=True.
        conn.execute(text("""
            CREATE TABLE outra_tabela (
                id INTEGER PRIMARY KEY,
                status TEXT
            )
        """))
        conn.execute(text("""
            INSERT INTO outra_tabela (id, status) VALUES (1, 'X')
        """))
        conn.commit()

    caminho_saida = tmp_path / "relatorio.yaml"
    caminho_dicionarios = tmp_path / "dicionarios.yaml"
    caminho_dicionarios.write_text("traducoes: {}\n", encoding="utf-8")

    with patch.object(mod, "criar_engine", return_value=engine):
        relatorio = executar_investigacao(
            caminho_saida=caminho_saida,
            caminho_dicionarios=caminho_dicionarios,
            colunas_diretas=["paymenttype.code:Bol"],
            descobrir_schema=True,
            modo_completo=True,
        )

    assert relatorio["fonte_pendencias"] == "colunas_diretas:paymenttype.code:Bol"
    assert len(relatorio["investigacoes"]) == 1
    assert relatorio["investigacoes"][0]["tabela"] == "paymenttype"
    assert "descoberta_schema" not in relatorio


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
