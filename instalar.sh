#!/usr/bin/env bash
# Instalador do Monitor SMR para servidores Ubuntu (ex.: Oracle Cloud Always Free).
# Uso (no servidor):
#   curl -fsSL https://raw.githubusercontent.com/heytorhelanpsi-bot/Claude-Projects/monitor-smr/instalar.sh | bash
# Rodar de novo atualiza o programa e mantém as configurações.
# Para refazer as configurações (senha, token...):  bash ~/monitor-smr/instalar.sh --reconfigurar
set -euo pipefail

main() {
REPO="${MONITOR_REPO:-https://github.com/heytorhelanpsi-bot/Claude-Projects.git}"
BRANCH="monitor-smr"
DIR="$HOME/monitor-smr"
SERVICE="monitor-smr"

verde() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
erro() { printf '\n\033[1;31mERRO: %s\033[0m\n' "$*"; exit 1; }

perguntar() {  # perguntar VAR "texto" [secreto]
  local var="$1" texto="$2" valor=""
  while [ -z "$valor" ]; do
    if [ "${3:-}" = "secreto" ]; then
      read -r -s -p "$texto: " valor < /dev/tty; echo
    else
      read -r -p "$texto: " valor < /dev/tty
    fi
    valor="$(printf '%s' "$valor" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [ -z "$valor" ] && echo "   (não pode ficar vazio)"
  done
  printf -v "$var" '%s' "$valor"
}

trap 'erro "a instalação parou na linha $LINENO. Copie as mensagens acima e envie para o Claude."' ERR

[ "$(id -u)" -eq 0 ] && erro "rode como usuário normal (ex.: ubuntu), não como root."
command -v apt-get >/dev/null || erro "este instalador é para Ubuntu/Debian."

verde "1/6 Instalando programas básicos (pode levar alguns minutos)"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git python3-venv python3-pip curl >/dev/null

verde "2/6 Conferindo memória"
MEM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
if [ "$MEM_MB" -lt 2000 ] && ! swapon --show | grep -q .; then
  echo "Servidor com ${MEM_MB} MB de RAM: criando 2 GB de memória extra (swap)."
  sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
  sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
else
  echo "Memória ok."
fi

verde "3/6 Baixando o programa"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch -q origin "$BRANCH" && git -C "$DIR" checkout -q "$BRANCH" && git -C "$DIR" reset -q --hard "origin/$BRANCH"
else
  git clone -q -b "$BRANCH" "$REPO" "$DIR"
fi
cd "$DIR"

verde "4/6 Instalando o navegador interno (pode levar 5 minutos)"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/playwright install chromium >/dev/null
sudo "$DIR/.venv/bin/playwright" install-deps chromium >/dev/null

verde "5/6 Configurações"
if [ ! -f .env ] || [ "${1:-}" = "--reconfigurar" ]; then
  echo "Responda as perguntas abaixo. A senha não aparece enquanto você digita (é normal)."
  perguntar SMR_USER "Usuário do SMR"
  perguntar SMR_PASSWORD "Senha do SMR" secreto
  perguntar TG_TOKEN "Token do bot do Telegram (passo 1 do guia)"
  perguntar TG_CHAT "Chat ID do Telegram (passo 2 do guia; vários separados por vírgula)"
  umask 077
  cp .env.example .env
  # valores passados por variáveis de ambiente (não aparecem na lista de processos)
  SMR_USER="$SMR_USER" SMR_PASSWORD="$SMR_PASSWORD" TG_TOKEN="$TG_TOKEN" TG_CHAT="$TG_CHAT" python3 - <<'PY'
import os, re
def q(v): return "'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'"
vals = {"SMR_USER": os.environ["SMR_USER"], "SMR_PASSWORD": os.environ["SMR_PASSWORD"],
        "TELEGRAM_BOT_TOKEN": os.environ["TG_TOKEN"], "TELEGRAM_CHAT_ID": os.environ["TG_CHAT"].replace(" ", "")}
s = open(".env").read()
for k, v in vals.items():
    s = re.sub(rf"(?m)^{k}=.*$", lambda m, k=k, v=v: f"{k}={q(v)}", s)
open(".env", "w").write(s)
PY
  chmod 600 .env
  echo "Configurações salvas em $DIR/.env"
else
  echo "Configurações já existem (para refazer: bash $DIR/instalar.sh --reconfigurar)."
fi

verde "6/6 Ligando o monitor (liga sozinho quando o servidor reiniciar)"
sudo tee /etc/systemd/system/$SERVICE.service >/dev/null <<EOF
[Unit]
Description=Monitor SMR (alertas no Telegram)
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python -m smr_monitor
Restart=always
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo tee /usr/local/bin/monitor-smr >/dev/null <<EOF
#!/usr/bin/env bash
case "\${1:-}" in
  status)      systemctl status $SERVICE --no-pager ;;
  logs)        journalctl -u $SERVICE -n 50 --no-pager ;;
  acompanhar)  journalctl -u $SERVICE -f ;;
  reiniciar)   sudo systemctl restart $SERVICE && echo "Reiniciado." ;;
  parar)       sudo systemctl stop $SERVICE && echo "Parado (para religar: monitor-smr reiniciar)." ;;
  atualizar)   bash $DIR/instalar.sh ;;
  configurar)  bash $DIR/instalar.sh --reconfigurar ;;
  testar)      cd $DIR && .venv/bin/python -m smr_monitor --test --debug ;;
  *) echo "Uso: monitor-smr status | logs | acompanhar | reiniciar | parar | atualizar | configurar | testar" ;;
esac
EOF
sudo chmod +x /usr/local/bin/monitor-smr

sudo systemctl daemon-reload
sudo systemctl enable -q $SERVICE
sudo systemctl restart $SERVICE
sleep 20

if systemctl is-active -q $SERVICE; then
  verde "PRONTO! O monitor está rodando."
  echo "Em até 1 minuto devem chegar mensagens no seu Telegram."
  echo
  echo "Últimas linhas do registro:"
  journalctl -u $SERVICE -n 15 --no-pager -o cat || true
  echo
  echo "Comandos úteis neste servidor: monitor-smr status | logs | reiniciar | atualizar | configurar"
else
  journalctl -u $SERVICE -n 40 --no-pager -o cat || true
  erro "o monitor não ligou. Copie as linhas acima e envie para o Claude."
fi
}

main "$@" < /dev/null
