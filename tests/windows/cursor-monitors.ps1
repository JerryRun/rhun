# Used by wsl-cursor.py after creating two disposable windows.
# Never relocate WSLg HWNDs with SetWindowPos: compositor geometry must agree.
Add-Type @'
using System;using System.Runtime.InteropServices;
public static class MonitorPointer {
 [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
 [DllImport("user32.dll")] public static extern void mouse_event(uint flags,uint x,uint y,uint data,UIntPtr extra);
}
'@
[void][MonitorPointer]::SetThreadDpiAwarenessContext([IntPtr](-4))
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing @'
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
public static class CursorImage {
 [StructLayout(LayoutKind.Sequential)] struct Icon { public int IsIcon; public uint X,Y; public IntPtr Mask,Color; }
 [DllImport("user32.dll")] static extern bool GetIconInfo(IntPtr c,out Icon i);
 [DllImport("gdi32.dll")] static extern bool DeleteObject(IntPtr h);
 [DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr h);
 public static string Read(IntPtr cursor) {
  Icon i; if(cursor==IntPtr.Zero || !GetIconInfo(cursor,out i)) throw new Exception("Cursor image unavailable");
  try {
   using(var bitmap=Image.FromHbitmap(i.Color!=IntPtr.Zero?i.Color:i.Mask))
   using(var stream=new MemoryStream())
   using(var sha=SHA256.Create()) {
    bitmap.Save(stream,ImageFormat.Png);
    return bitmap.Width+"x"+bitmap.Height+":"+BitConverter.ToString(sha.ComputeHash(stream.ToArray()));
   }
  } finally {
   if(i.Mask!=IntPtr.Zero) DeleteObject(i.Mask);
   if(i.Color!=IntPtr.Zero) DeleteObject(i.Color);
  }
 }
}
'@
function Move-ToMonitor([IntPtr]$h,$screen) {
 [void][CursorTest]::SetForegroundWindow($h)
 [void][CursorTest]::ShowWindow($h,3)
 Start-Sleep -Milliseconds 400
 for($move=0;$move -le [System.Windows.Forms.Screen]::AllScreens.Count;$move++) {
  if([System.Windows.Forms.Screen]::FromHandle($h).DeviceName -eq $screen.DeviceName){return}
  if([CursorTest]::GetForegroundWindow() -ne $h){throw 'Test window lost focus before system move'}
  try {
   [CursorTest]::keybd_event(0x5b,0x5b,0,[UIntPtr]::Zero)
   [CursorTest]::keybd_event(0x10,0x2a,0,[UIntPtr]::Zero)
   [CursorTest]::keybd_event(0x27,0x4d,1,[UIntPtr]::Zero)
   [CursorTest]::keybd_event(0x27,0x4d,3,[UIntPtr]::Zero)
  } finally {
   [CursorTest]::keybd_event(0x10,0x2a,2,[UIntPtr]::Zero)
   [CursorTest]::keybd_event(0x5b,0x5b,2,[UIntPtr]::Zero)
  }
  Start-Sleep -Milliseconds 700
 }
 throw ('System move did not reach '+$screen.DeviceName)
}
function Assert-Placement {
 if([System.Windows.Forms.Screen]::AllScreens.Count -lt 2){throw 'Display layout changed during regression'}
 for($n=0;$n -lt 2;$n++) {
  $actual=[System.Windows.Forms.Screen]::FromHandle($handles[$n])
  if($actual.DeviceName -ne $screens[$n].DeviceName -or -not [CursorImage]::IsZoomed($handles[$n])){throw 'Test windows must stay maximized on distinct monitors'}
  $r=New-Object CursorTest+Rect;[void][CursorTest]::GetWindowRect($handles[$n],[ref]$r)
  $a=$actual.WorkingArea
  if($r.L -ne $a.Left -or $r.T -ne $a.Top -or $r.R -ne $a.Right -or $r.B -ne $a.Bottom){throw ('Maximized window does not match its monitor work area: '+$actual.DeviceName+' actual='+$r.L+','+$r.T+','+$r.R+','+$r.B+' expected='+$a.Left+','+$a.Top+','+$a.Right+','+$a.Bottom)}
 }
}
function Check-DragMaximize([IntPtr]$h,$destination,$source) {
 [void][CursorTest]::ShowWindow($h,9)
 Start-Sleep -Milliseconds 500
 Move-ToMonitor $h $source
 [void][CursorTest]::ShowWindow($h,9)
 Start-Sleep -Milliseconds 500
 $r=New-Object CursorTest+Rect;[void][CursorTest]::GetWindowRect($h,[ref]$r)
 $sx=$r.L+650;$sy=$r.T+18
 $tx=$destination.WorkingArea.Left+800;$ty=$destination.WorkingArea.Top+200
 $desktop=[System.Windows.Forms.SystemInformation]::VirtualScreen
 [void][CursorTest]::SetCursorPos($sx,$sy)
 Start-Sleep -Milliseconds 150
 [MonitorPointer]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
 try {
  Start-Sleep -Milliseconds 150
  for($step=1;$step -le 24;$step++){
   $x=[int]($sx+($tx-$sx)*$step/24);$y=[int]($sy+($ty-$sy)*$step/24)
   [MonitorPointer]::mouse_event(0xc001,[uint32](($x-$desktop.Left)*65535/($desktop.Width-1)),[uint32](($y-$desktop.Top)*65535/($desktop.Height-1)),0,[UIntPtr]::Zero)
   Start-Sleep -Milliseconds 30
  }
 } finally {[MonitorPointer]::mouse_event(4,0,0,0,[UIntPtr]::Zero)}
 Start-Sleep -Milliseconds 700
 if([System.Windows.Forms.Screen]::FromHandle($h).DeviceName -ne $destination.DeviceName){throw 'Actual drag did not reach destination monitor'}
 [void][CursorTest]::GetWindowRect($h,[ref]$r)
 [void][CursorTest]::SetCursorPos($r.R-72,$r.T+18)
 Start-Sleep -Milliseconds 150
 [MonitorPointer]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
 Start-Sleep -Milliseconds 80
 [MonitorPointer]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
 Start-Sleep -Milliseconds 1300
 if([System.Windows.Forms.Screen]::FromHandle($h).DeviceName -ne $destination.DeviceName -or -not [CursorImage]::IsZoomed($h)){throw 'Maximize did not preserve dragged-to monitor'}
 Write-Output ('ok actual drag and toolbar maximize on '+$destination.DeviceName)
}
function Read-Shape([IntPtr]$h,[int]$x,[int]$y,[bool]$focus) {
 if($focus){[void][CursorTest]::SetForegroundWindow($h)}
 $r=New-Object CursorTest+Rect;[void][CursorTest]::GetWindowRect($h,[ref]$r)
 [void][CursorTest]::SetCursorPos($r.L+$x,$r.T+$y)
 Start-Sleep -Milliseconds 350
 $info=New-Object CursorTest+Info;$info.Size=[Runtime.InteropServices.Marshal]::SizeOf($info)
 [void][CursorTest]::GetCursorInfo([ref]$info)
 if([CursorTest]::WindowFromPoint($info.Position) -ne $h){throw 'Pointer did not hit the test window'}
 if($focus -and [CursorTest]::GetForegroundWindow() -ne $h){throw 'Test window lost focus'}
 if($info.Flags -ne 1 -or $info.Cursor -eq [IntPtr]::Zero){throw ('Cursor hidden or suppressed, flags='+$info.Flags)}
 return [CursorImage]::Read($info.Cursor)
}
$all=@([System.Windows.Forms.Screen]::AllScreens)
if($all.Count -lt 2){Write-Output 'SKIP: multi-monitor cursor regression requires two active displays';return}
$screens=@(($all | Where-Object Primary | Select-Object -First 1),($all | Where-Object {-not $_.Primary} | Select-Object -First 1))
$handles=@((Find-Test '__FIRST__'),(Find-Test '__SECOND__'))
$original=[CursorTest]::GetForegroundWindow()
$saved=New-Object CursorTest+Info;$saved.Size=[Runtime.InteropServices.Marshal]::SizeOf($saved)
[void][CursorTest]::GetCursorInfo([ref]$saved)
try {
 for($n=0;$n -lt 2;$n++){Move-ToMonitor $handles[$n] $screens[$n]}
 for($cycle=0;$cycle -lt 3;$cycle++){Check-DragMaximize $handles[0] $screens[0] $screens[1]}
 Move-ToMonitor $handles[0] $screens[1]
 Start-Sleep -Milliseconds 1200
 if([System.Windows.Forms.Screen]::FromHandle($handles[0]).DeviceName -ne $screens[1].DeviceName){throw 'Explicit system monitor move was undone'}
 Write-Output 'ok explicit monitor move remains under user control'
 Check-DragMaximize $handles[0] $screens[0] $screens[1]
 Assert-Placement
 $reference=@{}
 for($pass=0;$pass -lt 3;$pass++){
  foreach($focus in @($true,$false)){
   for($n=0;$n -lt 2;$n++){
    Assert-Placement
    $text=Read-Shape $handles[$n] 500 300 $focus
    $arrow=Read-Shape $handles[$n] 450 20 $focus
    $again=Read-Shape $handles[$n] 501 301 $focus
    if($text -eq $arrow -or $again -ne $text){throw ('Native text/arrow/text cursor mismatch on '+$screens[$n].DeviceName)}
    if($reference.ContainsKey($n) -and $reference[$n] -ne $text){throw 'Text cursor changed across window switches'}
    $reference[$n]=$text
    Write-Output ('ok native cursor images '+$screens[$n].DeviceName+' pass='+$pass+' focus='+$focus)
   }
  }
 }
 Write-Output 'PASS: distinct primary/secondary maximized windows retain actual cursor images across focus and hover switches'
} finally {
 if($original -ne [IntPtr]::Zero){[void][CursorTest]::SetForegroundWindow($original)}
 [void][CursorTest]::SetCursorPos($saved.Position.X,$saved.Position.Y)
}
