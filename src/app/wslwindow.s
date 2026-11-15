# WSLg private-input and cursor-lifetime helper (RHUN_WSL_WINDOW_FIX=0 disables).
# One helper owns exactly this window; stdin EOF ends it when rhun exits.
.include "rhun.inc"
.bss
.p2align 3
ww_script: .zero SB_SIZE
ww_tag: .zero SB_SIZE
ww_title: .zero SB_SIZE
ww_display: .zero SB_SIZE
ww_pid: .long 0
ww_tagged: .long 0
.globl wsl_window_keyboard
wsl_window_keyboard: .long 0
ww_keys: .quad 0
ww_used: .long 0
ww_packet: .zero 20
.p2align 3
ww_until: .quad 0
ww_key_until: .quad 0
.data
ww_read: .long -1
ww_write: .long -1
.section .rodata
ww_enable: .asciz "RHUN_WSL_WINDOW_FIX"
ww_interop: .asciz "WSL_INTEROP"
ww_wslg: .asciz "/mnt/wslg"
ww_ps: .asciz "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
ww_noprofile: .asciz "-NoProfile"
ww_noninteractive: .asciz "-NonInteractive"
ww_command: .asciz "-Command"
ww_tag_start: .asciz " [rhun-wsl-"
ww_script_start: .asciz "$rhunWindowTag='"
ww_script_end: .asciz "';"
.text

# Read-only diagnostics for native GUI regression tests.
FN wsl_window_input_dump
    PROLOGUE
    mov rbx, rdi
    lea rsi, [rip + ww_route]
    call sb_push_cstr
    mov rdi, rbx
    mov esi, [rip + wsl_window_keyboard]
    call sb_push_u64
    mov rdi, rbx
    lea rsi, [rip + ww_keycount]
    call sb_push_cstr
    mov rdi, rbx
    mov rsi, [rip + ww_keys]
    call sb_push_u64
    mov rdi, rbx
    call fcitx_host_dump
    mov rdi, rbx
    mov esi, 10
    call sb_push_byte
    EPILOGUE
.section .rodata
ww_route: .asciz "host_relay="
ww_keycount: .asciz " keys="
.text

FN wsl_window_start
.ifdef MACOS
    ret
.else
.ifdef WINDOWS
    ret
.else
    PROLOGUE 64
    lea rdi, [rip + ww_enable]
    call getenv
    test rax, rax
    jz 1f
    cmp byte ptr [rax], '0'
    je .Lww_start_done
1:
    lea rdi, [rip + ww_interop]
    call getenv
    test rax, rax
    jz .Lww_start_done
    lea rdi, [rip + ww_wslg]
    xor esi, esi
    SYS SYS_access
    test eax, eax
    js .Lww_start_done
    lea rdi, [rip + ww_ps]
    mov esi, 1
    SYS SYS_access
    test eax, eax
    js .Lww_start_done
    lea rdi, [rip + ww_tag]
    lea rsi, [rip + ww_tag_start]
    call sb_push_cstr
    SYS SYS_getpid
    mov rsi, rax
    lea rdi, [rip + ww_tag]
    call sb_push_u64
    lea rdi, [rip + ww_tag]
    mov esi, '-'
    call sb_push_byte
    call time_ms
    mov rsi, rax
    lea rdi, [rip + ww_tag]
    call sb_push_u64
    lea rdi, [rip + ww_tag]
    mov esi, ']'
    call sb_push_byte
    lea rdi, [rip + ww_script]
    lea rsi, [rip + ww_script_start]
    call sb_push_cstr
    lea rdi, [rip + ww_script]
    mov rsi, [rip + ww_tag + SB_ptr]
    mov rdx, [rip + ww_tag + SB_len]
    call sb_push
    lea rdi, [rip + ww_script]
    lea rsi, [rip + ww_script_end]
    call sb_push_cstr
    lea rdi, [rip + ww_script]
    lea rsi, [rip + wsl_window_script]
    call sb_push_cstr
    lea rdi, [rip + ww_script]
    xor esi, esi
    call sb_push_byte
    lea rax, [rip + ww_ps]
    mov [rsp], rax
    lea rax, [rip + ww_noprofile]
    mov [rsp + 8], rax
    lea rax, [rip + ww_noninteractive]
    mov [rsp + 16], rax
    lea rax, [rip + ww_command]
    mov [rsp + 24], rax
    mov rax, [rip + ww_script + SB_ptr]
    mov [rsp + 32], rax
    mov qword ptr [rsp + 40], 0
    mov rdi, rsp
    mov rsi, [rip + g_envp]
    xor edx, edx
    xor ecx, ecx
    mov r8d, 1
    mov r9d, 4                  # keep stdin pipe: EOF terminates host helper
    call run_piped_input
    test eax, eax
    js .Lww_start_free
    mov [rip + ww_pid], eax
    mov [rip + ww_read], edx
    mov [rip + ww_write], ecx
    mov dword ptr [rip + ww_tagged], 1
    call time_ms
    add rax, 25000
    mov [rip + ww_until], rax
.Lww_start_free:
    lea rdi, [rip + ww_script]
    call sb_free
.Lww_start_done:
    EPILOGUE
.endif
.endif

# wsl_window_title(title) -> same title, with temporary process token before handshake.
FN wsl_window_title
    cmp dword ptr [rip + ww_tagged], 0
    jne 1f
    mov rax, rdi
    ret
1:  PROLOGUE
    mov rbx, rdi
    lea rdi, [rip + ww_title]
    call sb_clear
    lea rdi, [rip + ww_title]
    mov rsi, rbx
    call sb_push_cstr
    lea rdi, [rip + ww_title]
    xor esi, esi
    call sb_push_byte
    lea rdi, [rip + ww_display]
    call sb_clear
    lea rdi, [rip + ww_display]
    mov rsi, rbx
    call sb_push_cstr
    lea rdi, [rip + ww_display]
    mov rsi, [rip + ww_tag + SB_ptr]
    mov rdx, [rip + ww_tag + SB_len]
    call sb_push
    lea rdi, [rip + ww_display]
    xor esi, esi
    call sb_push_byte
    mov rax, [rip + ww_display + SB_ptr]
    EPILOGUE

FN wsl_window_timeout
    mov eax, -1
    cmp dword ptr [rip + ww_read], -1
    je 1f
    mov eax, 10
1:  ret

FN wsl_window_tick
.ifdef MACOS
    ret
.else
.ifdef WINDOWS
    ret
.else
    cmp dword ptr [rip + ww_read], -1
    jne 1f
    ret
1:  PROLOGUE 16
    cmp dword ptr [rip + ww_tagged], 0
    jne .Lww_read_start
    call time_ms
    cmp rax, [rip + ww_key_until]
    jb .Lww_read_start
    add rax, 250
    mov [rip + ww_key_until], rax
    call fcitx_active
    cmp dword ptr [rip + cfg_chinese_follow_host], 0
    je .Lww_heartbeat
    or eax, 2
.Lww_heartbeat:
    mov [rsp], al
    mov edi, [rip + ww_write]
    mov rsi, rsp
    mov edx, 1
    SYS SYS_write
.Lww_read_start:
    mov r12d, 128
.Lww_read_next:
    mov edi, [rip + ww_read]
    cmp dword ptr [rip + ww_tagged], 0
    je .Lww_read_event
    mov rsi, rsp
    mov edx, 1
    jmp .Lww_do_read
.Lww_read_event:
    mov esi, [rip + ww_used]
    lea rax, [rip + ww_packet]
    add rsi, rax
    mov edx, 20
    sub edx, [rip + ww_used]
.Lww_do_read:
    SYS SYS_read
    cmp dword ptr [rip + ww_tagged], 0
    je .Lww_event_read
    cmp eax, 1
    jne 2f
    cmp byte ptr [rsp], 'R'
    je .Lww_ready
    jmp .Lww_failed
2:
    test eax, eax
    jz .Lww_failed
    call time_ms
    cmp rax, [rip + ww_until]
    jb .Lww_tick_done
.Lww_failed:
    mov edi, [rip + ww_write]
    SYS SYS_close
    mov dword ptr [rip + ww_write], -1
    mov edi, [rip + ww_read]
    SYS SYS_close
    mov dword ptr [rip + ww_read], -1
.Lww_ready:
    mov dword ptr [rip + ww_tagged], 0
    mov edi, [rip + ww_pid]
    call reap_later
    mov rdi, [rip + ww_title + SB_ptr]
    test rdi, rdi
    jz .Lww_tick_done
    call qword ptr [rip + g_plat + P_title]
    jmp .Lww_tick_done
.Lww_event_read:
    cmp eax, -EAGAIN
    je .Lww_tick_done
    cmp eax, -EINTR
    je .Lww_tick_done
    test eax, eax
    jle .Lww_disconnect
    add [rip + ww_used], eax
    cmp dword ptr [rip + ww_used], 20
    jne .Lww_tick_done
    mov dword ptr [rip + ww_used], 0
    cmp dword ptr [rip + ww_packet], 8
    jne .Lww_not_cursor_recovery
    call wl_cursor_refresh
    mov dword ptr [rip + g_dirty], 1
    jmp .Lww_continue
.Lww_not_cursor_recovery:
    cmp dword ptr [rip + ww_packet], 7
    jne .Lww_not_ime_state
    mov edi, [rip + ww_packet + 12]
    call fcitx_follow_host
    jmp .Lww_continue
.Lww_not_ime_state:
    cmp dword ptr [rip + ww_packet], 6
    jne .Lww_keyboard_event
    mov eax, [rip + ww_packet + 12]
    mov [rip + wsl_window_keyboard], eax
    call wl_host_input_reset
    jmp .Lww_continue
.Lww_keyboard_event:
    cmp dword ptr [rip + ww_packet], 5
    jne .Lww_continue
    inc qword ptr [rip + ww_keys]
    mov edi, [rip + ww_packet + 4]
    mov esi, [rip + ww_packet + 8]
    mov edx, [rip + ww_packet + 12]
    call wl_host_key
    jmp .Lww_continue
.Lww_continue:
    dec r12d
    jnz .Lww_read_next
    jmp .Lww_tick_done
.Lww_disconnect:
    mov edi, -1
    call fcitx_follow_host
    mov dword ptr [rip + wsl_window_keyboard], 0
    mov edi, [rip + ww_read]
    SYS SYS_close
    mov dword ptr [rip + ww_read], -1
    mov edi, [rip + ww_write]
    SYS SYS_close
    mov dword ptr [rip + ww_write], -1
.Lww_tick_done:
    EPILOGUE
.endif
.endif
