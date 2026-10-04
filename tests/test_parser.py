from datetime import datetime

from smr_monitor.config import POINTS
from smr_monitor.parser import parse_number, parse_readings

# Texto como aparece nas capturas de tela do SMR
PAGE = """
Reservatório
62%
QUEBRA CARGA CX QUADR...
2,11 m
-
04/10/2026 17:16:11
Reservatório
53%
R0 SOBRADO (NÍVEL)
3,62 m
-
04/10/2026 17:03:13
Vazão
87%
R0 900mm (VAZÃO)
2.059 m3/h
100 m3
04/10/2026 17:17:21
Vazão
78%
R0-R2 (VAZÃO)
2.140,13 m3/h
57 m3
04/10/2026 17:17:55
Vazão
59%
R0-R8 MACRO
904,22 m3/h
47 m3
04/10/2026 17:18:46
Vazão
87%
R1-R2 (VAZÃO)
0 m3/h
-1 m3
Sem comunicação desde 18/09/2025 15:06:43
"""


def test_parse_number():
    assert parse_number("2.140,13") == 2140.13
    assert parse_number("2.059") == 2059
    assert parse_number("0,56") == 0.56
    assert parse_number("-1") == -1


def test_parse_readings():
    r = parse_readings(PAGE, POINTS)
    assert r["r0_sobrado"].value == 3.62
    assert r["r0_sobrado"].timestamp == datetime(2026, 10, 4, 17, 3, 13)
    assert r["r0_r2"].value == 2140.13
    assert r["r0_r2"].timestamp == datetime(2026, 10, 4, 17, 17, 55)
    assert r["r0_r8"].value == 904.22
    assert not any(x.no_comm for x in r.values())


def test_no_comm_and_missing():
    page = PAGE.replace("R0-R8 MACRO", "R0-R8 MACRO\n0 m3/h\n-1 m3\nSem comunicação desde 18/09/2025 15:06:43\nX")
    r = parse_readings(page, POINTS)
    assert r["r0_r8"].no_comm
    assert r["r0_r8"].timestamp == datetime(2025, 9, 18, 15, 6, 43)
    assert "r0_sobrado" not in parse_readings("R1-R2 (VAZÃO)\n0 m3/h", POINTS)
