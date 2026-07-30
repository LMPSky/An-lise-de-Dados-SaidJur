# Pendências de Tradução — Revisão Humana Necessária

Gerado em: 2026-07-30  
Fonte: `relatorio_auditoria_traducoes.yaml`

---

## Resumo

| Categoria | Automático (esta tarefa) | Pendente (revisão humana) | Total |
|-----------|--------------------------|--------------------------|-------|
| Nomes de coluna | 1 674 | 13 | 1 687 |
| Valores de ENUM/código | 116 | 94 | 210 |
| **Total** | **1 790** | **107** | **1 897** |

> **99,2% das colunas** e **55,2% dos valores ENUM** foram traduzidos automaticamente.  
> Os itens abaixo requerem decisão de um especialista no domínio jurídico/financeiro do SaidJur.

---

## 1. Nomes de coluna pendentes

### 1.1 Campos técnicos de estrutura de árvore — tabela `accounts`

| Coluna | Tradução atual (fallback) | Motivo da pendência |
|--------|--------------------------|---------------------|
| `lft` | Lft | Coluna de estrutura de árvore MPTT (Nested Sets). Significado interno do motor de persistência; não faz sentido expor para o usuário. |
| `rgt` | Rgt | Idem — right boundary da árvore MPTT. |

**Sugestão não confirmada:** ocultar essas colunas na interface (não traduzir, filtrar na exposição via API).

---

### 1.2 Campos de calendário externo — tabela `jqcalendar`

Estes campos usam nomenclatura original da biblioteca jqCalendar (camelCase em inglês). São colunas de integração com sistema externo.

| Coluna | Tradução atual (fallback) | Sugestão não confirmada |
|--------|--------------------------|------------------------|
| `StartTime` | Starttime | "Hora de Início" |
| `EndTime` | Endtime | "Hora de Término" |
| `IsAllDayEvent` | Isalldayevent | "Evento de Dia Inteiro" |
| `Color` | Color | "Cor" |
| `RecurringRule` | Recurringrule | "Regra de Recorrência" |

**Ação recomendada:** confirmar se esses campos são exibidos ao usuário final ou apenas usados internamente pela integração do calendário.

---

### 1.3 Abreviações internas sem correspondência clara

| Tabela | Coluna | Tradução atual (fallback) | Contexto / Motivo da pendência |
|--------|--------|--------------------------|-------------------------------|
| `lawsuits` | `nd` | Nd | Sigla desconhecida no contexto de processos judiciais. Possível: "Número do Documento"? "Não Definido"? |
| `lawsuits_log` | `nd` | Nd | Idem (tabela de log de processos). |
| `pedidos2lawsuit` | `ias` | Ias | Sigla desconhecida no contexto de pedidos vinculados a processos. |
| `prazos` | `adm` | ADM | Ambíguo: "Administrativo"? "ADM (sigla interna)"? |

---

### 1.4 Colunas com nome igual ao da tabela

| Tabela | Coluna | Motivo da pendência |
|--------|--------|---------------------|
| `lawsuits` | `lawsuitdifflevel` | Coluna tem o mesmo nome que outra tabela (`lawsuitdifflevel`). Pode ser uma FK ou campo denormalizado. |
| `lawsuits_log` | `lawsuitdifflevel` | Idem. |

**Sugestão não confirmada:** "Nível Diferenciado do Processo" — mas confirmar se é FK ou valor.

---

## 2. Valores de ENUM/código pendentes

### 2.1 Tabela `accounts` — códigos contábeis

Esses valores são usados em campos de classificação de contas (`code`, `type`, `nature`) e representam categorias contábeis. Precisam de validação por profissional contábil.

**`accounts.code`** — valores encontrados: `ativo`, `pass`, `desp`, `rec`, `pl`, `CONT`

| Valor | Sugestão não confirmada |
|-------|------------------------|
| `ativo` | Ativo (já em português) |
| `pass` | Passivo |
| `desp` | Despesa |
| `rec` | Receita |
| `pl` | Patrimônio Líquido |
| `CONT` | Contabilidade / Conta |

**`accounts.type`** — valores encontrados: `a`, `d`, `p`, `pl`, `r`

| Valor | Sugestão não confirmada |
|-------|------------------------|
| `a` | Ativo |
| `d` | Despesa |
| `p` | Passivo / Provisão |
| `pl` | Patrimônio Líquido |
| `r` | Receita |

**`accounts.nature`** — valores encontrados: `a`, `p`, `d`, `r`, `pl`

Mesmos valores de `accounts.type`. Provável mesma semântica.

---

### 2.2 Tabela `clientsystem2lawsuit` — fases e status do sistema do cliente

Valores numéricos sem rótulos conhecidos. Dependem da configuração específica do cliente.

**`clientsystem2lawsuit.phase`** — valores encontrados: `1`, `2`, `3`, `4`, `5`

Sugestão: consultar a tabela `clientsystem` para ver os nomes das fases.

**`clientsystem2lawsuit.status`** — valores encontrados: `1`, `2`, `3`, `4`, `5`

Idem.

---

### 2.3 Tabela `expedients` — tipo de expediente

**`expedients.type`** — valores encontrados: `p`, `l`

| Valor | Sugestão não confirmada |
|-------|------------------------|
| `p` | Protocolo |
| `l` | Levantamento |

---

### 2.4 Tabela `final_payments` — tipo de pagamento final

**`final_payments.payment_type`** — valores encontrados: `1`, `2`, `3`

Valores numéricos sem rótulos. Sugestão: cruzar com a tabela de tipos de pagamento do sistema.

---

### 2.5 Tabelas `hearingcontrol` e `hearings_log` — status de audiência

**`hearingcontrol.hearingstatus`** e **`hearings_log.hearingstatus`** — valores encontrados: `0`, `1`, `2`

| Valor | Sugestão não confirmada |
|-------|------------------------|
| `0` | Agendada |
| `1` | Realizada |
| `2` | Cancelada |

Confirmar com a equipe de negócio qual é a semântica exata.

---

### 2.6 Tabela `lawsuitdocs` — fase do documento

**`lawsuitdocs.phase`** — valores encontrados: `0`, `1`, `2`, `3`, `5`

Valores numéricos de fase. Checar se há uma tabela de referência de fases de documentos.

---

### 2.7 Tabela `lawsuitdocsmetadata` — campos de status

| Coluna | Valor | Sugestão não confirmada |
|--------|-------|------------------------|
| `prazophase` | `1` | Fase 1 do prazo |
| `pjestatus` | `0` | Inativo no PJe |
| `docstatus` | `1` | Ativo / Concluído |

---

### 2.8 Tabelas `lawsuits` e `lawsuits_log` — tipo de contrato e tipo de pagamento final

**`lawsuits.contract_type`** e **`lawsuits_log.contract_type`** — valores encontrados: `es`, `co`, `ctrl`, `es2`

| Valor | Sugestão não confirmada |
|-------|------------------------|
| `es` | Êxito Simples |
| `co` | Condicionado |
| `ctrl` | Controlado |
| `es2` | Êxito Simples 2 |

**`lawsuits.finalpayment_type`** e **`lawsuits_log.finalpayment_type`** — valores encontrados: `1`, `2`, `3`

Sem rótulos conhecidos. Verificar junto à equipe financeira do SaidJur.

---

### 2.9 Tabela `paymentguarantee2lawsuit` — natureza e tipo antigo

**`paymentguarantee2lawsuit.nature`** — valores encontrados: `1`, `2`, `3`

| Valor | Sugestão não confirmada |
|-------|------------------------|
| `1` | Garantia Real |
| `2` | Garantia Fidejussória |
| `3` | Garantia Mista |

**`paymentguarantee2lawsuit.type_old`** — valores encontrados: `1`–`12`, `14`, `16`–`19`

Muitos códigos numéricos. Há provável tabela de referência de tipos de garantia.

---

### 2.10 Tabela `person2lawsuit` — tipo de pessoa e tipo de vínculo

**`person2lawsuit.persontype`** — valores encontrados: `p`, `d`, `c`

| Valor | Sugestão não confirmada |
|-------|------------------------|
| `p` | Autor (Plaintiff) |
| `d` | Réu (Defendant) |
| `c` | Terceiro / Corresponsável |

**`person2lawsuit.link_type`** — valores encontrados: `t`, `s`, `u`

| Valor | Sugestão não confirmada |
|-------|------------------------|
| `t` | Técnico |
| `s` | Solidário |
| `u` | Único |

---

### 2.11 Tabelas `prazo2publication` e `prazos_log` — fase e tipo de conclusão

**`prazo2publication.pzphase`** e **`prazos_log.pzphase`** — valores encontrados: `1`, `2`, `3`, `4`

Já traduzidos genericamente como "Fase 1–4" em `dicionarios.yaml`. Confirmar se há rótulos específicos (ex.: "Cadastrado", "Em Análise", "Concluído", "Arquivado").

**`prazo2publication.finishtype`** e **`prazos_log.finishtype`** — valor pendente: `p`

Os outros valores (`n`=Normal, `f`=Fatal, `pje`=PJe) já foram traduzidos. O significado de `p` não é claro neste contexto. Sugestão não confirmada: "Por Prazo" ou "Publicação".

---

### 2.12 Tabela `varas` — código da vara

**`varas.code`** — valores encontrados: `4`, `5`, `8`

São códigos numéricos de identificação de varas. Não representam texto legível — provavelmente IDs de referência. Sugestão: verificar se faz sentido traduzir ou apenas exibir o número.

---

## 3. Próximos passos

1. **Campos técnicos** (`lft`, `rgt`): Verificar se são exibidos ao usuário — se não, excluir da lista de tradução.
2. **jqcalendar**: Confirmar se os campos são exibidos ao usuário final ou apenas usados internamente.
3. **Códigos contábeis** (`accounts.code/type/nature`): Consultar profissional contábil ou documentação do Plano de Contas do sistema.
4. **Fases/status numéricos** (`clientsystem2lawsuit`, `lawsuitdocs`, `hearingcontrol`): Consultar documentação de regras de negócio ou a equipe de desenvolvimento.
5. **Tipo de contrato** (`es`, `co`, `ctrl`, `es2`): Confirmar com equipe comercial/jurídica do SaidJur.
6. **Garantias de pagamento** (`paymentguarantee2lawsuit`): Consultar tabela de referência de tipos de garantia.
7. **Vínculos de pessoa** (`person2lawsuit`): Confirmar semântica de `p`, `d`, `c` (persontype) e `t`, `s`, `u` (link_type).
8. **Fase do prazo** (`prazos_log.finishtype: p`): Confirmar se é "Por Prazo", "Publicação" ou outro.

Após confirmação, adicionar as traduções em:
- `src/traducoes_colunas.py` — para nomes de coluna
- `dicionarios.yaml` — para valores de ENUM/código
