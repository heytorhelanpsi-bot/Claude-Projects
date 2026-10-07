from datetime import datetime, timedelta

import pytest

from smr_monitor import rules
from smr_monitor.config import Settings
from smr_monitor.parser import Reading

T0 = datetime(2026, 10, 4, 12, 0, 0)


@pytest.fixture
def cfg(tmp_path):
    return Settings(report_interval_min=15, critical_repeat_min=15)


def readings(level, t, no_comm=False, r2=2140.13, r8=904.22):
    return {
        "r0_sobrado": Reading("r0_sobrado", level, t, no_comm),
        "r0_r2": Reading("r0_r2", r2, t),
        "r0_r8": Reading("r0_r8", r8, t),
    }


def run(cfg, state, level, minutes, no_comm=False, **flows):
    t = T0 + timedelta(minutes=minutes)
    return rules.evaluate(readings(level, t, no_comm, **flows), t, state, cfg)


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
    assert "Não foi possível ler" in rules.register_failure("<erro>", state, cfg)[0]  # 2ª falha = 40 min
    assert rules.register_failure("x", state, cfg) == []
    assert any("restabelecido" in m for m in run(cfg, state, 3.0, 0))


def test_flow_r0_r2_below_range(cfg):
    state = {}
    run(cfg, state, 3.0, 0, r2=2000)
    msgs = run(cfg, state, 3.0, 5, r2=1850.5)
    assert any("Vazão R0-R2 ABAIXO da faixa" in m and "1.850,50 m³/h" in m and "mínimo 1.900" in m for m in msgs)
    assert not alerts(run(cfg, state, 3.0, 10, r2=1800))  # sem repetir antes de 15 min
    assert any("R0-R2 continua abaixo" in m for m in run(cfg, state, 3.0, 20, r2=1800))
    assert not alerts(run(cfg, state, 3.0, 25, r2=1910))  # histerese de 1%: ainda baixa
    assert any("R0-R2 voltou à faixa normal" in m for m in run(cfg, state, 3.0, 30, r2=1950))


def test_flow_r0_r8_below_range_and_report(cfg):
    state = {}
    msgs = run(cfg, state, 3.0, 0, r8=780)
    assert any("Vazão R0-R8 ABAIXO da faixa" in m for m in msgs)
    report = [m for m in msgs if m.startswith("📊")][0]
    assert "780,00 m³/h</b> 🚨 fora da faixa" in report


def test_flow_high_values_are_normal_by_default(cfg):
    state = {}
    assert not alerts(run(cfg, state, 3.0, 0, r2=2300, r8=1000))


def test_flow_max_when_configured(cfg):
    cfg.flow_limits["r0_r8"] = (790, 910)
    state = {}
    assert any("R0-R8 ACIMA da faixa" in m and "790 a 910" in m for m in run(cfg, state, 3.0, 0, r8=950))


def test_padrao_20_minutos():
    cfg = Settings()
    assert cfg.check_interval_min == 20 and cfg.report_interval_min == 20 and cfg.critical_repeat_min == 20
    state = {}
    reports = [m for i in range(0, 80, 20) for m in run(cfg, state, 2.5, i) if m.startswith("📊")]
    assert len(reports) == 4  # um relatório a cada leitura de 20 min


def test_subida_rapida_com_leituras_de_20_min():
    cfg = Settings()
    state = {}
    run(cfg, state, 2.30, 0)
    assert any("Subida rápida" in m and "+0,20 m em 20 min" in m for m in run(cfg, state, 2.50, 20))


def test_critico_repete_a_cada_20_min():
    cfg = Settings()
    state = {}
    assert any("NÍVEL CRÍTICO MÁXIMO" in m for m in run(cfg, state, 3.96, 0))
    assert any("Continua em nível crítico" in m for m in run(cfg, state, 3.97, 20))
