/* Voice Assistant — Modern Web UI */
"use strict";

// ── State ────────────────────────────────────────────────────────────────────
let ws = null;
let wsConnected = false;
let mode = "voice";
let listening = false;
let muted = false;
let recognition = null;
let audioCtx = null;
let conversationHistory = [];

// ── Elements ─────────────────────────────────────────────────────────────────
const orb = document.getElementById("orb");
const micBtn = document.getElementById("mic-btn");
const statusText = document.getElementById("status-text");
const wsDot = document.getElementById("ws-dot");
const wsStatusEl = document.getElementById("ws-status");
const liveBadge = document.getElementById("live-badge");
const transcriptPreview = document.getElementById("transcript-preview");
const conversationEl = document.getElementById("conversation");
const memoryListEl = document.getElementById("memory-list");

// ── WebSocket ─────────────────────────────────────────────────────────────────
function connectWS() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${proto}//${location.host}/ws`);

  ws.onopen = () => {
    wsConnected = true;
    wsDot.classList.remove("offline");
    wsStatusEl.textContent = "Connected";
    liveBadge.style.display = "inline-flex";
    statusText.textContent = "Ready — click mic or type to start";
    log("WS connected");
  };

  ws.onmessage = async (evt) => {
    const msg = JSON.parse(evt.data);
    handleMessage(msg);
  };

  ws.onclose = () => {
    wsConnected = false;
    wsDot.classList.add("offline");
    wsStatusEl.textContent = "Reconnecting...";
    liveBadge.style.display = "none";
    statusText.textContent = "Reconnecting...";
    setTimeout(connectWS, 3000);
  };

  ws.onerror = (e) => log("WS error: " + e);
}

function sendPayload(payload) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
  }
}

// ── Message Handler ────────────────────────────────────────────────────────────
function handleMessage(msg) {
  switch (msg.type) {
    case "processing":
      orb.className = "orb listening";
      statusText.textContent = "Thinking...";
      break;

    case "status":
      statusText.textContent = msg.text || "";
      break;

    case "audio":
      orb.className = "orb speaking";
      playAudio(msg.data).then(() => {
        orb.className = "orb";
        statusText.textContent = "Ready";
        // Continuous listening — restart mic after assistant finishes speaking
        if (mode === "voice" && !muted && recognition && !listening) {
          setTimeout(() => {
            listening = true;
            micBtn.classList.add("listening");
            orb.className = "orb listening";
            statusText.textContent = "Listening...";
            try { recognition.start(); } catch (_) {}
          }, 400);
        }
      });
      break;

    case "error":
      orb.className = "orb";
      statusText.textContent = "Error: " + (msg.message || "Unknown error");
      break;

    case "transcript":
      // Echo back to conversation
      if (msg.text) addMessage("user", msg.text);
      break;

    case "assistant_message":
      if (msg.text) {
        addMessage("assistant", msg.text);
        orb.className = "orb";
        statusText.textContent = "Ready";
        transcriptPreview.textContent = "";
      }
      break;

    case "pong":
      break;

    default:
      log("Unknown msg type: " + msg.type);
  }
}

// ── Audio Playback ────────────────────────────────────────────────────────────
function playAudio(b64Data) {
  return new Promise((resolve) => {
    (async () => {
      try {
        audioCtx = audioCtx || new AudioContext();
        const raw = Uint8Array.from(atob(b64Data), c => c.charCodeAt(0));
        const audioBuffer = await audioCtx.decodeAudioData(raw.buffer);
        const src = audioCtx.createBufferSource();
        src.buffer = audioBuffer;
        src.connect(audioCtx.destination);
        src.onended = () => resolve();
        src.start();
      } catch (e) {
        log("Audio play error: " + e.message);
        resolve();
      }
    })();
  });
}

// ── Speech Recognition ────────────────────────────────────────────────────────
function initSpeech() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    statusText.textContent = "Speech not supported — use text mode";
    return;
  }
  recognition = new SR();
  recognition.lang = "en-US";
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onresult = (event) => {
    const text = event.results[0][0].transcript.trim();
    if (!text) return;
    transcriptPreview.textContent = "You: " + text;
    sendPayload({ type: "transcript", text });
  };

  recognition.onerror = (e) => {
    if (e.error !== "aborted") {
      log("Speech error: " + e.error);
      statusText.textContent = "Mic error: " + e.error;
    }
  };

  recognition.onend = () => {
    if (listening) {
      listening = false;
      micBtn.classList.remove("listening");
      micBtn.classList.remove("muted");
      orb.className = "orb";
    }
  };
}

micBtn.addEventListener("mousedown", () => {
  if (!recognition || muted) return;
  listening = true;
  micBtn.classList.add("listening");
  orb.className = "orb listening";
  statusText.textContent = "Listening...";
  recognition.start();
});

micBtn.addEventListener("mouseup", () => {
  if (listening && recognition) {
    recognition.stop();
  }
});

micBtn.addEventListener("mouseleave", () => {
  if (listening && recognition) recognition.stop();
});

// ── Mode Switching ─────────────────────────────────────────────────────────────
document.getElementById("mode-voice-btn").addEventListener("click", () => setMode("voice"));
document.getElementById("mode-text-btn").addEventListener("click", () => setMode("text"));

function setMode(newMode) {
  mode = newMode;
  const voiceBtn = document.getElementById("mode-voice-btn");
  const textBtn = document.getElementById("mode-text-btn");
  const textPanel = document.getElementById("text-panel-main");

  if (newMode === "voice") {
    voiceBtn.classList.add("active");
    textBtn.classList.remove("active");
    textPanel.classList.remove("active");
    if (recognition) recognition.abort();
    transcriptPreview.textContent = "";
    statusText.textContent = "Click mic to speak";
  } else {
    voiceBtn.classList.remove("active");
    textBtn.classList.add("active");
    textPanel.classList.add("active");
    document.getElementById("text-input-main").focus();
    transcriptPreview.textContent = "";
    statusText.textContent = "Type your command";
  }
}

// ── Text Input ────────────────────────────────────────────────────────────────
document.getElementById("send-btn").addEventListener("click", sendTextInput);
document.getElementById("text-input-main").addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendTextInput();
});

function sendTextInput() {
  const input = document.getElementById("text-input-main");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  addMessage("user", text);
  transcriptPreview.textContent = "You: " + text;
  sendPayload({ type: "transcript", text });
}

// ── Quick Commands ─────────────────────────────────────────────────────────────
document.querySelectorAll(".cmd-chip").forEach(chip => {
  chip.addEventListener("click", () => {
    const cmd = chip.dataset.cmd;
    addMessage("user", cmd);
    transcriptPreview.textContent = "You: " + cmd;
    sendPayload({ type: "transcript", text: cmd });
  });
});

// ── Sidebar Navigation ─────────────────────────────────────────────────────────
document.querySelectorAll(".nav-item").forEach(item => {
  item.addEventListener("click", () => {
    const panel = item.dataset.panel;
    document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
    item.classList.add("active");
    document.querySelectorAll(".panel-content").forEach(p => p.classList.remove("active"));
    document.getElementById("panel-" + panel).classList.add("active");
  });
});

// ── Mute Toggle ─────────────────────────────────────────────────────────────────
document.getElementById("toggle-mute").addEventListener("click", function() {
  muted = !muted;
  this.classList.toggle("active", muted);
  if (muted && recognition) recognition.abort();
  micBtn.classList.toggle("muted", muted);
  statusText.textContent = muted ? "Muted" : "Ready";
});

// ── Mic toggle (Settings panel) ───────────────────────────────────────────────
document.getElementById("toggle-mic").addEventListener("click", function() {
  const enabled = !this.classList.contains("active");
  this.classList.toggle("active", enabled);
  if (!enabled && recognition) recognition.abort();
  micBtn.disabled = !enabled;
  statusText.textContent = enabled ? "Mic enabled" : "Mic disabled";
});

// ── Ollama toggle (Settings panel) ────────────────────────────────────────────
document.getElementById("toggle-ollama").addEventListener("click", function() {
  const enabled = !this.classList.contains("active");
  this.classList.toggle("active", enabled);
  fetch("/config/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ollama_base_url: enabled ? "http://localhost:11434" : "" }),
  }).catch(e => log("Ollama toggle error: " + e.message));
});

// ── Topbar clap toggle ────────────────────────────────────────────────────────
document.getElementById("clap-toggle")?.addEventListener("click", function() {
  const enabled = !this.classList.contains("active");
  this.classList.toggle("active", enabled);
  // Sync with Settings clap toggle
  const settingsToggle = document.getElementById("toggle-clap");
  if (settingsToggle) settingsToggle.classList.toggle("active", enabled);
  setTrigger("clap", enabled);
});

// ── Wake Trigger Toggles ───────────────────────────────────────────────────────
async function setTrigger(type, enabled) {
  try {
    const res = await fetch(`/triggers/${type}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled }),
    });
    const data = await res.json();
    if (data.status !== "ok") log(`Trigger ${type} toggle failed: ${data.message}`);
  } catch (e) {
    log(`Trigger ${type} error: ${e.message}`);
  }
}

document.getElementById("toggle-clap").addEventListener("click", function() {
  const enabled = !this.classList.contains("active");
  this.classList.toggle("active", enabled);
  setTrigger("clap", enabled);
});

document.getElementById("toggle-keyword").addEventListener("click", function() {
  const enabled = !this.classList.contains("active");
  this.classList.toggle("active", enabled);
  setTrigger("keyword", enabled);
});

// ── Browser Panel ──────────────────────────────────────────────────────────────
document.getElementById("browser-go-btn").addEventListener("click", () => {
  const input = document.getElementById("browser-url-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  const display = document.getElementById("browser-result");
  display.style.display = "block";
  display.textContent = "Navigating: " + text + "...";
  addMessage("user", text);
  sendPayload({ type: "transcript", text: "open " + text });
});

// ── Launch Panel ──────────────────────────────────────────────────────────────
document.getElementById("launch-all-btn").addEventListener("click", () => {
  sendPayload({ type: "transcript", text: "launch everything" });
  document.querySelectorAll(".launch-item").forEach(item => {
    item.classList.remove("pending");
    item.querySelector(".check").textContent = "●";
  });
  statusText.textContent = "Launching workspace...";
});

document.getElementById("snap-btn").addEventListener("click", () => {
  sendPayload({ type: "transcript", text: "snap windows" });
  statusText.textContent = "Snapping windows...";
});

// ── Memory Panel ──────────────────────────────────────────────────────────────
async function loadMemoryFacts() {
  try {
    const res = await fetch("/memory/facts");
    const data = await res.json();
    const facts = data.facts || {};
    const keys = Object.keys(facts);
    memoryListEl.innerHTML = "";
    if (keys.length === 0) {
      memoryListEl.innerHTML = '<div style="padding:1rem;text-align:center;color:var(--text-muted);font-size:0.85rem;">No facts stored yet. Have a conversation and they\'ll appear here.</div>';
      return;
    }
    keys.forEach(key => {
      const div = document.createElement("div");
      div.className = "msg assistant";
      div.style.cssText = "display:flex;justify-content:space-between;align-items:center;";
      div.innerHTML = `<span><strong>${key}:</strong> ${facts[key]}</span>`;
      memoryListEl.appendChild(div);
    });
  } catch (e) {
    log("Could not load memory facts: " + e.message);
  }
}

document.getElementById("clear-memory-btn").addEventListener("click", async () => {
  try {
    await fetch("/memory/clear", { method: "POST" });
    memoryListEl.innerHTML = '<div style="padding:1rem;text-align:center;color:var(--text-muted);font-size:0.85rem;">Memory cleared.</div>';
    statusText.textContent = "Memory cleared";
  } catch (e) {
    log("Clear memory failed: " + e.message);
  }
});

// Load facts when memory nav item is clicked
document.querySelectorAll(".nav-item").forEach(item => {
  if (item.dataset.panel === "memory") {
    item.addEventListener("click", loadMemoryFacts);
  }
});

// ── Conversation UI ─────────────────────────────────────────────────────────
function addMessage(role, text) {
  conversationHistory.push({ role, content: text });
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.textContent = text;

  const time = document.createElement("span");
  time.className = "time";
  time.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  div.appendChild(time);

  conversationEl.appendChild(div);
  conversationEl.scrollTop = conversationEl.scrollHeight;

  // Add to memory list display if it's from assistant
  if (role === "assistant" && memoryListEl.querySelector("div[style]")) {
    // Don't duplicate initial placeholder
  }
}

// ── Orb interaction states ────────────────────────────────────────────────────
micBtn.addEventListener("mouseenter", () => {
  if (!listening && !muted) orb.className = "orb";
});
micBtn.addEventListener("mouseleave", () => {
  if (!listening) orb.className = "orb";
});

// ── Utilities ──────────────────────────────────────────────────────────────────
function log(msg) { console.log("[Jarviz UI] " + msg); }

// ── Load saved config into Settings panel ─────────────────────────────────────
async function loadConfig() {
  try {
    const res = await fetch("/config");
    const cfg = await res.json();
    const map = {
      minimax_api_key:    "key-minimax",
      openai_api_key:     "key-openai",
      openai_model:       "key-openai-model",
      anthropic_api_key:  "key-anthropic",
      anthropic_model:    "key-anthropic-model",
      elevenlabs_api_key: "key-elevenlabs",
      elevenlabs_voice_id:"key-voice",
      user_name:          "cfg-username",
      city:               "cfg-city",
    };
    for (const [key, id] of Object.entries(map)) {
      const el = document.getElementById(id);
      if (el && cfg[key]) el.placeholder = cfg[key].includes("***") ? "••••••••" + cfg[key].slice(-3) : cfg[key];
    }
  } catch (e) {
    log("Could not load config: " + e.message);
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
initSpeech();
connectWS();
loadConfig();
log("UI initialized");
// ── API Key Saving ────────────────────────────────────────────────────────────
document.querySelectorAll(".save-key-btn").forEach(btn => {
  btn.addEventListener("click", async () => {
    const keyField = btn.dataset.key;
    const keyToId = {
      minimax_api_key:    "key-minimax",
      openai_api_key:     "key-openai",
      openai_model:       "key-openai-model",
      anthropic_api_key:  "key-anthropic",
      anthropic_model:    "key-anthropic-model",
      elevenlabs_api_key: "key-elevenlabs",
      elevenlabs_voice_id:"key-voice",
      user_name:          "cfg-username",
      city:               "cfg-city",
    };
    const input = document.getElementById(keyToId[keyField] || "");

    if (!input) return;
    const value = input.value.trim();

    const payload = { [keyField]: value };

    try {
      const res = await fetch("/config/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      const statusEl = document.getElementById("key-save-status");
      if (data.status === "ok") {
        statusEl.textContent = "Saved! Restart server to apply.";
        statusEl.classList.remove("error");
        btn.classList.add("saved");
        setTimeout(() => btn.classList.remove("saved"), 2000);
      } else {
        statusEl.textContent = "Failed to save config.";
        statusEl.classList.add("error");
      }
    } catch (e) {
      const statusEl = document.getElementById("key-save-status");
      statusEl.textContent = "Error: " + e.message;
      statusEl.classList.add("error");
    }
  });
});

// ── Reminders Panel ───────────────────────────────────────────────────────────
async function loadReminders() {
  const el = document.getElementById("reminders-list");
  if (!el) return;
  el.innerHTML = '<div style="padding:1rem;text-align:center;color:var(--text-muted);font-size:0.85rem;">Loading...</div>';
  try {
    const res = await fetch("/reminders");
    const data = await res.json();
    const reminders = data.reminders || [];
    el.innerHTML = "";
    if (reminders.length === 0) {
      el.innerHTML = '<div style="padding:1rem;text-align:center;color:var(--text-muted);font-size:0.85rem;">No upcoming reminders. Say "remind me in 10 minutes to check the oven."</div>';
      return;
    }
    reminders.forEach(r => {
      const div = document.createElement("div");
      div.className = "reminder-item";
      const dt = r.remind_at.replace("T", " ").slice(0, 16) + " UTC";
      div.innerHTML = `<span class="reminder-msg">${r.message}</span><span class="reminder-time">${dt}</span><button class="reminder-del" data-id="${r.id}" title="Dismiss">✕</button>`;
      div.querySelector(".reminder-del").addEventListener("click", async () => {
        await fetch(`/reminders/${r.id}`, { method: "DELETE" });
        loadReminders();
      });
      el.appendChild(div);
    });
  } catch (e) {
    log("Load reminders failed: " + e.message);
  }
}

document.querySelectorAll(".nav-item").forEach(item => {
  if (item.dataset.panel === "reminders") {
    item.addEventListener("click", loadReminders);
  }
});

// ── Response Style ────────────────────────────────────────────────────────────
let currentStyle = "normal";

function applyResponseStyleUI(style) {
  currentStyle = style;
  document.querySelectorAll(".style-pill").forEach(pill => {
    pill.classList.toggle("active", pill.dataset.style === style);
  });
}

function setResponseStyle(style) {
  applyResponseStyleUI(style);
  fetch("/config/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ response_style: style }),
  }).catch(e => log("Style save error: " + e.message));
}

document.querySelectorAll(".style-pill").forEach(pill => {
  pill.addEventListener("click", () => setResponseStyle(pill.dataset.style));
});

// ── Voice Tuning Sliders ──────────────────────────────────────────────────────
const sliderStability  = document.getElementById("slider-stability");
const sliderSimilarity = document.getElementById("slider-similarity");
const stabilityVal     = document.getElementById("stability-val");
const similarityVal    = document.getElementById("similarity-val");

sliderStability?.addEventListener("input", () => {
  if (stabilityVal) stabilityVal.textContent = parseFloat(sliderStability.value).toFixed(2);
});
sliderSimilarity?.addEventListener("input", () => {
  if (similarityVal) similarityVal.textContent = parseFloat(sliderSimilarity.value).toFixed(2);
});

document.getElementById("save-voice-tuning")?.addEventListener("click", async () => {
  const btn = document.getElementById("save-voice-tuning");
  try {
    const res = await fetch("/config/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        elevenlabs_stability: parseFloat(sliderStability.value),
        elevenlabs_similarity_boost: parseFloat(sliderSimilarity.value),
      }),
    });
    const data = await res.json();
    if (data.status === "ok" && btn) {
      const orig = btn.textContent;
      btn.textContent = "Saved!";
      btn.style.background = "var(--success)";
      setTimeout(() => { btn.textContent = orig; btn.style.background = ""; }, 2000);
    }
  } catch (e) { log("Voice tuning save error: " + e.message); }
});

// ── System Prompt Editor ──────────────────────────────────────────────────────
document.getElementById("save-system-prompt")?.addEventListener("click", async () => {
  const text = document.getElementById("system-prompt-input")?.value || "";
  const statusEl = document.getElementById("prompt-save-status");
  try {
    const res = await fetch("/config/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ system_prompt_override: text || "__clear__" }),
    });
    const data = await res.json();
    if (statusEl) statusEl.textContent = data.status === "ok" ? "Saved!" : "Failed.";
  } catch (e) { if (statusEl) statusEl.textContent = "Error: " + e.message; }
  if (statusEl) setTimeout(() => { statusEl.textContent = ""; }, 3000);
});

document.getElementById("clear-system-prompt")?.addEventListener("click", async () => {
  const textarea = document.getElementById("system-prompt-input");
  if (textarea) textarea.value = "";
  const statusEl = document.getElementById("prompt-save-status");
  try {
    const res = await fetch("/config/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ system_prompt_override: "__clear__" }),
    });
    const data = await res.json();
    if (statusEl) statusEl.textContent = data.status === "ok" ? "Cleared — using default prompt." : "Failed.";
  } catch (e) { if (statusEl) statusEl.textContent = "Error: " + e.message; }
  if (statusEl) setTimeout(() => { statusEl.textContent = ""; }, 3000);
});

// ── Tool Toggles ──────────────────────────────────────────────────────────────
const ALL_TOOLS = [
  "search_web", "open_url", "describe_screen", "get_memory_facts",
  "remember_fact", "launch_app", "read_page_content", "get_weather",
  "remind_me", "list_reminders", "read_clipboard", "write_clipboard",
];
let enabledTools = new Set(ALL_TOOLS);

function renderToolGrid(enabled) {
  const grid = document.getElementById("tool-grid");
  if (!grid) return;
  grid.innerHTML = "";
  ALL_TOOLS.forEach(name => {
    const label = name.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    const item  = document.createElement("div");
    item.className = "tool-toggle-item";
    const isOn = enabled.has(name);
    item.innerHTML = `<button class="toggle ${isOn ? "active" : ""}" data-tool="${name}"></button><span>${label}</span>`;
    item.querySelector(".toggle").addEventListener("click", function() {
      this.classList.toggle("active");
      if (this.classList.contains("active")) enabledTools.add(this.dataset.tool);
      else enabledTools.delete(this.dataset.tool);
    });
    grid.appendChild(item);
  });
}

document.getElementById("save-tools")?.addEventListener("click", async () => {
  const payload = enabledTools.size === ALL_TOOLS.length ? [] : [...enabledTools];
  const statusEl = document.getElementById("tools-save-status");
  try {
    const res = await fetch("/config/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled_tools: payload }),
    });
    const data = await res.json();
    if (statusEl) statusEl.textContent = data.status === "ok" ? "Saved!" : "Failed.";
  } catch (e) { if (statusEl) statusEl.textContent = "Error: " + e.message; }
  if (statusEl) setTimeout(() => { statusEl.textContent = ""; }, 3000);
});

// ── Keyboard Shortcuts ────────────────────────────────────────────────────────
document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
  if (e.code === "Space") {
    e.preventDefault();
    if (mode !== "voice" || muted || !recognition) return;
    if (listening) {
      recognition.stop();
    } else {
      listening = true;
      micBtn.classList.add("listening");
      orb.className = "orb listening";
      statusText.textContent = "Listening...";
      try { recognition.start(); } catch (_) {}
    }
  }
  if (e.code === "Escape" && listening && recognition) {
    recognition.abort();
    listening = false;
    micBtn.classList.remove("listening");
    orb.className = "orb";
    statusText.textContent = "Cancelled";
  }
});

// ── Export Conversation ────────────────────────────────────────────────────────
document.getElementById("export-btn")?.addEventListener("click", () => {
  if (!conversationHistory.length) return;
  const lines = conversationHistory.map(m => `[${m.role.toUpperCase()}]\n${m.content}`);
  const text  = `Jarviz Conversation — ${new Date().toLocaleString()}\n${"─".repeat(40)}\n\n${lines.join("\n\n")}`;
  const blob  = new Blob([text], { type: "text/plain" });
  const a     = document.createElement("a");
  a.href      = URL.createObjectURL(blob);
  a.download  = `jarviz-${Date.now()}.txt`;
  a.click();
  URL.revokeObjectURL(a.href);
});

// ── Load extended config (style, sliders, prompt, tools) ─────────────────────
async function loadConfigExtended() {
  try {
    const res = await fetch("/config");
    const cfg = await res.json();

    if (cfg.response_style && ["brief","normal","detailed"].includes(cfg.response_style)) {
      applyResponseStyleUI(cfg.response_style);
    }
    if (sliderStability && cfg.elevenlabs_stability !== undefined) {
      sliderStability.value = cfg.elevenlabs_stability;
      if (stabilityVal) stabilityVal.textContent = parseFloat(cfg.elevenlabs_stability).toFixed(2);
    }
    if (sliderSimilarity && cfg.elevenlabs_similarity_boost !== undefined) {
      sliderSimilarity.value = cfg.elevenlabs_similarity_boost;
      if (similarityVal) similarityVal.textContent = parseFloat(cfg.elevenlabs_similarity_boost).toFixed(2);
    }
    const promptEl = document.getElementById("system-prompt-input");
    if (promptEl && cfg.system_prompt_override && cfg.system_prompt_override !== "__clear__") {
      promptEl.value = cfg.system_prompt_override;
    }
    const configEnabled = cfg.enabled_tools;
    enabledTools = Array.isArray(configEnabled) && configEnabled.length > 0
      ? new Set(configEnabled)
      : new Set(ALL_TOOLS);
    renderToolGrid(enabledTools);
  } catch (e) {
    log("Extended config load error: " + e.message);
    renderToolGrid(enabledTools);
  }
}

loadConfigExtended();
