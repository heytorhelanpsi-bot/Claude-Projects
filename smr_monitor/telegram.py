"""Envio de mensagens e leitura de comandos pelo Telegram."""

import os
import time

import requests

from .config import Settings

API = os.getenv("TELEGRAM_API", "https://api.telegram.org") + "/bot{token}/{method}"


def _call(cfg: Settings, method: str, payload: dict, timeout: float = 20):
    r = requests.post(API.format(token=cfg.telegram_token, method=method), json=payload, timeout=timeout)
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if not r.ok or not data.get("ok"):
        raise RuntimeError(f"Telegram {method} erro {r.status_code}: {r.text[:200]}")
    return data["result"]


def send_to(cfg: Settings, chat_id, text: str) -> bool:
    if not cfg.telegram_token:
        print(f"[telegram não configurado] {text}")
        return False
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    for attempt in range(3):
        try:
            _call(cfg, "sendMessage", payload)
            return True
        except (requests.RequestException, RuntimeError, ValueError) as e:
            print(f"[telegram] falha ao enviar: {e}")
            time.sleep(2 ** attempt)
    return False


def send(cfg: Settings, text: str) -> bool:
    """Envia para todos os chats configurados."""
    if not cfg.telegram_token or not cfg.telegram_chat_ids:
        print(f"[telegram não configurado] {text}")
        return False
    return all([send_to(cfg, chat_id, text) for chat_id in cfg.telegram_chat_ids])


def get_updates(cfg: Settings, offset, timeout: int) -> list:
    """Espera até `timeout` segundos por mensagens novas (long polling)."""
    payload = {"timeout": timeout, "allowed_updates": ["message"]}
    if offset is not None:
        payload["offset"] = offset
    return _call(cfg, "getUpdates", payload, timeout=timeout + 15)


def set_commands(cfg: Settings, commands: list):
    """Cadastra o menu de comandos que aparece no botão "/" do Telegram."""
    try:
        _call(cfg, "setMyCommands",
              {"commands": [{"command": c, "description": d} for c, d in commands]})
    except (requests.RequestException, RuntimeError, ValueError) as e:
        print(f"[telegram] não foi possível cadastrar o menu de comandos: {e}")
