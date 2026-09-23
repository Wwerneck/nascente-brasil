"""Export polished 16:9 screenshots of the running dashboard."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, sync_playwright


URL = "http://127.0.0.1:8501"
OUTPUT = Path("exports/linkedin")
SECTIONS = [
    ("01_visao_geral.png", "Visão geral", "Visão geral"),
    ("02_nascimentos.png", "Nascimentos", "Nascimentos"),
    ("03_saude_materna.png", "Saúde materna", "Morbidades maternas"),
    ("04_mortalidade.png", "Mortalidade", "Mortalidade"),
    ("05_mapa_estadual.png", "Comparação e mapa", "Comparação estadual"),
]


def prepare(page: Page) -> None:
    page.goto(URL)
    page.get_by_text("NASCENTE BRASIL", exact=True).wait_for(timeout=30_000)
    page.add_style_tag(
        content="""
        [data-testid="stToolbar"], [data-testid="stStatusWidget"],
        [data-testid="stHeaderActionElements"], .stAppDeployButton,
        button[kind="header"] { display: none !important; }
        header { background: transparent !important; }
        """
    )


def capture(page: Page, filename: str, section: str, heading: str) -> None:
    page.get_by_role("radio", name=section, exact=True).check(force=True)
    page.get_by_role("heading", name=heading, exact=True).wait_for(timeout=30_000)
    page.wait_for_timeout(1_200)
    plots = page.locator(".js-plotly-plot")
    if plots.count():
        plots.first.wait_for(timeout=30_000)

    if section == "Comparação e mapa":
        charts = page.locator('[data-testid="stPlotlyChart"]')
        first_chart = charts.first
        first_chart.evaluate(
            """element => {
                const container = element.closest('[data-testid="stElementContainer"]');
                (container || element).style.display = 'none';
            }"""
        )
        map_plot = page.locator(".js-plotly-plot").last
        map_plot.evaluate(
            "element => Plotly.relayout(element, {height: 400, 'map.zoom': 2.35})"
        )
        page.wait_for_timeout(500)

    page.evaluate("window.scrollTo(0, 0)")
    main = page.locator('[data-testid="stMain"]')
    if main.count():
        main.evaluate("element => element.scrollTop = 0")
    page.wait_for_timeout(200)
    assert page.locator('[data-testid="stException"]').count() == 0
    page.screenshot(path=str(OUTPUT / filename))


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for filename, section, heading in SECTIONS:
            page = browser.new_page(viewport={"width": 1440, "height": 810}, device_scale_factor=1)
            prepare(page)
            capture(page, filename, section, heading)
            page.close()
        browser.close()
    print(f"Exported {len(SECTIONS)} LinkedIn screenshots to {OUTPUT}")


if __name__ == "__main__":
    main()
