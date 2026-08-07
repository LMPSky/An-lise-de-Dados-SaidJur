# Pendências de Tradução — Revisão Humana Necessária

Gerado em: 2026-07-30  
Atualizado em: 2026-08-07 (Rodada 2 — investigação direcionada de ENUMs observados na prática)  
Fonte: `relatorio_auditoria_traducoes.yaml`

---

## Atualizações da Rodada 2 (2026-08-07)

### Traduções aplicadas automaticamente (alta confiança)

As seguintes traduções booleanas foram adicionadas a `dicionarios.yaml` para a tabela
`hearingcontrol`, uma vez que colunas com nomes como `needwitness`, `needinterpreter`,
`needexpert`, `needother` e `hearingfile` são inequivocamente booleanas
(`0` = Não, `1` = Sim):

| Tabela | Coluna | Valor | Tradução aplicada |
|--------|--------|-------|-------------------|
| `hearingcontrol` | `needwitness` | `0` | Não |
| `hearingcontrol` | `needwitness` | `1` | Sim |
| `hearingcontrol` | `needinterpreter` | `0` | Não |
| `hearingcontrol` | `needinterpreter` | `1` | Sim |
| `hearingcontrol` | `needexpert` | `0` | Não |
| `hearingcontrol` | `needexpert` | `1` | Sim |
| `hearingcontrol` | `needother` | `0` | Não |
| `hearingcontrol` | `needother` | `1` | Sim |
| `hearingcontrol` | `hearingfile` | `0` | Não |
| `hearingcontrol` | `hearingfile` | `1` | Sim |

> **Como investigar valores adicionais de forma direcionada:**
> ```bash
> python investigar_pendencias.py --colunas hearingcontrol.hearingtype:11 pedidos2lawsuit.status:6
> ```
> O parâmetro `--colunas` permite passar qualquer `tabela.coluna` (ou `tabela.coluna:valor`)
> sem precisar esperar o relatório de auditoria completo capturar aquele valor específico.

---

### Pendências residuais — necessitam confirmação no banco real

As pendências abaixo foram identificadas na prática pelo usuário (prints de tela),
mas **não têm tradução suficientemente confiável sem acesso ao banco real**:

| Tabela | Coluna | Valor observado | Contexto / Motivo da pendência |
|--------|--------|-----------------|-------------------------------|
| `hearingcontrol` | `hearingtype` | `11` | Tipo de audiência judicial. O significado do código `11` varia entre sistemas jurídicos — rodar `investigar_pendencias.py --colunas hearingcontrol.hearingtype:11` contra o banco real para obter pistas. |
| `pedidos2lawsuit` | `status` | `6` | Status do pedido/andamento. Outros valores de status já presentes no dicionário não cobrem `6` — investigar com `--colunas pedidos2lawsuit.status:6`. |
| `hearingcontrol` | coluna "Prazo Incluído" | `2` | Não foi possível mapear o nome exato da coluna. Pode ser `prazotype`, `prazo_included` ou similar. Investigar com `--colunas hearingcontrol.<nome_real_da_coluna>:2`. |

---

## Resumo

| Categoria | Automático (esta tarefa) | Pendente (revisão humana) | Total |
|-----------|--------------------------|--------------------------|-------|
| Nomes de coluna | 7 | 6 | 13 |
| Valores de ENUM/código | 96 | 120 | 216 |
| **Total** | **103** | **126** | **229** |

> Nesta rodada foram resolvidos automaticamente os campos do `jqcalendar`,
> `lawsuitdifflevel` e os casos inequívocos de ENUM/flags binárias.  
> Os itens abaixo continuam exigindo validação humana para evitar traduções erradas.

---

## 1. Nomes de coluna pendentes

### 1.1 Campos técnicos de estrutura de árvore — tabela `accounts`

| Coluna | Tradução atual (fallback) | Motivo da pendência |
|--------|--------------------------|---------------------|
| `lft` | Lft | Coluna técnica de estrutura Nested Sets / MPTT. Pode não fazer sentido expor ao usuário final. |
| `rgt` | Rgt | Idem — limite direito da árvore. |

**Sugestão:** confirmar se esses campos devem ser ocultados da interface em vez de traduzidos.

---

### 1.2 Abreviações internas sem contexto suficiente

| Tabela | Coluna | Tradução atual (fallback) | Contexto / Motivo da pendência |
|--------|--------|--------------------------|-------------------------------|
| `lawsuits` | `nd` | Nd | Sigla ambígua no contexto de processos. |
| `lawsuits_log` | `nd` | Nd | Mesmo caso da tabela principal. |
| `pedidos2lawsuit` | `ias` | Ias | Abreviação interna sem semântica confiável no relatório. |
| `prazos` | `adm` | Adm | Pode significar "Administrativo" ou outra convenção interna. |

---

## 2. Valores de ENUM/código pendentes

### 2.1 Códigos contábeis — tabela `accounts`

**`accounts.code`** — valores encontrados: `ativo`, `pass`, `desp`, `rec`, `pl`, `CONT`  
**`accounts.type`** — valores encontrados: `a`, `d`, `p`, `pl`, `r`  
**`accounts.nature`** — valores encontrados: `a`, `p`, `d`, `r`, `pl`

Apesar de parecerem siglas contábeis conhecidas, esses códigos afetam
classificações financeiras e devem ser confirmados com a regra de negócio do SaidJur.

---

### 2.2 Tipos curtos com significado ainda ambíguo

| Tabela | Coluna | Valores pendentes | Observação |
|--------|--------|-------------------|------------|
| `activitynature` | `type` | `con`, `com` | Podem representar categorias internas de atividade. |
| `automaticprazos_lawsuits` | `type_days` | `b`, `n` | Provável distinção entre dias úteis/corridos, mas sem confirmação. |
| `claims` | `lawsuittype` | `j` | Código isolado, sem legenda confiável. |
| `expedients` | `type` | `p`, `l` | Prováveis tipos operacionais, mas sem confirmação documental. |
| `lawsuitdocs` | `processtype` | `j` | Mesmo padrão ambíguo de tipo de processo. |
| `lawsuits` | `type` | `j` | Idem. |
| `lawsuits_log` | `type` | `j` | Idem. |
| `otherdocs` | `processtype` | `j` | Idem. |
| `projecteventtypes` | `type` | `con` | Sigla curta sem contexto suficiente. |
| `projects` | `type` | `con` | Mesmo código da tabela de tipos de projeto. |
| `timesheet_tasks` | `type` | `i` | Código unitário sem legenda confiável. |

---

### 2.3 Status/fases numéricos dependentes de configuração do sistema

| Tabela | Coluna | Valores pendentes | Motivo da pendência |
|--------|--------|-------------------|---------------------|
| `clientsystem2lawsuit` | `phase` | `1`, `2`, `3`, `4`, `5` | IDs/configuração do sistema do cliente. |
| `clientsystem2lawsuit` | `status` | `1`, `2`, `3`, `4`, `5` | Mesmo caso acima. |
| `final_payments` | `payment_type` | `1`, `2`, `3` | Referência a tipo de pagamento final. |
| `hearingcontrol` | `hearingstatus` | `0`, `1`, `2` | Estados de audiência sem legenda oficial no relatório. |
| `hearings_log` | `hearingstatus` | `0`, `1`, `2` | Mesmo caso acima. |
| `lawsuitdocs` | `phase` | `0`, `1`, `2`, `3`, `5` | Fases numéricas do fluxo documental. |
| `lawsuitdocsmetadata` | `prazophase` | `1` | Fase de prazo sem legenda confirmada. |
| `lawsuits` | `finalpayment_type` | `1`, `2`, `3` | Tipo de pagamento final. |
| `lawsuits_log` | `finalpayment_type` | `1`, `2`, `3` | Mesmo caso acima. |
| `paymentguarantee2lawsuit` | `nature` | `1`, `2`, `3` | Natureza de garantia dependente de tabela/regra de referência. |
| `paymentguarantee2lawsuit` | `type_old` | `1`–`12`, `14`, `16`–`19` | Códigos legados sem legenda textual. |
| `prazo2publication` | `pzphase` | `1`, `2`, `3`, `4` | Fases de prazo. |
| `prazos_log` | `pzphase` | `1`, `2`, `3`, `4` | Mesmo caso acima. |
| `tasks2publication` | `status` | `0`, `1`, `2` | Status com três estados, sem documentação no relatório. |
| `varas` | `code` | `4`, `5`, `8` | Código numérico de vara, parece identificador e não rótulo. |

---

### 2.4 Códigos jurídicos/comerciais que ainda precisam de validação

| Tabela | Coluna | Valores pendentes | Observação |
|--------|--------|-------------------|------------|
| `lawsuits` | `contract_type` | `es`, `co`, `ctrl`, `es2` | Padrão comercial/jurídico ainda sem confirmação oficial. |
| `lawsuits_log` | `contract_type` | `es`, `co`, `ctrl`, `es2` | Mesmo caso acima. |
| `person2lawsuit` | `link_type` | `t`, `s`, `u` | Códigos muito curtos para traduzir sem contexto adicional. |
| `person2lawsuit` | `persontype` | `p`, `d`, `c` | Papel da pessoa no processo ainda precisa de confirmação. |
| `prazo2publication` | `finishtype` | `p` | Os valores `n`, `f` e `pje` já eram conhecidos; `p` continua ambíguo. |
| `prazos_log` | `finishtype` | `p` | Mesmo caso acima. |

---

### 2.5 Casos binários ainda parcialmente vistos no relatório

| Tabela | Coluna | Valores pendentes | Observação |
|--------|--------|-------------------|------------|
| `automaticprazos_lawsuits` | `lawsuit_phase` | `0` | Valor isolado sem legenda. |
| `automaticprazos_lawsuits` | `status` | `0` | Só um dos lados do binário apareceu na amostra. |
| `deniedprazo_reasons` | `status` | `0`, `1` | Pode ser ativo/inativo, mas não há confirmação funcional. |
| `pedidos2lawsuit` | `status` | `1` | Apenas um valor observado. |
| `projectevents` | `status` | `0` | Apenas um valor observado. |
| `projects` | `status` | `0` | Apenas um valor observado. |
| `returned_prazo_reasons` | `status` | `1` | Apenas um valor observado. |
| `timesheet_tasks` | `status` | `0` | Apenas um valor observado. |

---

## 3. Tabela colossal `publicationxml`

A tabela `publicationxml` continua sendo um caso especial: ela tem volume
muito alto e segue sujeita a timeout ao tentar amostrar valores textuais.

Nesta rodada, a decisão foi:

1. **Manter a auditoria dos nomes de coluna** normalmente.
2. **Pular a auditoria de ENUM** quando a tabela ultrapassar o limiar de
   tabela colossal configurado no script.
3. **Registrar explicitamente no relatório** que a amostragem de ENUM foi
   pulada por tamanho, em vez de deixar a tabela falhar com erro de conexão.

---

## 4. Próximos passos

1. Confirmar com a equipe funcional se `lft`/`rgt` devem ser ocultados.
2. Levantar o significado interno de `nd`, `ias` e `adm`.
3. Consultar tabelas de referência/configuração para fases e status numéricos.
4. Validar com o time jurídico/comercial os códigos de `contract_type`,
   `person2lawsuit.*` e `finishtype = p`.
5. Após validação, complementar `src/traducoes_colunas.py` e `dicionarios.yaml`.
