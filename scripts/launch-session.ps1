# Launch all workspace apps from config
$apps = @(
    "C:\Path\To\App1.exe",
    "C:\Path\To\App2.exe"
)
# Loaded from config.json at runtime — this is a template

foreach ($app in $apps) {
    if (Test-Path $app) {
        Start-Process $app
        Write-Host "Launched: $app"
    } else {
        Write-Host "Not found: $app"
    }
}