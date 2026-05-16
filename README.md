# Jarviz Voice Assistant

Personal AI voice assistant for Windows. Speak, listen, control your browser and screen.

## Stack

- **Brain:** MiniMax LLM + Vision (auto-fallback to Ollama)
- **Voice:** ElevenLabs TTS + Web Speech API
- **Automation:** Playwright
- **Backend:** FastAPI + WebSockets
- **Platform:** Windows

---

## 🚀 One-Command Setup (克隆并自动启动)

Open **PowerShell** or **Command Prompt** and run:

```powershell
git clone https://github.com/Mula8641/Jarviz.git && cd Jarviz && launch-everything.bat
```

That's it. It will:
1. Clone the repo
2. Create a virtual environment
3. Install all dependencies
4. Download Chromium
5. Start the server
6. Open **http://localhost:8340** in your browser

> First run only: add your API keys in the Settings UI (⚙️ tab) after the server starts. Restart after saving.

---

## Features

- 🎤 **Voice in / Voice out** — push-to-talk or continuous wake
- 👀 **Screen vision** — describe what's on your screen
- 🌐 **Browser automation** — search, open, interact with sites
- 🔔 **Clap wake trigger** — clap hands to activate
- 🎵 **Keyword wake** — say "Hey Assistant" to activate (configurable)
- 💬 **Cross-session memory** — remembers facts about you over time
- ⌨️ **Text input mode** — type commands when voice isn't convenient
- 🤖 **Ollama fallback** — works offline when MiniMax rate limits
- 🚀 **One-trigger launch** — launch everything with one button
- ⚙️ **Settings UI** — add API keys directly from the browser

## Requirements

- Python 3.10+ (add to PATH during install)
- Windows 10/11
- Google Chrome
- MiniMax API key
- ElevenLabs API key

## Troubleshooting

**Python not found?** Download from [python.org](https://python.org) — check "Add Python to PATH" during install.

**Mic not working?** Make sure Chrome has microphone permissions. Allow it when the browser asks.

**TTS not playing?** Check your system volume and that ElevenLabs API key is set in Settings → ⚙️ → Save → restart server.

**"Launch Everything" stuck?** Run PowerShell as Administrator and try again.