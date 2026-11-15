#!/usr/bin/env python3
"""Opt-in WSLg cursor regressions using only disposable rhun windows."""
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
EXE = Path(os.environ.get('RHUN_TEST_EXE', ROOT / 'build/rhun')).resolve()
PS = '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'


def main():
    if '--live' not in sys.argv or not os.environ.get('WSL_INTEROP'):
        print('skip WSLg/cursor (use --live inside WSLg)')
        return
    same_file = '--same-file-unsaved' in sys.argv
    multi_input = '--multi-input' in sys.argv
    multi_monitor = '--multi-monitor' in sys.argv
    children = []
    clients = []
    with tempfile.TemporaryDirectory(prefix='rhun-cursor-live-') as tmp:
        work = Path(tmp)
        config = work / 'config/rhun/config'
        config.parent.mkdir(parents=True)
        config.write_text('[ui]\nsidebar=false\nagents_panel=false\n'
                          '[editor]\nchinese_input=' + ('true' if same_file or multi_input else 'false') + '\n'
                          'chinese_follow_host=' + ('true' if multi_input else 'false') + '\n'
                          '[files]\nrestore_session=false\nrestore_project=false\n'
                          '[git]\nenabled=false\n[updates]\ncheck=false\n')
        env = dict(os.environ, RHUN_BACKEND='wayland', RHUN_WSL_WINDOW_FIX='1',
                   XDG_CONFIG_HOME=str(work / 'config'), XDG_STATE_HOME=str(work / 'state'))
        names = ['RHUN_CURSOR_' + uuid.uuid4().hex + '.txt' for _ in range(2)]
        try:
            for i, name in enumerate(names):
                doc = work / name
                doc.write_text('Pointer visibility test\n')
                control = work / ('control' + str(i))
                p = subprocess.Popen([str(EXE), '--wait', str(work), str(doc),
                                      '--control', str(control)], env=env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                children.append(p)
                deadline = time.monotonic() + 20
                while not control.exists():
                    assert p.poll() is None, 'test editor exited'
                    assert time.monotonic() < deadline, 'test control socket missing'
                    time.sleep(.05)
                client = socket.socket(socket.AF_UNIX)
                client.settimeout(15)
                client.connect(str(control))
                clients.append((client, client.makefile('rb')))

            def command(index, line):
                client, reader = clients[index]
                client.sendall((line+'\n').encode())
                output = []
                while True:
                    data = reader.readline()
                    if data == b'ok\n':
                        return b''.join(output).decode()
                    assert data not in (b'', b'error\n'), (line, data)
                    output.append(data)

            script = r'''
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class CursorTest {
 [StructLayout(LayoutKind.Sequential)] public struct Point {public int X,Y;}
 [StructLayout(LayoutKind.Sequential)] public struct Rect {public int L,T,R,B;}
 [StructLayout(LayoutKind.Sequential)] public struct Info {public int Size,Flags;public IntPtr Cursor;public Point Position;}
 public delegate bool CB(IntPtr h,IntPtr p);
 [DllImport("user32.dll")] public static extern bool EnumWindows(CB cb,IntPtr p);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h,StringBuilder b,int n);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h,out Rect r);
 [DllImport("user32.dll")] public static extern bool GetCursorInfo(ref Info i);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(Point p);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int mode);
 [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h,uint m,IntPtr w,IntPtr l);
 [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code,uint type);
 [DllImport("user32.dll")] public static extern void keybd_event(byte key,byte scan,uint flags,UIntPtr extra);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);
 [DllImport("user32.dll")] public static extern IntPtr GetKeyboardLayout(uint t);
 [DllImport("imm32.dll")] public static extern IntPtr ImmGetDefaultIMEWnd(IntPtr h);
 [DllImport("user32.dll")] static extern IntPtr SendMessageTimeout(IntPtr h,uint m,UIntPtr w,IntPtr l,uint f,uint t,out UIntPtr r);
 public static int HostMode(IntPtr h) {
  uint p;uint t=GetWindowThreadProcessId(h,out p);
  if((GetKeyboardLayout(t).ToInt64() & 0x3ff)!=4)throw new Exception("Chinese host input profile required");
  UIntPtr opened,conversion;IntPtr ime=ImmGetDefaultIMEWnd(h);
  if(ime==IntPtr.Zero || SendMessageTimeout(ime,0x283,(UIntPtr)5,IntPtr.Zero,2,100,out opened)==IntPtr.Zero ||
    SendMessageTimeout(ime,0x283,(UIntPtr)1,IntPtr.Zero,2,100,out conversion)==IntPtr.Zero)
    throw new Exception("Host mode unavailable");
  return opened.ToUInt64()!=0 && ((conversion.ToUInt64() & 1)!=0 || conversion.ToUInt64()==0x400) ? 1 : 0;
 }
 public static IntPtr Find(string name) {
  IntPtr found=IntPtr.Zero;
  CB cb=(h,p)=>{var s=new StringBuilder(4096);GetWindowText(h,s,4096);
   if(s.ToString().Contains(name) && !s.ToString().Contains("[rhun-wsl-"))found=h;return true;};
  EnumWindows(cb,IntPtr.Zero);return found;
 }
}
'@
function Find-Test([string]$name){
 if($name.StartsWith('HWND_')){return [IntPtr][long]$name.Substring(5)}
 $until=[DateTime]::UtcNow.AddSeconds(15)
 do {
  $h=[CursorTest]::Find($name)
  if([DateTime]::UtcNow -gt $until){throw 'test window handshake timed out'}
  Start-Sleep -Milliseconds 100
 } while($h -eq [IntPtr]::Zero)
 return $h
}
function Check-Pointer([IntPtr]$h,[int]$x,[int]$y,[string]$label){
 [void][CursorTest]::SetForegroundWindow($h)
 $until=[DateTime]::UtcNow.AddSeconds(3)
 do {
  if([CursorTest]::GetForegroundWindow() -ne $h){[void][CursorTest]::SetForegroundWindow($h)}
  $r=New-Object CursorTest+Rect;[void][CursorTest]::GetWindowRect($h,[ref]$r)
  [void][CursorTest]::SetCursorPos($r.L+$x,$r.T+$y)
  Start-Sleep -Milliseconds 100
  $info=New-Object CursorTest+Info;$info.Size=[Runtime.InteropServices.Marshal]::SizeOf($info)
  [void][CursorTest]::GetCursorInfo([ref]$info)
  $ok=[CursorTest]::GetForegroundWindow() -eq $h -and [CursorTest]::WindowFromPoint($info.Position) -eq $h -and $info.Flags -eq 1 -and $info.Cursor -ne [IntPtr]::Zero
  if([DateTime]::UtcNow -gt $until){throw "$label pointer missing: target=$h foreground=$([CursorTest]::GetForegroundWindow()) hit=$([CursorTest]::WindowFromPoint($info.Position)) flags=$($info.Flags) handle=$($info.Cursor)"}
 } while(-not $ok)
 Write-Output ('ok '+$label)
}
$original=[CursorTest]::GetForegroundWindow()
$saved=New-Object CursorTest+Info;$saved.Size=[Runtime.InteropServices.Marshal]::SizeOf($saved)
[void][CursorTest]::GetCursorInfo([ref]$saved)
try {
 $a=Find-Test '__FIRST__';$b=Find-Test '__SECOND__'
 [void][CursorTest]::ShowWindow($a,9)
 Check-Pointer $a 500 300 'normal editor'
 Check-Pointer $a 450 20 'normal toolbar'
 Check-Pointer $a 501 301 'normal editor return'
 [CursorTest]::keybd_event(0x41,[byte][CursorTest]::MapVirtualKey(0x41,0),0,[UIntPtr]::Zero)
 [CursorTest]::keybd_event(0x41,[byte][CursorTest]::MapVirtualKey(0x41,0),2,[UIntPtr]::Zero)
 Check-Pointer $a 502 302 'after typing'
 [void][CursorTest]::ShowWindow($a,3)
 Start-Sleep -Milliseconds 600
 for($i=0;$i -lt 3;$i++){
  Check-Pointer $a (500+$i) 300 ('maximized '+$i)
  Check-Pointer $b 500 300 ('other window '+$i)
 }
 Check-Pointer $a 503 301 'return to maximized window'
 [void][CursorTest]::PostMessage($b,0x10,[IntPtr]::Zero,[IntPtr]::Zero)
 Start-Sleep -Milliseconds 700
 Check-Pointer $a 504 302 'after other cursor owner closes'
 [void][CursorTest]::ShowWindow($a,9)
 Start-Sleep -Milliseconds 500
 Check-Pointer $a 505 303 'restored window'
} finally {
 if($original -ne [IntPtr]::Zero){[void][CursorTest]::SetForegroundWindow($original)}
 [void][CursorTest]::SetCursorPos($saved.Position.X,$saved.Position.Y)
}
'''.replace('__FIRST__', names[0]).replace('__SECOND__', names[1])
            if multi_monitor:
                setup = script.split('$original=[CursorTest]::GetForegroundWindow()')[0]
                probe = (ROOT / 'tests/windows/cursor-monitors.ps1').read_text()
                probe = probe.replace('__FIRST__', names[0]).replace('__SECOND__', names[1])
                native_script = work / 'cursor-monitors.ps1'
                native_script.write_text(setup+probe)
                native_path = (chr(92)*2+'wsl.localhost'+chr(92)+os.environ['WSL_DISTRO_NAME']
                               +str(native_script).replace('/', chr(92)))
                launch = "& ([ScriptBlock]::Create([IO.File]::ReadAllText('"+native_path+"')))"
                result = subprocess.run([PS, '-NoProfile', '-NonInteractive', '-EncodedCommand',
                    base64.b64encode(launch.encode('utf-16le')).decode()],
                    capture_output=True, timeout=120)
                print(result.stdout.decode(errors='replace'), end='')
                assert result.returncode == 0, result.stderr.decode(errors='replace')
                return
            if multi_input:
                setup = script.split('$original=[CursorTest]::GetForegroundWindow()')[0]
                def native(action):
                    result = subprocess.run([PS, '-NoProfile', '-NonInteractive', '-EncodedCommand',
                        base64.b64encode((setup+action).encode('utf-16le')).decode()],
                        capture_output=True, timeout=30)
                    assert result.returncode == 0, result.stderr.decode(errors='replace')
                    return result.stdout.decode(errors='replace').strip()

                handles = [int(native("Write-Output (Find-Test '"+name+"')")) for name in names]
                assert len(set(handles)) == 2, handles
                for i in range(2):
                    command(i, 'wait-input')
                    native('[void][CursorTest]::ShowWindow([IntPtr]'+str(handles[i])+',3);Start-Sleep -Milliseconds 500')
                print('both test windows maximized:', handles, flush=True)
                for turn, i in enumerate([0, 1, 0, 1]):
                    target = '$h=[IntPtr]'+str(handles[i])+'; '
                    for x, y, shape in [(500, 300, '1'), (450, 20, '0'), (500, 300, '1')]:
                        # SetCursorPos and focus/stacking changes alone must work.
                        # Injecting relative mouse input here would mask the bug.
                        native(target+'[void][CursorTest]::ShowWindow($h,3); '
                            'Check-Pointer $h '+str(x)+' '+str(y)+" 'both maximized'")
                        command(i, 'wait 200')
                        assert command(i, 'print-shape').strip() == shape, (i, x, y, command(i, 'print-shape'))
                    result = native(target+r'''
function Key([byte]$key) {
 if([CursorTest]::GetForegroundWindow() -ne $h){throw 'Test window lost focus'}
 [CursorTest]::keybd_event($key,[byte][CursorTest]::MapVirtualKey($key,0),0,[UIntPtr]::Zero)
 Start-Sleep -Milliseconds 40
 [CursorTest]::keybd_event($key,[byte][CursorTest]::MapVirtualKey($key,0),2,[UIntPtr]::Zero)
 Start-Sleep -Milliseconds 50
}
function Mode([int]$wanted) {
 if([CursorTest]::HostMode($h) -ne $wanted){Key 0x10}
 Start-Sleep -Milliseconds 250
 if([CursorTest]::HostMode($h) -ne $wanted){throw 'Host mode did not switch'}
}
$originalMode=[CursorTest]::HostMode($h)
try {
 foreach($mode in @(1,0,1)) {
  Mode $mode
  foreach($key in 'NIHAO'.ToCharArray()){Key ([byte][char]$key)}
  if($mode -eq 1){Key 0x20}
  Key 0x0D
 }
} finally {Mode $originalMode}
Write-Output 'native Chinese-English-Chinese input completed'
''')
                    command(i, 'wait 300')
                    content = command(i, 'print-doc')
                    expected = ('你好\nnihao\n你好\n' * (turn//2+1))+'Pointer visibility test\n'
                    assert content == expected+'\n<eod>\n', (i, content, expected, command(i, 'print-input-route'))
                    print('ok both maximized window', i, 'cursor shapes and committed Chinese/English', flush=True)
                print('PASS: two maximized windows retain pointer shapes and host-following input across focus switches')
                return
            if same_file:
                setup = script.split('$original=[CursorTest]::GetForegroundWindow()')[0]
                handles = subprocess.run([PS, '-NoProfile', '-NonInteractive', '-Command',
                    setup + "Write-Output (Find-Test '"+names[0]+"');Write-Output (Find-Test '"+names[1]+"')"],
                    capture_output=True, timeout=25)
                assert handles.returncode == 0, handles.stderr.decode(errors='replace')
                hwnds = list(map(int, handles.stdout.decode().split()))
                assert len(hwnds) == 2 and hwnds[0] != hwnds[1], hwnds
                shared = work/'shared-file.txt'
                shared.write_text('Original content\n')
                for i in range(2):
                    focused = subprocess.run([PS, '-NoProfile', '-NonInteractive', '-Command',
                        setup+'[void][CursorTest]::SetForegroundWindow([IntPtr]'+str(hwnds[i])+');Start-Sleep -Milliseconds 300'],
                        capture_output=True, timeout=15)
                    assert focused.returncode == 0, focused.stderr.decode(errors='replace')
                    command(i, 'open '+str(shared))
                    command(i, 'wait-input')
                    command(i, 'wait 500')
                    command(i, 'key ctrl+End')
                    command(i, 'type unsaved window '+str(i))
                    command(i, 'wait 400')
                    assert 'dirty=1' in command(i, 'print-state'), command(i, 'print-state')
                script = script.replace("$a=Find-Test '"+names[0]+"';$b=Find-Test '"+names[1]+"'",
                    '$a=[IntPtr]'+str(hwnds[0])+';$b=[IntPtr]'+str(hwnds[1]))
                start = script.index(' [void][CursorTest]::ShowWindow($a,9)')
                end = script.index('} finally {', start)
                script = script[:start] + r'''
 [void][CursorTest]::ShowWindow($a,3)
 [void][CursorTest]::ShowWindow($b,3)
 Start-Sleep -Milliseconds 500
 Check-Pointer $a 500 300 'first dirty editor'
 Check-Pointer $b 500 300 'second dirty editor'
 [void][CursorTest]::PostMessage($b,0x10,[IntPtr]::Zero,[IntPtr]::Zero)
 Start-Sleep -Milliseconds 500
 Write-Output 'UNSAVED_DIALOG_READY'
''' + script[end:]
                if '--windowed' in sys.argv:
                    script = script.replace('::ShowWindow($a,3)', '::ShowWindow($a,9)').replace('::ShowWindow($b,3)', '::ShowWindow($b,9)')
                result = subprocess.run([PS, '-NoProfile', '-NonInteractive', '-Command', script],
                    capture_output=True, timeout=40)
                print(result.stdout.decode(errors='replace'), end='')
                assert result.returncode == 0, result.stderr.decode(errors='replace')
                assert children[1].poll() is None, 'dirty window closed without save prompt'
                command(1, 'shot /tmp/rhun-cursor-unsaved-dialog.ppm')
                with Path('/tmp/rhun-cursor-unsaved-dialog.ppm').open('rb') as frame:
                    assert frame.readline() == b'P6\n'
                    width, height = map(int, frame.readline().split())
                # The centered dialog's middle button is Don't Save.
                # Discard only this disposable file; preserve the surviving edit.
                stationary = subprocess.run([PS, '-NoProfile', '-NonInteractive', '-Command',
                    setup+'Check-Pointer ([IntPtr]'+str(hwnds[0])+") 500 300 'survivor stationary before close'"],
                    capture_output=True, timeout=15)
                assert stationary.returncode == 0, stationary.stderr.decode(errors='replace')
                print(stationary.stdout.decode(errors='replace'), end='')
                command(1, 'wait 300')
                for attempt in range(3):
                    if children[1].poll() is not None:
                        break
                    try:
                        command(1, 'click '+str(width//2+65)+' '+str(height//2-5))
                    except (OSError, AssertionError):
                        children[1].wait(timeout=5)
                        break
                    time.sleep(.3)
                    if children[1].poll() is None:
                        command(1, 'wait 200')
                children[1].wait(timeout=5)
                time.sleep(.3)
                recovery = setup + '$a=[IntPtr]'+str(hwnds[0])+r'''
Start-Sleep -Milliseconds 700
$before=New-Object CursorTest+Info;$before.Size=[Runtime.InteropServices.Marshal]::SizeOf($before)
[void][CursorTest]::GetCursorInfo([ref]$before)
Write-Output ('stationary after close flags='+$before.Flags+' cursor='+$before.Cursor)
if([CursorTest]::GetForegroundWindow() -ne $a -or [CursorTest]::WindowFromPoint($before.Position) -ne $a){throw 'stationary pointer left survivor'}
if($before.Flags -ne 1 -or $before.Cursor -eq [IntPtr]::Zero){throw 'stationary survivor cursor missing'}
[void][CursorTest]::SetForegroundWindow($a)
Start-Sleep -Milliseconds 300
$r=New-Object CursorTest+Rect;[void][CursorTest]::GetWindowRect($a,[ref]$r)
[void][CursorTest]::SetCursorPos($r.L+500,$r.T+300)
Start-Sleep -Milliseconds 600
$info=New-Object CursorTest+Info;$info.Size=[Runtime.InteropServices.Marshal]::SizeOf($info)
[void][CursorTest]::GetCursorInfo([ref]$info)
Write-Output ('survivor flags='+$info.Flags+' cursor='+$info.Cursor)
if($info.Flags -ne 1 -or $info.Cursor -eq [IntPtr]::Zero){throw 'dirty survivor cursor missing'}
Check-Pointer $a 500 300 'dirty survivor after other dirty window closes'
'''
                result = subprocess.run([PS, '-NoProfile', '-NonInteractive', '-Command', recovery],
                    capture_output=True, timeout=15)
                print(result.stdout.decode(errors='replace'), end='')
                assert result.returncode == 0, result.stderr.decode(errors='replace')
                assert 'dirty=1' in command(0, 'print-state')
                assert 'unsaved window 0' in command(0, 'print-doc')
                assert shared.read_text() == 'Original content\n'
                print('PASS: same-folder same-file unsaved close preserves survivor and visible cursor')
                return
            result = subprocess.run([PS, '-NoProfile', '-NonInteractive', '-Command', script],
                                    capture_output=True, timeout=50)
            print(result.stdout.decode(errors='replace'), end='')
            assert result.returncode == 0, result.stderr.decode(errors='replace')
            print('PASS: WSLg visible cursor across typing, maximize, window switches and cursor-owner exit')
        finally:
            for index, p in enumerate(children):
                if p.poll() is None and index < len(clients):
                    try:
                        command(index, 'quit')
                        p.wait(timeout=8)
                    except (OSError, AssertionError, subprocess.TimeoutExpired):
                        pass
            for client, reader in clients:
                reader.close()
                client.close()
            for p in children:
                if p.poll() is None:
                    p.terminate()
                p.wait(timeout=5)


if __name__ == '__main__':
    main()
