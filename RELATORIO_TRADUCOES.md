# Relatório de Auditoria de Traduções

**Data:** 2026-07-30  
**Responsável:** Copilot Coding Agent  

---

## 1. Consolidação da Fonte Canônica de Tradução de Nomes de Coluna

### Problema
Existiam **quatro** cópias desincronizadas do dicionário de nomes de coluna:

| Arquivo | Entradas | Status |
|---|---|---|
| `src/traducoes_colunas.py` | ~90 | ✅ Fonte canônica (mantida) |
| `src/api_export.py` | ~90 (idêntica) | ✅ Refatorado — agora importa da fonte canônica |
| `src/web/app.js` | ~100 (constante JS) | ✅ Refatorado — agora consome `/api/traducoes/colunas` |
| `traducoes_nomes_colunas.py` (raiz) | ~65 (protótipo legado) | ✅ Marcado como **DEPRECATED** |

### Solução implementada
1. **`src/traducoes_colunas.py`** expandido para **208 entradas** com todas as traduções de cada fonte anterior e termos adicionais do domínio jurídico.
2. **Novo endpoint** `GET /api/traducoes/colunas` criado em `src/api/routes_traducoes.py` e registrado em `src/api/main.py`. Retorna o dicionário canônico em JSON.
3. **`src/api_export.py`** agora importa `TRADUCOES_COLUNAS` e `traduzir_nome_coluna` diretamente de `src/traducoes_colunas.py` — sem cópia local.
4. **`src/web/app.js`** carrega as traduções do endpoint `/api/traducoes/colunas` durante a inicialização (`iniciar()`), populando a variável de módulo `_traducoesColunas` usada por `traduzirNomeColuna()`. **Nenhuma constante JS duplicada.**
5. **`traducoes_nomes_colunas.py`** tem agora um cabeçalho de deprecação explícito apontando para a fonte canônica.

### Entradas adicionadas ao dicionário canônico (merges)

Provenientes de `src/web/app.js` (únicas):
- `hearingcontrol_id`, `prazoid`, `expedientfileid`, `remote`, `amount`, `location`, `judgement`, `state`, `obs`, `canceled`, `rescheduled`, `sinedie`, `text`, `recipienttype`, `reason`

Provenientes de `traducoes_nomes_colunas.py` (raiz, únicas):
- `person_id`, `client_id`, `employee_id`, `total`, `unit`, `businessunit`, `created_by`, `updated_by`, `deleted_by`, `inserted_by`, `user_changed`, `userid`, `file`, `filepath`, `filesize`, `information`

Termos novos do domínio jurídico/SaidJur (baseado em `dicionario.yaml` e `analise_banco_completo.json`):
- `agreement_in_hearing`, `markup_reason`, `non_agreement_reason`, `resp_evaluation`, `protocoldate`, `startdate`, `hiring_date`, `system_date_insert_proposal`, `all_prazos`, `all_clients`, `all_groups`, `date_reference`, `new_prazo_update_option`, `prazo_days`, `type_days`, `user_change_status`, `user_inserted`, `user_updated`, `what_lawsuits`, `deactivated`, `confirmed`, `businessarea`, `correspondent`, `empstatus`, `lawyerdifflevel`, `oab`, `dateupdated`, `finish_fail`, `finish_success`, `flow`, `perfil`, `morto`, `no_uf`, `direct_member`, `lawsuittype`, `fundamento`, `search_term`, `sigla`, `rate`, `paymentlimit`, `court_division_name`, `confession`, `third_party_presence`, `deferred_protection`, `insurer_flow`, `market_place`, `protection_inserted_system`, `supplier_flow`, `transferred`, `operation`, `access_module`, `approve_requests`, `close_requests`, `designate_correspondent`, `edit_requests_all`, `view_finance`, `view_log`, `view_requests`, `view_requests_all`, `write_requests`, `activity_type`, `action`, `sector`, `region`, `system`, `amount`

---

## 2. Auditoria do `dicionario.yaml` (Tradução de Valores ENUM/Códigos)

### Estatísticas gerais

| Métrica | Valor |
|---|---|
| Tabelas no dicionário | 126 |
| Colunas auditadas | 989 |
| Entradas totais | 17.273 |
| Entradas **auto-traduzidas** | 170 |
| Entradas com **placeholder** (revisão humana necessária) | 17.103 |

> ℹ️ **Contexto**: O arquivo `dicionario.yaml` foi gerado pelo script `gerar_dicionario_traducoes.py` com todos os valores como `[placeholder]`. Nenhuma tradução havia sido preenchida antes desta auditoria. O `dicionarios.yaml` (runtime, lido pelo backend) foi **criado** com as traduções automáticas aplicadas.

### Traduções automáticas aplicadas

Foram traduzidos automaticamente os padrões inequívocos:

**Abreviações universais no domínio:**
| Valor | Tradução |
|---|---|
| `n` | Não |
| `y` | Sim |
| `na` | Não Aplicável |
| `o` | Outro |
| `all` | Todos |
| `s` | Selecionado |
| `refuse_request` | Recusar Solicitação |

**Códigos contábeis (tabela `accounts`):**
| Valor | Tradução |
|---|---|
| `CONT` | Conta |
| `ativo` | Ativo |
| `desp` | Despesa |
| `pass` | Passivo |
| `pl` | Patrimônio Líquido |
| `rec` | Receita |
| `a` / `d` / `p` / `r` | Ativo / Despesa / Passivo / Receita |

**Tipos de dia (`type_days`):**
| Valor | Tradução |
|---|---|
| `b` | Dia Útil |
| `h` | Feriado |

**Tipos de atividade (`type` em `activitynature`):**
| Valor | Tradução |
|---|---|
| `com` | Comercial |
| `con` | Consultoria |
| `j` | Judicial |

**Campos booleanos 0/1** (42 colunas como `active`, `deleted`, `confirmed`, `pericia`, etc.):
| Valor | Tradução |
|---|---|
| `0` | Não |
| `1` | Sim |

### ⚠️ Entradas que requerem revisão humana (17.103 entradas)

As entradas restantes não foram auto-traduzidas pelos seguintes motivos:

1. **Texto descritivo em português** — valores como `"Honorário de Êxito"`, `"Acórdão condenou..."`, `"Reunião no nosso Escritório"` são já texto legível; não precisam de tradução, só de confirmação. Exemplos de tabelas: `acordo_nucleus.agreement_viable_other`, `acordo_nucleus.non_agreement_reason` (IDs numéricos 1–15), `activitynature.nature`, etc.

2. **IDs numéricos sem mapeamento** — colunas como `acordo_nucleus.resp_evaluation` (valores 1–12), `dates2hearing.reason` (valores 1, 3) referenciam tabelas de configuração do sistema. A tradução exige consulta às tabelas referenciadas no banco real.

3. **Nomes próprios e dados de sistema** — valores de colunas `name`, `description`, `nome` etc. são dados do banco (nomes de clientes, varas, tribunais) que não precisam de "tradução" — são exibidos como estão.

4. **Colunas de datas e timestamps** — não há tradução aplicável.

5. **Caminhos de arquivo** — `relativepath`, `topath`, `filename` — dados técnicos sem tradução.

#### Lista de colunas/tabelas prioritárias para revisão humana:

| Tabela | Coluna | Valores | Motivo |
|---|---|---|---|
| `acordo_nucleus` | `agreement_viable_other` | textos longos | Texto jurídico específico |
| `acordo_nucleus` | `non_agreement_reason` | 1–15 (IDs) | Tabela de referência necessária |
| `acordo_nucleus` | `resp_evaluation` | 1–12 (IDs) | Tabela de referência necessária |
| `claims_pericias_control` | `pericia_result` | `d`, `p`, `pe` | Código pericial ambíguo (`d`=deferido? `p`=parcial?) |
| `automaticprazos_lawsuits` | `date_reference` | `a` | Contexto ambíguo (audiência? automático?) |
| `activitynature` | `nature` | lista de atividades | Texto descritivo — revisar adequação |
| `publicationxml` | `nature` | `m`, `p`, `i`, etc. | Requer confirmação (manifestação/publicação/intimação) |

---

## 3. Revisão da Heurística de FK Inferida

### Alterações em `src/db.py`

#### `_CANDIDATAS_LABEL` — adicionado:
- `numero` — número do processo (campo identificador em tabelas de processos brasileiras)
- `number` — variante em inglês
- `lawsuitnumber` — coluna específica do SaidJur

#### `_candidatos_para()` — adicionados mapeamentos inglês→português:
| Inglês | Português |
|---|---|
| `client` | `cliente` |
| `person` | `pessoa` |
| `employee` | `funcionario` |
| `lawsuit` | `processo` |
| `hearing` | `audiencia` |
| `lawyer` | `advogado` |
| `court` | `tribunal` |

Esses mapeamentos permitem que colunas como `client_id` detectem a tabela `clientes` (em português), `lawsuit_id` detecte `processos`, etc.

### Padrões cobertos vs. não cobertos

| Padrão de coluna | Coberto? | Observação |
|---|---|---|
| `*_id` sufixo (ex: `city_id`) | ✅ | Padrão principal |
| `*id` sem underscore (ex: `userid`) | ✅ | Regex captura |
| `*_pk` (ex: `registro_pk`) | ✅ | Regex captura |
| `id_*` prefixo (ex: `id_processo`) | ✅ | Match de prefixo |
| Plural inglês (`cities`, `clients`) | ✅ | Gerado automaticamente |
| Singular inglês → plural pt (`client→clientes`) | ✅ | Novo mapeamento |
| Nomes puramente numéricos sem sufixo | ❌ | Fora do escopo (ambíguo) |
| FKs implícitas por nome de coluna sem `id` | ❌ | Fora do escopo (muitos falsos positivos) |

---

## 4. Novos Testes

Foram adicionados **6 novos testes** cobrindo:

- `TestRotaTraducoes` (3 testes em `tests/test_routes.py`):
  - `test_retorna_dicionario_de_traducoes` — endpoint retorna 200 com dict não-vazio
  - `test_contem_traducoes_essenciais` — campos básicos traduzidos corretamente
  - `test_contem_traducoes_consolidadas` — entradas das 3 fontes anteriores presentes

- `TestFksInferidasExtendidas` (3 testes em `tests/test_db.py`):
  - `test_encontra_numero_como_label` — `numero` reconhecida como coluna de label
  - `test_detecta_client_id_com_mapeamento_portugues` — `client_id` → `clientes`
  - `test_detecta_lawsuit_id_com_mapeamento_portugues` — `lawsuit_id` → `lawsuits`

**Resultado:** 55 testes passando (49 originais + 6 novos), 0 falhas.

---

## 5. Arquivos Modificados

| Arquivo | Tipo de mudança |
|---|---|
| `src/traducoes_colunas.py` | Expandido: 90 → 208 entradas; documentação de fonte canônica |
| `src/api_export.py` | Refatorado: importa de `src/traducoes_colunas.py` em vez de cópia local |
| `src/api/routes_traducoes.py` | **Novo**: endpoint `GET /api/traducoes/colunas` |
| `src/api/main.py` | Registra o novo router de traduções |
| `src/web/app.js` | Remove constante hardcoded; carrega do endpoint via fetch |
| `src/db.py` | `_CANDIDATAS_LABEL` e `_candidatos_para` estendidos |
| `dicionarios.yaml` | **Novo**: 170 traduções auto-aplicadas (gerado desta auditoria) |
| `traducoes_nomes_colunas.py` | Marcado como DEPRECATED |
| `tests/test_routes.py` | 3 novos testes para endpoint de traduções |
| `tests/test_db.py` | 3 novos testes para heurística FK estendida |

---

## 6. Próximos Passos Recomendados (Revisão Humana)

1. **Revisar `dicionarios.yaml`** e preencher as ~17.103 entradas restantes com traduções específicas do jargão jurídico do escritório. Priorizar as colunas da tabela prioritária acima.

2. **Verificar o `publicationxml.nature`** — os valores `m/p/i` provavelmente mapeiam para "Manifestação/Publicação/Intimação" mas necessitam confirmação com a equipe jurídica.

3. **Verificar `claims_pericias_control.pericia_result`** — os valores `d/n/p/pe` não foram auto-traduzidos por ambiguidade (deferido? negado? parcial? perícia?).

4. **Revisar `acordo_nucleus.non_agreement_reason`** e `resp_evaluation` — esses IDs numéricos (1–15) referenciam tabelas de configuração do sistema. Consultar diretamente o banco para obter as descrições.

5. **Testar o visualizador** localmente após a criação do `dicionarios.yaml` para validar que as traduções aparecem corretamente na interface.
