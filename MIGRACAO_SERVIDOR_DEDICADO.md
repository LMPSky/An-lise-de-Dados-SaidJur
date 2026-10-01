# 🖥️ Migração para um computador dedicado (acesso remoto para a equipe)

Este guia descreve como mover o banco de dados SaidJur do seu computador para
um **computador dedicado** (um PC/servidor só para isso), para que vários
advogados possam acessar o Visualizador pela rede local, sem depender do seu
computador pessoal ficar ligado.

## 🏗️ Arquitetura escolhida

O computador dedicado roda **os dois componentes juntos**:

- O **MySQL** (banco de dados) — continua escutando apenas em `127.0.0.1`
  (local àquele computador). Ele **não precisa, e não deve**, aceitar conexões
  vindas de outros computadores da rede.
- O **Visualizador** (aplicação web) — escuta em `0.0.0.0:8000`, ou seja,
  aceita conexões de qualquer computador da rede local.

Os advogados **não instalam nada**: apenas abrem o navegador e acessam
`http://<IP-do-computador-dedicado>:8000`. Quem fala diretamente com o MySQL é
sempre o Visualizador, rodando no mesmo computador que o banco — isso evita
expor a porta do MySQL (3306) na rede, o que seria um risco de segurança
desnecessário.

```
┌─────────────────────────────┐        ┌──────────────────┐
│   Computador dedicado        │        │  PC do advogado 1 │
│                              │  LAN   │  (navegador)      │
│  MySQL (127.0.0.1:3306)      │◄──────►│                   │
│  Visualizador (0.0.0.0:8000) │        └──────────────────┘
└─────────────────────────────┘        ┌──────────────────┐
              ▲                        │  PC do advogado 2 │
              │ RDP (só você)          │  (navegador)      │
              │                        └──────────────────┘
      Seu computador
```

> ℹ️ Este guia assume acesso **apenas dentro da rede local/escritório**. Se no
> futuro for necessário acesso de fora (internet, home office), será preciso
> VPN ou um proxy reverso com HTTPS — fora do escopo deste guia.

> ⚠️ O Visualizador **não tem login/senha**. Qualquer pessoa na mesma rede
> local que souber o endereço consegue acessar. Isso foi uma decisão
> consciente (confiar na rede local do escritório); se isso mudar, será
> necessário adicionar autenticação à aplicação.

---

## ✅ Passo 1 — Preparar o computador dedicado

No computador dedicado (acessando via Área de Trabalho Remota):

1. Instale **Python 3.11+** e **MySQL Community Server 8.x**, igual ao que
   você já fez no seu computador. Siga o [INSTALL_WINDOWS.md](INSTALL_WINDOWS.md).
2. Copie esta pasta do projeto (o repositório inteiro) para o computador
   dedicado — por exemplo, via `git clone` (se tiver internet/Git) ou
   copiando a pasta pela Área de Trabalho Remota (copiar/colar arquivos
   funciona normalmente entre os dois computadores quando a conexão RDP
   permite compartilhamento de área de transferência/unidades).
3. Execute `instalar.bat` nessa cópia, dentro do computador dedicado.
4. Edite o `config.yaml` gerado e confira a senha do MySQL **local** àquele
   computador (ainda não mexa em `servidor.host` — isso é feito no Passo 4).

## ✅ Passo 2 — Exportar o banco do seu computador

No **seu computador** (onde o banco está hoje), com o Visualizador **fechado**
(não use durante a exportação):

```
exportar.bat
```

Isso roda `mysqldump` com as opções certas para um banco grande
(`--single-transaction` para não travar o banco durante o dump,
`--quick` para não estourar memória com tabelas de dezenas de milhões de
linhas) e gera um arquivo em `dados\saidjur_export_AAAAMMDD_HHmmss.sql`.

Para um banco de ~50 GB, espere de **1 a 4 horas**, dependendo do disco e da
rede. O arquivo gerado tem tamanho parecido com o `.sql` original que você já
importou.

> 💡 Você também pode indicar o caminho de saída:
> `exportar.bat D:\backups\saidjur.sql`

## ✅ Passo 3 — Transferir o arquivo .sql para o computador dedicado

Algumas opções, em ordem de praticidade:

- **Copiar/colar pela Área de Trabalho Remota**: se a sua conexão RDP tiver
  redirecionamento de área de transferência ou de unidades de disco
  habilitado, basta copiar o arquivo no seu computador e colar dentro da
  sessão remota (ou acessar diretamente `\\tsclient\C` de dentro do RDP para
  arrastar o arquivo).
- **Compartilhamento de rede (SMB)**: compartilhe a pasta `dados\` no seu
  computador e acesse `\\<seu-ip>\dados` a partir do computador dedicado, ou
  vice-versa.
- **Pen drive / HD externo**: para arquivos muito grandes, às vezes é mais
  rápido fisicamente do que pela rede.

Coloque o arquivo `.sql` na pasta `dados\` da cópia do projeto no computador
dedicado.

## ✅ Passo 4 — Importar no computador dedicado

No computador dedicado, dentro da pasta do projeto:

```
importar.bat dados\saidjur_export_AAAAMMDD_HHmmss.sql
```

Igual ao processo que você já conhece — espere de 2 a 12 horas dependendo do
hardware. Acompanhe o progresso e o log em `logs\`.

## ✅ Passo 5 — Configurar o Visualizador para aceitar conexões da rede

Ainda no computador dedicado, edite `config.yaml`:

```yaml
servidor:
  host: 0.0.0.0     # aceita conexões de outros computadores da rede
  porta: 8000

banco:
  host: 127.0.0.1   # o MySQL fica só local a este computador, não exposto na rede
  porta: 3306
  usuario: root
  senha: "..."
  nome: saidjur
```

> O valor `0.0.0.0` em `servidor.host` já é o padrão do projeto — na prática
> você só precisa confirmar que não foi trocado para `127.0.0.1`.

## ✅ Passo 6 — Liberar a porta 8000 no Firewall do Windows

No computador dedicado, abra o **PowerShell como Administrador** e rode:

```powershell
New-NetFirewallRule -DisplayName "Visualizador SaidJur" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

**Não libere a porta 3306** (MySQL) — ela deve continuar acessível apenas
localmente naquele computador.

## ✅ Passo 7 — Iniciar e descobrir o IP do computador dedicado

No computador dedicado:

```
iniciar.bat
```

Depois, descubra o IP dele na rede local (rode no mesmo computador):

```powershell
ipconfig | findstr IPv4
```

## ✅ Passo 8 — Acesso pelos advogados

Cada advogado abre o navegador e acessa:

```
http://<IP-do-computador-dedicado>:8000
```

Nenhuma instalação é necessária nos computadores deles.

---

## 🔁 Mantendo os dois bancos sincronizados (opcional)

Se você continuar recebendo atualizações do banco no seu computador por um
tempo, repita os passos 2 a 4 (exportar → transferir → importar) sempre que
quiser atualizar os dados no computador dedicado. Não existe hoje um
mecanismo de sincronização automática/incremental — cada rodada reimporta o
banco inteiro.

Quando o computador dedicado passar a ser a única fonte de dados, você pode
parar de usar o Visualizador no seu computador pessoal.

## ❓ Dúvidas comuns

**Preciso abrir a porta do MySQL (3306) no firewall?**
Não, e não deve. Só a aplicação web (porta 8000) precisa ser acessível pela
rede; o MySQL conversa apenas com o Visualizador rodando no mesmo computador.

**E se eu quiser acesso de fora do escritório (casa, outra cidade)?**
Este guia cobre apenas a rede local. Acesso externo exigiria VPN ou um proxy
reverso com HTTPS, além de reavaliar a ausência de login na aplicação — não
coberto aqui.

**O Visualizador suporta vários advogados usando ao mesmo tempo?**
Sim, para o uso típico de navegação/consulta — a conexão com o banco já usa
um pool de conexões (até 15 conexões simultâneas). Evite apenas rodar
`importar.bat`/`exportar.bat` enquanto várias pessoas estão usando o
Visualizador.
