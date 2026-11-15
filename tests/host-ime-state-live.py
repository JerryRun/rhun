#!/usr/bin/python3
"""Read Windows IME mode and drive the app-private engine; no host IME setters.

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
EXE = Path(os.environ.get('RHUN_TEST_EXE', ROOT/'build/rhun')).resolve()
PS = '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'

if '--live' not in sys.argv:
    raise SystemExit('Use /usr/bin/python3 tests/host-ime-state-live.py --live')

with tempfile.TemporaryDirectory(prefix='rhun-fcitx-live-') as tmp:
    work = Path(tmp)
    filename = 'RHUN_IME_' + uuid.uuid4().hex[:12] + '.txt'
    doc = work/filename
    doc.write_text('')
    config = work/'config/rhun/config'
    config.parent.mkdir(parents=True)
    config.write_text('[ui]\nsidebar=false\nagents_panel=false\n'
        'font=/mnt/c/Windows/Fonts/msyh.ttc\n'
        '[editor]\nchinese_input=true\n'
        'fallback_font=/mnt/c/Windows/Fonts/msyh.ttc\n'
        '[terminal]\nshell=/bin/sh\n'
        '[files]\nrestore_session=false\nrestore_project=false\n'
        '[updates]\ncheck=false\n[git]\nenabled=false\n')
    env = dict(os.environ, RHUN_BACKEND='wayland', RHUN_WSL_WINDOW_FIX='1',
        XDG_CONFIG_HOME=str(work/'config'), XDG_STATE_HOME=str(work/'state'))
    env.pop('RHUN_WSL_FOLLOW_HOST_IME', None)
    control = work/'control'
    proc = subprocess.Popen([str(EXE), '--wait', str(work),
        str(doc), '--control', str(control)], env=env, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    client = socket.socket(socket.AF_UNIX)
    client.settimeout(12)
    original_mode = None
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
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h,out uint pid);
 [DllImport("user32.dll")] public static extern IntPtr GetKeyboardLayout(uint thread);
 [DllImport("imm32.dll")] public static extern IntPtr ImmGetDefaultIMEWnd(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr SendMessageTimeout(IntPtr h,uint m,IntPtr w,IntPtr l,uint flags,uint timeout,out UIntPtr result);
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
Write-Output ('RHUN_TEST_HWND='+$h.ToInt64())
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
function Click([int]$x,[int]$y) {
 if([IMETest]::GetForegroundWindow() -ne $h){throw 'test window lost focus'}
 $p=New-Object IMETest+Point; $p.X=$x; $p.Y=$y
 if(-not [IMETest]::ClientToScreen($h,[ref]$p)){throw 'test coordinates unavailable'}
 [void][IMETest]::SetCursorPos($p.X,$p.Y)
 [IMETest]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
 Start-Sleep -Milliseconds 80
 [IMETest]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
 Start-Sleep -Milliseconds 250
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
function HostState {
 if([IMETest]::GetForegroundWindow() -ne $h){throw 'test window lost focus'}
 [uint32]$owner=0
 $thread=[IMETest]::GetWindowThreadProcessId($h,[ref]$owner)
 $layout=[IMETest]::GetKeyboardLayout($thread).ToInt64()
 if(($layout -band 0x3FF) -ne 4){throw 'Chinese host input profile required; refusing to change profile'}
 $ime=[IMETest]::ImmGetDefaultIMEWnd($h)
 [UIntPtr]$open=[UIntPtr]::Zero
 [UIntPtr]$conversion=[UIntPtr]::Zero
 if([IMETest]::SendMessageTimeout($ime,0x283,[IntPtr]5,[IntPtr]::Zero,2,200,[ref]$open) -eq [IntPtr]::Zero){throw 'host open state unavailable'}
 if([IMETest]::SendMessageTimeout($ime,0x283,[IntPtr]1,[IntPtr]::Zero,2,200,[ref]$conversion) -eq [IntPtr]::Zero){throw 'host conversion state unavailable'}
 $opened=$open.ToUInt64() -ne 0
 $mode=$conversion.ToUInt64()
 $state=[int]($opened -and (($mode -band 1) -ne 0 -or $mode -eq 0x400))
 return @{state=$state;open=$open.ToUInt64();conversion=$conversion.ToUInt64();layout=$layout}
}
function Mode([int]$wanted) {
 $current=HostState
 if($current.state -ne $wanted){Key 0x10}
 $until=[DateTime]::UtcNow.AddSeconds(3)
 do {
  Start-Sleep -Milliseconds 100
  $current=HostState
  if([DateTime]::UtcNow -gt $until){throw 'Shift did not change host mode; stopping validation'}
 } while($current.state -ne $wanted)
 Start-Sleep -Milliseconds 30
 Write-Output ('mode='+$current.state+' open='+$current.open+' conversion='+$current.conversion)
}
'''.replace('__FILE__', filename)

        native_hwnd = 0

        def native(code):
            global native_hwnd
            current_setup = setup.replace('$script:target=[IntPtr]::Zero', '$script:target=[IntPtr]'+str(native_hwnd))
            run = subprocess.run([PS, '-NoProfile', '-EncodedCommand',
                base64.b64encode((current_setup+code).encode('utf-16le')).decode()],
                capture_output=True, timeout=25)
            assert run.returncode == 0, (run.stdout.decode(errors='replace'), run.stderr.decode(errors='replace'))
            output = run.stdout.decode(errors='replace')
            lines = output.splitlines()
            native_hwnd = int(next(line.split('=')[1] for line in lines if line.startswith('RHUN_TEST_HWND=')))
            return '\n'.join(line for line in lines if not line.startswith('RHUN_TEST_HWND='))+'\n'

        command('wait-input')
        result = native(r"""
$original=HostState
Write-Output ('original='+$original.state+' open='+$original.open+' conversion='+$original.conversion)
try {
 Mode 1
 foreach($c in 'NIHAO'.ToCharArray()){Key ([byte][char]$c)}
 Key 0x20
 Key 0x0D
 Mode 0
 foreach($c in 'NIHAO'.ToCharArray()){Key ([byte][char]$c)}
 Key 0x0D
 Mode 1
 foreach($c in 'CESHI'.ToCharArray()){Key ([byte][char]$c)}
 Key 0x20
 CtrlKey 0x53
} finally {
 $now=HostState
 if($now.open -ne $original.open -or $now.conversion -ne $original.conversion) {
  Key 0x10
  Start-Sleep -Milliseconds 400
 }
 $restored=HostState
 Write-Output ('restored='+$restored.state+' open='+$restored.open+' conversion='+$restored.conversion)
 if($restored.open -ne $original.open -or $restored.conversion -ne $original.conversion){throw 'host state restoration failed'}
}
""")
        print(result, flush=True)
        original_mode = int(next(line.split()[0].split('=')[1] for line in result.splitlines() if line.startswith('original=')))
        command('wait 300')
        route = command('print-input-route')
        print(route, flush=True)
        assert 'host_relay=1' in route, route
        assert 'host_mode=unknown' not in route, route
        assert 'host_mode='+str(original_mode)+' private_mode='+str(original_mode) in route, route
        assert doc.read_text() == '你好\nnihao\n测试\n', (doc.read_text(),command('print-doc'),command('print-toast'),route)
        print('PASS: saved Chinese -> English -> Chinese text from host mode', flush=True)
        command('shot /tmp/rhun-host-ime-state-live.ppm')
        native('Mode 0')
        command('wait 300')
        command('cmd settings')
        command('key ctrl+f')
        command('wait-input')
        command('type chinese_follow_host')
        command('wait-input')
        assert 'editor.chinese_follow_host' in command('print-settings'), command('print-settings')
        command('wait 300')
        assert 'editor.chinese_follow_host' in command('print-settings'), command('print-settings')
        command('shot /tmp/rhun-host-follow-settings.ppm')
        native('Click 967 348')
        command('wait 700')
        assert 'host_mode=unknown' in command('print-input-route'), command('print-input-route')
        command('open '+str(doc))
        command('cmd toggle_chinese')
        command('wait 200')
        wanted_toast = 'Chinese Pinyin input on.'
        assert wanted_toast in command('print-toast'), command('print-toast')
        command('cmd toggle_chinese')
        command('wait 200')
        assert 'English input on.' in command('print-toast'), command('print-toast')
        command('cmd settings')
        command('key ctrl+f')
        command('wait-input')
        command('type chinese_follow_host')
        command('wait-input')
        command('wait 300')
        assert 'editor.chinese_follow_host' in command('print-settings'), command('print-settings')
        command('shot /tmp/rhun-host-follow-settings.ppm')
        native('Click 967 348')
        command('wait 700')
        native("Write-Output 'focused'")
        command('wait 300')
        route = command('print-input-route')
        assert 'host_mode=0 private_mode=0' in route, route
        native('Mode '+str(original_mode))
        command('wait 300')
        route = command('print-input-route')
        assert 'host_mode='+str(original_mode)+' private_mode='+str(original_mode) in route, route
        original_mode = None
        command('quit')
        proc.wait(timeout=10)
        assert proc.returncode == 0
        assert 'chinese_follow_host=true' in config.read_text().replace(' ', ''), config.read_text()
        print('PASS: host Chinese -> private Chinese, host English -> private English, restored host state')
    finally:
        if original_mode is not None and proc.poll() is None:
            native('Mode '+str(original_mode))
        client.close()
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)
