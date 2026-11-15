# Read-only IME telemetry. No text, registry writes, layout changes or IME setters.
param([int]$Seconds = 8, [long]$WindowHandle = 0)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class HostImeProbe {
    [StructLayout(LayoutKind.Sequential)] public struct Rect { public int L,T,R,B; }
    [StructLayout(LayoutKind.Sequential)] public struct GuiInfo {
        public int Size, Flags;
        public IntPtr Active,Focus,Capture,MenuOwner,MoveSize,Caret;
        public Rect CaretRect;
    }
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h,out uint pid);
    [DllImport("user32.dll")] public static extern IntPtr GetKeyboardLayout(uint thread);
    [DllImport("user32.dll")] public static extern bool GetGUIThreadInfo(uint thread,ref GuiInfo info);
    [DllImport("imm32.dll")] public static extern IntPtr ImmGetDefaultIMEWnd(IntPtr h);
    [DllImport("user32.dll",SetLastError=true)] public static extern IntPtr SendMessageTimeout(
        IntPtr h,uint message,UIntPtr w,IntPtr l,uint flags,uint timeout,out UIntPtr result);
    public static long Query(IntPtr h,uint command) {
        if(h == IntPtr.Zero) return -1;
        UIntPtr result;
        if(SendMessageTimeout(h,0x283,new UIntPtr(command),IntPtr.Zero,2,100,out result)==IntPtr.Zero)
            return -1;
        return unchecked((long)result.ToUInt64());
    }
}
'@
$until=[DateTime]::UtcNow.AddSeconds($Seconds)
$last=''
do {
    $foreground=[HostImeProbe]::GetForegroundWindow()
    $window=$foreground
    if($WindowHandle -ne 0){$window=[IntPtr]$WindowHandle}
    [uint32]$owner=0
    $thread=[HostImeProbe]::GetWindowThreadProcessId($window,[ref]$owner)
    $gui=New-Object HostImeProbe+GuiInfo
    $gui.Size=[Runtime.InteropServices.Marshal]::SizeOf($gui)
    $focus=$window
    if([HostImeProbe]::GetGUIThreadInfo($thread,[ref]$gui) -and $gui.Focus -ne [IntPtr]::Zero){$focus=$gui.Focus}
    $ime=[HostImeProbe]::ImmGetDefaultIMEWnd($focus)
    $row=[ordered]@{
        foreground=$foreground.ToInt64();window=$window.ToInt64();focus=$focus.ToInt64();owner=$owner
        layout=[HostImeProbe]::GetKeyboardLayout($thread).ToInt64().ToString('x')
        ime=$ime.ToInt64();open=[HostImeProbe]::Query($ime,5);conversion=[HostImeProbe]::Query($ime,1)
    }
    $json=$row|ConvertTo-Json -Compress
    if($json -ne $last){Write-Output $json;$last=$json}
    Start-Sleep -Milliseconds 100
} while([DateTime]::UtcNow -lt $until)
