#!/usr/bin/python3
"""Physical F2 binding recording, save/display, re-edit and immediate use.

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
    raise SystemExit('Use /usr/bin/python3 tests/shortcuts-live.py --live')

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

        def wait_route(enabled):
            deadline = time.monotonic()+6
            while True:
                route = command('print-input-route')
                if 'host_relay='+str(int(enabled)) in route:
                    return
                assert time.monotonic() < deadline, route
                time.sleep(.1)

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
        native('Start-Sleep -Milliseconds 700')
        route = command('print-input-route')
        assert 'host_relay=1' in route, route
        command('cmd keyboard_shortcuts')
        command('type Chinese Pinyin')
        native('Key 0x71')
        assert 'Press shortcut' in command('print-palette')
        native('CtrlKey 0x74')
        assert 'field=Ctrl+F5' in command('print-palette'), command('print-palette')
        native('Key 0x0D')
        command('type Chinese Pinyin')
        page = command('print-palette')
        assert '> Ctrl+F5  Input: Toggle Chinese Pinyin' in page, page
        assert 'Ctrl+Alt+Space  Input: Toggle Chinese Pinyin' not in page, page
        native('Key 0x1B\nCtrlKey 0x74')
        command('wait 300')
        assert 'Chinese Pinyin input on.' in command('print-toast'), command('print-toast')
        native("foreach($c in 'NIHAO'.ToCharArray()){Key ([byte][char]$c)}\nKey 0x20\nCtrlKey 0x53")
        command('wait 250')
        assert doc.read_text() == '你好\n', doc.read_text()
        command('cmd keyboard_shortcuts')
        command('type Chinese Pinyin')
        native('Key 0x71\nKey 0x75\nKey 0x0D')
        command('type Chinese Pinyin')
        assert '> F6  Input: Toggle Chinese Pinyin' in command('print-palette'), command('print-palette')
        native('Key 0x1B\nKey 0x75')
        command('wait 200')
        assert 'English input on.' in command('print-toast'), command('print-toast')
        assert 'F6 = toggle_chinese' in config.read_text()
        assert 'Ctrl+F5 = none' in config.read_text()
        route = command('print-input-route')
        assert int(route.split('keys=')[1].split()[0]) > 20, route
        # Disable and re-enable in Settings: no launcher or system change.
        command('cmd settings')
        command('type chinese_input')
        command('wait 300')
        command('shot /tmp/rhun-shortcuts-live-settings.ppm')
        command('click 967 348')  # live window is 1280 wide; Settings has a centered 720px body
        command('wait 700')
        assert command('print-input').strip() == '0', (command('print-state'),command('print-settings'),command('print-toast'))
        wait_route(False)
        command('click 967 348')
        command('wait-input')
        command('wait 700')
        wait_route(True)
        command('open '+str(doc))
        command('key ctrl+End')
        native("foreach($c in 'NIHAO'.ToCharArray()){Key ([byte][char]$c)}\nCtrlKey 0x53")
        command('wait 200')
        assert doc.read_text() == '你好\nnihao\n', doc.read_text()
        command('quit')
        proc.wait(timeout=10)
        print('PASS: real F2 recording, immediate use, Chinese/English typing, relay release/re-enable')
    finally:
        client.close()
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)
