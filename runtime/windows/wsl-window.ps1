# $rhunWindowTag is supplied by rhun, unique to this process and startup.
# The pipe belongs to rhun: EOF stops this helper even if the HWND is gone.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Text;
using System.Threading;
using System.Collections.Concurrent;
using System.Runtime.InteropServices;
public static class RhunWindowArea {
    public struct Point { public int X, Y; }
    [StructLayout(LayoutKind.Sequential)]
    struct MouseData { public Point Point; public uint Data, Flags, Time; public UIntPtr Extra; }
    [StructLayout(LayoutKind.Sequential)]
    struct Message { public IntPtr Hwnd; public uint Id; public UIntPtr W; public IntPtr L; public uint Time; public Point Point; }
    delegate IntPtr MouseHook(int code, IntPtr message, IntPtr data);
    static MouseHook callback = OnMouse;
    static IntPtr hook, target;
    static Thread thread;
    static uint threadId;
    static ManualResetEvent started = new ManualResetEvent(false);
    static bool inside;
    static int pressed;
    public static volatile bool Active;
    public static ConcurrentQueue<int[]> Events = new ConcurrentQueue<int[]>();
    [DllImport("user32.dll")] static extern IntPtr SetWindowsHookEx(int type, MouseHook cb, IntPtr module, uint thread);
    [DllImport("user32.dll")] static extern bool UnhookWindowsHookEx(IntPtr hook);
    [DllImport("user32.dll")] static extern IntPtr CallNextHookEx(IntPtr hook,int code,IntPtr message,IntPtr data);
    [DllImport("user32.dll")] static extern int GetMessage(out Message message,IntPtr window,uint min,uint max);
    [DllImport("user32.dll")] static extern bool PostThreadMessage(uint thread,uint message,IntPtr w,IntPtr l);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode)] static extern IntPtr GetModuleHandle(string name);
    [DllImport("user32.dll")] static extern IntPtr WindowFromPoint(Point point);
    [DllImport("user32.dll")] static extern bool ScreenToClient(IntPtr hwnd,ref Point point);
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hwnd,out Rect rect);
    static void Enqueue(int kind, Point point, int a, int b) {
        if (Events.Count < 1024) Events.Enqueue(new int[] {kind,point.X,point.Y,a,b});
    }
    static IntPtr OnMouse(int code,IntPtr message,IntPtr data) {
        if (code >= 0 && Active && IsZoomed(target)) {
            MouseData m = (MouseData)Marshal.PtrToStructure(data,typeof(MouseData));
            bool hit = WindowFromPoint(m.Point) == target;
            int id = message.ToInt32();
            if (hit || pressed != 0) {
                if (id == 0x201) pressed |= 1;
                if (id == 0x204) pressed |= 2;
                if (id == 0x207) pressed |= 4;
                if (id == 0x202) pressed &= ~1;
                if (id == 0x205) pressed &= ~2;
                if (id == 0x208) pressed &= ~4;
            }
            if (hit || pressed != 0 || (inside && (id == 0x202 || id == 0x205 || id == 0x208))) {
                Point p = m.Point;
                ScreenToClient(target,ref p);
                inside = true;
                if (id == 0x200) Enqueue(1,p,0,0);
                else if (id == 0x201 || id == 0x202) Enqueue(2,p,1,id == 0x201 ? 1 : 0);
                else if (id == 0x204 || id == 0x205) Enqueue(2,p,3,id == 0x204 ? 1 : 0);
                else if (id == 0x207 || id == 0x208) Enqueue(2,p,2,id == 0x207 ? 1 : 0);
                else if (id == 0x20A || id == 0x20E)
                    Enqueue(3,p,id == 0x20E ? (short)(m.Data >> 16) : 0,
                        id == 0x20A ? -(short)(m.Data >> 16) : 0);
            } else if (inside) { inside = false; Enqueue(4,new Point(),0,0); }
        } else { pressed = 0; }
        // Never intercept or delay other applications' input; output happens on the main thread.
        return CallNextHookEx(hook,code,message,data);
    }
    public static bool Start(IntPtr hwnd) {
        target = hwnd;
        thread = new Thread(() => {
            threadId = GetCurrentThreadId();
            hook = SetWindowsHookEx(14,callback,GetModuleHandle(null),0);
            started.Set();
            Message m;
            while (GetMessage(out m,IntPtr.Zero,0,0) > 0) {}
            if (hook != IntPtr.Zero) UnhookWindowsHookEx(hook);
        });
        thread.IsBackground = true;
        thread.Start();
        return started.WaitOne(3000) && hook != IntPtr.Zero;
    }
    public static void Stop() {
        Active = false;
        if (threadId != 0) PostThreadMessage(threadId,0x12,IntPtr.Zero,IntPtr.Zero);
        if (thread != null) thread.Join(1000);
    }
    public delegate bool Callback(IntPtr hwnd, IntPtr data);
    [StructLayout(LayoutKind.Sequential)]
    public struct Rect { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool EnumWindows(Callback cb, IntPtr data);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int count);
    [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out Rect rect);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hwnd, IntPtr after,
        int x, int y, int width, int height, uint flags);
}
'@
$inputStream = [Console]::OpenStandardInput()
$inputByte = New-Object byte[] 1
$parentClosed = $inputStream.ReadAsync($inputByte, 0, 1)
$script:targetWindow = [IntPtr]::Zero
$findWindow = [RhunWindowArea+Callback]{ param($hwnd, $unused)
    $title = New-Object System.Text.StringBuilder 4096
    [void][RhunWindowArea]::GetWindowText($hwnd, $title, $title.Capacity)
    # WSLg appends the distribution name after the application's title.
    if ($title.ToString().Contains($rhunWindowTag)) {
        $script:targetWindow = $hwnd
        return $false
    }
    return $true
}
$deadline = [DateTime]::UtcNow.AddSeconds(20)
while ($script:targetWindow -eq [IntPtr]::Zero -and -not $parentClosed.IsCompleted) {
    [void][RhunWindowArea]::EnumWindows($findWindow, [IntPtr]::Zero)
    if ([DateTime]::UtcNow -gt $deadline) { exit 1 }
    if ($script:targetWindow -eq [IntPtr]::Zero) { Start-Sleep -Milliseconds 100 }
}
if ($parentClosed.IsCompleted) { exit 0 }
$targetWindow = $script:targetWindow
[uint32]$ownerPid = 0
[void][RhunWindowArea]::GetWindowThreadProcessId($targetWindow, [ref]$ownerPid)
# Handshake only after native input is ready, so we never disable working input on failure.
if (-not [RhunWindowArea]::Start($targetWindow)) { exit 1 }
[Console]::Out.Write('R')
[Console]::Out.Flush()
$output = New-Object System.IO.BinaryWriter ([Console]::OpenStandardOutput())
$lastMode = -1
$lastWidth = -1
$lastHeight = -1
$nextAreaCheck = [DateTime]::MinValue
try {
while (-not $parentClosed.IsCompleted -and [RhunWindowArea]::IsWindow($targetWindow)) {
    [uint32]$currentPid = 0
    [void][RhunWindowArea]::GetWindowThreadProcessId($targetWindow, [ref]$currentPid)
    if ($currentPid -ne $ownerPid) { break }
    $mode = [int][RhunWindowArea]::IsZoomed($targetWindow)
    if ($mode -eq 1 -and [DateTime]::UtcNow -ge $nextAreaCheck) {
        $area = [System.Windows.Forms.Screen]::FromHandle($targetWindow).WorkingArea
        $rect = New-Object RhunWindowArea+Rect
        if ([RhunWindowArea]::GetWindowRect($targetWindow, [ref]$rect) -and
            ($rect.Left -ne $area.Left -or $rect.Top -ne $area.Top -or
             $rect.Right -ne $area.Right -or $rect.Bottom -ne $area.Bottom)) {
            # SWP_NOZORDER | SWP_NOACTIVATE: preserve focus and maximized state.
            [void][RhunWindowArea]::SetWindowPos($targetWindow, [IntPtr]::Zero,
                $area.Left, $area.Top, $area.Width, $area.Height, 0x14)
        }
        $nextAreaCheck = [DateTime]::UtcNow.AddMilliseconds(200)
    }
    $clientRect = New-Object RhunWindowArea+Rect
    [void][RhunWindowArea]::GetClientRect($targetWindow,[ref]$clientRect)
    if ($mode -ne $lastMode -or $clientRect.Right -ne $lastWidth -or $clientRect.Bottom -ne $lastHeight) {
        foreach ($v in @(0,$clientRect.Right,$clientRect.Bottom,$mode,0)) { $output.Write([int]$v) }
        $lastMode = $mode
        $lastWidth = $clientRect.Right
        $lastHeight = $clientRect.Bottom
        [RhunWindowArea]::Active = $mode -eq 1
    }
    $event = $null
    while ([RhunWindowArea]::Events.TryDequeue([ref]$event)) {
        foreach ($v in $event) { $output.Write([int]$v) }
    }
    $output.Flush()
    Start-Sleep -Milliseconds 10
}
} finally { [RhunWindowArea]::Stop() }
