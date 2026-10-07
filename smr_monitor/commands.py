"""Comandos do Telegram para ligar/desligar o monitor e pausar relatórios."""

from . import telegram
from .config import Settings

COMMANDS = [
    ("ligar", "Liga o monitoramento e os alertas"),
    ("desligar", "Desliga o monitoramento (nenhum aviso)"),
    ("status", "Lê o SMR agora e mostra os valores"),
    ("relatorios_off", "Pausa os relatórios periódicos (alertas continuam)"),
    ("relatorios_on", "Volta a enviar os relatórios periódicos"),
    ("ajuda", "Mostra os comandos"),
]

ALIASES = {"start": "ajuda", "help": "ajuda", "comandos": "ajuda", "parar": "desligar",
           "iniciar": "ligar", "valores": "status"}


def help_text(state: dict) -> str:
    lines = ["🤖 <b>Monitor SMR – comandos</b>"]
    lines += [f"/{c} – {d}" for c, d in COMMANDS]
    lines.append("")
    lines.append(situation(state))
    return "\n".join(lines)


def situation(state: dict) -> str:
    mon = "🟢 LIGADO" if state.get("enabled", True) else "🔴 DESLIGADO"
    rep = "ligados" if state.get("reports", True) else "pausados"
    return f"Situação: monitor {mon} · relatórios periódicos {rep}"


def parse(text: str):
    """'/Desligar@meu_bot agora' -> 'desligar'."""
    if not text:
        return None
    word = text.strip().split()[0].lstrip("/").split("@")[0].lower()
    word = ALIASES.get(word, word)
    return word if word in {c for c, _ in COMMANDS} else None


def handle_update(update: dict, cfg: Settings, state: dict) -> dict:
    """Processa uma mensagem recebida. Retorna ações para o laço principal:
    {"check_now": True} para verificar o SMR já, {"status_to": chat_id} para mandar um /status."""
    msg = update.get("message") or {}
    chat_id = str((msg.get("chat") or {}).get("id", ""))
    if not chat_id:
        return {}
    if chat_id not in cfg.telegram_chat_ids:
        print(f"[telegram] mensagem ignorada de chat não autorizado: {chat_id}")
        return {}

    cmd = parse(msg.get("text", ""))
    who = (msg.get("from") or {}).get("first_name", "alguém")

    if cmd is None:
        if msg.get("chat", {}).get("type") == "private":
            telegram.send_to(cfg, chat_id, "Não entendi. Envie /ajuda para ver os comandos.")
        return {}

    if cmd == "ajuda":
        telegram.send_to(cfg, chat_id, help_text(state))
    elif cmd == "status":
        return {"status_to": chat_id}
    elif cmd == "ligar":
        if state.get("enabled", True):
            telegram.send_to(cfg, chat_id, "O monitor já está ligado. 🟢")
            return {}
        state["enabled"] = True
        state["last_report"] = None  # manda um relatório logo na primeira leitura
        state["fail_count"] = 0
        telegram.send(cfg, f"▶️ Monitor <b>LIGADO</b> por {who}. Lendo o SMR agora…")
        return {"check_now": True}
    elif cmd == "desligar":
        if not state.get("enabled", True):
            telegram.send_to(cfg, chat_id, "O monitor já está desligado. 🔴 Envie /ligar para religar.")
            return {}
        state["enabled"] = False
        telegram.send(cfg, f"⏸ Monitor <b>DESLIGADO</b> por {who}.\n"
                           "Nenhum acesso ao SMR e nenhum alerta até alguém enviar /ligar.")
    elif cmd == "relatorios_off":
        state["reports"] = False
        telegram.send(cfg, f"🔕 Relatórios periódicos <b>pausados</b> por {who}.\n"
                           "Os alertas (nível crítico, subida rápida, vazão baixa) continuam. "
                           "Envie /relatorios_on para voltar.")
    elif cmd == "relatorios_on":
        state["reports"] = True
        state["last_report"] = None
        telegram.send(cfg, f"🔔 Relatórios periódicos <b>religados</b> por {who}.")
        return {"check_now": state.get("enabled", True)}
    return {}
