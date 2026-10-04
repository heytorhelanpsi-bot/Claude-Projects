"""Ponto de entrada: python -m smr_monitor [--once | --test | --debug]"""

import argparse
import json
import signal
import sys
import time
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from . import rules, telegram
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
            raise RuntimeError("nenhum dos pontos monitorados foi encontrado na página")
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


def main():
    ap = argparse.ArgumentParser(description="Supervisão do SMR/DESO com avisos no Telegram")
    ap.add_argument("--once", action="store_true", help="faz uma única verificação e sai")
    ap.add_argument("--test", action="store_true", help="lê o SMR e envia um relatório de teste ao Telegram")
    ap.add_argument("--debug", action="store_true", help="salva captura/HTML/texto da página em data/debug")
    args = ap.parse_args()

    cfg = Settings()
    state = load_state(cfg)

    if args.test:
        readings = parse_readings(fetch_text(cfg, debug=args.debug), POINTS)
        msg = "🧪 Teste do monitor SMR\n" + rules.build_report(readings, now_local(cfg), state, cfg)
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

    telegram.send(
        cfg,
        f"▶️ Monitor SMR iniciado. Verificação a cada {rules.fmt(cfg.check_interval_min, 0)} min, "
        f"relatório a cada {rules.fmt(cfg.report_interval_min, 0)} min.",
    )
    interval = cfg.check_interval_min * 60
    while running:
        started = time.monotonic()
        check_once(cfg, state, debug=args.debug)
        while running and time.monotonic() - started < interval:
            time.sleep(1)


if __name__ == "__main__":
    main()
