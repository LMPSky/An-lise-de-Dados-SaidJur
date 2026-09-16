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
