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
  if (window.__cropcalCloseCard) window.__cropcalCloseCard();
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
        removeToast();
        showCard(result);
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

  // ---- Review card: the extracted events, editable, before anything is added.
  // Lives in a shadow root so the page's CSS cannot restyle it and its own
  // cannot leak out; styles go in through a constructed stylesheet, which a
  // page's Content-Security-Policy does not block.

  const CARD_CSS = `
    :host { all: initial; position: fixed; top: 16px; right: 16px; z-index: 2147483647; }
    .card { width: 340px; max-height: calc(100vh - 32px); display: flex; flex-direction: column;
      background: #fff; color: #1d1d1f; border-radius: 12px; overflow: hidden;
      box-shadow: 0 12px 40px rgba(0,0,0,.28), 0 0 0 1px rgba(0,0,0,.08);
      font: 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    header { padding: 12px 14px; font-weight: 600; font-size: 14px; border-bottom: 1px solid #e5e5ea;
      display: flex; justify-content: space-between; align-items: center; }
    .x { border: 0; background: none; font-size: 18px; line-height: 1; color: #6e6e73; cursor: pointer; padding: 2px 6px; }
    .list { overflow-y: auto; }
    .event { padding: 12px 14px; border-bottom: 1px solid #e5e5ea; }
    .event.off .fields { display: none; }
    .pick { display: flex; align-items: center; gap: 8px; font-weight: 600; }
    label.pick { font-size: 13px; color: #1d1d1f; margin: 0 0 8px; }
    .event.off label.pick { margin-bottom: 0; color: #6e6e73; }
    .pick span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    label { display: block; font-size: 11px; color: #6e6e73; margin: 8px 0 2px; }
    input[type=text], input[type=date], input[type=time] { width: 100%; box-sizing: border-box; padding: 6px 8px;
      font: inherit; color: inherit; background: #fff; border: 1px solid #c7c7cc; border-radius: 6px; }
    .row { display: flex; gap: 8px; }
    .row > div { flex: 1; min-width: 0; }
    .check { display: flex; align-items: center; gap: 6px; margin-top: 8px; font-size: 12px; color: #1d1d1f; }
    .note { margin-top: 8px; font-size: 12px; color: #6e6e73; }
    .warn { margin-top: 8px; font-size: 12px; color: #9a5b00; background: #fff6e0; border-radius: 6px; padding: 6px 8px; }
    .err { margin-top: 8px; font-size: 12px; color: #b3261e; }
    footer { padding: 12px 14px; display: flex; gap: 8px; }
    button.act { flex: 1; padding: 8px 10px; font: inherit; font-weight: 600; border: 0; border-radius: 8px; cursor: pointer; background: #e5e5ea; color: #1d1d1f; }
    button.primary { background: #4f8ef7; color: #fff; flex: 2; }
    button:disabled { opacity: .5; cursor: default; }
    [hidden] { display: none !important; }
  `;

  function el(tag, props = {}, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else node[k] = v;
    }
    node.append(...children);
    return node;
  }

  function field(labelText, input) {
    return el("div", {}, el("label", { text: labelText }), input);
  }

  function showCard(result) {
    const host = document.createElement("div");
    host.id = "cropcal-card";
    const root = host.attachShadow({ mode: "closed" });
    const sheet = new CSSStyleSheet();
    sheet.replaceSync(CARD_CSS);
    root.adoptedStyleSheets = [sheet];

    const many = result.items.length > 1;
    const rows = result.items.map((item, index) => {
      const f = item.form;
      const pick = el("input", { type: "checkbox", checked: true });
      const title = el("input", { type: "text", value: f.title });
      const allDay = el("input", { type: "checkbox", checked: f.allDay });
      const date = el("input", { type: "date", value: f.date });
      const startTime = el("input", { type: "time", value: f.startTime });
      const endDate = el("input", { type: "date", value: f.endDate });
      const endTime = el("input", { type: "time", value: f.endTime });
      const location = el("input", { type: "text", value: f.location, placeholder: "None" });
      const repeat = el("input", { type: "checkbox", checked: f.repeat });
      const err = el("div", { class: "err", hidden: true });

      const startTimeBox = field("Starts", startTime);
      const endTimeBox = field("Ends", endTime);
      const endDateBox = field("End date", endDate);
      const syncAllDay = () => {
        startTimeBox.hidden = allDay.checked;
        endTimeBox.hidden = allDay.checked;
        // A separate end date only matters for all-day spans and overnight events.
        endDateBox.hidden = !allDay.checked && (!endDate.value || endDate.value === date.value);
      };
      allDay.addEventListener("change", syncAllDay);
      syncAllDay();

      const fields = el(
        "div",
        { class: "fields" },
        field("Title", title),
        el("div", { class: "row" }, field("Date", date), endDateBox),
        el("div", { class: "row" }, startTimeBox, endTimeBox),
        el("label", { class: "check" }, allDay, "All day"),
        field("Location", location)
      );
      if (f.repeat) fields.append(el("label", { class: "check" }, repeat, "Repeats (edit the schedule in Google Calendar)"));
      if (item.past) fields.append(el("div", { class: "warn", text: "This date is in the past — check the year." }));
      if (item.event.confidence === "low") fields.append(el("div", { class: "warn", text: "Some details were uncertain — check them." }));
      if (item.event.notes) fields.append(el("div", { class: "note", text: item.event.notes }));
      fields.append(err);

      const section = el("div", { class: "event" });
      const heading = el("span", { text: f.title || "Event" });
      title.addEventListener("input", () => (heading.textContent = title.value || "Event"));
      if (many) {
        section.append(el("label", { class: "pick" }, pick, heading));
        pick.addEventListener("change", () => {
          section.classList.toggle("off", !pick.checked);
          syncButton();
        });
      }
      section.append(fields);

      return {
        index,
        section,
        err,
        picked: () => pick.checked,
        form: () => ({
          title: title.value,
          allDay: allDay.checked,
          date: date.value,
          startTime: allDay.checked ? "" : startTime.value,
          endDate: endDate.value,
          endTime: allDay.checked ? "" : endTime.value,
          location: location.value,
          repeat: repeat.checked
        })
      };
    });

    const add = el("button", { class: "act primary" });
    const discard = el("button", { class: "act", text: "Discard" });
    const close = el("button", { class: "x", text: "×", title: "Discard" });
    const syncButton = () => {
      const n = rows.filter((r) => r.picked()).length;
      add.disabled = n === 0;
      add.textContent = n > 1 ? `Add ${n} to Google Calendar` : "Add to Google Calendar";
    };
    syncButton();

    const shut = () => {
      host.remove();
      document.removeEventListener("keydown", onCardKey, true);
      window.__cropcalCloseCard = null;
    };
    const onCardKey = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        shut();
      }
    };
    document.addEventListener("keydown", onCardKey, true);
    window.__cropcalCloseCard = shut;
    discard.addEventListener("click", shut);
    close.addEventListener("click", shut);
    // Typing in the card must not trigger the page's own keyboard shortcuts.
    for (const type of ["keydown", "keyup", "keypress"]) {
      host.addEventListener(type, (e) => {
        if (e.key !== "Escape") e.stopPropagation();
      });
    }

    add.addEventListener("click", () => {
      const chosen = rows.filter((r) => r.picked());
      rows.forEach((r) => (r.err.hidden = true));
      add.disabled = true;
      chrome.runtime.sendMessage(
        {
          type: "cropcal-open",
          timezone: result.timezone,
          items: chosen.map((r) => ({ index: r.index, event: result.items[r.index].event, form: r.form() }))
        },
        (res) => {
          if (chrome.runtime.lastError || !res) {
            shut();
            showToast(`CropCal error: ${chrome.runtime.lastError ? chrome.runtime.lastError.message : "no response"}`, { error: true });
            return;
          }
          if (!res.ok) {
            syncButton();
            if (!res.errors) {
              shut();
              showToast(`CropCal: ${res.error}`, { error: true });
              return;
            }
            for (const { index, error } of res.errors) {
              const row = rows[index];
              if (!row) continue;
              row.err.textContent = error;
              row.err.hidden = false;
              row.section.scrollIntoView({ block: "nearest" });
            }
            return;
          }
          shut();
          showToast(res.count === 1 ? "Opening Google Calendar…" : `Opening ${res.count} Google Calendar tabs…`, { timeout: 4000 });
        }
      );
    });

    root.append(
      el(
        "div",
        { class: "card" },
        el("header", {}, el("span", { text: many ? `${rows.length} events found` : "Event found" }), close),
        el("div", { class: "list" }, ...rows.map((r) => r.section)),
        el("footer", {}, discard, add)
      )
    );
    document.documentElement.appendChild(host);
  }
})();
