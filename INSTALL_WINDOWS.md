# 🪟 Guia de Instalação no Windows

Este guia explica passo a passo como instalar o **Python** e o **MySQL** no Windows,
com descrição de cada tela dos instaladores.

---

## 1️⃣ Instalando o Python

### Onde baixar
Acesse: **https://www.python.org/downloads/**

Clique no botão amarelo grande **"Download Python 3.x.x"** (a versão mais recente aparece automaticamente).

### Executando o instalador

**Tela inicial do instalador:**
- Você verá duas caixas de seleção na parte inferior:
  - `[ ] Use admin privileges when installing py.exe` — pode deixar marcada
  - `[ ] Add python.exe to PATH` — ⚠️ **MARQUE ESTA OBRIGATORIAMENTE**
- Clique em **"Install Now"** (instalação simplificada — recomendada)

**Aguarde a instalação** (barra de progresso verde).

**Tela final:**
- Aparece "Setup was successful"
- Clique em **"Close"**

### Verificando se deu certo

Abra o **Prompt de Comando** (`cmd`):
- Pressione `Win + R`, digite `cmd` e pressione Enter

Digite e pressione Enter:
```
python --version
```

Deve aparecer algo como: `Python 3.12.3`

Se aparecer esse resultado, o Python está instalado corretamente! ✅

---

## 2️⃣ Instalando o MySQL

### Onde baixar
Acesse: **https://dev.mysql.com/downloads/installer/**

Na página, você verá duas opções:
- `mysql-installer-web-community` (menor, baixa pacotes pela internet)
- `mysql-installer-community` (maior, todos os pacotes incluídos)

Recomendamos a **segunda opção** (maior) para evitar problemas de conexão durante a instalação.

Clique em **"Download"** e depois em **"No thanks, just start my download"** (não precisa criar conta).

### Executando o instalador

**Tela "Choosing a Setup Type":**
- Selecione **"Server only"** (apenas o servidor — é o que precisamos)
- Clique em **"Next"**

**Tela "Check Requirements":**
- Se aparecer algum requisito faltando, clique em **"Execute"** para instalar automaticamente
- Clique em **"Next"**

**Tela "Installation":**
- Clique em **"Execute"** para iniciar a instalação
- Aguarde a barra de progresso
- Clique em **"Next"**

**Tela "Product Configuration":**
- Clique em **"Next"**

**Tela "Type and Networking":**
- Deixe tudo como está (Config Type: Development Computer, Port: 3306)
- Clique em **"Next"**

**Tela "Authentication Method":**
- Selecione **"Use Strong Password Encryption"** (primeira opção)
- Clique em **"Next"**

**Tela "Accounts and Roles" — ⚠️ IMPORTANTE:**
- No campo **"MySQL Root Password"**, crie uma senha forte
- **Anote essa senha!** Você vai precisar dela mais tarde
- Confirme a senha no campo "Repeat Password"
- Clique em **"Next"**

**Tela "Windows Service":**
- Deixe tudo como está (inicia automaticamente com o Windows)
- Clique em **"Next"**

**Tela "Apply Configuration":**
- Clique em **"Execute"**
- Aguarde todos os itens ficarem com ✅ verde
- Clique em **"Finish"**

**Telas restantes:**
- Clique em **"Next"** → **"Finish"** para concluir

### Adicionando o MySQL ao PATH do Windows

Para que o programa de importação funcione, o comando `mysql` precisa ser reconhecido
pelo Windows. Siga estes passos:

**1.** Pressione `Win + R`, digite `sysdm.cpl` e pressione Enter
   - Isso abre "Propriedades do Sistema"

**2.** Clique na aba **"Avançado"**

**3.** Clique no botão **"Variáveis de Ambiente..."** (na parte inferior)

**4.** Na seção **"Variáveis do sistema"** (parte de baixo da janela):
   - Procure a variável chamada **"Path"**
   - Clique nela para selecionar
   - Clique em **"Editar..."**

**5.** Na janela que abrir, clique em **"Novo"**

**6.** Digite o caminho abaixo e pressione Enter:
   ```
   C:\Program Files\MySQL\MySQL Server 8.0\bin
   ```
   > ⚠️ Se você instalou uma versão diferente (ex: 8.4), ajuste o número da versão.

**7.** Clique em **"OK"** em todas as janelas abertas

**8.** Feche e reabra qualquer janela de Prompt de Comando que estava aberta

### Verificando se deu certo

Abra um **novo** Prompt de Comando e digite:
```
mysql --version
```

Deve aparecer algo como: `mysql  Ver 8.0.x ...`

Se aparecer esse resultado, o MySQL está no PATH corretamente! ✅

### Verificando a conexão com o MySQL

Para testar se o MySQL está rodando, digite no Prompt de Comando:
```
mysql -u root -p
```

Quando pedir a senha, digite a senha que você criou durante a instalação e pressione Enter.

Se aparecer `mysql>`, está funcionando! Digite `exit` e pressione Enter para sair.

---

## 3️⃣ Verificando tudo de uma vez

Abra o Prompt de Comando e execute os dois comandos abaixo:

```
python --version
mysql --version
```

Se ambos mostrarem versões (sem mensagens de erro), você está pronto para
seguir o [README.md](README.md) e instalar o Visualizador! 🎉

---

## ❓ Problemas comuns na instalação

### Python não é reconhecido
Se `python --version` mostrar erro, o Python não foi adicionado ao PATH.

**Solução:** Desinstale o Python e reinstale, marcando **"Add Python to PATH"** na
primeira tela.

### MySQL não é reconhecido
Se `mysql --version` mostrar erro, veja a seção **"Adicionando o MySQL ao PATH"** acima.

### Erro ao abrir o instalador do MySQL
Alguns antivírus podem bloquear. Desative temporariamente durante a instalação,
ou clique em "Mais informações" → "Executar assim mesmo" na tela de aviso do Windows.

### Esqueci a senha do MySQL
Se esqueceu a senha definida na instalação, você pode redefini-la:
1. Abra o **MySQL Installer** novamente (está nos programas instalados)
2. Clique em **"Reconfigure"** ao lado do MySQL Server
3. Siga os passos até a tela de senha e defina uma nova

---

*Depois de instalar Python e MySQL, volte ao [README.md](README.md) e continue do Passo 2.*
