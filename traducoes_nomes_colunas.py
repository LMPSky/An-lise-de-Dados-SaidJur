"""
Traduz nomes de colunas (remover underscore, deixar em português).
"""

# Mapeamento manual de tradução de nomes de colunas
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
    
    # IDs e chaves
    'id': 'ID',
    'user_id': 'ID do Usuário',
    'lawsuit_id': 'ID do Processo',
    'hearing_id': 'ID da Audiência',
    'person_id': 'ID da Pessoa',
    'client_id': 'ID do Cliente',
    'employee_id': 'ID do Funcionário',
    
    # Status e tipos
    'status': 'Status',
    'type': 'Tipo',
    'nature': 'Natureza',
    'phase': 'Fase',
    'result': 'Resultado',
    
    # Nomes descritivos
    'name': 'Nome',
    'description': 'Descrição',
    'code': 'Código',
    'number': 'Número',
    'value': 'Valor',
    'amount': 'Valor',
    'total': 'Total',
    
    # Campos jurídicos
    'lawsuit': 'Processo',
    'plaintiff': 'Autor',
    'defendant': 'Réu',
    'lawyer': 'Advogado',
    'judge': 'Juiz',
    'vara': 'Vara',
    'court': 'Tribunal',
    'hearing': 'Audiência',
    'sentence': 'Sentença',
    
    # Campos específicos do SaidJur
    'agreement_viable': 'Acordo Viável',
    'markup_necessary': 'Markup Necessário',
    'markup_approved': 'Markup Aprovado',
    'pericia': 'Perícia',
    'pericia_result': 'Resultado da Perícia',
    'prazo': 'Prazo',
    'publication': 'Publicação',
    'expedient': 'Expediente',
    'instructions': 'Instruções',
    'observations': 'Observações',
    'city': 'Cidade',
    'state': 'Estado',
    'unit': 'Unidade',
    'businessunit': 'Unidade de Negócio',
    
    # Campos booleanos
    'active': 'Ativo',
    'deleted': 'Excluído',
    'archived': 'Arquivado',
    'visible': 'Visível',
    'enabled': 'Habilitado',
    
    # Campos de controle
    'created_by': 'Criado por',
    'updated_by': 'Atualizado por',
    'deleted_by': 'Excluído por',
    'inserted_by': 'Inserido por',
    'user_changed': 'Alterado por Usuário',
    'userid': 'ID do Usuário',
    
    # Campos de comunicação
    'email': 'E-mail',
    'phone': 'Telefone',
    'message': 'Mensagem',
    'subject': 'Assunto',
    'content': 'Conteúdo',
    
    # Campos de arquivo
    'file': 'Arquivo',
    'filename': 'Nome do Arquivo',
    'filepath': 'Caminho do Arquivo',
    'filesize': 'Tamanho do Arquivo',
    
    # Campos adicionais
    'link': 'Link',
    'url': 'URL',
    'path': 'Caminho',
    'reference': 'Referência',
    'comments': 'Comentários',
    'notes': 'Notas',
    'details': 'Detalhes',
    'information': 'Informação',
}


def traduzir_nome_coluna(nome_coluna):
    """
    Traduz nome da coluna.
    Substitui underscores por espaços e deixa mais legível.
    """
    
    # Se tem tradução direta, usar
    if nome_coluna in TRADUCOES_COLUNAS:
        return TRADUCOES_COLUNAS[nome_coluna]
    
    # Tentar encontrar partes
    partes = nome_coluna.lower().split('_')
    partes_traduzidas = []
    
    for parte in partes:
        if parte in TRADUCOES_COLUNAS:
            partes_traduzidas.append(TRADUCOES_COLUNAS[parte])
        else:
            # Capitalizar primeira letra
            partes_traduzidas.append(parte.capitalize())
    
    # Juntar com espaço
    resultado = ' '.join(partes_traduzidas)
    
    return resultado


if __name__ == "__main__":
    # Testes
    testes = [
        'user_id',
        'created_at',
        'lawsuit_id',
        'plaintiff_name',
        'hearing_date',
        'agreement_viable',
    ]
    
    for teste in testes:
        print(f"{teste:30s} → {traduzir_nome_coluna(teste)}")