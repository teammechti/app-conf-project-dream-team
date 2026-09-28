"""Browser-level smoke test for onboarding, controls, and direct queue links."""
from datetime import date, timedelta
from uuid import uuid4

from playwright.sync_api import sync_playwright


ROOT = "http://127.0.0.1:8000"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=EDGE, headless=True)
        context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        page = context.new_page()
        page.goto(ROOT, wait_until="networkidle")
        assert page.locator("#organizer-role").is_visible()
        assert page.locator("#participant-role").is_visible()
        page.locator("#organizer-role").click()
        assert page.locator("#organizer-modal").is_visible()

        email = f"smoke-{uuid4().hex}@example.com"
        registered = context.request.post(f"{ROOT}/api/auth/register", data={
            "name": "Smoke Test", "email": email, "password": "SmokePass123", "accept_terms": True,
        })
        assert registered.status == 201
        page.goto(f"{ROOT}/organizer", wait_until="networkidle")
        assert page.locator(".empty-state:visible").count() == 1
        create_button = page.locator(".create-button")
        background_before = create_button.evaluate("node => getComputedStyle(node).backgroundImage")
        create_button.hover()
        page.wait_for_timeout(220)
        assert create_button.evaluate("node => getComputedStyle(node).backgroundImage") == background_before

        payload = {
            "name": "Browser smoke", "description": "", "location": None,
            "date": None, "start_time": None, "end_time": None,
            "max_participants": 10, "allow_join_after_start": True,
            "show_participant_list": True, "participant_instruction": "",
        }
        created = context.request.post(f"{ROOT}/api/queues", data=payload).json()
        page.goto(f"{ROOT}/organizer", wait_until="networkidle")
        page.locator('[data-filter="active"]').click()
        assert page.locator('.queue-card[data-status="active"]:visible').count() == 1
        page.locator(".queue-card summary").click()
        assert page.locator(".action-menu-popover").is_visible()

        participant = browser.new_page(viewport={"width": 390, "height": 844})
        participant.goto(created["public_url"], wait_until="networkidle")
        assert participant.locator(".public-brand").count() == 1
        assert participant.locator(".public-header .brand[href]").count() == 0

        delete_response = page.expect_response(lambda response: response.request.method == "DELETE" and "/api/queues/" in response.url)
        page.locator("[data-delete-queue]").click()
        assert page.locator("#delete-queue-modal").is_visible()
        with delete_response:
            page.locator("#confirm-queue-delete").click()
        page.wait_for_timeout(450)
        page.wait_for_load_state("networkidle")
        assert page.locator(f'[data-delete-queue="{created["id"]}"]').count() == 0
        browser.close()
    print("browser smoke: ok")


if __name__ == "__main__":
    main()
