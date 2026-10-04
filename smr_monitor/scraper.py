"""Acessa o SMR com um navegador headless (Playwright), faz login e devolve o texto da página."""

from datetime import datetime

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from .config import Settings

USER_SELECTORS = [
    "input[name*='user' i]", "input[id*='user' i]",
    "input[name*='login' i]", "input[id*='login' i]",
    "input[name*='usuario' i]", "input[id*='usuario' i]",
    "input[type='email']", "input[type='text']",
]
SUBMIT_SELECTORS = [
    "button[type='submit']", "input[type='submit']",
    "button:has-text('Entrar')", "button:has-text('Login')", "button:has-text('Acessar')",
]


class ScrapeError(Exception):
    pass


def _first_visible(page, selectors):
    for sel in selectors:
        loc = page.locator(sel)
        for i in range(loc.count()):
            if loc.nth(i).is_visible():
                return loc.nth(i)
    return None


def _login(page, cfg: Settings):
    pwd = _first_visible(page, [cfg.password_selector] if cfg.password_selector else ["input[type='password']"])
    if pwd is None:
        return  # já está logado ou a página não exige login
    if not cfg.smr_user or not cfg.smr_password:
        raise ScrapeError("SMR_USER / SMR_PASSWORD não configurados")

    user = _first_visible(page, [cfg.user_selector] if cfg.user_selector else USER_SELECTORS)
    if user is None:
        raise ScrapeError("campo de usuário não encontrado (defina SMR_USER_SELECTOR)")
    user.fill(cfg.smr_user)
    pwd.fill(cfg.smr_password)

    submit = _first_visible(page, [cfg.submit_selector] if cfg.submit_selector else SUBMIT_SELECTORS)
    if submit is not None:
        submit.click()
    else:
        pwd.press("Enter")

    try:
        page.wait_for_load_state("networkidle", timeout=30_000)
    except PWTimeout:
        pass
    if _first_visible(page, ["input[type='password']"]) is not None:
        raise ScrapeError("login não aceito (usuário/senha incorretos ou formulário diferente)")


def _settle(page):
    try:
        page.wait_for_load_state("networkidle", timeout=30_000)
    except PWTimeout:
        pass
    # Os cartões podem ser carregados por JavaScript após o carregamento da página
    page.wait_for_timeout(3_000)


def fetch_text(cfg: Settings, debug: bool = False) -> str:
    """Faz login e retorna o texto visível de todas as páginas configuradas."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 2000}, locale="pt-BR")
            page.set_default_timeout(45_000)
            page.goto(cfg.smr_url, wait_until="domcontentloaded")
            _settle(page)
            _login(page, cfg)
            _settle(page)

            texts = [page.inner_text("body")]
            if debug:
                _dump(page, cfg, "inicio")
            for i, url in enumerate(cfg.smr_pages):
                page.goto(url, wait_until="domcontentloaded")
                _settle(page)
                texts.append(page.inner_text("body"))
                if debug:
                    _dump(page, cfg, f"pagina{i + 1}")
            return "\n".join(texts)
        except PWTimeout as e:
            raise ScrapeError(f"tempo esgotado ao acessar o SMR: {e}") from e
        finally:
            browser.close()


def _dump(page, cfg: Settings, name: str):
    cfg.debug_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = cfg.debug_dir / f"{stamp}-{name}"
    page.screenshot(path=f"{base}.png", full_page=True)
    (base.with_suffix(".html")).write_text(page.content(), encoding="utf-8")
    (base.with_suffix(".txt")).write_text(page.inner_text("body"), encoding="utf-8")
    print(f"[debug] página salva em {base}.png/.html/.txt (URL: {page.url})")
