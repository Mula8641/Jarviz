# Snap all open windows into screen quadrants using Win32 API
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")]
    public static extern bool MoveWindow(IntPtr hWnd, int x, int y, int w, int h, bool repaint);
    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder lpString, int nMaxCount);
    [DllImport("user32.dll")]
    public static extern IntPtr GetShellWindow();
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
}
"@

$shell = [Win32]::GetShellWindow()
$screens = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$halfW = $screens.Width / 2
$halfH = $screens.Height / 2

$windows = @()

[Win32]::EnumWindows({
    param($hWnd, $lParam)
    if ([Win32]::IsWindowVisible($hWnd) -and $hWnd -ne $shell) {
        $sb = New-Object System.Text.StringBuilder 256
        [Win32]::GetWindowText($hWnd, $sb, 256) | Out-Null
        $title = $sb.ToString()
        if ($title.Length -gt 0) {
            $windows += $hWnd
        }
    }
    return $true
} , [IntPtr]::Zero)

$slots = @(
    @{x=0; y=0; w=$halfW; h=$halfH},          # top-left
    @{x=$halfW; y=0; w=$halfW; h=$halfH},     # top-right
    @{x=0; y=$halfH; w=$halfW; h=$halfH},     # bottom-left
    @{x=$halfW; y=$halfH; w=$halfW; h=$halfH} # bottom-right
)

for ($i = 0; $i -lt [Math]::Min($windows.Count, 4); $i++) {
    $slot = $slots[$i]
    [Win32]::MoveWindow($windows[$i], $slot.x, $slot.y, $slot.w, $slot.h, $true) | Out-Null
    Write-Host "Snapped window $($i+1) to $($slot.x),$($slot.y) (${slot.w}x${slot.h})"
}