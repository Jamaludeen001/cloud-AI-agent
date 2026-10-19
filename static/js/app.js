// static/js/app.js
(function () {
  "use strict";

  function $(id) { return document.getElementById(id); }

  var state = {
    sessionId: sessionStorage.getItem("sessionId") || null,
    hasData: false,
    currentMode: "url",
  };

  // ── Ensure Session exists ──
  function ensureSession() {
    if (state.sessionId) return Promise.resolve(state.sessionId);
    
    return fetch("/api/sessions", { method: "POST" })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        state.sessionId = data.session_id;
        sessionStorage.setItem("sessionId", data.session_id);
        return state.sessionId;
      });
  }

  // ── Panel templates ──
  var PANEL_HTML = {
    url: '<label for="url-input">API URL</label>' +
         '<input id="url-input" type="text" placeholder="https://api.github.com/repos/vercel/next.js/issues?per_page=20"/>' +
         '<label for="limit-url">Text limit</label>' +
         '<input id="limit-url" type="number" value="20000" min="1000" max="50000"/>',

    file: '<label for="file-input">File (.txt, .md, .json, .csv, .html, .xml, .yaml)</label>' +
          '<input id="file-input" type="file" accept=".txt,.md,.csv,.json,.html,.xml,.yaml,.yml,.log,.pdf"/>' +
          '<label for="limit-file">Text limit</label>' +
          '<input id="limit-file" type="number" value="20000" min="1000" max="50000"/>',

    paste: '<label for="paste-input">Paste your text</label>' +
           '<textarea id="paste-input" rows="10" placeholder="Paste any text..."></textarea>' +
           '<label for="limit-paste">Text limit</label>' +
           '<input id="limit-paste" type="number" value="20000" min="1000" max="50000"/>',
  };

  function setActivePanel(mode) {
    document.querySelectorAll(".tab-btn").forEach(function (btn) {
      btn.classList.toggle("active", btn.dataset.mode === mode);
    });
    var container = $("panel-container");
    if (container) {
      container.className = "tab-panel";
      container.innerHTML = PANEL_HTML[mode] || PANEL_HTML.url;
    }
    state.currentMode = mode;
  }

  function addMessage(text, role, extra) {
    var cw = $("chat-window");
    if (!cw) return null;
    var empty = $("chat-empty");
    if (empty) empty.remove();

    var div = document.createElement("div");
    div.className = ("chat-msg " + role + " " + (extra || "")).trim();
    div.textContent = text;
    cw.appendChild(div);
    cw.scrollTop = cw.scrollHeight;
    return div;
  }

  function addSources(container, sources) {
    if (!sources || !sources.length) return;
    var details = document.createElement("details");
    details.className = "chat-sources";
    details.innerHTML = "<summary>" + sources.length + " source chunk" +
                        (sources.length > 1 ? "s" : "") + "</summary>";
    sources.forEach(function (s, i) {
      var pre = document.createElement("pre");
      var score = s.score != null ? Number(s.score).toFixed(3) : "n/a";
      pre.textContent = "[" + (i + 1) + "] score=" + score + "\n" + (s.chunk || "");
      details.appendChild(pre);
    });
    container.appendChild(details);
    var cw = $("chat-window");
    if (cw) cw.scrollTop = cw.scrollHeight;
  }

  function updateDataStatus(label) {
    var wrap = $("data-status");
    var val  = $("data-status-value");
    if (!wrap) return;
    if (label) {
      state.hasData = true;
      if (val) val.textContent = label;
      wrap.hidden = false;
    } else {
      state.hasData = false;
      wrap.hidden = true;
    }
  }

  function sendMessage() {
    var input   = $("chat-input");
    var sendBtn = $("chat-send");
    if (!input) return;

    var question = input.value.trim();
    if (!question) return;

    input.value = "";
    addMessage(question, "user");
    var thinking = addMessage("Thinking…", "bot", "thinking");
    if (!thinking) return;

    if (sendBtn) sendBtn.disabled = true;

    ensureSession()
      .then(function(sid) {
        return fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sid, question: question }),
        });
      })
      .then(function (res) {
        return res.json().then(function (d) { return { ok: res.ok, data: d }; });
      })
      .then(function (r) {
        if (!r.ok) {
          thinking.className = "chat-msg bot error";
          thinking.textContent = r.data.detail || "Request failed.";
          return;
        }
        thinking.className = "chat-msg bot";
        thinking.textContent = r.data.answer || "(no answer)";
        if (r.data.sources && r.data.sources.length) {
          addSources(thinking, r.data.sources);
        }
      })
      .catch(function (e) {
        thinking.className = "chat-msg bot error";
        thinking.textContent = "Network error: " + e.message;
      })
      .finally(function () {
        if (sendBtn) sendBtn.disabled = false;
        if (input)   input.focus();
      });
  }

  function openModal() {
    var modal = $("attach-modal");
    if (modal) modal.hidden = false;
    var status = $("attach-status");
    if (status) {
      status.textContent = "";
      status.className = "status-line";
    }
    setActivePanel("url");
  }

  function closeModal() {
    var modal = $("attach-modal");
    if (modal) modal.hidden = true;
  }

  function submitData() {
    var btn    = $("attach-submit");
    var status = $("attach-status");
    if (status) {
      status.textContent = "";
      status.className = "status-line";
    }

    if (btn) { btn.disabled = true; btn.classList.add("loading"); }
    if (status) status.textContent = "Loading and indexing...";

    ensureSession()
      .then(function(sid) {
        if (state.currentMode === "url") {
          var urlInput   = $("url-input");
          var limitInput = $("limit-url");
          var url = urlInput ? urlInput.value.trim() : "";
          if (!url) throw new Error("URL is required.");
          return fetch("/api/session/url", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: sid,
              url: url,
              text_limit: parseInt(limitInput ? limitInput.value : "20000", 10) || 20000,
            }),
          });
        } else if (state.currentMode === "file") {
          var fileInput = $("file-input");
          var fileLimit = $("limit-file");
          var file = fileInput && fileInput.files ? fileInput.files[0] : null;
          if (!file) throw new Error("File is required.");
          var fd = new FormData();
          fd.append("session_id", sid);
          fd.append("file", file);
          fd.append("text_limit", parseInt(fileLimit ? fileLimit.value : "20000", 10) || 20000);
          return fetch("/api/session/file", { method: "POST", body: fd });
        } else {
          var pasteInput = $("paste-input");
          var pasteLimit = $("limit-paste");
          var text = pasteInput ? pasteInput.value.trim() : "";
          if (!text) throw new Error("Text is required.");
          return fetch("/api/session/paste", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: sid,
              text: text,
              text_limit: parseInt(pasteLimit ? pasteLimit.value : "20000", 10) || 20000,
            }),
          });
        }
      })
      .then(function (res) {
        return res.json().then(function (d) { return { ok: res.ok, data: d }; });
      })
      .then(function (r) {
        if (!r.ok) throw new Error(r.data.detail || "Failed");
        if (status) {
          status.textContent = "Ready. " + r.data.chunk_count + " chunks loaded.";
          status.className = "status-line ok";
        }
        updateDataStatus(r.data.chunk_count + " chunks · " + r.data.source_label);
        setTimeout(function () {
          closeModal();
          addMessage(
            "Data attached: " + r.data.source_label +
            " (" + r.data.chunk_count + " chunks). You can now ask questions about it.",
            "bot"
          );
        }, 800);
      })
      .catch(function (e) {
        if (status) {
          status.textContent = e.message;
          status.className = "status-line error";
        }
      })
      .finally(function () {
        if (btn) { btn.disabled = false; btn.classList.remove("loading"); }
      });
  }

  function removeData() {
    var sessionId = state.sessionId;
    function afterRemoval() {
      state.hasData = false;
      updateDataStatus(null);
      addMessage("Data removed. You can attach new data anytime.", "bot");
    }

    if (!sessionId) { afterRemoval(); return; }

    fetch("/api/session/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, url: "" }),
    })
    .then(function (res) {
      if (!res.ok) {
        return res.json().then(function (d) { throw new Error(d.detail || "Remove failed"); });
      }
      return res.json();
    })
    .then(afterRemoval)
    .catch(function (e) {
      addMessage("Could not remove data: " + e.message, "bot", "error");
    });
  }

  function safeListen(id, event, handler) {
    var el = $(id);
    if (el) el.addEventListener(event, handler);
  }

  safeListen("chat-send",      "click", sendMessage);
  safeListen("attach-btn",     "click", openModal);
  safeListen("attach-cancel",  "click", closeModal);
  safeListen("attach-submit",  "click", submitData);
  safeListen("clear-data-btn", "click", removeData);

  (function () {
    var input = $("chat-input");
    if (input) {
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") sendMessage();
      });
      input.focus();
    }
  })();

  document.querySelectorAll(".tab-btn").forEach(function (btn) {
    btn.addEventListener("click", function () { setActivePanel(btn.dataset.mode); });
  });

  setActivePanel("url");
})();