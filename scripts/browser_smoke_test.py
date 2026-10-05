"""
Optional real-browser smoke test of the dashboard with FICTIONAL chats only (needs Playwright + Microsoft Edge/Chromium).

    pip install playwright            # not needed for the normal test suite
    python scripts/browser_smoke_test.py --out screenshots

It starts the Streamlit app on a free local port, then drives it like a user would: empty state, invalid and empty
uploads, one-to-one, 12- and 30-participant groups, every page and NLP tab, theme apply / reset / invalid image,
a second upload, a failed second upload and a zero-text chat. It saves one screenshot per step and checks that no
sender name, phone number or link from the fictional fixtures appears in the rendered text. Screenshots are written
to --out (default: screenshots/, ignored by Git); review them by eye, the script only captures them.
"""

import argparse
import io
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
FICTIONAL_NAMES = ["Alex Demo", "Sam Sample", "Riya Testwala", "Kabir Fictional", "Member 07 Fictional", "Solo Fictional"]
LEAK_TOKENS = ["http", "chat.whatsapp", "@", "9000012345", "+91"]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(port):
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "streamlit_app.py"),
                             "--server.headless", "true", "--server.port", str(port), "--browser.gatherUsageStats", "false"],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=1)
            return proc
        except Exception:
            time.sleep(1)
    proc.terminate()
    raise RuntimeError("Streamlit did not start")


def make_theme_images(folder):
    from PIL import Image, ImageDraw
    folder.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, colour in (("blue", (30, 80, 190)), ("green", (24, 130, 70)), ("purple", (90, 40, 150)),
                         ("dark", (8, 8, 8)), ("light", (250, 250, 250)), ("grey", (128, 128, 128))):
        img = Image.new("RGB", (600, 300), colour)
        d = ImageDraw.Draw(img)
        for i in range(0, 600, 50):
            d.ellipse((i, 50, i + 110, 200), fill=tuple(min(255, c + 40) for c in colour))
        paths[name] = folder / f"theme_{name}.png"
        img.save(paths[name])
    bad = folder / "not_an_image.png"
    bad.write_bytes(b"this is not an image")
    paths["invalid"] = bad
    return paths


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "screenshots")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=2300, help="tall viewport so a whole page is visible in one screenshot")
    args = ap.parse_args(argv)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed (pip install playwright). This script is optional.")
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    work = args.out / "_inputs"
    themes = make_theme_images(work)
    (work / "invalid.txt").write_text("just some notes\nnothing here\n", encoding="utf-8")
    (work / "empty.txt").write_bytes(b"")
    port = free_port()
    server = start_server(port)
    steps, problems = [], []
    try:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(channel="msedge", headless=True)
            except Exception:
                browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": args.width, "height": args.height})
            page.goto(f"http://127.0.0.1:{port}")
            page.wait_for_selector("text=No chat loaded yet", timeout=60000)

            def shot(name, full=True, names=True):
                # names=False for the empty state: its "expected format" example text uses the fictional names on purpose
                page.wait_for_timeout(1200)
                try:                                              # wait until charts and tables have finished loading
                    page.wait_for_function("document.querySelectorAll('[data-testid=stSkeleton]').length === 0", timeout=20000)
                except Exception:
                    problems.append(f"{name}: page still showed loading placeholders")
                page.wait_for_timeout(600)
                page.screenshot(path=str(args.out / f"{name}.png"), full_page=full)
                steps.append(name)
                text = page.evaluate("document.body.innerText")
                for token in (FICTIONAL_NAMES if names else []) + LEAK_TOKENS:
                    if token.lower() in text.lower():
                        problems.append(f"{name}: '{token}' appears in the rendered page")

            def chat_input():
                return page.locator("input[type='file']").first

            def clear_uploads():
                btns = page.locator("[data-testid='stFileUploaderDeleteBtn'] button")
                while btns.count():
                    btns.first.click()
                    page.wait_for_timeout(600)

            def upload_chat(path, wait_text):
                clear_uploads()
                chat_input().set_input_files(str(path))
                page.wait_for_selector(f"text={wait_text}", timeout=120000)
                page.wait_for_timeout(2500)

            def go(label):
                page.get_by_text(label, exact=True).first.click()
                page.wait_for_timeout(2500)

            shot("01_empty_state", names=False)
            chat_input().set_input_files(str(work / "invalid.txt"))
            page.wait_for_selector("text=does not look like a supported", timeout=60000)
            shot("02_error_invalid", names=False)
            clear_uploads()
            chat_input().set_input_files(str(work / "empty.txt"))
            page.wait_for_selector("text=The file is empty", timeout=60000)
            shot("03_error_empty", names=False)

            for key, fixture in (("04_one_to_one", "one_to_one.txt"), ("05_group_12", "group_12.txt"),
                                 ("06_group_30", "group_30.txt")):
                upload_chat(FIXTURES / fixture, fixture)
                go("Overview")
                shot(f"{key}_overview")
                if key != "04_one_to_one":
                    continue
                go("Conversation")
                shot(f"{key}_conversation")
                go("NLP Insights")
                for tab in ("Unigrams", "Bigrams", "Trigrams", "TF-IDF", "Script Mix", "Key Terms"):
                    page.get_by_role("tab", name=tab).click()
                    page.wait_for_timeout(1800)
                    shot(f"{key}_nlp_{tab.replace(' ', '_').replace('-', '').lower()}")
                go("Patterns")
                shot(f"{key}_patterns")
            go("Conversation")
            shot("07_group_30_conversation")

            # theme: apply, reset, invalid image
            theme_input = page.locator("input[type='file']").nth(1)
            for name in ("blue", "green", "purple", "dark", "light", "grey"):
                theme_input = page.locator("input[type='file']").nth(1)
                theme_input.set_input_files(str(themes[name]))
                page.wait_for_timeout(2000)
                page.get_by_role("button", name="Apply Theme").click()
                go("Overview")
                shot(f"08_theme_{name}", full=False)
                page.get_by_role("button", name="Reset Theme").click()
                page.wait_for_timeout(2000)
            theme_input = page.locator("input[type='file']").nth(1)
            theme_input.set_input_files(str(themes["invalid"]))
            page.wait_for_selector("text=Theme image could not be applied.", timeout=30000)
            shot("09_theme_invalid_image", full=False)

            # second valid upload, failed second upload, zero-text chat
            upload_chat(FIXTURES / "single_sender.txt", "single_sender.txt")
            go("Overview")
            shot("10_second_upload_single_sender")
            clear_uploads()
            chat_input().set_input_files(str(work / "invalid.txt"))
            page.wait_for_selector("text=still shown below", timeout=60000)
            shot("11_failed_second_upload", full=False)
            upload_chat(FIXTURES / "zero_text.txt", "zero_text.txt")
            go("Overview")
            shot("12_zero_text_overview")
            go("NLP Insights")
            shot("13_zero_text_nlp")
            browser.close()
    finally:
        server.terminate()
    print(f"{len(steps)} screenshots written to {args.out}")
    for p in problems:
        print("PROBLEM:", p)
    print("privacy check of rendered text:", "FAILED" if problems else "no fictional names, numbers or links found")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
