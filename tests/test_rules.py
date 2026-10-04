from datetime import datetime, timedelta

import pytest

from smr_monitor import rules
from smr_monitor.config import Settings
from smr_monitor.parser import Reading

T0 = datetime(2026, 10, 4, 12, 0, 0)


@pytest.fixture
def cfg(tmp_path):
    return Settings(report_interval_min=15)


def readings(level, t, no_comm=False):
    return {
        "r0_sobrado": Reading("r0_sobrado", level, t, no_comm),
        "r0_r2": Reading("r0_r2", 2140.13, t),
        "r0_r8": Reading("r0_r8", 904.22, t),
    }


def run(cfg, state, level, minutes, no_comm=False):
    t = T0 + timedelta(minutes=minutes)
    return rules.evaluate(readings(level, t, no_comm), t, state, cfg)


def alerts(msgs):
    return [m for m in msgs if not m.startswith("📊")]


def test_first_run_sends_report_only(cfg):
    state = {}
    msgs = run(cfg, state, 3.62, 0)
    assert len(msgs) == 1 and msgs[0].startswith("📊")
    assert "3,62 m" in msgs[0] and "2.140,13 m³/h" in msgs[0] and "904,22 m³/h" in msgs[0]


def test_report_every_15_min(cfg):
    state = {}
    reports = [m for i in range(0, 60, 5) for m in run(cfg, state, 2.5, i) if m.startswith("📊")]
    assert len(reports) == 4  # 0, 15, 30, 45


def test_critical_max_enter_repeat_exit(cfg):
    state = {}
    run(cfg, state, 3.80, 0)
    assert any("NÍVEL CRÍTICO MÁXIMO" in m for m in run(cfg, state, 3.95, 5))
    assert not alerts(run(cfg, state, 3.96, 10))  # sem repetir antes de 15 min
    assert any("Continua em nível crítico" in m for m in run(cfg, state, 3.97, 20))
    assert not alerts(run(cfg, state, 3.92, 25))  # histerese: ainda crítico
    assert any("saiu do nível crítico máximo" in m for m in run(cfg, state, 3.85, 30))


def test_critical_min(cfg):
    state = {}
    run(cfg, state, 1.40, 0)
    assert any("NÍVEL CRÍTICO MÍNIMO" in m for m in run(cfg, state, 1.20, 5))
    assert any("saiu do nível crítico mínimo" in m for m in run(cfg, state, 1.30, 10))


def test_fast_rise(cfg):
    state = {}
    run(cfg, state, 2.30, 0)
    assert not any("Subida rápida" in m for m in run(cfg, state, 2.40, 10))
    msgs = run(cfg, state, 2.50, 20)
    assert any("Subida rápida" in m and "+0,20 m em 20 min" in m for m in msgs)
    # não repete dentro da mesma janela
    assert not any("Subida rápida" in m for m in run(cfg, state, 2.60, 25))


def test_slow_rise_is_not_alerted(cfg):
    state = {}
    for i, lvl in enumerate([2.30, 2.35, 2.40, 2.45, 2.50]):
        msgs = run(cfg, state, lvl, i * 15)  # +0,20 m em 60 min
        assert not any("Subida rápida" in m for m in msgs)


def test_meter_marks_up_and_down(cfg):
    state = {}
    run(cfg, state, 2.90, 0)
    assert any("alcançou <b>3 m</b>" in m for m in run(cfg, state, 3.01, 5))
    assert not any("desceu" in m for m in run(cfg, state, 2.98, 10))  # histerese
    assert any("desceu abaixo de <b>3 m</b>" in m for m in run(cfg, state, 2.90, 15))


def test_same_reading_not_duplicated(cfg):
    state = {}
    run(cfg, state, 2.0, 0)
    run(cfg, state, 2.0, 0)
    assert len(state["history"]) == 1


def test_no_comm_alert_once_and_recovery(cfg):
    state = {}
    run(cfg, state, 3.0, 0)
    assert any("sem comunicação" in m for m in run(cfg, state, 3.0, 5, no_comm=True))
    assert not alerts(run(cfg, state, 3.0, 10, no_comm=True))
    assert any("voltou a atualizar" in m for m in run(cfg, state, 3.0, 20))


def test_stale_reading(cfg):
    state = {}
    t_old = T0 - timedelta(minutes=90)
    msgs = rules.evaluate(readings(3.0, t_old), T0, state, cfg)
    assert sum("sem atualização desde" in m for m in msgs) == 3


def test_failures(cfg):
    state = {}
    assert rules.register_failure("x", state, cfg) == []
    assert rules.register_failure("x", state, cfg) == []
    assert "Não foi possível ler" in rules.register_failure("<erro>", state, cfg)[0]
    assert rules.register_failure("x", state, cfg) == []
    assert any("restabelecido" in m for m in run(cfg, state, 3.0, 0))
