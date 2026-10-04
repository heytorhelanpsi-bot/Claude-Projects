"""Roda o monitor completo contra o SMR e o Telegram simulados."""

import os
import subprocess
import sys
import time

from . import fake_smr, fake_telegram


def wait_for(sent, text, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        if any(text in t for _, t in sent):
            return True
        time.sleep(0.3)
    raise AssertionError(f"mensagem com {text!r} não chegou. Recebidas: {[t[:60] for _, t in sent]}")


def test_monitor_completo(tmp_path):
    smr = fake_smr.make_server(level="3,96")
    tg, sent, inbox = fake_telegram.make_server()
    env = dict(os.environ,
               SMR_URL=f"http://127.0.0.1:{smr.server_address[1]}/", SMR_USER="Washington", SMR_PASSWORD="segredo",
               TELEGRAM_API=f"http://127.0.0.1:{tg.server_address[1]}", TELEGRAM_BOT_TOKEN="x",
               TELEGRAM_CHAT_ID="111", STATE_FILE=str(tmp_path / "state.json"), DADO_ATRASADO_MIN="100000",
               INTERVALO_VERIFICACAO_MIN="0.05")
    proc = subprocess.Popen([sys.executable, "-m", "smr_monitor"], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_for(sent, "Monitor SMR iniciado")
        wait_for(sent, "NÍVEL CRÍTICO MÁXIMO")
        wait_for(sent, "Supervisão SMR")

        inbox.put("/desligar")
        wait_for(sent, "DESLIGADO</b> por Washington")
        time.sleep(8)  # desligado: nenhuma mensagem nova (lembrete crítico etc.)
        n = len(sent)
        time.sleep(5)
        assert len(sent) == n

        inbox.put("/status")
        wait_for(sent, "monitor 🔴 DESLIGADO")

        inbox.put("/ligar")
        wait_for(sent, "LIGADO</b> por Washington")
        before = sum("Supervisão SMR" in t for _, t in sent)
        end = time.time() + 60
        while sum("Supervisão SMR" in t for _, t in sent) <= before and time.time() < end:
            time.sleep(0.3)
        assert sum("Supervisão SMR" in t for _, t in sent) > before  # relatório logo após religar
    finally:
        proc.terminate()
        proc.wait(timeout=60)
        smr.shutdown()
        tg.shutdown()

    # o estado (desligado/ligado) fica salvo para sobreviver a reinícios
    assert '"enabled": true' in (tmp_path / "state.json").read_text()
