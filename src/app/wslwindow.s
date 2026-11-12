# WSLg host work-area workaround (RHUN_WSL_WINDOW_FIX=0 disables).
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
.globl wsl_window_native
wsl_window_native: .long 0
ww_used: .long 0
ww_width: .long 0
ww_height: .long 0
ww_packet: .zero 20
.p2align 3
ww_until: .quad 0
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
    cmp dword ptr [rip + ww_packet], 0
    jne .Lww_pointer
    mov eax, [rip + ww_packet + 4]
    mov [rip + ww_width], eax
    mov eax, [rip + ww_packet + 8]
    mov [rip + ww_height], eax
    mov eax, [rip + ww_packet + 12]
    mov [rip + wsl_window_native], eax
    jmp .Lww_continue
.Lww_pointer:
    cmp dword ptr [rip + wsl_window_native], 0
    je .Lww_continue
    test dword ptr [rip + g_win_states], 1
    jz .Lww_continue
    cmp dword ptr [rip + ww_packet], 4
    jne 3f
    call app_on_pointer_leave
    jmp .Lww_continue
3:  mov ecx, [rip + ww_width]
    test ecx, ecx
    jle .Lww_continue
    mov eax, [rip + ww_packet + 4]
    imul eax, [rip + g_cv + CV_w]
    cdq
    idiv ecx
    mov r13d, eax
    mov ecx, [rip + ww_height]
    test ecx, ecx
    jle .Lww_continue
    mov eax, [rip + ww_packet + 8]
    imul eax, [rip + g_cv + CV_h]
    cdq
    idiv ecx
    mov edi, r13d
    mov esi, eax
    call app_on_motion
    cmp dword ptr [rip + ww_packet], 2
    jne 4f
    mov edi, [rip + ww_packet + 12]
    mov esi, [rip + ww_packet + 16]
    mov edx, [rip + g_mods]
    call app_on_button
    jmp .Lww_continue
4:  cmp dword ptr [rip + ww_packet], 3
    jne .Lww_continue
    mov edi, [rip + ww_packet + 12]
    mov esi, [rip + ww_packet + 16]
    # Match Wayland's wheel scaling (120 protocol units -> 600 pixels / notch).
    imul edi, edi, 5
    imul esi, esi, 5
    mov edx, [rip + g_mods]
    call app_on_scroll
.Lww_continue:
    dec r12d
    jnz .Lww_read_next
    jmp .Lww_tick_done
.Lww_disconnect:
    mov dword ptr [rip + wsl_window_native], 0
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
