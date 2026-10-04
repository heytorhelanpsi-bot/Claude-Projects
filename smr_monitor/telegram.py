"""Envio de mensagens pelo Telegram."""

import time

import requests

from .config import Settings


def send(cfg: Settings, text: str) -> bool:
    if not cfg.telegram_token or not cfg.telegram_chat_ids:
        print(f"[telegram não configurado] {text}")
        return False
    ok = True
    url = f"https://api.telegram.org/bot{cfg.telegram_token}/sendMessage"
    for chat_id in cfg.telegram_chat_ids:
        for attempt in range(3):
            try:
                r = requests.post(
                    url,
                    json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                          "disable_web_page_preview": True},
                    timeout=20,
                )
                if r.ok:
                    break
                print(f"[telegram] erro {r.status_code}: {r.text[:200]}")
            except requests.RequestException as e:
                print(f"[telegram] falha de rede: {e}")
            time.sleep(2 ** attempt)
        else:
            ok = False
    return ok
