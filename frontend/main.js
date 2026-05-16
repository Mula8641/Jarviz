/* Voice Assistant — Frontend: WebSocket + Web Speech API */
let ws = null;
let recognition = null;
let muted = false;
let audioCtx = null;

const status = document.getElementById("status");
const micBtn = document.getElementById("mic-btn");
const muteBtn = document.getElementById("mute-btn");
const transcriptDisplay = document.getElementById("transcript-display");

function connect() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${protocol}//${location.host}/ws`);

  ws.onopen = () => {
    status.textContent = "Connected — click mic to speak";
    micBtn.disabled = false;
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

/* Web Speech API — mic to text */
function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    status.textContent = "Speech recognition not supported in this browser";
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
    sendTranscript(text);
  };

  recognition.onerror = (e) => log("Speech error: " + e.error);
  recognition.onend = () => {
    if (!muted) micBtn.classList.remove("active");
  };
}

function startListening() {
  if (!recognition) return;
  muted = false;
  recognition.start();
  micBtn.classList.add("active");
  status.textContent = "Listening...";
}

function sendTranscript(text) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "transcript", text }));
  }
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
  if (recognition.recording) {
    recognition.abort();
  } else {
    startListening();
  }
});

/* Init */
initSpeechRecognition();
connect();