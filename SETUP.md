# Voice Assistant — Windows Setup

## Prerequisites

- Python 3.10+
- Windows 10/11
- Google Chrome
- Admin access (for some system features)

## Step 1 — Clone & Install

```powershell
git clone <your-repo-url>
cd voice-assistant
pip install -r requirements.txt
playwright install chromium
```

## Step 2 — Configure

```powershell
cp config.example.json config.json
```

Edit `config.json`:

```json
{
  "minimax_api_key": "YOUR_MINIMAX_KEY",
  "elevenlabs_api_key": "YOUR_ELEVENLABS_KEY",
  "elevenlabs_voice_id": "YOUR_VOICE_ID",
  "user_name": "YourName",
  "city": "Berlin",
  "workspace_path": "C:\\path\\to\\voice-assistant",
  "apps": ["C:\\Path\\To\\App1.exe", "C:\\Path\\To\\App2.exe"]
}
```

Or use environment variables (recommended — don't commit keys):

```powershell
$env:MINIMAX_API_KEY = "your-key"
$env:ELEVENLABS_API_KEY = "your-key"
$env:ELEVENLABS_VOICE_ID = "your-voice-id"
```

## Step 3 — Run

```powershell
python server.py
```

## Step 4 — Open Browser

Open Chrome → go to `http://localhost:8340`

Click the mic button and speak.

## Features

| Command | What happens |
|---------|-------------|
| "Search for AI news" | Opens browser, searches, summarizes |
| "Open google.com" | Navigates to URL |
| "What's on my screen?" | Captures and describes screen |
| Double-clap | Wake trigger — greets you |
| Any question | MiniMax LLM responds via ElevenLabs TTS |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "TTS failed" | Check ElevenLabs API key and voice ID |
| "Search failed" | Run `playwright install chromium` |
| Mic not working | Use Chrome — Web Speech API only works in Chrome |
| Clap not detected | Lower threshold in config.json: `"clap_threshold": 0.10` |
| Screen capture fails | Run as admin, ensure pywin32 installed |