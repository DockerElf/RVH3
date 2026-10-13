import os, sys, base64, subprocess, threading
from pathlib import Path

def _request_foreground(folder):
    script=r'''
$ErrorActionPreference='Stop'
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class RoggleWindow {
 [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd,int nCmdShow);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}
'@
$target=[IO.Path]::GetFullPath($env:ROGGLE_EXPLORER_FOLDER).TrimEnd('\')
$shell=New-Object -ComObject Shell.Application
$deadline=[DateTime]::UtcNow.AddSeconds(4)
while ([DateTime]::UtcNow -lt $deadline) {
 $found=$false
 foreach ($window in @($shell.Windows())) {
  try {
   if ([IO.Path]::GetFileName([string]$window.FullName) -ine 'explorer.exe') {continue}
   $uri=[Uri]([string]$window.LocationURL)
   if (-not $uri.IsFile) {continue}
   $current=[IO.Path]::GetFullPath($uri.LocalPath).TrimEnd('\')
   if (-not [String]::Equals($target,$current,[StringComparison]::OrdinalIgnoreCase)) {continue}
   $handle=[IntPtr]([Int64]$window.HWND)
   if ([RoggleWindow]::IsIconic($handle)) {[void][RoggleWindow]::ShowWindow($handle,9)}
   [void][RoggleWindow]::SetForegroundWindow($handle)
   $found=$true;break
  } catch {}
 }
 if ($found) {break}
 Start-Sleep -Milliseconds 200
}
'''
    try:
        env=os.environ.copy();env['ROGGLE_EXPLORER_FOLDER']=str(folder)
        encoded=base64.b64encode(script.encode('utf-16-le')).decode('ascii')
        subprocess.run(['powershell.exe','-NoProfile','-STA','-EncodedCommand',encoded],env=env,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=8,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except (OSError,subprocess.SubprocessError):pass

def open_folder(folder):
    folder=Path(folder).resolve()
    if not folder.is_dir():raise FileNotFoundError('Folder not found: '+str(folder))
    if sys.platform!='win32':raise RuntimeError('Opening Explorer requires Windows.')
    os.startfile(str(folder))
    requested=False
    try:
        threading.Thread(target=_request_foreground,args=(folder,),daemon=True).start();requested=True
    except RuntimeError:pass
    return {'opened':True,'foreground_requested':requested}
