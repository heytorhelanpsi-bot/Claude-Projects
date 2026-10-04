# Monitor SMR – DESO (R0 Sobrado)

Agente que entra no **SMR** (http://smr.deso-se.com.br) com o seu login, lê os pontos abaixo
e envia avisos pelo **Telegram**.

| Ponto | O que é monitorado |
|---|---|
| **R0 Sobrado (nível)** | níveis críticos, subida rápida, cada metro alcançado |
| **R0-R2 (vazão)** | valor no relatório + aviso de "sem comunicação" |
| **R0-R8 (macro)** | valor no relatório + aviso de "sem comunicação" |

## Regras de aviso

| Situação | Mensagem |
|---|---|
| Nível **≤ 1,20 m** ou **≥ 3,95 m** | 🚨 alerta na hora, repetido a cada 15 min enquanto durar, e ✅ quando normalizar |
| Nível sobe **0,20 m ou mais em menos de 30 min** | 📈 subida rápida (no máximo 1 aviso a cada 30 min) |
| Nível passa por um **metro inteiro** (1 m, 2 m, 3 m…) | ⬆️ alcançou / ⬇️ desceu abaixo |
| A cada **15 min** | 📊 relatório com os 3 pontos e a tendência do nível |
| Ponto "sem comunicação" ou parado há mais de 60 min | ⚠️ aviso (uma vez) e ✅ quando voltar |
| SMR fora do ar ou login recusado (3 tentativas seguidas) | ❌ aviso e ✅ quando voltar |

O agente verifica o SMR **a cada 5 minutos**, para que um nível crítico seja avisado logo, e
manda o relatório completo a cada 15 minutos. Todos os valores podem ser alterados no arquivo `.env`
(veja `.env.example`). Uma margem de 0,05 m (histerese) evita que o mesmo aviso fique se repetindo
quando o nível oscila em cima de um limite.

## 1. Criar o bot do Telegram (5 minutos)

1. No Telegram, abra uma conversa com **@BotFather** e envie `/newbot`. Escolha um nome.
   Ele devolve um **token** parecido com `123456:ABC-DEF...` → é o `TELEGRAM_BOT_TOKEN`.
2. Abra a conversa com o seu bot novo e envie qualquer mensagem (ex.: `oi`).
   Para avisar um grupo, adicione o bot ao grupo e envie uma mensagem lá.
3. No navegador, abra `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates` e procure
   `"chat":{"id": ...}`. Esse número é o `TELEGRAM_CHAT_ID` (de grupo começa com `-`).
   Pode colocar vários, separados por vírgula.

## 2. Configurar

```bash
cp .env.example .env
nano .env          # preencha SMR_USER, SMR_PASSWORD, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

O `.env` fica só no servidor e está no `.gitignore`, então a senha nunca vai para o GitHub.

## 3. Colocar na nuvem

O agente precisa ficar ligado 24 h. Qualquer servidor Linux pequeno com Docker serve, por exemplo:

- **Google Cloud – e2-micro** (faixa gratuita "Always Free", regiões dos EUA);
- **Oracle Cloud – Always Free**;
- uma VPS barata (Hostinger, DigitalOcean, Contabo…, de US$ 4 a 6 por mês).

No servidor:

```bash
# instalar Docker (Ubuntu/Debian)
curl -fsSL https://get.docker.com | sh

git clone https://github.com/heytorhelanpsi-bot/Claude-Projects.git monitor-smr
cd monitor-smr
cp .env.example .env && nano .env

# teste: lê o SMR, salva captura da página em data/debug e manda um relatório ao Telegram
docker compose run --rm smr-monitor python -m smr_monitor --test --debug

# ligar de vez (reinicia sozinho se o servidor reiniciar)
docker compose up -d --build
docker compose logs -f        # acompanhar
```

Para atualizar depois de mudanças no código: `git pull && docker compose up -d --build`.

> **Por que não GitHub Actions?** O repositório é privado. Rodar a cada 5 ou 15 minutos gastaria
> de 3.000 a 9.000 minutos por mês, acima dos 2.000 gratuitos, e os agendamentos do Actions
> costumam atrasar, o que é ruim para alertas críticos.

## Se o agente não encontrar os valores

O SMR não pôde ser acessado durante o desenvolvimento, então a leitura foi feita a partir das
capturas de tela do sistema. Se o teste reclamar de login ou de "ponto não encontrado":

1. Rode o teste com `--debug` e veja os arquivos em `data/debug/` (`.png`, `.html` e `.txt` da página).
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
aviso e o login com navegador num SMR simulado (`tests/fake_smr.py`).
