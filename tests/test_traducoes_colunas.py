from src.traducoes_colunas import (
    TRADUCOES_COLUNAS,
    traduzir_nome_coluna,
    traduzir_nome_tabela_exportacao,
)


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


# ── Testes das novas traduções adicionadas a partir do relatório de auditoria ─


def test_traducoes_booleanos_financeiros() -> None:
    """Verifica traduções de campos booleanos e financeiros de alta frequência."""
    assert TRADUCOES_COLUNAS["approved"] == "Aprovado"
    assert TRADUCOES_COLUNAS["denied"] == "Negado"
    assert TRADUCOES_COLUNAS["viewed"] == "Visualizado"
    assert TRADUCOES_COLUNAS["billed"] == "Faturado"
    assert TRADUCOES_COLUNAS["finished"] == "Concluído"
    assert TRADUCOES_COLUNAS["delivered"] == "Entregue"


def test_traducoes_campos_de_data() -> None:
    """Verifica traduções de campos de data adicionados pelo relatório."""
    assert TRADUCOES_COLUNAS["datepaid"] == "Data de Pagamento"
    assert TRADUCOES_COLUNAS["birthdate"] == "Data de Nascimento"
    assert TRADUCOES_COLUNAS["duedate"] == "Data de Vencimento"
    assert TRADUCOES_COLUNAS["fataldeadline"] == "Prazo Fatal"
    assert TRADUCOES_COLUNAS["status_changed_at"] == "Data de Alteração de Status"
    assert TRADUCOES_COLUNAS["hearingdate"] == "Data da Audiência"
    assert TRADUCOES_COLUNAS["hearingtime"] == "Horário da Audiência"


def test_traducoes_ids_relacionais_novos() -> None:
    """Verifica traduções de IDs relacionais adicionados a partir do relatório."""
    assert TRADUCOES_COLUNAS["purchaseorder_id"] == "ID do Pedido de Compra"
    assert TRADUCOES_COLUNAS["expensereport_id"] == "ID do Relatório de Despesas"
    assert TRADUCOES_COLUNAS["task_id"] == "ID da Tarefa"
    assert TRADUCOES_COLUNAS["supplier_id"] == "ID do Fornecedor"
    assert TRADUCOES_COLUNAS["supervisor_id"] == "ID do Supervisor"
    assert TRADUCOES_COLUNAS["project_id"] == "ID do Projeto"
    assert TRADUCOES_COLUNAS["transaction_id"] == "ID da Transação"


def test_traducoes_permissoes() -> None:
    """Verifica uma amostra das traduções de permissões (read_/write_)."""
    assert TRADUCOES_COLUNAS["read_lawsuits"] == "Ver Processos"
    assert TRADUCOES_COLUNAS["write_lawsuits"] == "Editar Processos"
    assert TRADUCOES_COLUNAS["read_hearings"] == "Ver Audiências"
    assert TRADUCOES_COLUNAS["write_publications"] == "Editar Publicações"
    assert TRADUCOES_COLUNAS["approve_purchaseorder"] == "Aprovar Pedido de Compra"
    assert TRADUCOES_COLUNAS["cancel_prazo"] == "Cancelar Prazo"


def test_traducoes_financeiras() -> None:
    """Verifica traduções de campos financeiros."""
    assert TRADUCOES_COLUNAS["account"] == "Conta"
    assert TRADUCOES_COLUNAS["accountspayable"] == "Contas a Pagar"
    assert TRADUCOES_COLUNAS["balance"] == "Saldo"
    assert TRADUCOES_COLUNAS["invoice"] == "Fatura"
    assert TRADUCOES_COLUNAS["settlement"] == "Liquidação"
    assert TRADUCOES_COLUNAS["totalamount"] == "Valor Total"
    assert TRADUCOES_COLUNAS["netamount"] == "Valor Líquido"


def test_traducoes_campos_juridicos() -> None:
    """Verifica traduções de campos do domínio jurídico."""
    assert TRADUCOES_COLUNAS["procuracao"] == "Procuração"
    assert TRADUCOES_COLUNAS["hearingtype"] == "Tipo de Audiência"
    assert TRADUCOES_COLUNAS["transito_injulgado"] == "Trânsito em Julgado"
    assert TRADUCOES_COLUNAS["execucao_provisoria"] == "Execução Provisória"
    assert TRADUCOES_COLUNAS["lawsuit_object"] == "Objeto do Processo"
    assert TRADUCOES_COLUNAS["justification"] == "Justificativa"


def test_traducoes_campos_complementares() -> None:
    """Verifica campos complementares identificados no relatório."""
    assert TRADUCOES_COLUNAS["level"] == "Nível"
    assert TRADUCOES_COLUNAS["activity"] == "Atividade"
    assert TRADUCOES_COLUNAS["task"] == "Tarefa"
    assert TRADUCOES_COLUNAS["quantity"] == "Quantidade"
    assert TRADUCOES_COLUNAS["termination_reason"] == "Motivo de Rescisão"
    assert TRADUCOES_COLUNAS["cost_center_1"] == "Centro de Custo 1"


def test_traducao_relacional_via_entidade_nova() -> None:
    """Verifica que novas entidades base geram traduções relacionais via sufixo _id."""
    # 'activity' adicionado ao dict -> 'activity_id' deve ser gerado automaticamente
    assert traduzir_nome_coluna("activity_id") == "ID da Atividade"
    # 'task' adicionado ao dict -> 'task_id' deve ser gerado automaticamente
    assert traduzir_nome_coluna("task_id") == "ID da Tarefa"
    # 'business' adicionado ao dict -> 'business_id' deve ser gerado automaticamente
    assert traduzir_nome_coluna("business_id") == "ID do Negócio"


def test_traducoes_campos_jqcalendar_e_lawsuitdifflevel() -> None:
    """Verifica colunas residuais de alta confiança identificadas no relatório."""
    assert traduzir_nome_coluna("StartTime") == "Hora de Início"
    assert traduzir_nome_coluna("EndTime") == "Hora de Término"
    assert traduzir_nome_coluna("IsAllDayEvent") == "Evento de Dia Inteiro"
    assert traduzir_nome_coluna("Color") == "Cor"
    assert traduzir_nome_coluna("RecurringRule") == "Regra de Recorrência"
    assert TRADUCOES_COLUNAS["lawsuitdifflevel"] == "Nível Diferenciado do Processo"


def test_traducoes_relatorio_sila_do_brasil() -> None:
    """Verifica as traduções prioritárias do relatório apresentado ao cliente."""
    assert TRADUCOES_COLUNAS["client_id"] == "ID do Cliente"
    assert TRADUCOES_COLUNAS["search_term"] == "Termo de Busca"
    assert TRADUCOES_COLUNAS["created_at"] == "Data de Criação"
    assert TRADUCOES_COLUNAS["created_at_userid"] == "Usuário da Criação"
    assert TRADUCOES_COLUNAS["claim_id"] == "ID do Pedido"
    assert TRADUCOES_COLUNAS["claim_text"] == "Texto do Pedido"
    assert TRADUCOES_COLUNAS["details"] == "Detalhes"
    assert TRADUCOES_COLUNAS["pedido_id"] == "ID do Pedido"
    assert TRADUCOES_COLUNAS["amount"] == "Valor"
    assert TRADUCOES_COLUNAS["instance01"] == "1ª Instância"
    assert TRADUCOES_COLUNAS["instance01_amount"] == "Valor na 1ª Instância"
    assert TRADUCOES_COLUNAS["instance02"] == "2ª Instância"
    assert TRADUCOES_COLUNAS["instance02_amount"] == "Valor na 2ª Instância"
    assert TRADUCOES_COLUNAS["instancesup"] == "Instância Superior"
    assert TRADUCOES_COLUNAS["instancesup_amount"] == "Valor na Instância Superior"
    assert TRADUCOES_COLUNAS["instanceextra"] == "Instância Extra"
    assert TRADUCOES_COLUNAS["instanceextra_amount"] == "Valor na Instância Extra"
    assert TRADUCOES_COLUNAS["loss_diagnosis"] == "Diagnóstico de Perda"
    assert TRADUCOES_COLUNAS["amountpaid"] == "Valor Pago"
    assert TRADUCOES_COLUNAS["agent"] == "Agente"
    assert TRADUCOES_COLUNAS["status"] == "Status"
    assert TRADUCOES_COLUNAS["publication_id"] == "ID da Publicação"
    assert TRADUCOES_COLUNAS["jurify_pub_id"] == "ID da Publicação Jurify"
    assert TRADUCOES_COLUNAS["jurify_pasta"] == "Pasta Jurify"
    assert TRADUCOES_COLUNAS["pub_classification"] == "Classificação da Publicação"
    assert TRADUCOES_COLUNAS["pub_classification_id"] == "ID da Classificação da Publicação"
    assert TRADUCOES_COLUNAS["source_api"] == "API de Origem"
    assert traduzir_nome_coluna("ias") == "Ias"


def test_traduz_nomes_de_abas_prioritarias_da_exportacao() -> None:
    """Verifica os nomes amigáveis de abas usados no Excel exportado."""
    assert traduzir_nome_tabela_exportacao("client_publication_search_terms") == "Termos de Busca do Cliente"
    assert traduzir_nome_tabela_exportacao("pedidos2lawsuit") == "Pedidos do Processo"
    assert traduzir_nome_tabela_exportacao("publicationxml_extra") == "Extras da Publicação XML"
