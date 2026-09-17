(() => {
  if (window.__cropcalActive) return;
  window.__cropcalActive = true;

  const overlay = document.createElement("div");
  overlay.id = "cropcal-overlay";
  const selection = document.createElement("div");
  selection.id = "cropcal-selection";
  const hint = document.createElement("div");
  hint.id = "cropcal-hint";
  hint.textContent = "Drag to select an event — Esc to cancel";
  document.documentElement.append(overlay, selection, hint);

  let startX = 0;
  let startY = 0;
  let dragging = false;
  let awaitingResult = false;

  const rectFrom = (e) => {
    const x = Math.min(startX, e.clientX);
    const y = Math.min(startY, e.clientY);
    return { x, y, w: Math.abs(e.clientX - startX), h: Math.abs(e.clientY - startY) };
  };

  const drawSelection = (r) => {
    selection.style.display = "block";
    selection.style.left = `${r.x}px`;
    selection.style.top = `${r.y}px`;
    selection.style.width = `${r.w}px`;
    selection.style.height = `${r.h}px`;
  };

  const cleanup = () => {
    overlay.remove();
    selection.remove();
    hint.remove();
    document.removeEventListener("keydown", onKey, true);
    window.__cropcalActive = false;
  };

  const onKey = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      cleanup();
      removeToast();
    }
  };
  document.addEventListener("keydown", onKey, true);

  // The background sends this right after it has taken the screenshot; only
  // then is it safe to draw the progress toast (it must not be in the capture).
  const onMessage = (msg) => {
    if (msg && msg.type === "cropcal-progress" && awaitingResult) {
      showToast("Extracting event…", { spinner: true });
    }
  };
  if (window.__cropcalOnMessage) {
    chrome.runtime.onMessage.removeListener(window.__cropcalOnMessage);
  }
  window.__cropcalOnMessage = onMessage;
  chrome.runtime.onMessage.addListener(onMessage);

  overlay.addEventListener("mousedown", (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    dragging = true;
    startX = e.clientX;
    startY = e.clientY;
    drawSelection(rectFrom(e));
  });

  overlay.addEventListener("mousemove", (e) => {
    if (dragging) drawSelection(rectFrom(e));
  });

  overlay.addEventListener("mouseup", (e) => {
    if (!dragging) return;
    dragging = false;
    const rect = rectFrom(e);
    if (rect.w < 8 || rect.h < 8) return; // treat as a stray click, keep overlay up
    cleanup();
    // Let the page repaint without the overlay before the tab is captured.
    requestAnimationFrame(() =>
      requestAnimationFrame(() => setTimeout(() => capture(rect), 30))
    );
  });

  function capture(rect) {
    awaitingResult = true;
    chrome.runtime.sendMessage(
      { type: "cropcal-capture", rect, dpr: window.devicePixelRatio || 1 },
      (result) => {
        awaitingResult = false;
        if (chrome.runtime.lastError) {
          showToast(`CropCal error: ${chrome.runtime.lastError.message}`, { error: true });
          return;
        }
        if (!result || !result.ok) {
          showToast(`CropCal: ${result ? result.error : "unknown error"}`, { error: true });
          return;
        }
        let text =
          result.count === 1
            ? "Event found — opening Google Calendar…"
            : `${result.count} events found — opening Google Calendar…`;
        if (result.skipped > 0) text += ` (${result.skipped} more skipped)`;
        if (result.lowConfidence) text += " Check the details — some fields were uncertain.";
        if (result.pastCount > 0) {
          text +=
            result.pastCount === 1
              ? " Heads up: the date is in the past — double-check the year."
              : ` Heads up: ${result.pastCount} dates are in the past — double-check the years.`;
        }
        showToast(text, { timeout: 5000 });
      }
    );
  }

  let toast = null;
  let toastTimer = null;

  function removeToast() {
    if (toast) toast.remove();
    toast = null;
    if (toastTimer) clearTimeout(toastTimer);
  }

  function showToast(text, { spinner = false, error = false, timeout = 8000 } = {}) {
    removeToast();
    toast = document.createElement("div");
    toast.id = "cropcal-toast";
    if (error) toast.dataset.state = "error";
    if (spinner) {
      const s = document.createElement("div");
      s.className = "cropcal-spinner";
      toast.appendChild(s);
    }
    toast.appendChild(document.createTextNode(text));
    document.documentElement.appendChild(toast);
    if (!spinner) toastTimer = setTimeout(removeToast, timeout);
  }
})();
