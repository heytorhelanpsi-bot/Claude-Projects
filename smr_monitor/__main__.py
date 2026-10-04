"""Ponto de entrada: python -m smr_monitor [--once | --test | --debug]"""

import argparse
import html
import json
import signal
import sys
import time
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from . import commands, rules, telegram
from .config import POINTS, Settings
from .parser import parse_readings
from .scraper import fetch_text


def load_state(cfg: Settings) -> dict:
    try:
        return json.loads(cfg.state_file.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(cfg: Settings, state: dict):
    cfg.state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = cfg.state_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(cfg.state_file)


def now_local(cfg: Settings) -> datetime:
    # Horário local sem fuso, para comparar com os horários exibidos pelo SMR
    return datetime.now(ZoneInfo(cfg.timezone)).replace(tzinfo=None, microsecond=0)


def check_once(cfg: Settings, state: dict, debug: bool = False):
    now = now_local(cfg)
    try:
        text = fetch_text(cfg, debug=debug)
        readings = parse_readings(text, POINTS)
        if not readings:
            trecho = " | ".join(line.strip() for line in text.splitlines() if line.strip())[:400]
            raise RuntimeError(f"nenhum dos pontos monitorados foi encontrado na página. Página lida: {trecho}")
    except Exception as e:  # noqa: BLE001 - qualquer falha vira aviso
        traceback.print_exc()
        msgs = rules.register_failure(f"{type(e).__name__}: {e}", state, cfg)
    else:
        for r in readings.values():
            print(f"[{now:%H:%M:%S}] {r.key}: {r.value} ({r.timestamp}){' SEM COMUNICAÇÃO' if r.no_comm else ''}")
        msgs = rules.evaluate(readings, now, state, cfg)

    for msg in msgs:
        telegram.send(cfg, msg)
    save_state(cfg, state)


def status_report(cfg: Settings, state: dict, debug: bool = False) -> str:
    """Lê o SMR agora e monta um relatório (sem disparar alertas)."""
    try:
        readings = parse_readings(fetch_text(cfg, debug=debug), POINTS)
        body = rules.build_report(readings, now_local(cfg), state, cfg)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        body = f"❌ Não foi possível ler o SMR agora.\nErro: <code>{html.escape(str(e)[:500])}</code>"
    return f"{body}\n\n{commands.situation(state)}"


def poll_commands(cfg: Settings, state: dict, wait: float) -> dict:
    """Espera comandos do Telegram por até `wait` segundos. Retorna as ações pedidas."""
    actions = {}
    if not cfg.telegram_token:
        time.sleep(wait)
        return actions
    try:
        updates = telegram.get_updates(cfg, state.get("tg_offset"), timeout=max(1, int(wait)))
    except Exception as e:  # noqa: BLE001 - rede instável não pode derrubar o monitor
        print(f"[telegram] falha ao ler comandos: {e}")
        time.sleep(min(wait, 10))
        return actions
    for upd in updates:
        state["tg_offset"] = upd["update_id"] + 1
        act = commands.handle_update(upd, cfg, state)
        actions.update({k: v for k, v in act.items() if v})
    if updates:
        save_state(cfg, state)
    return actions


def main():
    ap = argparse.ArgumentParser(description="Supervisão do SMR/DESO com avisos no Telegram")
    ap.add_argument("--once", action="store_true", help="faz uma única verificação e sai")
    ap.add_argument("--test", action="store_true", help="lê o SMR e envia um relatório de teste ao Telegram")
    ap.add_argument("--debug", action="store_true", help="salva captura/HTML/texto da página em data/debug")
    args = ap.parse_args()

    cfg = Settings()
    state = load_state(cfg)

    if args.test:
        msg = "🧪 Teste do monitor SMR\n" + status_report(cfg, state, debug=args.debug)
        print(msg)
        sys.exit(0 if telegram.send(cfg, msg) else 1)

    if args.once:
        check_once(cfg, state, debug=args.debug)
        return

    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    if cfg.telegram_token:
        telegram.set_commands(cfg, commands.COMMANDS)
    if state.get("enabled", True):
        telegram.send(
            cfg,
            f"▶️ Monitor SMR iniciado. Verificação a cada {rules.fmt(cfg.check_interval_min, 0)} min, "
            f"relatório a cada {rules.fmt(cfg.report_interval_min, 0)} min.\n"
            f"{commands.situation(state)}\nEnvie /ajuda para ver os comandos.",
        )
    else:
        telegram.send(cfg, "🔴 Monitor SMR reiniciado, mas está DESLIGADO. Envie /ligar para religar.")

    interval = cfg.check_interval_min * 60
    next_check = time.monotonic()
    while running:
        if state.get("enabled", True) and time.monotonic() >= next_check:
            check_once(cfg, state, debug=args.debug)
            next_check = time.monotonic() + interval

        wait = min(25, max(1, next_check - time.monotonic())) if state.get("enabled", True) else 25
        actions = poll_commands(cfg, state, wait)
        if "status_to" in actions:
            telegram.send_to(cfg, actions["status_to"], status_report(cfg, state))
        if actions.get("check_now"):
            next_check = time.monotonic()


if __name__ == "__main__":
    main()
