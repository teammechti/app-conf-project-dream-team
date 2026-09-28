"""Capture landing/account layouts and assert brands stay inside their headers."""
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import sync_playwright


ROOT = "http://127.0.0.1:8000"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def assert_no_horizontal_overflow(page) -> None:
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 1, f"horizontal overflow: {overflow}px at {page.viewport_size}"
    escaped = page.evaluate("""[...document.querySelectorAll('.brand')].filter(node => node.offsetParent !== null).map(node => {
      const box = node.getBoundingClientRect();
      const parent = (node.closest('header, aside') || node.parentElement).getBoundingClientRect();
      return Math.max(0, box.right - parent.right, parent.left - box.left);
    })""")
    assert all(value <= 1 for value in escaped), f"brand overflow: {escaped}"


def main() -> None:
    output = Path(".audit")
    output.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=EDGE, headless=True)
        for name, width, height in (("landing-desktop", 1366, 768), ("landing-mobile", 390, 844), ("landing-zoom-width", 320, 700)):
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(ROOT, wait_until="networkidle")
            assert_no_horizontal_overflow(page)
            page.screenshot(path=output / f"{name}.png", full_page=True)
            page.close()

        context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        page = context.new_page()
        email = f"visual-{uuid4().hex}@example.com"
        assert context.request.post(f"{ROOT}/api/auth/register", data={
            "name": "Алексей Смирнов", "email": email, "password": "VisualPass123", "accept_terms": True,
        }).status == 201
        for name, path in (("dashboard-empty-mobile", "/organizer"), ("settings-account-mobile", "/settings")):
            page.goto(f"{ROOT}{path}", wait_until="networkidle")
            assert_no_horizontal_overflow(page)
            if path == "/organizer":
                brand_text = page.locator(".topbar .brand > span")
                assert brand_text.inner_text() == "QueueManager"
                assert brand_text.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
                page.locator("#sidebar-toggle").click()
                page.wait_for_timeout(300)
                drawer_brand = page.locator(".sidebar .brand > span")
                assert drawer_brand.is_visible()
                assert drawer_brand.inner_text() == "QueueManager"
                assert drawer_brand.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
                page.screenshot(path=output / "sidebar-mobile-open.png", full_page=False)
                page.locator("#sidebar-backdrop").click(position={"x": 350, "y": 400})
                page.wait_for_timeout(250)
            page.screenshot(path=output / f"{name}.png", full_page=True)
        page.set_viewport_size({"width": 1366, "height": 900})
        page.goto(f"{ROOT}/organizer", wait_until="networkidle")
        assert_no_horizontal_overflow(page)
        desktop_brand = page.locator(".sidebar .brand > span")
        assert desktop_brand.is_visible()
        assert desktop_brand.inner_text() == "QueueManager"
        assert desktop_brand.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
        page.screenshot(path=output / "dashboard-empty-desktop.png", full_page=False)
        page.set_viewport_size({"width": 1366, "height": 900})
        page.goto(f"{ROOT}/settings", wait_until="networkidle")
        assert_no_horizontal_overflow(page)
        page.screenshot(path=output / "settings-desktop.png", full_page=True)
        page.set_viewport_size({"width": 320, "height": 700})
        page.goto(f"{ROOT}/organizer", wait_until="networkidle")
        assert_no_horizontal_overflow(page)
        narrow_brand = page.locator(".topbar .brand > span")
        assert narrow_brand.inner_text() == "QueueManager"
        assert narrow_brand.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
        page.screenshot(path=output / "dashboard-320.png", full_page=False)

        finished = context.request.post(f"{ROOT}/api/queues", data={
            "name": "Завершённая очередь", "description": "Проверка итогового экрана", "location": None,
            "date": None, "start_time": None, "end_time": None, "max_participants": 10,
            "allow_join_after_start": True, "show_participant_list": True, "participant_instruction": "",
        }).json()
        for name in ("Анна", "Иван", "Мария"):
            context.request.post(f"{ROOT}/api/queues/{finished['public_code']}/join", data={"name": name})
        context.request.post(f"{ROOT}/api/manage/{finished['management_token']}/next")
        context.request.post(f"{ROOT}/api/manage/{finished['management_token']}/next")
        context.request.post(f"{ROOT}/api/manage/{finished['management_token']}/skip")
        context.request.post(f"{ROOT}/api/manage/{finished['management_token']}/finish")
        page.set_viewport_size({"width": 1366, "height": 900})
        page.goto(finished["management_url"], wait_until="networkidle")
        assert_no_horizontal_overflow(page)
        assert page.get_by_text("История действий").is_visible()
        assert page.get_by_text("Участники очереди").is_visible()
        page.screenshot(path=output / "finished-desktop.png", full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(350)
        assert_no_horizontal_overflow(page)
        page.screenshot(path=output / "finished-mobile.png", full_page=True)
        browser.close()
    print("visual audit: ok")


if __name__ == "__main__":
    main()
