#!/usr/bin/env python3
"""Opt-in native WSLg regression, only operates on its own unique window."""
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


def main():
    if '--live' not in sys.argv or not os.environ.get('WSL_INTEROP'):
        print('skip WSLg/window-area (use --live inside WSLg)')
        return
    with tempfile.TemporaryDirectory(prefix='rhun-window-test-') as tmp:
        work = Path(tmp)
        filename = 'RHUN_WINDOW_' + uuid.uuid4().hex + '.txt'
        (work / filename).write_text(''.join('window area regression line '+str(n)+'\n' for n in range(300)))
        config = work / 'config/rhun/config'
        config.parent.mkdir(parents=True)
        config.write_text('[git]\nenabled=false\n[updates]\ncheck=false\n'
                          '[ui]\nsidebar=false\nagents_panel=false\n'
                          '[files]\nrestore_session=false\nrestore_project=false\n')
        env = dict(os.environ, RHUN_BACKEND='wayland', RHUN_WSL_WINDOW_FIX='1',
                   XDG_CONFIG_HOME=str(work/'config'), XDG_STATE_HOME=str(work/'state'))
        control = work / 'control'
        with (work/'log').open('wb') as log:
            proc = subprocess.Popen([str(ROOT/'build/rhun'), '--wait', str(work),
                                     str(work/filename), '--control', str(control)],
                                    env=env, stdout=log, stderr=log)
        client = socket.socket(socket.AF_UNIX)
        client.settimeout(15)
        helper = None
        try:
            deadline = time.monotonic() + 15
            while not control.exists():
                assert proc.poll() is None, 'editor exited'
                assert time.monotonic() < deadline, 'control socket missing'
                time.sleep(.05)
            client.connect(str(control))
            reader = client.makefile('rb')

            def command(value):
                client.sendall((value+'\n').encode())
                output = []
                while True:
                    line = reader.readline()
                    if line == b'ok\n':
                        return b''.join(output).decode('utf-8', 'replace')
                    assert line not in (b'', b'error\n'), (value, line)
                    output.append(line)

            # Wait for the real helper, including /init wrapper used for Windows interop.
            deadline = time.monotonic() + 10
            children = Path('/proc', str(proc.pid), 'task', str(proc.pid), 'children')
            while helper is None and time.monotonic() < deadline:
                for pid in children.read_text().split():
                    try:
                        args = Path('/proc', pid, 'cmdline').read_bytes()
                        if b'rhunWindowTag' in args:
                            helper = int(pid)
                    except OSError:
                        pass
                time.sleep(.1)
            assert helper, 'window helper did not start'
            ps = r'''
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class WindowTest {
 [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
 public delegate bool Callback(IntPtr h,IntPtr p);
 [StructLayout(LayoutKind.Sequential)] public struct Rect { public int Left,Top,Right,Bottom; }
 [DllImport("user32.dll")] public static extern bool EnumWindows(Callback cb,IntPtr p);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h,StringBuilder b,int n);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h,out Rect r);
 [DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr h);
 [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int c);
 [StructLayout(LayoutKind.Sequential)] public struct Point { public int X,Y; }
 [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h,ref Point p);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr extra);
}
'@
[void][WindowTest]::SetThreadDpiAwarenessContext([IntPtr](-4))
Add-Type -AssemblyName System.Windows.Forms
$script:target=[IntPtr]::Zero
$script:title=''
$find=[WindowTest+Callback]{param($h,$p)
 $s=New-Object System.Text.StringBuilder 4096
 [void][WindowTest]::GetWindowText($h,$s,4096)
 if($s.ToString().Contains('__FILENAME__')) {$script:target=$h;$script:title=$s.ToString()}
 return $true
}
$until=[DateTime]::UtcNow.AddSeconds(15)
do {
 [void][WindowTest]::EnumWindows($find,[IntPtr]::Zero)
 if([DateTime]::UtcNow -gt $until){throw 'helper handshake timed out'}
 Start-Sleep -Milliseconds 100
} while($script:target -eq [IntPtr]::Zero -or $script:title.Contains('[rhun-wsl-'))
$h=$script:target
$a=[System.Windows.Forms.Screen]::FromHandle($h).WorkingArea
for($i=0;$i -lt 3;$i++) {
 [void][WindowTest]::ShowWindow($h,9)
 $until=[DateTime]::UtcNow.AddSeconds(5)
 while([WindowTest]::IsZoomed($h)) {
  Start-Sleep -Milliseconds 100
  if([DateTime]::UtcNow -gt $until){throw 'restore did not apply'}
 }
 Start-Sleep -Milliseconds 300
 [void][WindowTest]::ShowWindow($h,3)
 $until=[DateTime]::UtcNow.AddSeconds(8)
 do {
  Start-Sleep -Milliseconds 200
  $r=New-Object WindowTest+Rect
  [void][WindowTest]::GetWindowRect($h,[ref]$r)
  $ok=[WindowTest]::IsZoomed($h) -and $r.Left -eq $a.Left -and $r.Top -eq $a.Top -and $r.Right -eq $a.Right -and $r.Bottom -eq $a.Bottom
  if([DateTime]::UtcNow -gt $until){throw "maximized bounds incorrect: $r"}
 } while(-not $ok)
}
Write-Output ($a.Width.ToString()+' '+$a.Height.ToString())
'''.replace('__FILENAME__', filename)
            result = subprocess.run([PS, '-NoProfile', '-EncodedCommand',
                base64.b64encode(ps.encode('utf-16le')).decode()],
                capture_output=True, timeout=45)
            assert result.returncode == 0, result.stderr.decode('utf-8', 'replace')
            expected = tuple(map(int, result.stdout.decode().strip().split()))
            command('wait 200')
            frame = work / 'frame.ppm'
            command('shot '+str(frame))
            deadline = time.monotonic() + 10
            while not frame.exists():
                assert time.monotonic() < deadline, 'render capture did not arrive'
                command('wait 100')
            with frame.open('rb') as f:
                assert f.readline() == b'P6\n'
                actual = tuple(map(int, f.readline().split()))
            assert actual == expected, (actual, expected)
            setup = ps.split('$a=[System.Windows.Forms.Screen]')[0]

            def native(action):
                script = setup + action
                r = subprocess.run([PS, '-NoProfile', '-EncodedCommand',
                    base64.b64encode(script.encode('utf-16le')).decode()],
                    capture_output=True, timeout=25)
                assert r.returncode == 0, r.stderr.decode('utf-8', 'replace')
                return r.stdout.decode().strip()

            def click(x, y):
                native('''
[void][WindowTest]::SetForegroundWindow($h)
Start-Sleep -Milliseconds 250
$p=New-Object WindowTest+Point
$p.X=__X__; $p.Y=__Y__
[void][WindowTest]::ClientToScreen($h,[ref]$p)
[void][WindowTest]::SetCursorPos($p.X,$p.Y)
Start-Sleep -Milliseconds 200
[WindowTest]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
Start-Sleep -Milliseconds 100
[WindowTest]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
Start-Sleep -Milliseconds 300
'''.replace('__X__', str(x)).replace('__Y__', str(y)))

            # These go through the Windows mouse path, not the synthetic control clicks.
            before = command('print-panels')
            click(24, 18)
            after = command('print-panels')
            assert before != after, ('sidebar toolbar button did not work', before, after)
            click(100, 18)
            menu = command('print-menu')
            assert 'Open Folder' in menu, ('project toolbar menu did not open', menu)
            command('key Escape')
            command('cmd toggle_sidebar')
            command('wait 150')
            command('key ctrl+Home')
            command('wait 100')
            command('click 500 200')
            command('wait 100')
            expected_cursor = command('print-state')
            expected_scroll = command('print-scroll')
            assert ' line=1 ' not in expected_cursor, expected_cursor
            command('key ctrl+Home')
            command('wait 100')
            click(500, 200)
            actual_cursor = command('print-state')
            assert actual_cursor == expected_cursor, ('editor pointer coordinates differ', expected_cursor, actual_cursor, expected_scroll, command('print-scroll'))
            click(expected[0]-72, 18)
            assert native('Write-Output ([int][WindowTest]::IsZoomed($h))') == '0', 'native restore button failed'
            native('[void][WindowTest]::ShowWindow($h,3);Start-Sleep -Milliseconds 500')
            click(expected[0]-120, 18)
            assert native('Write-Output ([int][WindowTest]::IsIconic($h))') == '1', 'native minimize button failed'
            native('[void][WindowTest]::ShowWindow($h,3);Start-Sleep -Milliseconds 500')
            click(expected[0]-24, 18)
            proc.wait(timeout=10)
            deadline = time.monotonic() + 8
            while Path('/proc', str(helper)).exists() and time.monotonic() < deadline:
                time.sleep(.1)
            assert not Path('/proc', str(helper)).exists(), 'helper survived editor exit'
            print('ok WSLg/window-area: bounds, native toolbar/menu/editor/restore/minimize/close, helper shutdown')
        finally:
            client.close()
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=10)


if __name__ == '__main__':
    main()
