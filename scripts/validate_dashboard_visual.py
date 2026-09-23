"""Smoke and visual checks for the running Streamlit dashboard."""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright


URL = "http://127.0.0.1:8501"
OUTPUT = Path("logs/screenshots")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    viewports = {"desktop": (1440, 1000), "mobile": (390, 844)}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for name, (width, height) in viewports.items():
            page = browser.new_page(viewport={"width": width, "height": height})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(URL, wait_until="networkidle", timeout=60_000)
            page.get_by_text("NASCENTE BRASIL", exact=True).wait_for(timeout=30_000)
            page.get_by_text("2.389.325", exact=True).wait_for(timeout=30_000)
            page.locator(".js-plotly-plot").first.wait_for(timeout=30_000)
            if name == "desktop":
                sections = [
                    "Nascimentos", "Parto e pré-natal", "Recém-nascidos", "Saúde materna",
                    "Mortalidade", "Comparação e mapa", "Qualidade dos dados", "Visão geral",
                ]
                for section in sections:
                    page.get_by_role("radio", name=section, exact=True).check(force=True)
                    page.wait_for_timeout(700)
                    assert page.locator('[data-testid="stException"]').count() == 0, section
                page.get_by_text("2.389.325", exact=True).wait_for(timeout=30_000)
            overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
            error_text = page.get_by_text("API analítica indisponível.").count()
            assert not errors, f"JavaScript errors ({name}): {errors}"
            assert not overflow, f"Horizontal overflow detected at {width}px"
            assert error_text == 0, f"API unavailable message shown at {width}px"
            page.screenshot(path=str(OUTPUT / f"dashboard_{name}.png"), full_page=True)
        browser.close()
    print("Dashboard visual validation passed: 8 sections, desktop=1440x1000, mobile=390x844")


if __name__ == "__main__":
    main()
