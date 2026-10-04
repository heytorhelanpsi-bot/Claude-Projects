"""Extrai as leituras dos cartões do SMR a partir do texto visível da página.

Cada cartão aparece no texto como (ver capturas de tela do sistema):

    Reservatório
    53%
    R0 SOBRADO (NÍVEL)
    3,62 m
    -
    04/10/2026 17:03:13

ou, quando o ponto está fora do ar:

    Sem comunicação desde 18/09/2025 15:06:43
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

VALUE_RE = re.compile(r"^(-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+(?:,\d+)?)\s*m")
TIMESTAMP_RE = re.compile(r"(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}(?::\d{2})?)")
LOOKAHEAD_LINES = 8


@dataclass
class Reading:
    key: str
    value: Optional[float]
    timestamp: Optional[datetime]  # horário informado pelo SMR (sem fuso)
    no_comm: bool = False  # "Sem comunicação desde ..."


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", text.upper()).split())


def parse_number(raw: str) -> float:
    """Converte número no formato brasileiro ('2.140,13') para float."""
    return float(raw.replace(".", "").replace(",", "."))


def parse_timestamp(raw: str) -> Optional[datetime]:
    raw = " ".join(raw.split())
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            pass
    return None


def _find_name_line(lines, match):
    target = normalize(match)
    norm = [normalize(line) for line in lines]
    for i, n in enumerate(norm):
        if n == target:
            return i
    for i, n in enumerate(norm):
        if n.startswith(target):
            return i
    return None


def parse_readings(text: str, points) -> dict:
    """Retorna {key: Reading} para cada ponto encontrado no texto."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    result = {}
    for point in points:
        idx = _find_name_line(lines, point.match)
        if idx is None:
            continue
        value = timestamp = None
        no_comm = False
        for line in lines[idx + 1 : idx + 1 + LOOKAHEAD_LINES]:
            if value is None:
                m = VALUE_RE.match(line)
                if m:
                    value = parse_number(m.group(1))
                    continue
            if "SEM COMUNICACAO" in normalize(line):
                no_comm = True
            ts = TIMESTAMP_RE.search(line)
            if ts:
                timestamp = parse_timestamp(ts.group(1))
                break
        result[point.key] = Reading(point.key, value, timestamp, no_comm)
    return result
