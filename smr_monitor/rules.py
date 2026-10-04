"""Regras de alerta. Funções puras: recebem leituras + estado e devolvem mensagens.

Regras do reservatório R0 Sobrado:
  * nível crítico mínimo (<= NIVEL_CRITICO_MIN) ou máximo (>= NIVEL_CRITICO_MAX):
    alerta ao entrar, lembrete a cada REPETIR_CRITICO_MIN e aviso ao normalizar;
  * subida de SUBIDA_RAPIDA_M ou mais em menos de SUBIDA_RAPIDA_JANELA_MIN;
  * a cada metro inteiro alcançado (subindo ou descendo).
Todos os pontos: aviso de "sem comunicação" / dado atrasado e de falha de acesso ao SMR.
Relatório de situação a cada INTERVALO_RELATORIO_MIN.
"""

import html
import math
from datetime import datetime, timedelta

from .config import LEVEL_KEY, POINTS, Settings
from .parser import Reading

HISTORY_KEEP = timedelta(hours=3)
EPS = 1e-9


def fmt(value, decimals=2):
    """Formata número no padrão brasileiro: 2.140,13."""
    s = f"{value:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _hhmm(dt):
    return dt.strftime("%H:%M")


def _ts(iso):
    return datetime.fromisoformat(iso) if iso else None


def _minutes_since(now, iso):
    t = _ts(iso)
    return math.inf if t is None else (now - t).total_seconds() / 60


def _level_rule(level, t, state, cfg: Settings):
    """Avalia as regras do nível. `t` = horário da leitura."""
    msgs = []

    # Histórico (sem duplicar a mesma leitura do SMR)
    hist = state.setdefault("history", [])
    if not hist or hist[-1]["t"] != t.isoformat():
        hist.append({"t": t.isoformat(), "level": level})
    state["history"] = [h for h in hist if t - _ts(h["t"]) <= HISTORY_KEEP]

    # 1) Nível crítico
    zone = None
    if level <= cfg.level_min + EPS:
        zone = "min"
    elif level >= cfg.level_max - EPS:
        zone = "max"
    elif state.get("critical") == "min" and level < cfg.level_min + cfg.hysteresis_m:
        zone = "min"
    elif state.get("critical") == "max" and level > cfg.level_max - cfg.hysteresis_m:
        zone = "max"

    limit_txt = {
        "min": f"MÍNIMO ({fmt(cfg.level_min)} m)",
        "max": f"MÁXIMO ({fmt(cfg.level_max)} m)",
    }
    prev = state.get("critical")
    if zone and zone != prev:
        msgs.append(
            f"🚨 <b>NÍVEL CRÍTICO {limit_txt[zone]}</b>\n"
            f"R0 Sobrado: <b>{fmt(level)} m</b> às {_hhmm(t)}"
        )
        state["last_critical_alert"] = t.isoformat()
    elif zone and _minutes_since(t, state.get("last_critical_alert")) >= cfg.critical_repeat_min - 0.5:
        msgs.append(
            f"🚨 <b>Continua em nível crítico {limit_txt[zone]}</b>\n"
            f"R0 Sobrado: <b>{fmt(level)} m</b> às {_hhmm(t)}"
        )
        state["last_critical_alert"] = t.isoformat()
    elif not zone and prev:
        msgs.append(
            f"✅ <b>R0 Sobrado saiu do nível crítico {limit_txt[prev].split(' ')[0].lower()}</b>\n"
            f"Nível atual: <b>{fmt(level)} m</b> às {_hhmm(t)}"
        )
    state["critical"] = zone

    # 2) Subida rápida
    window = [
        h for h in state["history"]
        if timedelta(0) < t - _ts(h["t"]) < timedelta(minutes=cfg.rise_window_min)
    ]
    if window:
        low = min(window, key=lambda h: h["level"])
        rise = level - low["level"]
        if rise >= cfg.rise_m - EPS and _minutes_since(t, state.get("last_rise_alert")) >= cfg.rise_window_min:
            mins = round((t - _ts(low["t"])).total_seconds() / 60)
            msgs.append(
                f"📈 <b>Subida rápida no R0 Sobrado</b>\n"
                f"+{fmt(rise)} m em {mins} min "
                f"({fmt(low['level'])} m → <b>{fmt(level)} m</b>, às {_hhmm(t)})"
            )
            state["last_rise_alert"] = t.isoformat()

    # 3) A cada metro alcançado
    band = state.get("band")
    if band is None:
        state["band"] = math.floor(level + EPS)
    elif cfg.meter_marks:
        if level >= band + 1 - EPS:
            new_band = math.floor(level + EPS)
            for m in range(band + 1, new_band + 1):
                msgs.append(f"⬆️ R0 Sobrado alcançou <b>{m} m</b> (atual {fmt(level)} m às {_hhmm(t)})")
            state["band"] = new_band
        elif level < band - cfg.hysteresis_m:
            new_band = math.floor(level + EPS)
            for m in range(band, new_band, -1):
                msgs.append(f"⬇️ R0 Sobrado desceu abaixo de <b>{m} m</b> (atual {fmt(level)} m às {_hhmm(t)})")
            state["band"] = new_band

    return msgs


def _freshness_rule(readings, now, state, cfg: Settings):
    msgs = []
    stale = state.setdefault("stale", {})
    for p in POINTS:
        r = readings.get(p.key)
        if r is None:
            problem = "não encontrado na página do SMR"
        elif r.no_comm:
            problem = "sem comunicação" + (f" desde {r.timestamp:%d/%m/%Y %H:%M}" if r.timestamp else "")
        elif r.value is None:
            problem = "valor não identificado na página"
        elif r.timestamp and (now - r.timestamp).total_seconds() / 60 > cfg.stale_min:
            problem = f"sem atualização desde {r.timestamp:%d/%m/%Y %H:%M}"
        else:
            problem = None

        if problem and not stale.get(p.key):
            msgs.append(f"⚠️ <b>{p.label}</b>: {problem}")
        elif not problem and stale.get(p.key):
            msgs.append(f"✅ <b>{p.label}</b> voltou a atualizar normalmente")
        stale[p.key] = bool(problem)
    return msgs


def _trend(state, level, t, cfg):
    past = [h for h in state.get("history", [])
            if timedelta(0) < t - _ts(h["t"]) <= timedelta(minutes=cfg.rise_window_min)]
    if not past:
        return ""
    oldest = min(past, key=lambda h: h["t"])
    diff = level - oldest["level"]
    arrow = "↑" if diff > 0.005 else "↓" if diff < -0.005 else "→"
    mins = round((t - _ts(oldest["t"])).total_seconds() / 60)
    sign = "+" if diff >= 0 else "−"
    return f" {arrow} {sign}{fmt(abs(diff))} m em {mins} min"


def build_report(readings, now, state, cfg: Settings):
    lines = [f"📊 <b>Supervisão SMR</b> — {now:%d/%m/%Y %H:%M}"]
    for p in POINTS:
        r = readings.get(p.key)
        icon = "🛢" if p.key == LEVEL_KEY else "💧"
        if r is None or r.value is None:
            lines.append(f"{icon} {p.label}: <i>indisponível</i>")
            continue
        txt = f"{icon} {p.label}: <b>{fmt(r.value)} {p.unit}</b>"
        if p.key == LEVEL_KEY and r.timestamp:
            txt += _trend(state, r.value, r.timestamp, cfg)
        if r.no_comm:
            txt += " ⚠️ sem comunicação"
        elif r.timestamp:
            txt += f" <i>(lido {_hhmm(r.timestamp)})</i>"
        lines.append(txt)
    lines.append(f"Limites R0: mín {fmt(cfg.level_min)} m · máx {fmt(cfg.level_max)} m")
    return "\n".join(lines)


def evaluate(readings: dict, now: datetime, state: dict, cfg: Settings):
    """Avalia uma rodada de leituras bem-sucedida. Retorna lista de mensagens."""
    msgs = []

    if state.get("fail_alerted"):
        msgs.append("✅ Acesso ao SMR restabelecido.")
    state["fail_count"] = 0
    state["fail_alerted"] = False

    msgs += _freshness_rule(readings, now, state, cfg)

    lvl: Reading = readings.get(LEVEL_KEY)
    if lvl and lvl.value is not None and not lvl.no_comm:
        t = lvl.timestamp or now
        msgs += _level_rule(lvl.value, t, state, cfg)

    if (
        cfg.report_interval_min > 0
        and _minutes_since(now, state.get("last_report")) >= cfg.report_interval_min - 0.5
    ):
        msgs.append(build_report(readings, now, state, cfg))
        state["last_report"] = now.isoformat()

    return msgs


def register_failure(error: str, state: dict, cfg: Settings):
    """Registra uma falha de acesso/leitura. Retorna mensagens (aviso após N falhas seguidas)."""
    state["fail_count"] = state.get("fail_count", 0) + 1
    if state["fail_count"] >= cfg.fail_alert_after and not state.get("fail_alerted"):
        state["fail_alerted"] = True
        return [
            f"❌ <b>Não foi possível ler o SMR</b> ({state['fail_count']} tentativas seguidas).\n"
            f"Erro: <code>{html.escape(error[:300])}</code>"
        ]
    return []
