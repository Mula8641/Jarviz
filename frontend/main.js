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
      }
      break;

    case "pong":
      break;

    default:
      log("Unknown msg type: " + msg.type);
  }
}

// ── Audio Playback ────────────────────────────────────────────────────────────
async function playAudio(b64Data) {
  try {
    audioCtx = audioCtx || new AudioContext();
    const raw = Uint8Array.from(atob(b64Data), c => c.charCodeAt(0));

    // Detect format — ElevenLabs returns mp3, decode via AudioContext
    const audioBuffer = await audioCtx.decodeAudioData(raw.buffer);
    const src = audioCtx.createBufferSource();
    src.buffer = audioBuffer;
    src.connect(audioCtx.destination);
    src.start();
  } catch (e) {
    log("Audio play error: " + e.message);
  }
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

document.getElementById("mute-btn-sidebar")?.addEventListener("click", () => {
  muted = !muted;
  const btn = document.getElementById("mute-btn-sidebar");
  if (btn) btn.classList.toggle("active", muted);
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
document.getElementById("clear-memory-btn").addEventListener("click", () => {
  sendPayload({ type: "transcript", text: "clear memory" });
  statusText.textContent = "Memory cleared";
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

// ── Init ──────────────────────────────────────────────────────────────────────
initSpeech();
connectWS();
log("UI initialized");