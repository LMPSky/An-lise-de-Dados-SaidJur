"""
Módulo de tradução de nomes de colunas.
Fonte canônica única — usada pelo backend (FastAPI) e exposta via
`GET /api/traducoes/colunas` para o frontend consumir.

NÃO duplique este dicionário em outros arquivos.
"""

TRADUCOES_COLUNAS = {
    # ── Campos de data/hora ───────────────────────────────────────────────────
    'created_at': 'Data de Criação',
    'updated_at': 'Data de Atualização',
    'deleted_at': 'Data de Exclusão',
    'inserted_at': 'Data de Inserção',
    'timestamp': 'Data/Hora',
    'date_inserted': 'Data de Inserção',
    'date': 'Data',
    'datemoved': 'Data de Movimentação',
    'dateupdated': 'Data de Atualização',
    'processing_date': 'Data de Processamento',
    'effectivedate': 'Data Efetiva',
    'instructionsdate': 'Data das Instruções',
    'instructionsinsertdate': 'Data de Inserção das Instruções',
    'instructionstimestamp': 'Timestamp das Instruções',
    'instructionsinsertdate_userid': 'Usuário da Inserção das Instruções',
    'naf_userid_date': 'Data do Usuário NAF',
    'updated_at_userid': 'Usuário da Atualização',
    'protocoldate': 'Data do Protocolo',
    'startdate': 'Data de Início',
    'hiring_date': 'Data de Contratação',
    'system_date_insert_proposal': 'Data de Inserção da Proposta',

    # ── IDs e chaves ──────────────────────────────────────────────────────────
    'id': 'ID',
    'user_id': 'ID do Usuário',
    'userid': 'ID do Usuário',
    'lawsuit_id': 'ID do Processo',
    'hearing_id': 'ID da Audiência',
    'hearingcontrol_id': 'ID Controle Audiência',
    'person_id': 'ID da Pessoa',
    'client_id': 'ID do Cliente',
    'employee_id': 'ID do Funcionário',
    'from_automatic_prazoid': 'ID do Prazo Automático',
    'fromhearingcontrolid': 'ID do Controle de Audiência',
    'prazoid': 'ID do Prazo',
    'expedientfileid': 'ID do Arquivo de Expediente',
    'av_clientid': 'ID Cliente Avaliação',
    'analise_prov_hearingid': 'ID Audiência Análise Provisória',

    # ── Status e tipos ────────────────────────────────────────────────────────
    'status': 'Status',
    'type': 'Tipo',
    'nature': 'Natureza',
    'phase': 'Fase',
    'result': 'Resultado',
    'aut_event': 'Evento Automático',
    'hearing': 'Audiência',
    'from_lawsuit': 'Originário de Processo',
    'event': 'Evento',
    'hearing_type': 'Tipo de Audiência',
    'lawsuit_phase': 'Fase do Processo',
    'lawsuittype': 'Tipo de Processo',
    'activity_type': 'Tipo de Atividade',
    'objecttype': 'Tipo de Objeto',
    'empstatus': 'Status do Funcionário',
    'operation': 'Operação',
    'action': 'Ação',
    'flow': 'Fluxo',
    'sector': 'Setor',
    'region': 'Região',
    'system': 'Sistema',

    # ── Nomes descritivos ─────────────────────────────────────────────────────
    'name': 'Nome',
    'description': 'Descrição',
    'code': 'Código',
    'number': 'Número',
    'value': 'Valor',
    'amount': 'Valor',
    'total': 'Total',
    'filename': 'Nome do Arquivo',
    'lawsuitnumber': 'Número do Processo',
    'location': 'Localização',
    'information': 'Informação',
    'search_term': 'Termo de Busca',
    'sigla': 'Sigla',
    'rate': 'Taxa',
    'paymentlimit': 'Limite de Pagamento',

    # ── Campos jurídicos ──────────────────────────────────────────────────────
    'lawsuit': 'Processo',
    'plaintiff': 'Autor',
    'defendant': 'Réu',
    'lawyer': 'Advogado',
    'judge': 'Juiz',
    'vara': 'Vara',
    'court': 'Tribunal',
    'city': 'Cidade',
    'state': 'Estado',
    'unit': 'Unidade',
    'businessunit': 'Unidade de Negócio',
    'businessunitgroup': 'Grupo de Unidade de Negócio',
    'businessarea': 'Área de Negócio',
    'paper': 'Papel',
    'link': 'Link',
    'observations': 'Observações',
    'obs': 'Observação',
    'observations_userid': 'Usuário das Observações',
    'correspondent': 'Correspondente',
    'oab': 'OAB',
    'fundamento': 'Fundamento',
    'sentence': 'Sentença',
    'judgement': 'Sentença',
    'perfil': 'Perfil',
    'court_division_name': 'Nome da Divisão do Tribunal',
    'confession': 'Confissão',
    'third_party_presence': 'Presença de Terceiros',
    'deferred_protection': 'Proteção Diferida',

    # ── Campos específicos do SaidJur ─────────────────────────────────────────
    'agreement_viable': 'Acordo Viável',
    'agreement_in_hearing': 'Acordo em Audiência',
    'markup_necessary': 'Markup Necessário',
    'markup_approved': 'Markup Aprovado',
    'markup_reason': 'Motivo do Markup',
    'non_agreement_reason': 'Motivo de Não Acordo',
    'resp_evaluation': 'Responsável da Avaliação',
    'pericia': 'Perícia',
    'pericia_result': 'Resultado da Perícia',
    'prazo': 'Prazo',
    'all_prazos': 'Todos os Prazos',
    'all_clients': 'Todos os Clientes',
    'all_groups': 'Todos os Grupos',
    'date_reference': 'Referência de Data',
    'new_prazo_update_option': 'Opção de Atualização do Novo Prazo',
    'prazo_days': 'Dias do Prazo',
    'type_days': 'Tipo de Dias',
    'user_change_status': 'Usuário que Alterou Status',
    'user_inserted': 'Usuário Inseridor',
    'user_updated': 'Usuário Atualizador',
    'what_lawsuits': 'Quais Processos',
    'publication': 'Publicação',
    'expedient': 'Expediente',
    'expedientfile': 'Arquivo de Expediente',
    'expedientfileobs': 'Observação de Arquivo de Expediente',
    'expedientprotocoldate': 'Data do Protocolo de Expediente',
    'instructions': 'Instruções',
    'instructions_resp': 'Responsável das Instruções',
    'instructions_respfinish': 'Conclusão Responsável Instruções',
    'instructions_sent': 'Instruções Enviadas',
    'instructionsstatus': 'Status das Instruções',
    'instructionstimestamp_userid': 'Usuário do Timestamp Instruções',
    'containsprazo': 'Contém Prazo',
    'noprazoemailsent01': 'E-mail Sem Prazo Enviado',
    'revised': 'Revisado',
    'sent': 'Enviado',
    'naf': 'NAF',
    'naf_userid': 'Usuário NAF',
    'analise_prov': 'Análise Provisória',
    'acomp_encerramento': 'Acompanhamento Encerramento',
    'exprovas': 'Exceção Provas',
    'cumsen': 'Cumprimento Sentença',
    'exccj': 'Exceção CCJ',
    'acum': 'Acumulação',
    'exfis': 'Exceção Fiscal',
    'extiex': 'Exceção TIEX',
    'cartprecciv': 'Cartório Precedência Civil',
    'disconsider': 'Desconsiderar',
    'deleted': 'Excluído',
    'deleted_at_userid': 'Usuário da Exclusão',
    'user_changed_lawsuit': 'Processo Alterado por Usuário',
    'user_changed': 'Alterado por Usuário',
    'includeexpedient': 'Incluir Expediente',
    'cpfl_spreadsheet_import': 'Importação Planilha CPFL',
    'finish_fail': 'Conclusão com Falha',
    'finish_success': 'Conclusão com Êxito',
    'remote': 'Remoto',
    'morto': 'Desativado',
    'no_uf': 'Sem UF',
    'direct_member': 'Membro Direto',
    'insurer_flow': 'Fluxo do Segurador',
    'market_place': 'Mercado',
    'protection_inserted_system': 'Proteção Inserida no Sistema',
    'supplier_flow': 'Fluxo do Fornecedor',
    'transferred': 'Transferido',
    'lawyerdifflevel': 'Nível Diferenciado do Advogado',
    'relativepath': 'Caminho Relativo',
    'topath': 'Caminho de Destino',

    # ── Booleanos ─────────────────────────────────────────────────────────────
    'active': 'Ativo',
    'archived': 'Arquivado',
    'visible': 'Visível',
    'enabled': 'Habilitado',
    'canceled': 'Cancelado',
    'rescheduled': 'Reagendado',
    'sinedie': 'Sem Hora Marcada',
    'confirmed': 'Confirmado',
    'deactivated': 'Desativado',

    # ── Comunicação ───────────────────────────────────────────────────────────
    'email': 'E-mail',
    'phone': 'Telefone',
    'message': 'Mensagem',
    'subject': 'Assunto',
    'content': 'Conteúdo',
    'text': 'Texto',
    'recipienttype': 'Tipo de Destinatário',

    # ── Arquivos ──────────────────────────────────────────────────────────────
    'file': 'Arquivo',
    'filepath': 'Caminho do Arquivo',
    'filesize': 'Tamanho do Arquivo',

    # ── Controle e auditoria ──────────────────────────────────────────────────
    'created_by': 'Criado por',
    'updated_by': 'Atualizado por',
    'deleted_by': 'Excluído por',
    'inserted_by': 'Inserido por',

    # ── Permissões de correspondente ──────────────────────────────────────────
    'access_module': 'Módulo de Acesso',
    'approve_requests': 'Aprovar Solicitações',
    'close_requests': 'Fechar Solicitações',
    'designate_correspondent': 'Designar Correspondente',
    'edit_requests_all': 'Editar Todas as Solicitações',
    'view_finance': 'Ver Financeiro',
    'view_log': 'Ver Log',
    'view_requests': 'Ver Solicitações',
    'view_requests_all': 'Ver Todas as Solicitações',
    'write_requests': 'Escrever Solicitações',

    # ── Adicionais ────────────────────────────────────────────────────────────
    'url': 'URL',
    'path': 'Caminho',
    'reference': 'Referência',
    'comments': 'Comentários',
    'notes': 'Notas',
    'details': 'Detalhes',
    'reason': 'Motivo',
}


def traduzir_nome_coluna(nome_coluna):
    """Traduz nome da coluna para português."""
    if not nome_coluna:
        return nome_coluna
    
    # Tradução direta
    if nome_coluna in TRADUCOES_COLUNAS:
        return TRADUCOES_COLUNAS[nome_coluna]
    
    # Tentar traduzir partes
    partes = nome_coluna.lower().split('_')
    partes_traduzidas = []
    
    for parte in partes:
        if parte in TRADUCOES_COLUNAS:
            partes_traduzidas.append(TRADUCOES_COLUNAS[parte])
        else:
            partes_traduzidas.append(parte.capitalize())
    
    return ' '.join(partes_traduzidas)