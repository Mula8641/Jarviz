/* Voice Assistant — Frontend: WebSocket + Web Speech API + Text Input */
let ws = null;
let recognition = null;
let muted = false;
let audioCtx = null;
let mode = "voice";  // "voice" | "text"

const status = document.getElementById("status");
const micBtn = document.getElementById("mic-btn");
const muteBtn = document.getElementById("mute-btn");
const modeBtn = document.getElementById("mode-btn");
const modeBtnText = document.getElementById("mode-btn-text");
const textPanel = document.getElementById("text-panel");
const textInput = document.getElementById("text-input");
const textSendBtn = document.getElementById("text-send-btn");
const transcriptDisplay = document.getElementById("transcript-display");

function connect() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${protocol}//${location.host}/ws`);

  ws.onopen = () => {
    status.textContent = mode === "voice"
      ? "Connected — click mic to speak"
      : "Connected — type your command";
    micBtn.disabled = mode !== "voice";
    muteBtn.disabled = false;
    log("WebSocket connected");
  };

  ws.onmessage = async (evt) => {
    const msg = JSON.parse(evt.data);
    if (msg.type === "ack") {
      log(`Sent: ${JSON.stringify(msg.data)}`);
    } else if (msg.type === "audio") {
      await playAudio(msg.data);
    } else if (msg.type === "transcript") {
      transcriptDisplay.textContent = msg.text;
    } else if (msg.type === "processing") {
      status.textContent = "Processing...";
    } else if (msg.type === "status") {
      status.textContent = msg.text;
    } else if (msg.type === "error") {
      status.textContent = "Error: " + msg.message;
    }
  };

  ws.onclose = () => {
    status.textContent = "Disconnected — reconnecting...";
    micBtn.disabled = true;
    setTimeout(connect, 3000);
  };

  ws.onerror = (err) => log("WS error: " + err);
}

function log(msg) {
  console.log("[Voice] " + msg);
  status.textContent = msg;
}

/* Mode switching */
function setMode(newMode) {
  mode = newMode;
  if (newMode === "voice") {
    modeBtn.classList.add("active");
    modeBtnText.classList.remove("active");
    textPanel.classList.add("hidden");
    micBtn.style.display = "";
    transcriptDisplay.textContent = "";
    if (ws && ws.readyState === WebSocket.OPEN) {
      status.textContent = "Click mic to speak";
    }
  } else {
    modeBtn.classList.remove("active");
    modeBtnText.classList.add("active");
    textPanel.classList.remove("hidden");
    textInput.focus();
    if (recognition) recognition.abort();
    micBtn.style.display = "none";
    transcriptDisplay.textContent = "";
    if (ws && ws.readyState === WebSocket.OPEN) {
      status.textContent = "Type your command and press Enter";
    }
  }
}

modeBtn.addEventListener("click", () => setMode("voice"));
modeBtnText.addEventListener("click", () => setMode("text"));

/* Text input sending */
function sendText(text) {
  if (!text.trim()) return;
  log("Text input: " + text);
  transcriptDisplay.textContent = text;
  sendPayload({ type: "transcript", text });
}

function sendPayload(payload) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
  }
}

textSendBtn.addEventListener("click", () => {
  sendText(textInput.value);
  textInput.value = "";
});

textInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    sendText(textInput.value);
    textInput.value = "";
  }
});

/* Web Speech API — mic to text */
function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    status.textContent = "Speech recognition not supported — use text mode";
    return;
  }

  recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onresult = (event) => {
    const text = event.results[0][0].transcript;
    log("Heard: " + text);
    transcriptDisplay.textContent = text;
    sendPayload({ type: "transcript", text });
  };

  recognition.onerror = (e) => log("Speech error: " + e.error);
  recognition.onend = () => {
    if (!muted && mode === "voice") micBtn.classList.remove("active");
  };
}

function startListening() {
  if (!recognition || mode !== "voice") return;
  muted = false;
  recognition.start();
  micBtn.classList.add("active");
  status.textContent = "Listening...";
}

function sendTranscript(text) {
  sendPayload({ type: "transcript", text });
}

/* Audio playback from base64 */
async function playAudio(base64Data) {
  try {
    audioCtx = audioCtx || new AudioContext();
    const buf = Uint8Array.from(atob(base64Data), (c) => c.charCodeAt(0));
    const ab = audioCtx.createBuffer(1, buf.length, 22050);
    ab.getChannelData(0).set(new Float32Array(buf.map((b) => (b - 128) / 128)));
    const src = audioCtx.createBufferSource();
    src.buffer = ab;
    src.connect(audioCtx.destination);
    src.start();
  } catch (e) {
    log("Audio play error: " + e);
  }
}

/* Mute toggle */
muteBtn.addEventListener("click", () => {
  muted = !muted;
  muteBtn.textContent = muted ? "Unmute 🎤" : "Mute 🔇";
  muteBtn.classList.toggle("mute-off", !muted);
  muteBtn.classList.toggle("active", muted);
  if (muted && recognition) recognition.abort();
});

/* Mic button — push to talk */
micBtn.addEventListener("click", () => {
  if (!recognition) return;
  if (recognition.recording || micBtn.classList.contains("active")) {
    recognition.abort();
    micBtn.classList.remove("active");
  } else {
    startListening();
  }
});

/* Init */
initSpeechRecognition();
connect();
setMode("voice");