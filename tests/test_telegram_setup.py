import os
import subprocess
import sys

from . import fake_telegram


def run(action, token, api):
    env = dict(os.environ, TG_TOKEN=token, TELEGRAM_API=api)
    return subprocess.run([sys.executable, "-m", "smr_monitor.telegram_setup", action],
                          env=env, capture_output=True, text=True)


def test_verificar_e_descobrir():
    srv, sent, inbox = fake_telegram.make_server()
    api = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        assert run("verificar", "bad", api).returncode == 1
        ok = run("verificar", "123:ABC", api)
        assert ok.returncode == 0 and ok.stdout.strip() == "monitor_sobrado_bot"
        assert run("descobrir", "123:ABC", api).stdout == ""  # ninguém mandou mensagem ainda
        inbox.put("oi")
        assert run("descobrir", "123:ABC", api).stdout.strip() == "111\tWashington"
    finally:
        srv.shutdown()
