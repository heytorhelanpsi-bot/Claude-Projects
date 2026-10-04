"""Configuração do monitor, lida de variáveis de ambiente (ou do arquivo .env)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(interpolate=False)  # senhas com "$" ficam como estão
except ImportError:  # python-dotenv é opcional
    pass


@dataclass(frozen=True)
class Point:
    key: str
    label: str
    match: str  # nome como aparece no SMR (comparado sem acentos/pontuação)
    unit: str


POINTS = [
    Point("r0_sobrado", "R0 Sobrado (nível)", "R0 SOBRADO (NÍVEL)", "m"),
    Point("r0_r2", "R0-R2 (vazão)", "R0-R2 (VAZÃO)", "m³/h"),
    Point("r0_r8", "R0-R8 (macro)", "R0-R8 MACRO", "m³/h"),
]
LEVEL_KEY = "r0_sobrado"


def _float(name, default):
    return float(os.getenv(name, default).replace(",", "."))


def _opt_float(name, default=""):
    raw = os.getenv(name, default).strip()
    return float(raw.replace(",", ".")) if raw else None


def _list(name, default=""):
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


@dataclass
class Settings:
    # Acesso ao SMR
    smr_url: str = field(default_factory=lambda: os.getenv("SMR_URL", "http://smr.deso-se.com.br"))
    smr_user: str = field(default_factory=lambda: os.getenv("SMR_USER", ""))
    smr_password: str = field(default_factory=lambda: os.getenv("SMR_PASSWORD", ""))
    # Páginas extras a visitar após o login (se os pontos estiverem em telas diferentes)
    smr_pages: list = field(default_factory=lambda: _list("SMR_PAGES"))
    # Seletores CSS opcionais, caso a detecção automática do formulário de login falhe
    user_selector: str = field(default_factory=lambda: os.getenv("SMR_USER_SELECTOR", ""))
    password_selector: str = field(default_factory=lambda: os.getenv("SMR_PASSWORD_SELECTOR", ""))
    submit_selector: str = field(default_factory=lambda: os.getenv("SMR_SUBMIT_SELECTOR", ""))

    # Telegram
    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_ids: list = field(default_factory=lambda: _list("TELEGRAM_CHAT_ID"))

    # Regras do reservatório R0 Sobrado
    level_min: float = field(default_factory=lambda: _float("NIVEL_CRITICO_MIN", "1.20"))
    level_max: float = field(default_factory=lambda: _float("NIVEL_CRITICO_MAX", "3.95"))
    rise_m: float = field(default_factory=lambda: _float("SUBIDA_RAPIDA_M", "0.20"))
    rise_window_min: float = field(default_factory=lambda: _float("SUBIDA_RAPIDA_JANELA_MIN", "30"))
    meter_marks: bool = field(default_factory=lambda: os.getenv("AVISAR_CADA_METRO", "1") == "1")
    hysteresis_m: float = field(default_factory=lambda: _float("HISTERESE_M", "0.05"))
    critical_repeat_min: float = field(default_factory=lambda: _float("REPETIR_CRITICO_MIN", "15"))

    # Faixas aceitáveis das vazões (m³/h). Alerta quando sai da faixa; vazio = sem limite.
    flow_limits: dict = field(default_factory=lambda: {
        "r0_r2": (_opt_float("R0_R2_VAZAO_MIN", "1900"), _opt_float("R0_R2_VAZAO_MAX")),
        "r0_r8": (_opt_float("R0_R8_VAZAO_MIN", "790"), _opt_float("R0_R8_VAZAO_MAX")),
    })
    flow_hysteresis_pct: float = field(default_factory=lambda: _float("VAZAO_HISTERESE_PCT", "1"))

    # Agendamento
    check_interval_min: float = field(default_factory=lambda: _float("INTERVALO_VERIFICACAO_MIN", "5"))
    report_interval_min: float = field(default_factory=lambda: _float("INTERVALO_RELATORIO_MIN", "15"))
    stale_min: float = field(default_factory=lambda: _float("DADO_ATRASADO_MIN", "60"))
    fail_alert_after: int = field(default_factory=lambda: int(os.getenv("FALHAS_ANTES_DE_AVISAR", "3")))

    timezone: str = field(default_factory=lambda: os.getenv("FUSO_HORARIO", "America/Maceio"))
    state_file: Path = field(default_factory=lambda: Path(os.getenv("STATE_FILE", "data/state.json")))
    debug_dir: Path = field(default_factory=lambda: Path(os.getenv("DEBUG_DIR", "data/debug")))
