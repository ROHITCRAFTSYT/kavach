"""Capture README screenshots + a demo GIF from a running Kavach instance.

Uses Playwright with the locally installed Microsoft Edge (no browser download):

    pip install playwright pillow
    python scripts/capture_media.py --url https://kavach-kappa.vercel.app

Writes PNGs and demo.gif to docs/media/.
"""

from __future__ import annotations

import argparse
import io
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "media"
DONE_JS = "() => (document.querySelector('#trace-total')?.textContent || '').trim().length > 0"


def run_sample(page: Page, title: str) -> None:
    # Clear the previous run's trace total so wait_done() waits for THIS run.
    page.evaluate("() => { const t = document.querySelector('#trace-total'); if (t) t.textContent = ''; }")
    card = page.locator("#sample-grid > *").filter(has_text=title).first
    card.get_by_role("button", name="Check this example").click()


def wait_done(page: Page, timeout_s: int = 150) -> None:
    page.wait_for_function(DONE_JS, timeout=timeout_s * 1000)
    page.wait_for_timeout(1200)  # let the gauge animation settle


def reset(page: Page) -> None:
    page.locator("#btn-reset").click()
    page.wait_for_selector("#input-view:not([hidden])")
    page.evaluate("window.scrollTo(0, 0)")


def shot(page: Page, name: str, selector: str | None = None) -> None:
    path = OUT / name
    if selector:
        page.locator(selector).first.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        page.locator(selector).first.screenshot(path=str(path))
    else:
        page.screenshot(path=str(path))
    print("wrote", path.relative_to(OUT.parents[1]))


def frame(page: Page) -> Image.Image:
    return Image.open(io.BytesIO(page.screenshot())).convert("RGB")


def build_gif(frames: list[tuple[Image.Image, int]], path: Path, width: int = 880) -> None:
    resized = []
    for img, ms in frames:
        h = round(img.height * width / img.width)
        resized.append((img.resize((width, h), Image.LANCZOS), ms))
    palette_src = resized[-1][0].quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    imgs = [im.quantize(palette=palette_src, dither=Image.Dither.NONE) for im, _ in resized]
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=[ms for _, ms in resized],
                 loop=0, optimize=True, disposal=1)
    print("wrote", path.relative_to(OUT.parents[1]), f"{path.stat().st_size / 1e6:.1f} MB, {len(imgs)} frames")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True, args=["--autoplay-policy=no-user-gesture-required", "--mute-audio"])
        ctx = browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1, color_scheme="dark")
        page = ctx.new_page()
        page.goto(args.url, wait_until="networkidle")
        page.wait_for_selector("#sample-grid button")
        shot(page, "home.png")

        # --- GIF: fake CBI notice, from click to verdict + evidence overlay -----------------
        gif: list[tuple[Image.Image, int]] = [(frame(page), 1200)]
        page.locator("#sample-grid").scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        gif.append((frame(page), 1000))
        run_sample(page, "“CBI” notice")
        t0 = time.time()
        while not page.evaluate(DONE_JS) and time.time() - t0 < 150:
            page.evaluate("window.scrollTo(0, 0)")
            gif.append((frame(page), 220))
            page.wait_for_timeout(900)
        wait_done(page)
        page.evaluate("window.scrollTo(0, 0)")
        gif.append((frame(page), 2600))
        shot(page, "result-scam.png")
        shot(page, "red-flags.png", "#flags-card")
        page.locator("#findings > *").first.click()
        page.wait_for_timeout(700)
        shot(page, "evidence-overlay.png", "#evidence-card")
        page.locator("#evidence-card").scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        gif.append((frame(page), 2600))
        page.locator("#facts-card").scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        gif.append((frame(page), 2000))
        page.locator("#trace-details summary").click()
        page.wait_for_timeout(500)
        shot(page, "trace.png", "#trace-details")
        build_gif(gif, OUT / "demo.gif")

        # --- Hindi "digital arrest" call: diarized transcript -------------------------------
        reset(page)
        run_sample(page, "“Digital arrest” call")
        wait_done(page)
        page.evaluate("window.scrollTo(0, 0)")
        shot(page, "result-call.png")
        shot(page, "call-transcript.png", "#evidence-card")

        # --- Genuine Tamil electricity notice: low risk, facts extracted --------------------
        reset(page)
        run_sample(page, "Electricity notice")
        wait_done(page)
        page.evaluate("window.scrollTo(0, 0)")
        shot(page, "result-genuine.png")

        # --- Mobile ------------------------------------------------------------------------
        m = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                is_mobile=True, has_touch=True, color_scheme="dark")
        mp = m.new_page()
        mp.goto(args.url, wait_until="networkidle")
        mp.wait_for_selector("#sample-grid button")
        run_sample(mp, "Bank KYC voice note")
        wait_done(mp)
        mp.evaluate("window.scrollTo(0, 0)")
        shot(mp, "mobile.png")
        browser.close()


if __name__ == "__main__":
    main()
