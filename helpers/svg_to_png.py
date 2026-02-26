from pathlib import Path
from threading import Lock
from io import BytesIO

from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import os
import subprocess


browser = None


def get_browser():
    global browser

    if browser is not None:
        try:
            _ = browser.current_url
            return browser
        except Exception:
            try:
                browser.quit()
            except Exception:
                pass
            browser = None

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--force-device-scale-factor=1")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--use-gl=desktop")
    options.add_argument("--enable-gpu-rasterization")
    options.add_argument("--enable-zero-copy")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-hang-monitor")
    options.add_argument("--disable-renderer-timeout")
    options.add_argument("--renderer-process-limit=1")

    if os.name == "nt":
        service = Service(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        service = Service(preexec_fn=os.setsid)

    browser = webdriver.Chrome(service=service, options=options)
    browser.set_script_timeout(600)
    browser.set_page_load_timeout(600)
    browser.command_executor.set_timeout(600)
    return browser


def svg_to_png(svg_path: Path, png_path: Path, lock: Lock) -> None:
    lock.acquire()
    try:
        browser = get_browser()

        file_url = svg_path.absolute().as_uri()
        browser.get(file_url)

        WebDriverWait(browser, 60).until(
            EC.presence_of_element_located((By.TAG_NAME, "svg"))
        )

        browser.execute_script(
            r"""
            window.__SVG_RENDER_READY__ = false;
            (async () => {
              try {
                const svg = document.querySelector("svg");
                if (!svg) { window.__SVG_RENDER_READY__ = true; return; }

                const images = Array.from(svg.querySelectorAll("image"));
                await Promise.all(images.map(img => new Promise(resolve => {
                  const href =
                    img.getAttribute("href") ||
                    img.getAttributeNS("http://www.w3.org/1999/xlink", "href");
                  if (!href) return resolve();

                  const probe = new Image();
                  probe.onload = () => resolve();
                  probe.onerror = () => resolve();
                  probe.src = href;
                })));

                if (document.fonts && document.fonts.ready) {
                  await document.fonts.ready;
                }

                await new Promise(requestAnimationFrame);
                await new Promise(requestAnimationFrame);

              } finally {
                window.__SVG_RENDER_READY__ = true;
              }
            })();
            """
        )

        WebDriverWait(browser, 60 * 60 * 5).until(
            lambda d: d.execute_script("return window.__SVG_RENDER_READY__ === true")
        )

        element = browser.find_element(By.TAG_NAME, "svg")
        location = element.location
        size = element.size

        left = int(location["x"])
        top = int(location["y"])
        right = int(location["x"] + size["width"])
        bottom = int(location["y"] + size["height"])

        content_w = max(1, right - left)
        content_h = max(1, bottom - top)

        TILE_MAX = 8192
        tile_w = min(TILE_MAX, content_w)
        tile_h = min(TILE_MAX, content_h)

        viewport_w = max(200, int(tile_w * 1.5))
        viewport_h = max(200, int(tile_h * 1.5))
        browser.set_window_size(viewport_w, viewport_h)

        browser.execute_script(
            r"""
            const svg = document.querySelector("svg");
            if (!svg) return;

            if (svg.__orig_style__ === undefined) {
              svg.__orig_style__ = {
                transform: svg.style.transform,
                transformOrigin: svg.style.transformOrigin
              };
            }

            const de = document.documentElement;
            if (de && de.style) {
              de.style.overflow = "hidden";
              de.style.margin = "0";
            }

            const body = document.body;
            if (body && body.style) {
              body.style.overflow = "hidden";
              body.style.margin = "0";
            }

            svg.style.transformOrigin = "top left";
            """
        )

        dpr = float(browser.execute_script("return window.devicePixelRatio || 1;"))

        final_im = Image.new("RGB", (content_w, content_h))
        try:
            y = 0
            while y < content_h:
                x = 0
                tile_h_eff = min(tile_h, content_h - y)

                while x < content_w:
                    tile_w_eff = min(tile_w, content_w - x)

                    browser.execute_script(
                        r"""
                        const svg = document.querySelector("svg");
                        if (!svg) return;
                        const tx = arguments[0];
                        const ty = arguments[1];
                        svg.style.transform = `translate(${-tx}px, ${-ty}px)`;
                        """,
                        left + x,
                        top + y,
                    )

                    browser.execute_script(
                        "return new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));"
                    )

                    png_bytes = browser.get_screenshot_as_png()
                    shot = Image.open(BytesIO(png_bytes))
                    try:
                        crop_right = int(round(tile_w_eff * dpr))
                        crop_bottom = int(round(tile_h_eff * dpr))
                        tile_img = shot.crop((0, 0, crop_right, crop_bottom))

                        if dpr != 1.0:
                            tile_img = tile_img.resize((tile_w_eff, tile_h_eff))

                        final_im.paste(tile_img, (x, y))
                    finally:
                        shot.close()

                    x += tile_w

                y += tile_h

            final_im.save(png_path)

        finally:
            final_im.close()
            browser.execute_script(
                r"""
                const svg = document.querySelector("svg");
                if (!svg || svg.__orig_style__ === undefined) return;
                svg.style.transform = svg.__orig_style__.transform || "";
                svg.style.transformOrigin = svg.__orig_style__.transformOrigin || "";
                """
            )

    finally:
        lock.release()


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python svg_to_png.py <input.svg> <output.png>")
        sys.exit(1)
    lock = Lock()
    svg_to_png(Path(sys.argv[1]), Path(sys.argv[2]), lock)
