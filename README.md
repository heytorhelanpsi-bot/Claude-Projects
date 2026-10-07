# Monitor SMR – DESO (R0 Sobrado)

Agente que entra no **SMR** (http://smr.deso-se.com.br) com o seu login, lê os pontos abaixo
e envia avisos pelo **Telegram**.

| Ponto | O que é monitorado |
|---|---|
| **R0 Sobrado (nível)** | níveis críticos, subida rápida, cada metro alcançado |
| **R0-R2 (vazão)** | vazão abaixo de **1.900 m³/h** (faixa normal 1.900 a 2.100) + "sem comunicação" |
| **R0-R8 (macro)** | vazão abaixo de **790 m³/h** (faixa normal 790 a 910) + "sem comunicação" |

## Regras de aviso

| Situação | Mensagem |
|---|---|
| Nível **≤ 1,20 m** ou **≥ 3,95 m** | 🚨 alerta na hora, repetido a cada 20 min enquanto durar, e ✅ quando normalizar |
| Nível sobe **0,20 m ou mais em menos de 30 min** | 📈 subida rápida (no máximo 1 aviso a cada 30 min) |
| Nível passa por um **metro inteiro** (1 m, 2 m, 3 m…) | ⬆️ alcançou / ⬇️ desceu abaixo |
| Vazão **R0-R2 < 1.900 m³/h** ou **R0-R8 < 790 m³/h** | 🚨 alerta com a vazão atual, repetido a cada 20 min enquanto durar, e ✅ quando voltar à faixa |
| A cada **20 min** | 📊 relatório com o nível e as vazões atuais (vazão fora da faixa vem marcada com 🚨) |
| Ponto "sem comunicação" ou parado há mais de 60 min | ⚠️ aviso (uma vez) e ✅ quando voltar |
| SMR fora do ar ou login recusado (2 tentativas seguidas) | ❌ aviso e ✅ quando voltar |

O monitor pode ser **ligado e desligado pelo Telegram** (veja "Comandos no Telegram").
O agente verifica o SMR **a cada 20 minutos** (alertas críticos saem na mesma leitura em que são detectados) e
manda o relatório completo a cada 20 minutos. Todos os valores podem ser alterados no arquivo `.env`
(veja `.env.example`). Vazão acima da faixa não gera alerta. Para alertar também vazão alta, preencha `R0_R2_VAZAO_MAX` /
`R0_R8_VAZAO_MAX`. Uma margem de 0,05 m no nível e de 1% na vazão (histerese) evita que o mesmo aviso fique se repetindo
quando o nível oscila em cima de um limite.

## 1. Criar o bot do Telegram (5 minutos)

1. No Telegram, abra uma conversa com **@BotFather** e envie `/newbot`. Escolha um nome.
   Ele devolve um **token** parecido com `123456:ABC-DEF...` → é o `TELEGRAM_BOT_TOKEN`.
2. Abra a conversa com o seu bot novo e envie qualquer mensagem (ex.: `oi`).
   Para avisar um grupo, adicione o bot ao grupo e envie uma mensagem lá.
3. No navegador, abra `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates` e procure
   `"chat":{"id": ...}`. Esse número é o `TELEGRAM_CHAT_ID` (de grupo começa com `-`).
   Pode colocar vários, separados por vírgula.

## 2. Comandos no Telegram

Qualquer pessoa cadastrada em `TELEGRAM_CHAT_ID` pode controlar o monitor pelo próprio chat do bot
(os comandos também aparecem no botão "/" do Telegram):

| Comando | O que faz |
|---|---|
| `/desligar` | Desliga tudo: o monitor para de acessar o SMR e não manda nenhum aviso |
| `/ligar` | Religa o monitor e manda um relatório na hora |
| `/status` | Lê o SMR agora e mostra os valores (funciona mesmo desligado) |
| `/relatorios_off` | Pausa só os relatórios de 20 min; os alertas continuam |
| `/relatorios_on` | Volta a mandar os relatórios de 20 min |
| `/ajuda` | Lista os comandos e mostra a situação atual |

A escolha (ligado/desligado, relatórios pausados) fica salva e continua valendo mesmo se o servidor
reiniciar. Mensagens de chats que não estão em `TELEGRAM_CHAT_ID` são ignoradas.

## 3. Colocar na nuvem de graça (Oracle Cloud Always Free)

O monitor roda numa máquina **gratuita para sempre** do Oracle Cloud (VM.Standard.E2.1.Micro ou
Ampere A1, região São Paulo). O passo a passo para leigos está no guia
"Guia passo a passo – Monitor SMR no Telegram". Resumo:

1. Criar a conta no Oracle Cloud (região **Brazil East – São Paulo**) e uma instância **Ubuntu** com
   formato *Always Free*.
2. Converter a conta para **Pay As You Go**. Continua gratuito dentro dos limites Always Free, mas o
   Oracle deixa de desligar máquinas gratuitas "ociosas" (e este monitor usa pouquíssima CPU).
   Por segurança, crie um orçamento (*Budget*) de US$ 1 com alerta por e-mail.
3. Abrir o terminal da instância pelo navegador (Cloud Shell → SSH) e rodar **um comando**:

```bash
curl -fsSL https://raw.githubusercontent.com/heytorhelanpsi-bot/Claude-Projects/monitor-smr/instalar.sh | bash
```

O instalador (`instalar.sh`) instala tudo, cria memória extra (swap) se o servidor tiver só 1 GB, pergunta
usuário/senha do SMR e os dados do Telegram (gravados só no servidor, em `~/monitor-smr/.env`, com
permissão restrita) e deixa o monitor como serviço que liga sozinho quando o servidor reinicia.

Depois, no servidor:

| Comando | Para quê |
|---|---|
| `monitor-smr status` | Ver se está rodando |
| `monitor-smr logs` | Ver as últimas linhas do registro |
| `monitor-smr atualizar` | Baixar a versão mais nova do programa |
| `monitor-smr configurar` | Trocar senha do SMR, token ou chat ID |
| `monitor-smr testar` | Ler o SMR e mandar um relatório de teste (salva capturas em `data/debug`) |
| `monitor-smr reiniciar` | Reiniciar o monitor |

Para mudar limites (ex.: `R0_R2_VAZAO_MIN`), edite `~/monitor-smr/.env` (`nano ~/monitor-smr/.env`) e
rode `monitor-smr reiniciar`.

> **Outras opções:** qualquer servidor Linux com Docker serve (`docker compose up -d --build`, usando
> o `Dockerfile` e o `docker-compose.yml`). O Google Cloud e2-micro também funciona, mas desde 2024 o
> IP público custa cerca de US$ 3,65/mês ([preços](https://cloud.google.com/vpc/pricing)).

## Se o agente não encontrar os valores

O SMR não pôde ser acessado durante o desenvolvimento, então a leitura foi feita a partir das
capturas de tela do sistema. Se o teste reclamar de login ou de "ponto não encontrado":

1. Rode `monitor-smr testar` e veja os arquivos em `~/monitor-smr/data/debug/` (`.png`, `.html` e `.txt` da página).
2. Se o formulário de login não for reconhecido, informe os seletores CSS no `.env`
   (`SMR_USER_SELECTOR`, `SMR_PASSWORD_SELECTOR`, `SMR_SUBMIT_SELECTOR`).
3. Se os cartões estiverem em outra tela depois do login, coloque a URL em `SMR_PAGES`.

## Rodar sem Docker (Windows/Linux/Mac)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install --with-deps chromium
python -m smr_monitor --test       # teste único
python -m smr_monitor              # monitoramento contínuo
```

## Testes

```bash
pip install pytest
python -m pytest -q
```

Os testes conferem a leitura dos cartões (com os textos das capturas de tela), todas as regras de
aviso, os comandos do Telegram e o monitor completo rodando contra um SMR e um Telegram simulados
(`tests/fake_smr.py`, `tests/fake_telegram.py`).
