"""Verify that statistics filters and the line chart use database values."""
import json

from playwright.sync_api import sync_playwright


ROOT = "http://127.0.0.1:8000"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=EDGE, headless=True)
        page = browser.new_page(viewport={"width": 1366, "height": 768})
        page.goto(f"{ROOT}/statistics", wait_until="networkidle")
        for period, expected_points in (("today", 12), ("month", 30), ("week", 7)):
            page.locator(f'[data-period="{period}"]').click()
            page.wait_for_url(f"**/statistics?**period={period}**")
            chart = page.locator("#attendance-chart")
            points = json.loads(chart.get_attribute("data-points"))
            total = int(page.locator(".analytics-metrics article").first.locator("strong").inner_text())
            assert len(points) == expected_points
            assert sum(points) == total
            assert len(page.locator("#attendance-chart polyline").get_attribute("points").split()) == expected_points
        page.screenshot(path=".audit/statistics-real.png", full_page=True)
        browser.close()
    print("statistics smoke: ok")


if __name__ == "__main__":
    main()
