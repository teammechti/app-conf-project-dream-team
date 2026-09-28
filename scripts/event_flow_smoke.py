"""Exercise the realtime participant acknowledgement flow in two browser sessions."""
from datetime import date, timedelta

import httpx
from playwright.sync_api import sync_playwright


ROOT = "http://127.0.0.1:8000"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def main() -> None:
    payload = {
        "name": "Проверка уведомлений",
        "description": "Автоматический smoke test",
        "location": "Каб. 101",
        "date": (date.today() + timedelta(days=1)).isoformat(),
        "start_time": "10:00",
        "end_time": "12:00",
        "max_participants": 10,
        "allow_join_after_start": True,
        "show_participant_list": True,
        "participant_instruction": "Подойдите к входу",
    }
    created = httpx.post(f"{ROOT}/api/queues", json=payload).json()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=EDGE, headless=True)
        organizer = browser.new_page(viewport={"width": 1366, "height": 768})
        participant = browser.new_page(viewport={"width": 390, "height": 844})
        organizer.goto(created["management_url"], wait_until="networkidle")
        participant.goto(created["public_url"], wait_until="networkidle")
        participant.locator('#join-form input[name="name"]').fill("Алексей")
        participant.locator("#join-form button[type=submit]").click()
        organizer.locator("#next-button").click()
        participant.locator("#call-overlay").wait_for(state="visible")
        participant.locator("#going-button").click()
        organizer.locator(".organizer-alert.kind-acknowledged").wait_for(state="visible")
        assert "Алексей" in organizer.locator(".organizer-alert.kind-acknowledged").inner_text()
        assert "Я иду" in organizer.locator("#event-list .kind-acknowledged").inner_text()
        assert "подтвердил" in organizer.locator("#called-note").inner_text()
        organizer.locator("#notification-center summary").click()
        assert "Алексей" in organizer.locator("#notification-items").inner_text()
        organizer.screenshot(path=".audit/realtime-event.png", full_page=False)
        organizer.locator("#notification-center summary").click()
        organizer.set_viewport_size({"width": 390, "height": 844})
        organizer.wait_for_timeout(350)
        organizer.screenshot(path=".audit/realtime-event-mobile.png", full_page=True)
        browser.close()
    print("realtime event flow: ok")


if __name__ == "__main__":
    main()
