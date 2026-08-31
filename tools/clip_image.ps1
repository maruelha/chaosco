# Saves the image currently in the Windows clipboard to a PNG file and prints
# its path — the way a screenshot gets to Claude without saving it by hand.
#
#   Win+Shift+S, then tell Claude "grab the clipboard".
#
# By hand (the -ExecutionPolicy flag is needed because script execution is
# disabled on this machine; it applies to this ONE process, nothing is
# changed system-wide):
#
#   powershell -ExecutionPolicy Bypass -sta -NoProfile -File tools\clip_image.ps1
#
# Images only. Copied TEXT and a file copied in Explorer are not clipboard
# images — for a file, just give Claude its path instead.
# Documentation: docs/dev_tools.md
param([string]$OutDir = (Join-Path $env:TEMP "claude_clip"))

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$img = [System.Windows.Forms.Clipboard]::GetImage()
if ($null -eq $img) {
    if ([System.Windows.Forms.Clipboard]::ContainsFileDropList()) {
        Write-Output "NO IMAGE IN CLIPBOARD - the clipboard holds FILE(S). Give Claude the path instead:"
        foreach ($f in [System.Windows.Forms.Clipboard]::GetFileDropList()) { Write-Output "  $f" }
    } elseif ([System.Windows.Forms.Clipboard]::ContainsText()) {
        Write-Output "NO IMAGE IN CLIPBOARD - the clipboard holds TEXT. Paste it into the chat directly."
    } else {
        Write-Output "NO IMAGE IN CLIPBOARD - take the screenshot with Win+Shift+S first."
    }
    exit 1
}
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
$path = Join-Path $OutDir ("clip_{0}.png" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
$img.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
Write-Output "$path  ($($img.Width)x$($img.Height))"
