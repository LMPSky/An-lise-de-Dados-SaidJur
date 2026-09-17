"""Constantes compartilhadas para tratamento de tabelas colossais.

Tabelas com um volume de linhas muito acima do normal (ex: ``publicationxml``,
~10M de linhas) podem travar consultas ``DISTINCT``/``GROUP BY`` sem índice
útil, causando timeouts (``Lost connection... timed out``). Este módulo
centraliza o limiar de linhas usado tanto pela auditoria completa
(``auditar_traducoes.py``) quanto pela descoberta automática de pendências em
lote (:mod:`src.investigacao_pendencias`), para que ambos os fluxos pulem
essas tabelas de forma consistente, sem duplicar a constante.
"""

from __future__ import annotations

# Acima deste número de linhas estimadas (via TABLE_ROWS do
# information_schema), a tabela é considerada "colossal": consultas de
# amostragem de valores distintos passam a ser evitadas por completo, em vez
# de descobertas coluna a coluna via timeout.
LIMITE_LINHAS_TABELA_COLOSSAL = 5_000_000

# Para tabelas colossais, em vez de pular a amostragem de valores distintos
# por completo (o que deixaria pendências de tradução dessas tabelas para
# sempre fora do radar), a amostragem passa a rodar sobre uma subseleção já
# limitada por LIMIT — evitando o GROUP BY/DISTINCT na tabela inteira, que é
# a operação que historicamente causa timeout. Mesmo valor já usado em
# ``auditar_traducoes.py`` (``LIMITE_SUBSELECAO_TABELA_COLOSSAL`` local).
LIMITE_SUBSELECAO_TABELA_COLOSSAL = 5_000

# Algumas colunas de tabelas colossais ainda estouram o timeout mesmo com a
# subseleção acima: como o armazenamento é por linha, ler N linhas de uma
# coluna curta ainda exige varrer outras colunas grandes (TEXT/BLOB) da mesma
# linha. Nesses casos, a subseleção é tentada de novo com um LIMIT cada vez
# menor (reduzido pela metade a cada tentativa) até este piso, antes de
# desistir e reportar a coluna como falha.
LIMITE_MINIMO_SUBSELECAO_TABELA_COLOSSAL = 200

# Variante do limite de subseleção usada pelo "modo completo" (varredura
# exaustiva do banco inteiro, pensada para rodar sem supervisão durante a
# noite — ver ``--completo`` em ``investigar_pendencias.py``). Como o tempo
# de execução deixa de ser uma restrição nesse modo, a amostragem inicial de
# tabelas colossais usa um LIMIT bem maior antes de recorrer ao mesmo
# mecanismo de retry decrescente (até o mesmo piso
# ``LIMITE_MINIMO_SUBSELECAO_TABELA_COLOSSAL``), aumentando a chance de
# descobrir valores distintos que só aparecem além da amostra padrão de
# ``LIMITE_SUBSELECAO_TABELA_COLOSSAL`` linhas.
LIMITE_SUBSELECAO_TABELA_COLOSSAL_MODO_COMPLETO = 50_000
