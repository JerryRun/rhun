#!/usr/bin/python3
"""Real Windows keyboard -> WSLg -> rhun -> private Fcitx -> saved UTF-8.

Only the unique test window is focused/maximized; no system IME configuration.
Run with --live to allow native GUI interaction. Uses bundled private input.
"""
import base64
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
PS = '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'

if '--live' not in sys.argv:
    raise SystemExit('Use /usr/bin/python3 tests/fcitx-live.py --live')

with tempfile.TemporaryDirectory(prefix='rhun-fcitx-live-') as tmp:
    work = Path(tmp)
    filename = 'RHUN_IME_' + uuid.uuid4().hex + '.txt'
    doc = work/filename
    doc.write_text('')
    config = work/'config/rhun/config'
    config.parent.mkdir(parents=True)
    config.write_text('[ui]\nsidebar=false\nagents_panel=false\n'
        'font=/mnt/c/Windows/Fonts/msyh.ttc\n'
        '[editor]\nchinese_input=true\nchinese_follow_host=false\nfallback_font=/mnt/c/Windows/Fonts/msyh.ttc\n'
        '[files]\nrestore_session=false\nrestore_project=false\n'
        '[updates]\ncheck=false\n[git]\nenabled=false\n')
    env = dict(os.environ, RHUN_BACKEND='wayland', RHUN_WSL_WINDOW_FIX='1',
        XDG_CONFIG_HOME=str(work/'config'), XDG_STATE_HOME=str(work/'state'))
    control = work/'control'
    proc = subprocess.Popen([str(ROOT/'build/rhun'), '--wait', str(work),
        str(doc), '--control', str(control)], env=env, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    client = socket.socket(socket.AF_UNIX)
    client.settimeout(12)
    try:
        deadline = time.monotonic()+15
        while not control.exists():
            assert proc.poll() is None, proc.communicate()
            assert time.monotonic() < deadline, 'control socket missing'
            time.sleep(.05)
        client.connect(str(control))
        reader = client.makefile('rb')

        def command(line):
            client.sendall((line+'\n').encode())
            out = []
            while True:
                data = reader.readline()
                if data == b'ok\n':
                    return b''.join(out).decode()
                assert data not in (b'', b'error\n'), (line, data)
                out.append(data)

        setup = r'''
$ErrorActionPreference='Stop'
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class IMETest {
 public delegate bool CB(IntPtr h,IntPtr p);
 [DllImport("user32.dll")] public static extern bool EnumWindows(CB cb,IntPtr p);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h,StringBuilder b,int n);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int n);
 [DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr h);
 [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code,uint type);
 [StructLayout(LayoutKind.Sequential)] public struct Point {public int X,Y;}
 [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h,ref Point p);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr extra);
 [DllImport("user32.dll")] public static extern void keybd_event(byte vk,byte scan,uint flags,UIntPtr extra);
}
'@
$script:target=[IntPtr]::Zero
$find=[IMETest+CB]{param($h,$p)
 $s=New-Object System.Text.StringBuilder 4096
 [void][IMETest]::GetWindowText($h,$s,4096)
 if($s.ToString().Contains('__FILE__') -and -not $s.ToString().Contains('[rhun-wsl-')) {$script:target=$h}
 return $true
}
$until=[DateTime]::UtcNow.AddSeconds(12)
do {
 [void][IMETest]::EnumWindows($find,[IntPtr]::Zero)
 if([DateTime]::UtcNow -gt $until){throw 'test window handshake timed out'}
 Start-Sleep -Milliseconds 100
} while($script:target -eq [IntPtr]::Zero)
$h=$script:target
[void][IMETest]::SetForegroundWindow($h)
Start-Sleep -Milliseconds 300
function Key([byte]$vk) {
 if([IMETest]::GetForegroundWindow() -ne $h){throw 'test window lost focus; refusing global key'}
 [IMETest]::keybd_event($vk,[byte][IMETest]::MapVirtualKey($vk,0),0,[UIntPtr]::Zero)
 Start-Sleep -Milliseconds 35
 [IMETest]::keybd_event($vk,[byte][IMETest]::MapVirtualKey($vk,0),2,[UIntPtr]::Zero)
 Start-Sleep -Milliseconds 35
}
function CtrlKey([byte]$vk) {
 if([IMETest]::GetForegroundWindow() -ne $h){throw 'test window lost focus'}
 [IMETest]::keybd_event(0x11,0x1D,0,[UIntPtr]::Zero)
 try {Key $vk} finally {[IMETest]::keybd_event(0x11,0x1D,2,[UIntPtr]::Zero)}
 Start-Sleep -Milliseconds 150
}
function ToggleChinese {
 [IMETest]::keybd_event(0x11,0x1D,0,[UIntPtr]::Zero)
 [IMETest]::keybd_event(0x12,0x38,0,[UIntPtr]::Zero)
 try {Key 0x20} finally {
  [IMETest]::keybd_event(0x12,0x38,2,[UIntPtr]::Zero)
  [IMETest]::keybd_event(0x11,0x1D,2,[UIntPtr]::Zero)
 }
 Start-Sleep -Milliseconds 250
}
'''.replace('__FILE__', filename)

        def native(code):
            run = subprocess.run([PS, '-NoProfile', '-EncodedCommand',
                base64.b64encode((setup+code).encode('utf-16le')).decode()],
                capture_output=True, timeout=25)
            assert run.returncode == 0, run.stderr.decode(errors='replace')

        command('wait-input')
        command('wait 1200')
        native("$p=New-Object IMETest+Point\n$p.X=100;$p.Y=86\n[void][IMETest]::ClientToScreen($h,[ref]$p)\n[void][IMETest]::SetCursorPos($p.X,$p.Y)\n[IMETest]::mouse_event(2,0,0,0,[UIntPtr]::Zero)\n[IMETest]::mouse_event(4,0,0,0,[UIntPtr]::Zero)\nStart-Sleep -Milliseconds 250\nToggleChinese\nforeach($c in 'ZHONGWEN'.ToCharArray()){Key ([byte][char]$c)}")
        command('wait 200')
        command('shot /tmp/rhun-fcitx-live-candidates.ppm')
        actual = command('print-doc').strip()
        assert actual == '<eod>', ('preedit modified document', actual, command('print-toast'))
        native('Key 0x20\nCtrlKey 0x53')
        command('wait 250')
        assert doc.read_text() == '中文\n', (doc.read_text(), command('print-doc'), command('print-state'), command('print-toast'))
        native("[void][IMETest]::ShowWindow($h,3)\nStart-Sleep -Milliseconds 1600\nif(-not [IMETest]::IsZoomed($h)){throw 'test window is not maximized'}\nKey 0x0D\nforeach($c in 'CESHI'.ToCharArray()){Key ([byte][char]$c)}\nKey 0x20\nCtrlKey 0x53")
        command('wait 250')
        assert doc.read_text() == '中文\n测试\n', doc.read_text()
        command('shot /tmp/rhun-fcitx-live-maximized.ppm')
        deadline = time.monotonic()+8
        while not Path('/tmp/rhun-fcitx-live-maximized.ppm').exists():
            assert time.monotonic() < deadline, 'maximized screenshot timed out'
            command('wait 100')
        command('quit')
        proc.wait(timeout=10)
        assert proc.returncode == 0
        print('PASS: real Windows keys, WSLg candidates, Chinese save, maximized input and clean exit')
    finally:
        client.close()
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)
