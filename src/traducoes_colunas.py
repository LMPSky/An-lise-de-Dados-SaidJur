"""
Módulo de tradução de nomes de colunas.
Integrado com o sistema de dicionários.
"""

TRADUCOES_COLUNAS = {
    # Campos de data/hora
    'created_at': 'Data de Criação',
    'updated_at': 'Data de Atualização',
    'deleted_at': 'Data de Exclusão',
    'inserted_at': 'Data de Inserção',
    'timestamp': 'Data/Hora',
    'date_inserted': 'Data de Inserção',
    'date': 'Data',
    'datemoved': 'Data de Movimentação',
    'processing_date': 'Data de Processamento',
    'effectivedate': 'Data Efetiva',
    'instructionsdate': 'Data das Instruções',
    'instructionsinsertdate': 'Data de Inserção das Instruções',
    'instructionstimestamp': 'Timestamp das Instruções',
    'naf_userid_date': 'Data do Usuário NAF',
    'updated_at_userid': 'Usuário da Atualização',
    
    # IDs
    'id': 'ID',
    'user_id': 'ID do Usuário',
    'lawsuit_id': 'ID do Processo',
    'hearing_id': 'ID da Audiência',
    'from_automatic_prazoid': 'ID do Prazo Automático',
    'fromhearingcontrolid': 'ID do Controle de Audiência',
    
    # Status e tipos
    'status': 'Status',
    'type': 'Tipo',
    'nature': 'Natureza',
    'phase': 'Fase',
    'result': 'Resultado',
    'aut_event': 'Evento Automático',
    'hearing': 'Audiência',
    'from_lawsuit': 'Originário de Processo',
    
    # Nomes descritivos
    'name': 'Nome',
    'description': 'Descrição',
    'code': 'Código',
    'number': 'Número',
    'value': 'Valor',
    'filename': 'Nome do Arquivo',
    'lawsuitnumber': 'Número do Processo',
    
    # Campos jurídicos
    'lawsuit': 'Processo',
    'plaintiff': 'Autor',
    'defendant': 'Réu',
    'lawyer': 'Advogado',
    'judge': 'Juiz',
    'vara': 'Vara',
    'court': 'Tribunal',
    'city': 'Cidade',
    'paper': 'Papel',
    'link': 'Link',
    'observations': 'Observações',
    'observations_userid': 'Usuário das Observações',
    
    # Campos específicos
    'agreement_viable': 'Acordo Viável',
    'markup_necessary': 'Markup Necessário',
    'markup_approved': 'Markup Aprovado',
    'pericia': 'Perícia',
    'pericia_result': 'Resultado da Perícia',
    'prazo': 'Prazo',
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
    'noprazoemailsent01': 'Email Sem Prazo Enviado',
    'revised': 'Revisado',
    'sent': 'Enviado',
    'naf': 'NAF',
    'naf_userid': 'Usuário NAF',
    'analise_prov': 'Análise Provisória',
    'analise_prov_hearingid': 'ID Audiência Análise Provisória',
    'acomp_encerramento': 'Acompanhamento Encerramento',
    'sentence': 'Sentença',
    'objecttype': 'Tipo de Objeto',
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
    'av_clientid': 'ID Cliente Avaliação',
    'includeexpedient': 'Incluir Expediente',
    'cpfl_spreadsheet_import': 'Importação Planilha CPFL',
    
    # Booleanos
    'active': 'Ativo',
    'archived': 'Arquivado',
    'visible': 'Visível',
    'enabled': 'Habilitado',
    
    # Comunicação
    'email': 'E-mail',
    'phone': 'Telefone',
    'message': 'Mensagem',
    'subject': 'Assunto',
    'content': 'Conteúdo',
    
    # Adicionais
    'url': 'URL',
    'path': 'Caminho',
    'reference': 'Referência',
    'comments': 'Comentários',
    'notes': 'Notas',
    'details': 'Detalhes',
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