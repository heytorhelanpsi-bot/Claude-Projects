"""Ajuda do instalador: confere o token do bot e descobre o Chat ID sozinho.

Uso (o token vem da variável de ambiente TG_TOKEN, para não aparecer na lista de processos):
    python -m smr_monitor.telegram_setup verificar   -> imprime o @usuario do bot (erro se token inválido)
    python -m smr_monitor.telegram_setup descobrir   -> imprime "id<TAB>nome" de quem mandou mensagem ao bot
"""

import os
import sys

import requests

API = os.getenv("TELEGRAM_API", "https://api.telegram.org") + "/bot{token}/{method}"


def call(token, method, **payload):
    r = requests.post(API.format(token=token, method=method), json=payload, timeout=30)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("description", "erro"))
    return data["result"]


def chat_name(chat):
    if chat.get("title"):
        return f"grupo \"{chat['title']}\""
    return " ".join(p for p in (chat.get("first_name"), chat.get("last_name")) if p) or chat.get("username", "?")


def main():
    token = os.environ.get("TG_TOKEN", "").strip()
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if action == "verificar":
            print(call(token, "getMe")["username"])
        elif action == "descobrir":
            updates = call(token, "getUpdates", timeout=0)
            chats = {}
            for upd in updates:
                msg = upd.get("message") or upd.get("my_chat_member") or {}
                chat = msg.get("chat")
                if chat:
                    chats[str(chat["id"])] = chat_name(chat)
            if updates:  # marca as mensagens como lidas, para o monitor não respondê-las depois
                call(token, "getUpdates", offset=updates[-1]["update_id"] + 1, timeout=0)
            for chat_id, name in chats.items():
                print(f"{chat_id}\t{name}")
        else:
            sys.exit(__doc__)
    except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError) as e:
        print(f"erro: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
