"""Playwright renderer that mimics the extension's capture pipeline.

The page is rendered once at a realistic viewport + device pixel ratio; the
crop is cut from that same capture around a target element (with jittered
margins so edges clip neighbouring text the way real drag-selects do), the
crop's long edge is capped at 1400 px, and the screen image is the full
viewport downscaled to a 1400 px long edge — exactly what background.js sends.
"""
from __future__ import annotations

import io
import random
from dataclasses import dataclass

from PIL import Image

MAX_DIM = 1400

# (css width, css height, device pixel ratio, weight)
VIEWPORTS = [
    (1440, 860, 2, 40),   # MacBook Air/Pro 13-14"
    (1728, 1005, 2, 15),  # MacBook Pro 16"
    (1536, 864, 1.25, 15),  # common Windows laptop
    (1920, 1080, 1, 15),
    (1280, 720, 1, 8),
    (1366, 768, 1, 7),
]


def pick_viewport(rng: random.Random) -> tuple[int, int, float]:
    w, h, dpr, _ = rng.choices(VIEWPORTS, weights=[v[3] for v in VIEWPORTS])[0]
    return w, h, dpr


@dataclass
class Rendered:
    crop_png: bytes
    screen_png: bytes
    rect: dict  # css px rect actually cropped


class Renderer:
    def __init__(self) -> None:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._contexts: dict[tuple, object] = {}

    def close(self) -> None:
        self._browser.close()
        self._pw.stop()

    def _page(self, w: int, h: int, dpr: float):
        key = (w, h, dpr)
        if key not in self._contexts:
            ctx = self._browser.new_context(viewport={"width": w, "height": h},
                                            device_scale_factor=dpr)
            self._contexts[key] = ctx.new_page()
        return self._contexts[key]

    def render(self, html: str, target: str, rng: random.Random,
               viewport: tuple[int, int, float] | None = None,
               scroll_to_target: bool = True, jitter: str = "normal") -> Rendered:
        """jitter="tight" keeps the vertical margins within a couple of px so a
        single-line target (a bullet, a list row) never pulls in a neighbour
        that would change the gold."""
        w, h, dpr = viewport or pick_viewport(rng)
        page = self._page(w, h, dpr)
        page.set_content(html, wait_until="load")
        loc = page.locator(target).first
        if scroll_to_target:
            # Put the target somewhere plausible on screen (not always centred).
            loc.evaluate("el => el.scrollIntoView({block: 'center'})")
            page.evaluate(f"window.scrollBy(0, {rng.randint(-160, 160)})")
        box = loc.bounding_box()
        if box is None:
            raise RuntimeError(f"target {target} not found / not visible")

        full = Image.open(io.BytesIO(page.screenshot(full_page=False))).convert("RGB")
        # jittered drag rectangle in css px; negative margins clip into the text
        mx0 = rng.choice([-6, -2, 4, 8, 14, 22, 36, 60])
        mx1 = rng.choice([-6, -2, 4, 8, 14, 22, 36, 60])
        if jitter == "tight":
            my0 = rng.choice([-2, 0, 2, 4])
            my1 = rng.choice([-2, 0, 2, 4])
        else:
            my0 = rng.choice([-4, -1, 3, 6, 10, 18, 30])
            my1 = rng.choice([-4, -1, 3, 6, 10, 18, 30])
        x0 = max(0, box["x"] - mx0)
        y0 = max(0, box["y"] - my0)
        x1 = min(w, box["x"] + box["width"] + mx1)
        y1 = min(h, box["y"] + box["height"] + my1)
        if x1 - x0 < 40 or y1 - y0 < 16:
            x0, y0 = max(0, box["x"] - 8), max(0, box["y"] - 6)
            x1, y1 = min(w, box["x"] + box["width"] + 8), min(h, box["y"] + box["height"] + 6)

        crop = full.crop((round(x0 * dpr), round(y0 * dpr), round(x1 * dpr), round(y1 * dpr)))
        crop = _cap(crop)
        screen = _cap(full)
        return Rendered(_png(crop), _png(screen), {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0})


def _cap(im: Image.Image) -> Image.Image:
    scale = min(1.0, MAX_DIM / max(im.size))
    if scale < 1.0:
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))),
                       Image.LANCZOS)
    return im


def _png(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
