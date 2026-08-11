# Pendências de Tradução — Revisão Humana Necessária

Gerado em: 2026-07-30  
Atualizado em: 2026-08-11 (Rodada 5 — auditoria ampla de corrupção em `dicionarios.yaml`)  
Fonte: `relatorio_auditoria_traducoes.yaml`

---

## Rodada 5 (2026-08-11) — Limpeza ampla de entradas corrompidas

### 1) Entradas removidas por corrupção clara (código→código / valor sem sentido)

Foram removidos blocos/entradas sem semântica confiável no dicionário atual, incluindo:
`activitynature.nature`, `automaticprazos_lawsuits.*`, `paymentguarantee2lawsuit.*`,
`clientsystem2lawsuit.phase/status`, `expedients.type`, `lawsuitdocs.phase/processtype`,
`otherdocs.processtype`, `person2lawsuit.persontype`, `person2lawsuit.link_type`,
`projects.type/status`, `timesheet_tasks.status`, `pedidos2lawsuit.status`,
`lawsuits.type/contract_type`, `lawsuits_log.type/contract_type/finalpayment_type`,
`lawsuitdocsmetadata.pjestatus/docstatus`, `projectactivityprazos.status`.

Esses casos precisam de confirmação no banco real antes de reintrodução:

```bash
python investigar_pendencias.py --colunas tabela.coluna
```

---

### 2) Remoções com destaque de higiene de dados (vazamento de conteúdo específico/sensível)

Foram removidas entradas que continham conteúdo de registro real (não rótulo genérico):

- `users.status` (`ramos01*`)
- `hearings_log.hearingstatus` (texto completo de audiência com data/hora/local)
- `tasks2publication.status` (texto de tarefa específica)

Esses dados **não devem** existir em um dicionário genérico versionado.
Como salvaguarda adicional, a investigação assistida agora descarta pistas com
aparência de texto livre longo/específico.

---

### 3) Correções diretas de baixo risco (idioma/capitalização e booleanos claros)

- `varas.code`: traduzido para português jurídico (`Vara do Trabalho`, `Vara Cível`, `Vara Federal`).
- `accounts.code`: normalização de capitalização (`Passivo`, `Despesas`, `Receitas`, `Sistema Auxiliar`).
- Status booleanos claramente identificáveis corrigidos para `0/1`:
  - `employees.empstatus`
  - `lawsuits.status`
  - `lawsuits_log.status`
  - `users.status`
  - campos binários de `usertasks.*` citados na auditoria
- `sent_hearing_emails.type.lawyer`: ajustado para `Advogado`.

---

### 4) Pendências que continuam dependentes de validação humana

- Reconstrução correta de `activitynature.nature` (estrutura original código→rótulo
  não é inferível com segurança sem acesso ao banco real).
- `returned_prazo_reasons.status` continua parcial no dicionário (`'1': Ativo`);
  o significado de `status=0` deve ser confirmado no banco real antes de incluir.
- Reintrodução de mapeamentos removidos dos blocos listados na seção 1, com
  validação por amostragem no ambiente real.

## Rodada 4 (2026-08-10) — Falso negativo, FKs de prazo e booleanos

### Parte 0 — Diagnóstico do falso negativo em `pedidos2lawsuit.status = 6`

A investigação direcionada continuava retornando `sem_registros` para
`pedidos2lawsuit.status = 6` mesmo após a PR #23.

**Causa provável identificada**: incompatibilidade de tipo entre a comparação
inteira da query (`WHERE status = 6`) e o tipo real da coluna no MySQL
(possivelmente `VARCHAR`/`TEXT` armazenando `'6'` como texto). No SQLite,
`'6' ≠ 6` por definição; no MySQL, a coerção costuma funcionar mas pode
falhar em codificações ou collations específicas.

**Correções implementadas**:
1. **Fallback de comparação via CAST**: se a query com comparação inteira
   retornar 0 linhas, tenta automaticamente `CAST(coluna AS TEXT) = CAST(:valor AS TEXT)`.
   Isso cobre o caso em que o valor está armazenado como texto.
2. **Diagnóstico COUNT**: ao retornar `sem_registros`, a ferramenta agora
   executa `SELECT COUNT(*)` e, se o count for > 0, inclui na justificativa
   uma nota explicando a discrepância (possível problema de tipo/nome).
3. **Testes adicionados** (`tests/test_investigacao_pendencias.py`) para o
   cenário SQLite in-memory com `pedidos2lawsuit` contendo linha `status = 6`
   tanto em coluna INTEGER (query direta) quanto em coluna TEXT (fallback CAST).

> **Nota**: se após estas correções `pedidos2lawsuit.status = 6` ainda retornar
> `sem_registros` no banco real, o problema é provavelmente o nome da coluna
> ou da tabela no MySQL (case sensitivity no Linux). Verifique com:
> ```sql
> SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS
> WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'pedidos2lawsuit';
> ```

### Parte A — FKs de funcionário/supervisor/usuário em tabelas de prazo

**Problema**: colunas como `userid`, `supervisorid`, `userchangedid` em
`prazos_log`, `prazo2publication` e `lawsuitdocsmetadata` exibiam o ID
numérico bruto em vez do nome do funcionário/usuário, mesmo sendo
reconhecidas como link clicável.

**Causa**: a heurística `_candidatos_para()` em `src/db.py` não gerava
`employees` como tabela candidata para bases como `user`, `supervisor` e
`userchanged`, pois esses nomes não têm mapeamento direto para `employees`
pelas substituições genéricas existentes.

**Correção implementada**:
- Adicionado bloco explícito em `_candidatos_para()` que inclui `employees`
  como candidata quando a base da coluna for `user`, `supervisor`,
  `userchanged`, `excludente` ou `criador`.
- Adicionado `_COLUNAS_FK_EXTRAS` dict para colunas FK que não seguem a
  convenção de sufixo `*_id` (ex: `pubtype` → `pubtypes`).
- Atualizados testes em `tests/test_db.py`.

**Colunas agora resolvidas** (requer que a tabela `employees` exista com
coluna `id` e uma coluna de label como `name` ou `empname`):

| Coluna | Tabela referenciada |
|--------|---------------------|
| `userid` | `employees` |
| `supervisorid` | `employees` |
| `userchangedid` | `employees` |
| `pubtype` | `pubtypes` |

**Ainda pendente**: colunas `employee_id` e `emp_id` já geravam `employees`
via heurística anterior; `user_del` não tem sufixo `_id` e não é um inteiro
puro — verificar o tipo real dessa coluna.

### Parte B — Booleanos de prazo adicionados ao `dicionarios.yaml`

As seguintes colunas booleanas foram adicionadas com `0`→"Não" / `1`→"Sim"
para `prazos_log` e `prazo2publication`, com base no nome inequivocamente
binário e nos valores `0` observados pelo usuário:

| Tabela | Coluna | Valor `0` | Valor `1` |
|--------|--------|-----------|-----------|
| `prazos_log` | `canceled` | Não | Sim |
| `prazos_log` | `denied` | Não | Sim |
| `prazos_log` | `returned` | Não | Sim |
| `prazos_log` | `skip_validate` | Não | Sim |
| `prazo2publication` | `canceled` | Não | Sim |
| `prazo2publication` | `denied` | Não | Sim |
| `prazo2publication` | `returned` | Não | Sim |
| `prazo2publication` | `skip_validate` | Não | Sim |

### Correção de traduções inválidas no `dicionarios.yaml`

As seguintes entradas, claramente inválidas (geradas pelo bug da ferramenta
de investigação antes da PR #23), foram corrigidas ou removidas:

| Tabela | Coluna | Valor | Era (errado) | Corrigido para |
|--------|--------|-------|--------------|----------------|
| `chatmessages` | `recipienttype` | `all` | `Prezados, boa tarde!` | `Todos` |
| `chatmessages` | `recipienttype` | `s` | `'1'` | `Individual` |
| `chatmessages` | `status` | `'0'`, `'1'` | `s`, `s` | `Inativo`, `Ativo` |
| `persons` | `persontype` | `n` | `'0'` | `Pessoa Física` |
| `persons` | `persontype` | `l` | `'0'` | `Pessoa Jurídica` |
| `persons` | `personstatus` | `'1'` | `'0'` | `Ativo` |
| `prazos_log` | `pzphase` | `'4'` | texto de agendamento | removido (pendente) |
| `prazos_log` | `finishtype` | `n` | texto de agendamento | removido (pendente) |
| `prazo2publication` | `pzphase` | `'1'`–`'4'` | `'0'` | removidos (pendentes) |

---

### Bugs corrigidos na ferramenta de investigação (`src/investigacao_pendencias.py`)

Três bugs foram identificados e corrigidos:

1. **Bug 1/2 — Query de amostragem sem conversão de tipo**: a query `WHERE coluna = :valor`
   usava o valor como string mesmo quando a coluna era inteira, o que causava falso negativo
   ("sem registros") em MySQL. **Correção**: valores numéricos agora são convertidos para `int`
   antes de serem passados como parâmetro da query.

2. **Bug 3 — Heurística de alta confiança fraca demais**: a classificação `alta_confianca`
   disparava para qualquer coluna com valor único e consistente nas linhas de amostra — incluindo
   colunas booleanas (`0`/`1`) que são constantes por padrão em qualquer amostra pequena.
   **Correção**: `alta_confianca` agora exige que a coluna-pista tenha nome semanticamente
   relacionado a rótulos/descrições (ex: `name`, `desc`, `title`). Colunas booleanas ou
   com nome técnico sem relação semântica são rebaixadas para `pista_unica` com aviso.

### Auditoria de traduções aplicadas via `aplicar_sugestoes_investigacao.py`

A entrada `hearingcontrol.hearingtype: {"11": "0"}` foi sugerida pela ferramenta com
`alta_confianca` porque a coluna `hearingfile` tinha valor `'0'` constante em 5/5 linhas de
amostra. Isso é um **falso positivo** — `hearingfile` é uma coluna booleana e o valor `'0'`
é o padrão de qualquer amostra, sem relação com o significado do código `11`.

> **Nota**: Verificação no repositório confirmou que a entrada
> `hearingcontrol.hearingtype: {"11": "0"}` **não foi commitada** ao `dicionarios.yaml`
> — apenas existia localmente no ambiente do usuário. Portanto, não é necessário reverter
> nenhuma entrada no repositório. O item permanece pendente na seção abaixo.

Com a heurística corrigida, este caso agora seria classificado como `pista_unica` (com aviso
de pista fraca), em vez de `alta_confianca`, evitando a aprovação automática equivocada.

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
| `pedidos2lawsuit` | `status` | `6` | Status do pedido/andamento. A ferramenta agora tenta CAST como fallback; se ainda retornar `sem_registros`, verificar o nome e tipo real da coluna no MySQL (ver nota na Rodada 4). |
| `hearingcontrol` | coluna "Prazo Incluído" | `2` | Não foi possível mapear o nome exato da coluna. Pode ser `prazotype`, `prazo_included` ou similar. Investigar com `--colunas hearingcontrol.<nome_real_da_coluna>:2`. |
| `prazos_log` | `pzphase` | `0`, `3`, `4` | Fase do Prazo — código numérico com mais de 2 valores, não é booleano simples. Investigar com `--colunas prazos_log.pzphase:0 prazos_log.pzphase:3 prazos_log.pzphase:4`. |
| `prazo2publication` | `pzphase` | `1`, `2`, `3`, `4` | Fase do Prazo (mesmas fases de `prazos_log`). Investigar com `--colunas prazo2publication.pzphase:1`. |
| `lawsuitdocsmetadata` | `prazophase` | (vários) | Fase de Prazo em metadados de documentos — investigar com `--colunas lawsuitdocsmetadata.prazophase`. |
| `prazos_log` | `finishtype` | `p`, `pje`, `n`, `f` | Tipo de Conclusão — valores curtos sem legenda textual confiável. Investigar com `--colunas prazos_log.finishtype:p`. |
| `prazo2publication` | `finishtype` | `p` | Mesmo padrão de `prazos_log.finishtype`. |
| `prazos_log` / `prazo2publication` | `pubtype` | `58704` (FK) | Tipo de Publicação — valor alto indica FK para tabela `pubtypes`. A resolução de label agora está configurada; confirmar se a tabela `pubtypes` existe com coluna `name` no banco real. |

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
