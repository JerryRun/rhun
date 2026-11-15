# Observe this WSLg window and relay private-input keys. Mouse input stays native.
# A bounded native monitor move repairs stale-work-area maximize transitions.
# $rhunWindowTag is supplied by rhun, unique to this process and startup.
# The pipe belongs to rhun: EOF stops this helper even if the HWND is gone.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Add-Type @'
using System;
using System.Text;
using System.Threading;
using System.Collections.Concurrent;
using System.Runtime.InteropServices;
public static class RhunWindowArea {
    public struct Point { public int X, Y; }
    [StructLayout(LayoutKind.Sequential)]
    struct KeyData { public uint Key, Scan, Flags, Time; public UIntPtr Extra; }
    [StructLayout(LayoutKind.Sequential)]
    struct Message { public IntPtr Hwnd; public uint Id; public UIntPtr W; public IntPtr L; public uint Time; public Point Point; }
    delegate IntPtr InputHook(int code, IntPtr message, IntPtr data);
    static InputHook keyCallback = OnKey;
    static IntPtr keyHook, target;
    static Thread thread;
    static uint threadId;
    static ManualResetEvent started = new ManualResetEvent(false);
    public static volatile bool Keyboard;
    public static volatile bool FollowHostIme;
    static readonly object imeLock = new object();
    static int lastHostIme = -2;
    [DllImport("imm32.dll")] static extern IntPtr ImmGetDefaultIMEWnd(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetKeyboardLayout(uint thread);
    [DllImport("user32.dll")] static extern IntPtr SendMessageTimeout(IntPtr h,
        uint message,UIntPtr command,IntPtr value,uint flags,uint timeout,out UIntPtr result);
    static long ImeQuery(IntPtr h,uint command) {
        UIntPtr result;
        if (h == IntPtr.Zero || SendMessageTimeout(h,0x283,new UIntPtr(command),
            IntPtr.Zero,2,25,out result) == IntPtr.Zero) return -1;
        return unchecked((long)result.ToUInt64());
    }
    public static int DecodeHostImeState(int language, long open, long conversion) {
        if (language == 0) return -1;
        if (language != 4) return 0;
        if (open < 0) return -1;
        if (open == 0) return 0;
        // WSLg's proxy can retain SYMBOL (0x400) in both modes.
        // In that state Shift changes open/close, not NATIVE.
        // Normal IMM contexts still use NATIVE to distinguish modes.
        if (conversion == 0x400) return 1;
        return conversion < 0 ? -1 : ((conversion & 1) != 0 ? 1 : 0);
    }
    // Only observe the host state; never change its open/conversion mode.
    public static void SetFollowHostIme(bool enabled) {
        lock (imeLock) {
            if (FollowHostIme == enabled) return;
            FollowHostIme = enabled;
            lastHostIme = -2;
            if (!enabled) Events.Enqueue(new int[]{7,0,0,-1,0});
        }
    }
    public static void ObserveHostIme() {
        lock (imeLock) {
            if (!FollowHostIme || !Keyboard || DateTime.UtcNow.Ticks > Interlocked.Read(ref keyboardUntil) ||
                GetForegroundWindow() != target) { lastHostIme = -2; return; }
            uint pid;
            uint thread = GetWindowThreadProcessId(target,out pid);
            int language = (int)(GetKeyboardLayout(thread).ToInt64() & 0x3FF);
            int state = -1;
            if (thread != 0) {
                IntPtr ime = ImmGetDefaultIMEWnd(target);
                long open = language == 4 ? ImeQuery(ime,5) : -1;
                long conversion = open > 0 ? ImeQuery(ime,1) : -1;
                state = DecodeHostImeState(language,open,conversion);
            }
            if (state != lastHostIme) {
                lastHostIme = state;
                Events.Enqueue(new int[]{7,0,0,state,0});
            }
        }
    }
    [StructLayout(LayoutKind.Sequential)]
    struct CursorInfo { public uint Size, Flags; public IntPtr Cursor; public Point Position; }
    [DllImport("user32.dll")] static extern bool GetCursorInfo(ref CursorInfo info);
    static long nextCursorRecovery;
    // WSLg hides the shared host cursor when any client's cursor surface dies.
    // Recovery must not depend on motion or focus events in the surviving app.
    public static void ObserveCursor() {
        if (GetForegroundWindow() != target) return;
        CursorInfo info = new CursorInfo();
        info.Size = (uint)Marshal.SizeOf(typeof(CursorInfo));
        if (!GetCursorInfo(ref info) || info.Flags != 0 || info.Cursor != IntPtr.Zero ||
            WindowFromPoint(info.Position) != target) return;
        long now = DateTime.UtcNow.Ticks;
        if (now < nextCursorRecovery) return;
        nextCursorRecovery = now + TimeSpan.TicksPerMillisecond * 250;
        Events.Enqueue(new int[]{8,0,0,0,0});
    }

    [StructLayout(LayoutKind.Sequential)] public struct Rect { public int Left,Top,Right,Bottom; }
    [StructLayout(LayoutKind.Sequential)] struct MonitorInfo { public int Size; public Rect Bounds,Work; public uint Flags; }
    [StructLayout(LayoutKind.Explicit,Size=40)] struct NativeInput {
        [FieldOffset(0)] public uint Type;
        [FieldOffset(8)] public ushort Key;
        [FieldOffset(12)] public uint Flags;
        [FieldOffset(24)] public UIntPtr Extra;
    }
    [DllImport("user32.dll")] static extern bool IsZoomed(IntPtr h);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr MonitorFromWindow(IntPtr h,uint flags);
    [DllImport("user32.dll")] static extern bool GetMonitorInfo(IntPtr h,ref MonitorInfo info);
    [DllImport("user32.dll")] static extern int GetSystemMetrics(int index);
    [DllImport("user32.dll")] static extern uint SendInput(uint count,NativeInput[] input,int size);
    static readonly UIntPtr monitorInputTag=new UIntPtr(0x52484D56);
    static IntPtr normalMonitor,pendingMonitor;
    static Rect normalBounds,pendingBounds;
    static bool wasZoomed;
    static long monitorDue,monitorDeadline,monitorIdleUntil;
    static int monitorUserMove,normalUserMove,pendingUserMove;
    static bool ReadMonitor(IntPtr h,out MonitorInfo info) {
        info=new MonitorInfo();info.Size=Marshal.SizeOf(typeof(MonitorInfo));
        return h!=IntPtr.Zero && GetMonitorInfo(h,ref info);
    }
    static bool SameRect(Rect a,Rect b) {
        return a.Left==b.Left && a.Top==b.Top && a.Right==b.Right && a.Bottom==b.Bottom;
    }
    static NativeInput MonitorKey(ushort key,bool up) {
        NativeInput i=new NativeInput();i.Type=1;i.Key=key;i.Extra=monitorInputTag;
        i.Flags=(key==0xA0?0u:1u)|(up?2u:0u);return i;
    }
    // Only repair a normal-to-maximized transition which unexpectedly changes
    // monitors. A system monitor move synchronizes RAIL and compositor position;
    // direct HWND geometry writes do not. Never take ownership of pointer input.
    public static void ObserveMaximizeMonitor() {
        long now=DateTime.UtcNow.Ticks;
        if(IsIconic(target)){normalMonitor=pendingMonitor=IntPtr.Zero;wasZoomed=false;return;}
        bool zoomed=IsZoomed(target);
        IntPtr current=MonitorFromWindow(target,0);
        MonitorInfo info;
        if(!ReadMonitor(current,out info))return;
        if(!zoomed) {
            pendingMonitor=IntPtr.Zero;
            normalMonitor=current;normalBounds=info.Bounds;
            normalUserMove=Interlocked.CompareExchange(ref monitorUserMove,0,0);
        } else if(!wasZoomed && normalMonitor!=IntPtr.Zero) {
            pendingMonitor=normalMonitor;pendingBounds=normalBounds;
            pendingUserMove=normalUserMove;
            monitorDue=now+TimeSpan.TicksPerMillisecond*200;
            monitorDeadline=now+TimeSpan.TicksPerSecond;
        }
        wasZoomed=zoomed;
        if(pendingMonitor==IntPtr.Zero || now<monitorDue)return;
        if(now>monitorDeadline || !zoomed || GetForegroundWindow()!=target || GetSystemMetrics(80)!=2 ||
            pendingUserMove!=Interlocked.CompareExchange(ref monitorUserMove,0,0)) {
            pendingMonitor=IntPtr.Zero;return;
        }
        if(current==pendingMonitor){pendingMonitor=IntPtr.Zero;return;}
        MonitorInfo wanted;
        if(!ReadMonitor(pendingMonitor,out wanted) || !SameRect(wanted.Bounds,pendingBounds)) {
            pendingMonitor=IntPtr.Zero;return;
        }
        // Do not interfere with a held key/button, focus switch or active typing.
        if(now<Interlocked.Read(ref monitorIdleUntil))return;
        for(int key=1;key<256;key++)if((GetAsyncKeyState(key)&0x8000)!=0)return;
        ushort arrow=wanted.Bounds.Left<info.Bounds.Left?(ushort)0x25:(ushort)0x27;
        NativeInput[] chord={MonitorKey(0x5B,false),MonitorKey(0xA0,false),
            MonitorKey(arrow,false),MonitorKey(arrow,true),MonitorKey(0xA0,true),MonitorKey(0x5B,true)};
        pendingMonitor=IntPtr.Zero; // one bounded attempt per maximize, never a polling fight
        if(GetForegroundWindow()==target && IsZoomed(target))
            SendInput((uint)chord.Length,chord,Marshal.SizeOf(typeof(NativeInput)));
    }

    public static bool KeyboardAvailable { get { return keyHook != IntPtr.Zero; } }
    static bool keyboardFocused;
    static bool[] down = new bool[256];
    static int locks;
    static long keyboardUntil;
    public static ConcurrentQueue<int[]> Events = new ConcurrentQueue<int[]>();
    [DllImport("user32.dll")] static extern IntPtr SetWindowsHookEx(int type, InputHook cb, IntPtr module, uint thread);
    [DllImport("user32.dll")] static extern bool UnhookWindowsHookEx(IntPtr hook);
    [DllImport("user32.dll")] static extern IntPtr CallNextHookEx(IntPtr hook,int code,IntPtr message,IntPtr data);
    [DllImport("user32.dll")] static extern int GetMessage(out Message message,IntPtr window,uint min,uint max);
    [DllImport("user32.dll")] static extern bool PostThreadMessage(uint thread,uint message,IntPtr w,IntPtr l);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode)] static extern IntPtr GetModuleHandle(string name);
    [DllImport("user32.dll")] static extern IntPtr WindowFromPoint(Point point);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern short GetKeyState(int key);
    [DllImport("user32.dll")] static extern short GetAsyncKeyState(int key);
    static int Modifiers() {
        return ((down[0x10] || down[0xA0] || down[0xA1]) ? 1 : 0) |
            ((down[0x11] || down[0xA2] || down[0xA3]) ? 4 : 0) |
            ((down[0x12] || down[0xA4] || down[0xA5]) ? 8 : 0) |
            ((down[0x5B] || down[0x5C]) ? 64 : 0);
    }
    // PC set-1 scan codes match evdev below 0x54; E0 keys need explicit mapping.
    static int LinuxKey(KeyData k) {
        int s = (int)k.Scan;
        if (k.Key == 0x13) return 119; // Pause
        if ((k.Flags & 1) == 0) {
            if (s >= 0x56 && s <= 0x58) return s; // ISO key, F11/F12
            return s > 0 && s <= 0x53 ? s : 0;
        }
        switch (s) {
            case 0x1C: return 96; case 0x1D: return 97; case 0x35: return 98;
            case 0x37: return 99; case 0x38: return 100; case 0x47: return 102;
            case 0x48: return 103; case 0x49: return 104; case 0x4B: return 105;
            case 0x4D: return 106; case 0x4F: return 107; case 0x50: return 108;
            case 0x51: return 109; case 0x52: return 110; case 0x53: return 111;
            case 0x5B: return 125; case 0x5C: return 126; case 0x5D: return 127;
        }
        return 0;
    }
    static IntPtr OnKey(int code, IntPtr message, IntPtr data) {
        // No input is read or retained for any other window. This temporary
        // relay leaves Windows IME contexts, layouts and configuration intact.
        if (code < 0 || DateTime.UtcNow.Ticks > Interlocked.Read(ref keyboardUntil) ||
            GetForegroundWindow() != target) {
            keyboardFocused = false;
            return CallNextHookEx(keyHook,code,message,data);
        }
        KeyData k = (KeyData)Marshal.PtrToStructure(data,typeof(KeyData));
        if(k.Extra==monitorInputTag)return CallNextHookEx(keyHook,code,message,data);
        Interlocked.Exchange(ref monitorIdleUntil,DateTime.UtcNow.AddMilliseconds(200).Ticks);
        if(k.Key==0x5B || k.Key==0x5C)Interlocked.Increment(ref monitorUserMove);
        if (!Keyboard) return CallNextHookEx(keyHook,code,message,data);
        if (k.Key >= 256) return CallNextHookEx(keyHook,code,message,data);
        if (!keyboardFocused) {
            Array.Clear(down,0,down.Length);
            foreach (int v in new int[]{0xA0,0xA1,0xA2,0xA3,0xA4,0xA5,0x5B,0x5C})
                down[v] = (GetAsyncKeyState(v) & 0x8000) != 0;
            locks = ((GetKeyState(0x14) & 1) != 0 ? 2 : 0) |
                ((GetKeyState(0x90) & 1) != 0 ? 16 : 0);
            keyboardFocused = true;
        }
        bool pressedKey = (k.Flags & 0x80) == 0;
        bool repeat = down[k.Key];
        down[k.Key] = pressedKey;
        int mods = Modifiers();
        // Keep desktop/window management shortcuts with Windows.
        if ((mods & 64) != 0 || k.Key == 0x5B || k.Key == 0x5C ||
            ((mods & 8) != 0 && (k.Key == 9 || k.Key == 0x1B || k.Key == 0x73)) ||
            ((mods & 4) != 0 && k.Key == 0x1B))
            return CallNextHookEx(keyHook,code,message,data);
        int key = LinuxKey(k);
        if (key == 0) return CallNextHookEx(keyHook,code,message,data);
        if (pressedKey && !repeat) {
            if (k.Key == 0x14) locks ^= 2;
            if (k.Key == 0x90) locks ^= 16;
        }
        if (pressedKey) ObserveHostIme(); // ordered before this physical key
        // Forward supported physical keys through the ordered window pipe.
        Events.Enqueue(new int[]{5,key,pressedKey ? 1 : 0,mods | locks,0});
        // Windows must still see modifier/lock transitions for Alt+Tab,
        // Alt+F4 and keyboard LEDs. Text-producing keys stop before its IME.
        if (k.Key == 0x10 || k.Key == 0x11 || k.Key == 0x12 ||
            (k.Key >= 0xA0 && k.Key <= 0xA5) || k.Key == 0x14 || k.Key == 0x90)
            return CallNextHookEx(keyHook,code,message,data);
        return new IntPtr(1);
    }
    public static void SetKeyboard(bool enabled) {
        Interlocked.Exchange(ref keyboardUntil,DateTime.UtcNow.AddSeconds(2).Ticks);
        bool next = enabled && keyHook != IntPtr.Zero;
        if (Keyboard != next) { keyboardFocused = false; lastHostIme = -2; }
        Keyboard = next;
    }
    public static bool Start(IntPtr hwnd) {
        target = hwnd;
        thread = new Thread(() => {
            threadId = GetCurrentThreadId();
            keyHook = SetWindowsHookEx(13,keyCallback,GetModuleHandle(null),0);
            started.Set();
            Message message;
            while (GetMessage(out message,IntPtr.Zero,0,0) > 0) { }
            if (keyHook != IntPtr.Zero) UnhookWindowsHookEx(keyHook);
        });
        thread.IsBackground = true;
        thread.Start();
        return started.WaitOne(3000) && keyHook != IntPtr.Zero;
    }
    public static void Stop() {
        SetKeyboard(false);
        if (threadId != 0) PostThreadMessage(threadId,0x12,IntPtr.Zero,IntPtr.Zero);
        if (thread != null) thread.Join(1000);
    }
    public delegate bool Callback(IntPtr hwnd, IntPtr data);
    [DllImport("user32.dll")] public static extern bool EnumWindows(Callback cb, IntPtr data);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int count);
    [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
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
$nextImeCheck = [DateTime]::MinValue
try {
while ([RhunWindowArea]::IsWindow($targetWindow)) {
    if ($parentClosed.IsCompleted) {
        $read = $parentClosed.GetAwaiter().GetResult()
        if ($read -eq 0) { break }
        $flags = [int]$inputByte[0]
        [RhunWindowArea]::SetFollowHostIme(($flags -band 2) -ne 0)
        $enableKeyboard = ($flags -band 1) -ne 0 -and [RhunWindowArea]::KeyboardAvailable
        if ($enableKeyboard -ne [RhunWindowArea]::Keyboard) {
            # Queue acknowledgement before enabling the hook: raw keys follow it.
            [RhunWindowArea]::Events.Enqueue([int[]]@(6,0,0,[int]$enableKeyboard,0))
        }
        [RhunWindowArea]::SetKeyboard($enableKeyboard)
        $parentClosed = $inputStream.ReadAsync($inputByte,0,1)
    }
    [uint32]$currentPid = 0
    [void][RhunWindowArea]::GetWindowThreadProcessId($targetWindow, [ref]$currentPid)
    if ($currentPid -ne $ownerPid) { break }
    if ([DateTime]::UtcNow -ge $nextImeCheck) {
        [RhunWindowArea]::ObserveHostIme()
        [RhunWindowArea]::ObserveCursor()
        $nextImeCheck = [DateTime]::UtcNow.AddMilliseconds(100)
    }
    [RhunWindowArea]::ObserveMaximizeMonitor()
    $event = $null
    while ([RhunWindowArea]::Events.TryDequeue([ref]$event)) {
        foreach ($v in $event) { $output.Write([int]$v) }
    }
    $output.Flush()
    Start-Sleep -Milliseconds 10
}
} finally { [RhunWindowArea]::Stop() }
