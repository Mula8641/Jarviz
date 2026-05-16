# Install deps for Voice Assistant on Windows
# Run this in PowerShell as admin

Write-Host "Installing Python dependencies..."
pip install -r requirements.txt

Write-Host "Installing Playwright browsers..."
playwright install chromium

Write-Host "Done. Run: python server.py"