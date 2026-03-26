/* ============================================================
   AI Assistant — shared JavaScript utilities
   ============================================================ */

/* ── Theme toggle ─────────────────────────────────────────── */
(function () {
  const STORAGE_KEY = "ai-theme";
  const html = document.documentElement;

  function applyTheme(theme) {
    html.setAttribute("data-theme", theme);
    localStorage.setItem(STORAGE_KEY, theme);
    const label = document.getElementById("theme-label");
    if (label) label.textContent = theme === "dark" ? "Light mode" : "Dark mode";
  }

  // Apply saved theme immediately (before paint)
  const saved = localStorage.getItem(STORAGE_KEY) ||
    (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  applyTheme(saved);

  window.toggleTheme = function () {
    const current = html.getAttribute("data-theme") || "dark";
    applyTheme(current === "dark" ? "light" : "dark");
  };

  // Expose for init after DOM ready
  window._applyTheme = applyTheme;
  window._savedTheme = saved;
})();

/* ── SSE streaming via fetch ReadableStream ───────────────── */

/**
 * Stream tokens from an SSE endpoint into a target element.
 *
 * @param {string}      url        - POST endpoint URL
 * @param {object}      payload    - JSON body
 * @param {Element}     targetEl   - Element to append tokens to (pre/div)
 * @param {object}      [opts]
 * @param {boolean}     [opts.prose=false]    - render markdown after stream ends
 * @param {Function}    [opts.onDone]         - called with full text when done
 * @param {Function}    [opts.onCitation]     - called with citation text if present
 * @param {AbortSignal} [opts.signal]         - for cancellation
 * @returns {Promise<string>} full accumulated text
 */
async function streamSSE(url, payload, targetEl, opts = {}) {
  targetEl.textContent = "";
  targetEl.classList.remove("prose");

  let fullText = "";

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
      body: JSON.stringify(payload),
      signal: opts.signal,
    });

    if (!resp.ok) {
      const err = await resp.text();
      targetEl.textContent = `Error ${resp.status}: ${err}`;
      return "";
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // keep incomplete line

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const data = line.slice(6);
        if (data === "[DONE]") {
          reader.cancel();
          break;
        }
        if (data.startsWith("[CITATION]")) {
          if (opts.onCitation) opts.onCitation(data.slice(10));
          continue;
        }
        fullText += data;
        targetEl.textContent = fullText;
        targetEl.scrollTop = targetEl.scrollHeight;
      }
    }
  } catch (e) {
    if (e.name !== "AbortError") {
      targetEl.textContent = `Stream error: ${e.message}`;
    }
  }

  if (opts.prose && fullText) {
    targetEl.innerHTML = markdownToHtml(fullText);
    targetEl.classList.add("prose");
  }

  if (opts.onDone) opts.onDone(fullText);
  return fullText;
}

/* ── Minimal Markdown → HTML ──────────────────────────────── */
function markdownToHtml(text) {
  let html = text;

  // Escape HTML first
  html = html.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // Fenced code blocks
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre><code class="lang-${lang}">${code}</code></pre>`
  );
  // Inline code
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  // Headers
  html = html.replace(/^#### (.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");
  // Bold / italic
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  // List items
  html = html.replace(/^[-*] (.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>[\s\S]*?<\/li>\n?)+/g, m => `<ul>${m}</ul>`);
  // Paragraphs
  html = html
    .split(/\n{2,}/)
    .map(p => {
      p = p.trim();
      if (!p || p.startsWith("<")) return p;
      return `<p>${p.replace(/\n/g, "<br>")}</p>`;
    })
    .join("\n");

  return html;
}

/* ── CSRF helper ──────────────────────────────────────────── */
function getCsrfToken() {
  const el = document.querySelector("[name=csrfmiddlewaretoken]");
  if (el) return el.value;
  const cookie = document.cookie.split(";").find(c => c.trim().startsWith("csrftoken="));
  return cookie ? cookie.split("=")[1].trim() : "";
}

/* ── JSON POST helper ─────────────────────────────────────── */
async function postJSON(url, data) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
    body: JSON.stringify(data),
  });
  return resp.json();
}

/* ── Auto-resize textarea ─────────────────────────────────── */
function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 200) + "px";
}

document.querySelectorAll("textarea[data-autoresize]").forEach(el => {
  el.addEventListener("input", () => autoResize(el));
});

/* ── Drag-and-drop file zone ──────────────────────────────── */
function initDropZone(zoneEl, inputEl, labelEl) {
  zoneEl.addEventListener("click", () => inputEl.click());
  zoneEl.addEventListener("dragover", e => { e.preventDefault(); zoneEl.classList.add("drag-over"); });
  zoneEl.addEventListener("dragleave", () => zoneEl.classList.remove("drag-over"));
  zoneEl.addEventListener("drop", e => {
    e.preventDefault();
    zoneEl.classList.remove("drag-over");
    if (e.dataTransfer.files.length) {
      inputEl.files = e.dataTransfer.files;
      if (labelEl) labelEl.textContent = e.dataTransfer.files[0].name;
    }
  });
  inputEl.addEventListener("change", () => {
    if (inputEl.files.length && labelEl) labelEl.textContent = inputEl.files[0].name;
  });
}

/* ── Expose globals ───────────────────────────────────────── */
window.streamSSE    = streamSSE;
window.markdownToHtml = markdownToHtml;
window.getCsrfToken = getCsrfToken;
window.postJSON     = postJSON;
window.autoResize   = autoResize;
window.initDropZone = initDropZone;
