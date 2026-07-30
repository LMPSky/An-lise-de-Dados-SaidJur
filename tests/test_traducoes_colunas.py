from src.traducoes_colunas import TRADUCOES_COLUNAS, traduzir_nome_coluna


def test_traduz_campos_reportados_com_entradas_especificas() -> None:
    assert TRADUCOES_COLUNAS["publication_id"] == "ID da Publicação"
    assert TRADUCOES_COLUNAS["search_term_id"] == "ID do Termo de Busca"
    assert TRADUCOES_COLUNAS["created_at_userid"] == "Usuário da Criação"
    assert TRADUCOES_COLUNAS["createdat_userid"] == "Usuário da Criação"


def test_traduz_colunas_relacionais_com_sufixo_id() -> None:
    assert traduzir_nome_coluna("publication_id") == "ID da Publicação"
    assert traduzir_nome_coluna("search_term_id") == "ID do Termo de Busca"
    assert traduzir_nome_coluna("client_id") == "ID do Cliente"


def test_fallback_preserva_id_em_maiusculo_quando_nao_ha_traducao_composta() -> None:
    assert traduzir_nome_coluna("search_id") == "ID da Busca"
    assert traduzir_nome_coluna("unknown_id") == "Unknown ID"
