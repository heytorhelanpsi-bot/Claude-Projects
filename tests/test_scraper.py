import pytest

from smr_monitor.config import POINTS, Settings
from smr_monitor.parser import parse_readings
from smr_monitor.scraper import ScrapeError, fetch_text

from .fake_smr import make_server


@pytest.fixture
def server():
    srv = make_server(level="3,96")
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()


def test_login_and_read(server):
    cfg = Settings(smr_url=server, smr_user="Washington", smr_password="segredo")
    r = parse_readings(fetch_text(cfg), POINTS)
    assert r["r0_sobrado"].value == 3.96
    assert r["r0_r2"].value == 2140.13
    assert r["r0_r8"].value == 904.22


def test_wrong_password(server):
    cfg = Settings(smr_url=server, smr_user="Washington", smr_password="errada")
    with pytest.raises(ScrapeError, match="login não aceito"):
        fetch_text(cfg)
