import pytest

from smr_monitor import commands, rules
from smr_monitor.config import Settings

from .test_rules import alerts, run


@pytest.fixture
def sent(monkeypatch):
    out = []
    monkeypatch.setattr(commands.telegram, "send", lambda cfg, text: out.append(("todos", text)) or True)
    monkeypatch.setattr(commands.telegram, "send_to", lambda cfg, chat, text: out.append((chat, text)) or True)
    return out


@pytest.fixture
def cfg():
    return Settings(telegram_chat_ids=["111", "-222"], report_interval_min=15)


def msg(text, chat="111", type_="private"):
    return {"update_id": 1, "message": {"text": text, "chat": {"id": int(chat), "type": type_},
                                        "from": {"first_name": "Washington"}}}


def test_parse():
    assert commands.parse("/desligar") == "desligar"
    assert commands.parse("/Ligar@monitor_bot") == "ligar"
    assert commands.parse("status agora") == "status"
    assert commands.parse("/start") == "ajuda"
    assert commands.parse("bom dia") is None


def test_desligar_e_ligar(cfg, sent):
    state = {}
    assert commands.handle_update(msg("/desligar"), cfg, state) == {}
    assert state["enabled"] is False
    assert "DESLIGADO</b> por Washington" in sent[-1][1] and sent[-1][0] == "todos"
    assert commands.handle_update(msg("/ligar"), cfg, state) == {"check_now": True}
    assert state["enabled"] is True and "LIGADO" in sent[-1][1]


def test_ligar_quando_ja_ligado(cfg, sent):
    assert commands.handle_update(msg("/ligar"), cfg, {}) == {}
    assert "já está ligado" in sent[-1][1]


def test_chat_nao_autorizado_e_ignorado(cfg, sent):
    state = {}
    assert commands.handle_update(msg("/desligar", chat="999"), cfg, state) == {}
    assert state == {} and sent == []


def test_status_e_ajuda(cfg, sent):
    assert commands.handle_update(msg("/status", chat="-222", type_="group"), cfg, {}) == {"status_to": "-222"}
    commands.handle_update(msg("/ajuda"), cfg, {})
    assert "/desligar" in sent[-1][1] and "LIGADO" in sent[-1][1]


def test_texto_qualquer(cfg, sent):
    commands.handle_update(msg("oi"), cfg, {})
    assert "Não entendi" in sent[-1][1]
    commands.handle_update(msg("conversa do grupo", chat="-222", type_="group"), cfg, {})
    assert len(sent) == 1  # em grupo, não responde conversa comum


def test_relatorios_off_mantem_alertas(cfg, sent):
    state = {}
    run(cfg, state, 3.0, 0)
    commands.handle_update(msg("/relatorios_off"), cfg, state)
    msgs = run(cfg, state, 3.0, 15, r2=1800)
    assert not any(m.startswith("📊") for m in msgs)  # sem relatório
    assert any("ABAIXO da faixa" in m for m in alerts(msgs))  # alerta continua
    commands.handle_update(msg("/relatorios_on"), cfg, state)
    assert any(m.startswith("📊") for m in run(cfg, state, 3.0, 20, r2=1800))
