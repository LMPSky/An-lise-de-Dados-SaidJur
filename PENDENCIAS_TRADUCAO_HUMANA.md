# Pendências de Tradução — Revisão Humana Necessária

Gerado em: 2026-07-30  
Atualizado em: 2026-08-28 (Rodada 9 — fechamento por evidência dos relatórios de banco real)  
Fonte: `relatorio_auditoria_traducoes.yaml`

## Investigação em lote (quando houver acesso ao banco)

Não é necessário listar manualmente cada `tabela.coluna[:valor]`. Na raiz do
projeto, execute `python investigar_pendencias.py --lote --limite-linhas 50`.
O comando extrai referências documentadas neste arquivo, consulta o domínio
atual dessas colunas e procura códigos curtos ainda sem tradução por
introspecção do schema. O relatório resultante é agrupado por confiança e
tabela; sugestões continuam exigindo revisão humana antes de qualquer alteração
em `dicionarios.yaml`.

---

## Rodada 9 (2026-08-28) — Fechamento por evidência dos relatórios de banco real

### 0) Método desta rodada (sem acesso ao banco)

Nesta rodada **não houve conexão com o banco**. Em vez de rodar
`investigar_pendencias.py` / `investigar_colunas.py`, as pendências foram
resolvidas por correlação entre os três artefatos de banco real já versionados:

| Artefato | O que fornece |
|----------|---------------|
| `relatorio_auditoria_traducoes.yaml` | Lista de colunas/valores pendentes e o conjunto de valores efetivamente observados na amostragem |
| `relatorio_investigacao_pendencias.yaml` | Resultado da investigação assistida, com `fonte`, `tabela_referencia` e nível de confiança por código |
| `dicionario.yaml` | Dump do **domínio completo** de valores distintos por `tabela.coluna` no banco real |

Só foram aplicadas traduções em que o `dicionario.yaml` confirma o **domínio
fechado** da coluna (ex.: exatamente `{0, 1}` ou `{n, y}`) ou em que o
`relatorio_investigacao_pendencias.yaml` registra `alta_confianca` com
`fonte: tabela_referencia`. Nenhum código ambíguo foi adivinhado.

### 1) Higiene de dados — entradas removidas do `dicionarios.yaml`

Duas entradas presentes no dicionário versionado contrariavam decisões já
documentadas nas Rodadas 5 e 6 e foram removidas:

| Tabela | Coluna | Valor | Conteúdo removido | Motivo |
|--------|--------|-------|-------------------|--------|
| `hearingcontrol` | `hearingstatus` | `2` | `Audiência instrução designada para 11/06/2019 14:30 Seção B da 31ª Vara Cível da Capital.` | Texto livre de um registro real (data/hora/local). É exatamente o mesmo vazamento removido de `hearings_log.hearingstatus` na Rodada 5, reintroduzido em `hearingcontrol` pelo bug corrigido na Rodada 7. |
| `lawsuits` | `finalpayment_type` | `2` | `JAC BH BARÃO` | A Rodada 6 declarou essa entrada como **removida do dicionário ativo** (possível nome de agência/unidade), mas ela continuava no arquivo. |

Com isso, `hearingcontrol.hearingstatus` volta a ser pendência aberta
(valores `0`, `1`, `2`), alinhada com `hearings_log.hearingstatus`.

### 2) Nomes de coluna — `accounts.lft` / `accounts.rgt` resolvidos

O `dicionario.yaml` confirma que ambas as colunas contêm apenas inteiros
sequenciais (`1`, `2`, `3`, …), o que caracteriza sem ambiguidade o padrão
**Nested Sets / MPTT** (limites esquerdo e direito do nó na árvore do plano de
contas). Como o padrão é notório e não depende de regra de negócio do SaidJur,
as colunas foram traduzidas em `src/traducoes_colunas.py`:

| Coluna | Tradução aplicada |
|--------|-------------------|
| `lft` | Limite Esquerdo (Árvore) |
| `rgt` | Limite Direito (Árvore) |

São **campos técnicos de estrutura**, não campos de negócio. A decisão de
**ocultá-los da interface** continua sendo uma escolha de produto (a definir com
a equipe funcional), mas o item deixa de ser pendência de *tradução*.

Com isso, o item 1.1 desta lista está encerrado. Restam apenas as abreviações
`lawsuits.nd`, `lawsuits_log.nd`, `pedidos2lawsuit.ias` e `prazos.adm`
(item 1.2), que continuam sem evidência.

### 3) Status/flags binários com domínio fechado confirmado

Aplicado o padrão já consolidado no projeto (`status` `0`/`1` →
`Inativo`/`Ativo`; flag booleana → `Não`/`Sim`) **somente** onde o
`dicionario.yaml` mostra o domínio completo com os dois lados presentes:

| Tabela | Coluna | Domínio no banco | Tradução aplicada |
|--------|--------|------------------|-------------------|
| `deniedprazo_reasons` | `status` | `{0, 1}` | Inativo / Ativo |
| `paymentguarantee2lawsuit` | `status` | `{0, 1}` | Inativo / Ativo |
| `projectactivityprazos` | `status` | `{0, 1}` | Inativo / Ativo |
| `prazos_log` | `status` | `{0, 1}` | Inativo / Ativo |
| `prazo2publication` | `status` | `{0, 1}` | Inativo / Ativo |
| `paymentguarantee2lawsuit` | `containstypefile` | `{0, 1}` | Não / Sim |
| `hearingcontrol` | `remote` | `{0, 1}` | Não / Sim |
| `hearingcontrol` | `confession` | `{n, y}` | Não / Sim |
| `hearingcontrol` | `third_party_presence` | `{n, y}` | Não / Sim |

> `prazo2publication.status` aparecia como `['0']` na amostra da auditoria, mas o
> dump de domínios (`dicionario.yaml`) registra `{0, 1}` — por isso entrou nesta
> rodada, e não nas anteriores.

`hearingcontrol.remote` também foi promovida a booleano confirmado em
`colunas_booleanas_confirmadas.yaml` (domínio `0`/`1`). `confession` e
`third_party_presence` **não** foram incluídas nesse arquivo porque ele é
específico para colunas com domínio `0`/`1`, e essas usam `n`/`y`.

### 4) Valor textual inequívoco

| Tabela | Coluna | Valor | Tradução aplicada |
|--------|--------|-------|-------------------|
| `automaticprazos_lawsuits` | `hearing_type` | `all` | Todos |

Domínio completo é `{all}` e a palavra é inglês corrente, não um código interno —
mesmo tratamento já dado a `chatmessages.recipienttype.all` e a
`print_reports.nature` (`lawsuits` → Processos, `hearing` → Audiência).

### 5) Propagação entre tabelas irmãs (mesma tabela de referência)

O `relatorio_investigacao_pendencias.yaml` registra que **`prazos_log.pzphase` e
`prazo2publication.pzphase` resolvem contra a mesma tabela de referência
`prazotype`**, e que os códigos `3` e `4` produziram rótulos idênticos nas duas
tabelas. Isso é evidência suficiente para completar `prazos_log.pzphase` com os
códigos que já estavam traduzidos em `prazo2publication.pzphase`:

| Tabela | Coluna | Valor | Tradução aplicada | Origem |
|--------|--------|-------|-------------------|--------|
| `prazos_log` | `pzphase` | `1` | audiência inicial | `prazotype` (via `prazo2publication.pzphase`) |
| `prazos_log` | `pzphase` | `2` | ENVIAR CTPS P/ ANOTAÇÃO | `prazotype` (via `prazo2publication.pzphase`) |
| `prazos_log` | `finishtype` | `p` | processo físico | `prazo2publication.finishtype` |

Os domínios de `pzphase` (`{1, 2, 3, 4}`) são idênticos nas duas tabelas no
`dicionario.yaml`, o que confirma que compartilham o mesmo catálogo.
`prazos_log.pzphase` fica assim **totalmente traduzida**.

> O valor `0` de `prazos_log.pzphase` citado na Rodada 2 **não existe** no dump de
> domínios do banco (`{1, 2, 3, 4}`); a investigação da Rodada 8 também retornou
> `sem_pista_encontrada` para ele. O item foi encerrado como inexistente.

### 6) Normalização documentada de `accounts.code`

A Rodada 5 declarou a normalização de capitalização de `accounts.code`
(`Passivo`, `Despesas`, `Receitas`, `Sistema Auxiliar`), mas o arquivo continuava
com os rótulos em caixa alta. A decisão foi aplicada de fato, e `ativo` foi
alinhado ao mesmo padrão (classe contábil, não "conta de ativos"):

| Valor | Era | Passou a ser |
|-------|-----|--------------|
| `ativo` | Conta de ativos | Ativo |
| `pass` | PASSIVO | Passivo |
| `desp` | DESPESAS | Despesas |
| `rec` | RECEITAS | Receitas |
| `pl` | SISTEMA AUXILIAR | Sistema Auxiliar |
| `CONT` | Conta | Conta (inalterado) |

`accounts.type` e `accounts.nature` **não** foram alterados: continuam
pendentes de validação com a regra de negócio contábil (item 2.1).

### 7) `activitynature.nature` — encerrado como "não requer tradução"

A Rodada 5 deixou em aberto a "reconstrução" de `activitynature.nature`. O dump
de domínios mostra que os valores armazenados **já são rótulos em português**
(`Reunião no nosso Escritório`, `Telefonema`, `E-mail`, `Almoço/jantar`,
`Redação da proposta`, …). Não é uma coluna de código: é texto de catálogo
mantido pelo usuário. Portanto **não deve** receber entradas no
`dicionarios.yaml` — qualquer mapeamento seria identidade e viraria ruído
versionado. Item encerrado.

### 8) Pendências que permanecem abertas (com motivo atualizado)

#### 8.1 Um único lado do binário observado

Continuam pendentes pela mesma regra da Rodada 5 (`returned_prazo_reasons.status`):
enquanto apenas um valor for observado no banco, não há prova de que a coluna
seja binária `Inativo`/`Ativo`.

| Tabela | Coluna | Domínio observado |
|--------|--------|-------------------|
| `automaticprazos_lawsuits` | `lawsuit_phase` | `{0}` |
| `automaticprazos_lawsuits` | `status` | `{0}` |
| `pedidos2lawsuit` | `status` | `{1}` |
| `projectevents` | `status` | `{0}` |
| `projects` | `status` | `{0}` |
| `returned_prazo_reasons` | `status` | `{1}` |
| `timesheet_tasks` | `status` | `{0}` |
| `lawsuitdocsmetadata` | `pjestatus` | `{0}` |
| `lawsuitdocsmetadata` | `docstatus` | `{1}` |

Reinvestigar com amostra maior quando houver banco:
```bash
python investigar_pendencias.py --limite-linhas 100 --colunas \
  automaticprazos_lawsuits.status projects.status projectevents.status \
  timesheet_tasks.status returned_prazo_reasons.status pedidos2lawsuit.status
```

#### 8.2 Status/fases com três ou mais estados, sem tabela de referência

| Tabela | Coluna | Domínio observado | Situação |
|--------|--------|-------------------|----------|
| `hearingcontrol` | `hearingstatus` | `{0, 1, 2}` | Reaberta nesta rodada (ver item 1). A única sugestão de alta confiança apontava para texto livre de `hearings_log`, não para um catálogo. |
| `hearings_log` | `hearingstatus` | `{0, 1, 2}` | Mesmo caso. |
| `tasks2publication` | `status` | `{0, 1, 2}` | Três estados sem catálogo identificado. |
| `clientsystem2lawsuit` | `phase` / `status` | `{1..5}` | Configuração do sistema do cliente. |
| `lawsuitdocs` | `phase` | `{0, 1, 2, 3, 5}` | Fases do fluxo documental. |
| `final_payments` | `payment_type` | `{1, 2, 3}` | Sem catálogo identificado. |
| `lawsuits` / `lawsuits_log` | `finalpayment_type` | `{1, 2, 3}` | Idem (após a remoção do item 1). |
| `paymentguarantee2lawsuit` | `nature` | `{1, 2, 3}` | Investigação retornou apenas `pista_unica`. |
| `paymentguarantee2lawsuit` | `type_old` | `{1..12, 14, 16..19}` | Códigos legados. |
| `lawsuitdocsmetadata` | `prazophase` | `{1}` | O rótulo atual (`Juntada de Substabelecimento`) **diverge** de `prazotype[1]` (`audiência inicial`), então **não** houve propagação a partir de `pzphase`. Confirmar se `prazophase` usa outro catálogo. |

#### 8.3 Códigos curtos sem catálogo

| Tabela | Coluna | Valores | Situação |
|--------|--------|---------|----------|
| `lawsuits` / `lawsuits_log` | `contract_type` | `es`, `co`, `ctrl`, `es2` | A investigação assistida retornou `pista_unica`/`sem_pista_encontrada` para todos os quatro. Nenhuma tabela de referência foi localizada mesmo após a ampliação de heurísticas da Rodada 7 (`contracttypes`, `tipos_contrato`, …). Sem evidência, nada foi aplicado. |
| `person2lawsuit` | `link_type` | `t`, `s`, `u` | `t` e `s` sem evidência. **Atenção**: o dicionário contém `u: SEM JUSTA CAUSA`, sem rastro de origem nos relatórios e sem coerência semântica com "tipo de vínculo". Entrada mantida, mas **marcada para confirmação humana** antes da próxima rodada. |
| `person2lawsuit` | `persontype` | `p`, `d`, `c` | Provavelmente autor/réu/cliente, mas sem confirmação — não aplicado. |
| `activitynature` | `type` | `con`, `com` | Sem catálogo. |
| `automaticprazos_lawsuits` | `type_days` | `b`, `n` | Provável "dias úteis"/"dias corridos", sem confirmação. |
| `claims` | `lawsuittype` | `j` | Código isolado. |
| `expedients` | `type` | `p`, `l` | Sem catálogo. |
| `lawsuitdocs` / `otherdocs` | `processtype` | `j` | Sem catálogo. |
| `lawsuits` / `lawsuits_log` | `type` | `j` | Sem catálogo. |
| `projecteventtypes` / `projects` | `type` | `con` | Sem catálogo. |
| `timesheet_tasks` | `type` | `i` | Sem catálogo. |
| `prazos_log` / `prazo2publication` | `finishtype` | `f`, `n`, `pje`, `adm` | Apenas `p` (processo físico) tem rótulo confirmado. `adm` só ocorre em `prazo2publication`. |
| `accounts` | `type` / `nature` | `a`, `d`, `p`, `pl`, `r` | Rótulos atuais mantidos, mas pendentes de validação contábil. |
| `prazos_log` / `prazo2publication` | `pubtype` | 50 valores distintos (FK) | Resolver via tabela `pubtypes` (ver Rodada 7/8), não por dicionário. |

### 9) Resumo da Rodada 9

| Ação | Quantidade |
|------|-----------|
| Nomes de coluna traduzidos | 2 (`lft`, `rgt`) |
| Valores de ENUM/código adicionados | 22 |
| Entradas corrigidas (capitalização) | 5 (`accounts.code`) |
| Entradas removidas por higiene de dados | 2 |
| Itens encerrados sem necessidade de tradução | 2 (`activitynature.nature`, `prazos_log.pzphase = 0`) |
| Colunas promovidas a booleano confirmado | 1 (`hearingcontrol.remote`) |

---

## Rodada 8 (2026-08-13) — Correlação com `prazoobs` e switch de nomes técnicos

### 1) Nova capacidade: correlação com coluna de observação (`prazoobs`) como contexto complementar

A ferramenta de investigação (`src/investigacao_pendencias.py`) agora inclui
automaticamente o campo **`contexto_obs`** no relatório YAML e na revisão
interativa quando:
- A investigação principal **não** chega a alta confiança para o código investigado; E
- A tabela investigada contém uma coluna de observação/texto-livre reconhecida
  (`prazoobs`, `obs`, `observacao`, `observacoes`, `remarks`, `comentario`, etc.).

O `contexto_obs` mostra a distribuição dos valores dessa coluna para as linhas
onde o código aparece, ajudando o usuário a inferir manualmente o significado sem
precisar consultar o banco diretamente.

**Exemplo de saída no relatório YAML** para `prazos_log.pzphase = 3`:
```yaml
contexto_obs:
  coluna_obs: prazoobs
  total_linhas_consultadas: 20
  valores_distintos: 4
  amostras:
    - valor: "Prazo de contestação"
      ocorrencias: 8
    - valor: "Resposta ao recurso"
      ocorrencias: 5
  nota: "Valores de coluna de observação correlacionados com o código investigado.
         Use como pista manual — não é tradução automática."
```

**Exemplo na revisão interativa** (`aplicar_sugestoes_investigacao.py`):
```
📝 Contexto adicional — coluna de observação 'prazoobs' (4 valor(es) distinto(s) em 20 linha(s)):
   [8x] 'Prazo de contestação'
   [5x] 'Resposta ao recurso'
```

**Regras de segurança mantidas**:
- O `contexto_obs` é apenas **informativo** — nunca gera sugestão automática.
- Nenhuma tradução de baixa confiança é aplicada sem aprovação humana.
- Se a investigação principal encontrar tabela de referência válida (alta confiança),
  o `contexto_obs` **não é** adicionado (não é necessário).

### 2) Pendências `pzphase` e `pubtype` — status atualizado

#### `prazos_log.pzphase` e `prazo2publication.pzphase` (Fase do Prazo)

**Status**: pendente — investigação aguarda `prazoobs` como contexto.  
Execute o comando abaixo para obter o contexto complementar de `prazoobs`:

```powershell
python investigar_pendencias.py --limite-linhas 50 --colunas `
  prazos_log.pzphase:0 prazos_log.pzphase:3 prazos_log.pzphase:4 `
  prazo2publication.pzphase:1 prazo2publication.pzphase:2 prazo2publication.pzphase:3 prazo2publication.pzphase:4
```

O campo `contexto_obs` no YAML resultante mostrará os textos de observação
(`prazoobs`) que ocorrem junto a cada fase, o que deve permitir inferência manual.

#### `prazos_log.pubtype` / `prazo2publication.publicationtype` (Tipo de Publicação)

**Status**: pendente — FK para tabela de tipos de publicação não confirmada.  
O valor `58704` provavelmente é FK para `pubtypes` (ou nome similar). Execute:

```sql
SELECT TABLE_NAME FROM information_schema.TABLES
WHERE TABLE_NAME LIKE '%pub%type%' OR TABLE_NAME LIKE '%publicac%';
```

Se `pubtypes` existir, a ferramenta resolverá automaticamente. Se não, use o
contexto de `prazoobs` (presente no relatório de investigação) para inferência manual.

### 3) Novo switch de interface "🔧 Mostrar nomes técnicos"

Disponível na interface web no **Modo Avançado** (botão `🔧 Nomes técnicos`
ao lado de `🏷️ Labels` e `👁️ Colunas`).

**Comportamento**:
- **Desligado** (padrão): exibe apenas o nome traduzido em português
  (ex: "Fase do Prazo").
- **Ligado**: exibe o nome traduzido seguido do nome técnico real da coluna
  no banco entre parênteses (ex: "Fase do Prazo (pzphase)").

**Onde é aplicado**: cabeçalhos de tabela, modal de detalhe, resultados de busca
global e console SQL.

**Persistência**: salvo em `localStorage` com chave `saidjur_mostrar_nomes_tecnicos`.
Independente do switch `🏷️ Labels` (que controla resolução de FK/label vs valor cru).

---

## Rodada 7 (2026-08-12) — Correção de bug crítico e ampliação de heurísticas

### 1) Bug corrigido — rótulo NULL aceito como tradução de alta confiança

**Causa raiz**: quando a coluna de rótulo de uma tabela de referência retornava
`NULL` no banco para o código investigado, o código anterior convertia o valor
Python `None` para a string literal `"None"` (via `str(None)`) e a tratava como
rótulo válido de alta confiança. Isso levou à entrada incorreta
`hearingcontrol.hearingstatus: {'1': 'None'}` gerada pela ferramenta.

**Nota para o usuário**: se essa entrada foi aplicada ao `dicionarios.yaml` local,
ela **deve ser removida manualmente**. Verifique:
```yaml
hearingcontrol:
  hearingstatus:
    # remover se existir:
    '1': 'None'
```

**Correção aplicada** em `src/investigacao_pendencias.py` (função
`_buscar_em_tabela_referencia`): valores `None` da coluna de rótulo são agora
rejeitados explicitamente antes de `str()`. Se todas as linhas candidatas tiverem
rótulo nulo, a tabela candidata é descartada e a busca continua nas demais
tabelas candidatas.

### 2) Detecção ampliada de tabelas de referência (Parte A)

A heurística de geração de nomes candidatos de tabela de referência foi ampliada
em `src/investigacao_pendencias.py`:

- **Prefixo `pz` expandido para `prazo`**: colunas como `pzphase` agora geram
  candidatos como `prazofase`, `prazofases`, `prazo_phase`, etc., cobrindo tabelas
  com nome completo baseado na entidade "prazo".
- **Variantes de tipo de contrato**: `contract_type` → `contracttypes`,
  `contract_types`, `tipos_contrato`, `tipocontrato`.
- **Variantes de tipo de publicação**: `publicationtype`, `publication_type` →
  `publicationtypes`, `publication_types`, `tipos_publicacao`.
- **Variantes de tipo de pessoa/vínculo**: `persontype` → `persontypes`,
  `tipos_pessoa`; `link_type` → `linktypes`, `link_types`, `tipos_vinculo`.
- A estrutura `_PREFIXOS_ABREVIADOS` e a lista de sufixos em
  `_gerar_nomes_candidatos_tabela` são **extensíveis**: adicione novas entradas
  conforme novos prefixos ou padrões forem identificados no banco.

**Ação necessária**: re-investigar as pendências abaixo com `investigar_pendencias.py`
para verificar se a ampliação resolve automaticamente a tradução:
- `prazos_log.pzphase` / `prazo2publication.pzphase`
- `lawsuits.contract_type`
- `person2lawsuit.link_type` / `person2lawsuit.persontype`

### 3) FK de "ID do Usuário Atualizador" corrigida (Parte B)

Adicionadas variações de nome de coluna de usuário atualizador à heurística de FK
em `src/db.py` (`_candidatos_para`). As bases adicionadas ao conjunto `_BASES_USUARIO`
(sem sufixo `id`, que é removido pela heurística antes da comparação) são:
- `updateduser`, `updateuser`, `updater`, `updatedby`, `userupdated`,
  `atualizador`, `useratualiz`, `atualiz`

Colunas como `updateduserid`, `updatedbyid`, `atualizadorid` agora
resolvem para a tabela `employees`.

**Ação necessária**: verificar visualmente nos relatórios exportados se o campo
"ID do Usuário Atualizador" em `prazos_log` e `lawsuitdocsmetadata` agora
exibe o nome do funcionário em vez do ID cru `97`.

### 4) FK de "Tipo de Publicação" com variantes de nome de coluna (Parte B)

Adicionadas à lista `_COLUNAS_FK_EXTRAS` em `src/db.py`:
- `pub_type`, `publicationtype`, `publication_type` → todos apontam para `pubtypes`.

**Nota**: se `pubtypes` não existir no banco com esse nome exato, o valor cru
`58704` continuará aparecendo. Nesse caso, verificar o nome real da tabela de
tipos de publicação com:
```sql
SELECT TABLE_NAME FROM information_schema.TABLES
WHERE TABLE_NAME LIKE '%pub%type%' OR TABLE_NAME LIKE '%publicac%';
```
e adicionar o nome real em `_COLUNAS_FK_EXTRAS`.

---

## Rodada 6 (2026-08-11) — Correções imediatas e salvaguardas adicionais

### 1) Correções imediatas confirmadas

- `varas.code` **permanece corrigido diretamente** no `dicionarios.yaml` com rótulos
  em português jurídico (`Vara Federal`, `Vara do Trabalho`, `Vara Cível`).
  Como a correção é segura e consistente com a Rodada 5, esse bloco **não foi
  reaberto** como pendência.
- `lawsuits.finalpayment_type['2']` **permanece removido** do dicionário ativo.
  A sugestão `JAC BH Barão` foi tratada como **possível dado específico/sensível**
  (nome de agência/unidade/entidade), e não como categoria genérica de domínio.

### 2) Higiene de dados reforçada

Além dos casos já listados na Rodada 5, a sugestão abaixo foi mantida fora do
dicionário por possível vazamento de dado específico:

- `lawsuits.finalpayment_type['2'] = JAC BH Barão`

O tratamento é o mesmo adotado para os demais casos removidos na Rodada 5:
esses valores **não devem** entrar em um dicionário versionado sem validação
humana explícita de que representam uma categoria genérica.

### 3) Salvaguardas novas na investigação assistida

- Busca prioritária de **tabela de referência/catálogo** via schema antes de usar
  pistas textuais da própria tabela.
- Preferência automática por **coluna em português** quando existir irmã em outro
  idioma no mesmo schema (por exemplo, `name`/`name_pt` antes de `name_en`).
- `--limite-linhas` documentado e coberto por teste também no modo direcionado
  `--colunas`, para permitir reinvestigação com amostras maiores (ex.: 50–100 linhas).
- A revisão interativa agora destaca um alerta separado para **possível dado
  específico/sensível**, distinto do aviso de pista fraca.

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
`pedidos2lawsuit.status = 6` mesmo após as correções da PR #23/24.

**Causa raiz identificada (PR #25)**: o fallback de comparação via CAST
introduzido na PR #24 usava `CAST(coluna AS TEXT)`, sintaxe válida apenas
no SQLite. No MySQL/MariaDB, o tipo de destino `TEXT` não é aceito no `CAST`
— a sintaxe correta é `CAST(coluna AS CHAR)`. Isso causava um erro de SQL
no banco real, que era silenciado e mascarado como `sem_registros`, ocultando
a causa raiz do usuário.

**Correções implementadas na PR #25**:
1. **Sintaxe CAST compatível**: substituído `CAST(... AS TEXT)` por
   `CAST(... AS CHAR)`, que é válido tanto no MySQL/MariaDB quanto no SQLite.
2. **Exceções do fallback não são mais mascaradas**: se o fallback de CAST
   lançar qualquer exceção, ela agora é propagada ao chamador e registrada
   com `status: erro` (com a mensagem original), em vez de ser silenciada
   e convertida em `sem_registros`.
3. **Testes adicionados** (`tests/test_investigacao_pendencias.py`) para
   verificar que a expressão CAST gerada é válida no dialeto MySQL (via
   compilação com `sqlalchemy.dialects.mysql`) e que exceções no fallback
   resultam em `status: erro`, não `sem_registros`.

> **Ação necessária**: agora que o bug de sintaxe foi corrigido, **rode a
> ferramenta novamente** contra o banco real para confirmar se
> `pedidos2lawsuit.status = 6` é encontrado:
> ```
> python investigar_pendencias.py --colunas pedidos2lawsuit.status:6
> ```
> Se o resultado ainda for `sem_registros` (sem erro), a linha de fato não
> existe no banco com esse valor. Se retornar `erro`, verifique a mensagem
> para diagnóstico adicional.

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
| `pedidos2lawsuit` | `status` | `6` | Status do pedido/andamento. O bug de sintaxe `CAST(... AS TEXT)` no fallback (inválido no MySQL) foi corrigido na PR #25 — rode `investigar_pendencias.py --colunas pedidos2lawsuit.status:6` novamente para obter o resultado correto. |
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

> ✅ **Resolvido na Rodada 9.** Ver seção "Rodada 9 → item 2".

| Coluna | Tradução aplicada | Situação |
|--------|-------------------|----------|
| `lft` | Limite Esquerdo (Árvore) | Campo técnico Nested Sets / MPTT — traduzido; exibi-lo ou não na interface é decisão de produto. |
| `rgt` | Limite Direito (Árvore) | Idem — limite direito da árvore. |

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

1. Confirmar com a equipe funcional se `lft`/`rgt` (já traduzidos na Rodada 9)
   devem ser ocultados da interface por serem campos técnicos de árvore.
2. Levantar o significado interno de `nd`, `ias` e `adm`.
3. Consultar tabelas de referência/configuração para fases e status numéricos
   ainda listados na seção 8 da Rodada 9.
4. Validar com o time jurídico/comercial os códigos de `contract_type`,
   `person2lawsuit.*` e `finishtype` (`f`, `n`, `pje`, `adm`).
5. Confirmar a origem de `person2lawsuit.link_type['u'] = SEM JUSTA CAUSA` e
   removê-la caso não venha de um catálogo real.
6. Após validação, complementar `src/traducoes_colunas.py` e `dicionarios.yaml`.
