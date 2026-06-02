# 📊 Visualizador de Dados SaidJur

Bem-vindo! Este programa permite **visualizar, pesquisar e exportar** o conteúdo
do banco de dados SaidJur diretamente no seu navegador — sem precisar escrever
nenhum comando técnico.

---

## 🤔 O que é isso?

É uma ferramenta que transforma um arquivo de banco de dados (`.sql`) em uma
interface fácil de usar, parecida com uma planilha do Excel, onde você pode:

- 🔍 **Pesquisar** qualquer texto em todo o banco de um só lugar
- 📋 **Navegar** pelos registros com paginação automática
- 🔽 **Filtrar** por coluna (como no Excel)
- 📥 **Exportar** para CSV ou Excel
- 🖥️ Tudo rodando **no seu próprio computador**, sem internet

---

## ✅ O que você precisa ter instalado

Antes de começar, instale os dois programas abaixo:

| Programa | Link para download | Para que serve |
|---|---|---|
| **Python 3.11 ou superior** | [python.org/downloads](https://www.python.org/downloads/) | Linguagem que roda o servidor |
| **MySQL Community Server 8.x** | [dev.mysql.com/downloads/installer](https://dev.mysql.com/downloads/installer/) | Banco de dados onde os dados ficam armazenados |

> 💡 **Dica:** Durante a instalação do Python, marque a opção **"Add Python to PATH"**.
> Consulte o arquivo [INSTALL_WINDOWS.md](INSTALL_WINDOWS.md) para um guia detalhado com imagens descritas.

---

## 🚀 Instalação em 3 passos

### Passo 1 — Instale Python e MySQL
Baixe e instale os dois programas da tabela acima.
Consulte [INSTALL_WINDOWS.md](INSTALL_WINDOWS.md) se precisar de ajuda.

### Passo 2 — Execute o instalador
Clique duas vezes no arquivo **`instalar.bat`**.

Ele vai:
- Criar um ambiente Python isolado
- Instalar todas as dependências automaticamente
- Criar o arquivo `config.yaml` para você configurar

### Passo 3 — Configure o banco de dados
Abra o arquivo **`config.yaml`** (com o Bloco de Notas) e preencha:

```yaml
banco:
  usuario: root          # Seu usuário do MySQL
  senha: "sua_senha"     # Sua senha do MySQL
  nome: saidjur          # Nome que será dado ao banco
```

> ✅ Senhas com caracteres especiais (`#`, `@`, `$`, `!` e aspas escapadas como `\"`)
> funcionam normalmente quando informadas entre aspas no `config.yaml`.

---

## 📂 Importando seu arquivo `.sql`

> ⚠️ Esta etapa pode levar **várias horas** para arquivos grandes (50 GB).
> Seu computador precisa ter pelo menos **100 GB livres em disco**.

**Passo a passo:**

1. Copie seu arquivo `.sql` para a pasta **`dados\`** do programa
2. Clique duas vezes em **`importar.bat`**
3. Quando perguntado, confirme com **S** e pressione Enter
4. Aguarde a barra de progresso concluir ☕

O programa mostrará:
- Quanto já foi carregado (ex: "Lido: 12 GB de 50 GB")
- A velocidade de importação
- O tempo restante estimado

---

## 🖥️ Abrindo o visualizador

1. Clique duas vezes em **`iniciar.bat`**
2. O navegador abre automaticamente em `http://127.0.0.1:8000`
3. Para encerrar, feche a janela do terminal

---

## 📖 Como usar o visualizador

### Busca global
Digite qualquer palavra na **barra de pesquisa no topo** (ex: "João Silva")
e clique em **Buscar**. O sistema vai procurar em **todas as tabelas e colunas** de uma só vez.

### Navegar por tabela
No menu **à esquerda**, clique no nome de qualquer tabela para ver seus dados.
O número ao lado mostra a quantidade de registros.

### Ordenar
Clique no **nome de uma coluna** para ordenar os dados por ela.
Clique de novo para inverter a ordem (▲ crescente / ▼ decrescente).

### Filtrar por coluna
Clique no ícone **🔽** ao lado do nome da coluna para abrir o menu de filtro:
- **Contém** — encontra registros que contenham o texto
- **É igual a** — valor exato
- **Começa com** — ex: "João" encontra "João Silva", "Joãozinho"...
- **Maior que / Menor que** — para números e datas

### Exportar para Excel ou CSV
Clique em **📥 Exportar Excel** ou **📥 Exportar CSV** no topo direito da tabela.
Os filtros aplicados são respeitados na exportação.

---

## 🌐 Compartilhando com colegas da rede

Por padrão, o programa só funciona no seu computador. Para liberar para outros
computadores da mesma rede:

**1. Edite o `config.yaml`:**
```yaml
servidor:
  host: 0.0.0.0   # Mude de 127.0.0.1 para 0.0.0.0
```

**2. Libere a porta no Firewall do Windows** (abra o PowerShell como Administrador):
```powershell
New-NetFirewallRule -DisplayName "Visualizador SaidJur" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```

**3. Descubra seu IP:**
```
ipconfig
```
Procure por **"Endereço IPv4"** (ex: `192.168.1.100`).

**4. Seus colegas acessam:** `http://192.168.1.100:8000`

---

## ⚡ Dicas para importação mais rápida (opcional)

Antes de importar, você pode otimizar o MySQL editando o arquivo `my.ini`
(geralmente em `C:\ProgramData\MySQL\MySQL Server 8.0\`):

```ini
[mysqld]
innodb_buffer_pool_size = 4G
innodb_log_file_size = 1G
innodb_flush_log_at_trx_commit = 2
unique_checks = 0
foreign_key_checks = 0
```

Reinicie o MySQL após salvar. Essas configurações podem **reduzir o tempo de
importação pela metade** em arquivos grandes.

---

## ❓ Perguntas frequentes

**Vai travar meu computador?**
Não. O programa lê os dados aos poucos (nunca mais de 500 registros por vez),
então não sobrecarrega a memória do computador.

**Quanto tempo demora a importação?**
Entre 2 e 12 horas, dependendo do tamanho do arquivo e do seu computador.
Um arquivo de 50 GB pode levar de 3 a 6 horas num PC moderno.

**Posso fechar a janela durante a importação?**
Não. Se fechar, a importação será interrompida e você terá que começar do zero.
Mantenha a janela aberta e minimize-a se precisar usar o computador.

**Posso usar o visualizador enquanto importa?**
Sim, mas o computador vai ficar mais lento. Recomendamos aguardar a importação
concluir antes de usar o visualizador.

**O programa acessa a internet?**
Não. Tudo roda localmente no seu computador. As únicas conexões externas são
para carregar o visual da interface (Tailwind CSS e Alpine.js via CDN na primeira abertura).

---

## 🔧 Problemas comuns

### ❌ `'mysql' não é reconhecido como um comando interno`
O MySQL não está no PATH do Windows.

**Solução:**
1. Abra "Editar variáveis de ambiente do sistema" (pesquise no menu Iniciar)
2. Clique em "Variáveis de Ambiente..."
3. Em "Variáveis do sistema", selecione "Path" e clique em "Editar"
4. Clique em "Novo" e adicione: `C:\Program Files\MySQL\MySQL Server 8.0\bin`
5. Clique OK em todas as janelas e feche o terminal

### ❌ `Acesso negado` ou `Access denied`
A senha do MySQL está incorreta.

**Solução:** Abra `config.yaml` e verifique se a senha está correta no campo `senha:`.

### ❌ `Porta 8000 em uso`
Outro programa já está usando a porta 8000.

**Solução:** Edite `config.yaml` e mude `porta: 8000` para outro número (ex: `8080`).

### ❌ `Não foi possível conectar ao banco de dados`
O MySQL não está rodando.

**Solução:** Abra o "MySQL Workbench" ou os "Serviços do Windows" e verifique se
o serviço "MySQL80" está iniciado.

---

## 📁 Estrutura dos arquivos

```
├── instalar.bat        ← Execute primeiro
├── importar.bat        ← Para importar o arquivo .sql
├── iniciar.bat         ← Para abrir o visualizador
├── config.yaml         ← Suas configurações (criado pelo instalar.bat)
├── dados/              ← Coloque aqui o arquivo .sql
└── logs/               ← Registros de tudo que aconteceu
```

---

*Feito com ❤️ para facilitar o acesso aos dados do SaidJur.*
