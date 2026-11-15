# Optional app-private Fcitx5 client. All I/O is bounded and nonblocking.
.include "rhun.inc"
.bss
.p2align 3
.globl fcitx_wire_pid, fcitx_wire_ready
fcitx_wire_pid:
fi_pid: .long 0
fcitx_wire_ready:
fi_ready: .long 0
fi_generation: .long 0
fi_focus: .long 0
fi_target: .quad 0
fi_deadline: .quad 0
fi_used: .long 0
fi_packet: .zero 4112
fi_request: .zero 32
fi_pending: .zero 8192
fi_exe: .zero 4096
fi_queued: .long 0
fi_sent: .long 0
.data
fi_host_mode: .long -1          # -1 unavailable, 0 English, 1 Chinese
fi_host_applied: .long -1       # acknowledgement from the private engine
fi_read: .long -1
fi_write: .long -1
.section .rodata
fi_enable: .asciz "RHUN_FCITX_ROOT"
fi_shell: .asciz "/bin/sh"
fi_arg: .asciz "-c"
fi_name: .asciz "rhun-ime"
fi_self: .asciz "/proc/self/exe"
fi_failed: .asciz "Inline Chinese input unavailable; normal keyboard input restored."
fi_chinese: .asciz "Chinese Pinyin input on. Shortcut: Keyboard Shortcuts > Input."
fi_english: .asciz "English input on. Shortcut: Keyboard Shortcuts > Input."
fi_available: .asciz "Chinese Pinyin input ready. WSL input mode follows Settings > Editor."
fi_following: .asciz "Input mode follows Windows. Disable Follow Windows input mode to use rhun input shortcuts."
.text
FN fcitx_apply
.ifdef WINDOWS
    ret
.else
.ifdef MACOS
    ret
.else
    cmp dword ptr [rip + cfg_chinese_input], 0
    je fcitx_stop
    jmp fcitx_start
.endif
.endif

FN fcitx_start
.ifdef MACOS
    ret
.else
.ifdef WINDOWS
    ret
.else
    PROLOGUE 64
    cmp dword ptr [rip + fi_pid], 0
    jne 9f
    cmp dword ptr [rip + cfg_chinese_input], 0
    jne .Lfi_start_client
    lea rdi, [rip + fi_enable]
    call getenv
    test rax, rax
    jz 9f
    cmp byte ptr [rax], 0
    je 9f
.Lfi_start_client:
    lea rdi, [rip + fi_self]
    lea rsi, [rip + fi_exe]
    mov edx, 4095
    SYS SYS_readlink
    test rax, rax
    js 9f
    lea rcx, [rip + fi_exe]
    mov byte ptr [rcx + rax], 0
    lea rax, [rip + fi_shell]
    mov [rsp], rax
    lea rax, [rip + fi_arg]
    mov [rsp + 8], rax
    lea rax, [rip + fcitx_start_script]
    mov [rsp + 16], rax
    lea rax, [rip + fi_name]
    mov [rsp + 24], rax
    call config_dir
    mov [rsp + 32], rax
    lea rax, [rip + fi_exe]
    mov [rsp + 40], rax
    lea rax, [rip + fcitx_client_script]
    mov [rsp + 48], rax
    mov qword ptr [rsp + 56], 0
    mov rdi, rsp
    mov rsi, [rip + g_envp]
    xor edx, edx
    xor ecx, ecx
    mov r8d, 1
    mov r9d, 4              # stdin retained; private engine needs its D-Bus socket
    call run_piped_input
    test eax, eax
    js 9f
    mov [rip + fi_pid], eax
    mov [rip + fi_read], edx
    mov [rip + fi_write], ecx
    call ime_clear             # discard native composition on ownership change
    call time_ms
    add rax, 15000
    mov [rip + fi_deadline], rax
9:  EPILOGUE
.endif
.endif

FN fcitx_timeout
    mov eax, -1
    cmp dword ptr [rip + fi_read], -1
    je 1f
    mov eax, 10
1:  ret

# Queue an entire fixed request, preserving order on a partially full pipe.
fi_send:
    PROLOGUE
    mov eax, [rip + fi_queued]
    cmp eax, 8192 - 32
    ja .Lfi_send_fail
    lea rdi, [rip + fi_pending]
    add rdi, rax
    lea rsi, [rip + fi_request]
    mov edx, 32
    call memcpy
    add dword ptr [rip + fi_queued], 32
    call fi_flush
    EPILOGUE
.Lfi_send_fail:
    call fcitx_stop
    EPILOGUE
fi_flush:
    PROLOGUE
    mov edx, [rip + fi_queued]
    sub edx, [rip + fi_sent]
    jle 9f
    mov edi, [rip + fi_write]
    lea rsi, [rip + fi_pending]
    mov eax, [rip + fi_sent]
    add rsi, rax
    SYS SYS_write
    cmp eax, -EAGAIN
    je 9f
    cmp eax, -EINTR
    je 9f
    test eax, eax
    jle 8f
    add [rip + fi_sent], eax
    mov eax, [rip + fi_sent]
    cmp eax, [rip + fi_queued]
    jne 9f
    mov dword ptr [rip + fi_sent], 0
    mov dword ptr [rip + fi_queued], 0
9:  EPILOGUE
8:  call fcitx_stop
    EPILOGUE

# Sync the composition destination before queuing input and before delivering replies.
fi_sync:
    PROLOGUE
    cmp dword ptr [rip + fi_ready], 0
    je 9f
    mov r12d, -1
    xor r13d, r13d
    mov eax, [rip + g_win_focused]
    test eax, eax
    je 3f
    call palette_is_secret
    test eax, eax
    jnz 3f
    call focused_field
    test rax, rax
    jnz 1f
    mov eax, [rip + g_focus]
    cmp eax, FOCUS_EDITOR
    je 1f
    cmp eax, FOCUS_TERMINAL
    jne 3f
1:  call ime_target_identity
    test rax, rax
    jz 3f
    mov r13, rax
    mov r12d, [rip + g_focus]
3:  cmp r12d, [rip + fi_focus]
    jne 4f
    cmp r13, [rip + fi_target]
    je 9f
4:  mov [rip + fi_focus], r12d
    mov [rip + fi_target], r13
    inc dword ptr [rip + fi_generation]
    call ime_clear
    call ime_candidates_clear
    mov dword ptr [rip + fi_request], 2
    mov eax, [rip + fi_generation]
    mov [rip + fi_request + 4], eax
    xor eax, eax
    cmp r12d, -1
    setne al
    mov [rip + fi_request + 8], eax
    call fi_send
9:  EPILOGUE

# fcitx_key(keysym, unicode, mods) -> 1 deferred, 0 physical path.
FN fcitx_key
    cmp dword ptr [rip + fi_ready], 0
    jne 1f
    xor eax, eax
    ret
1:  PROLOGUE 16
    mov [rsp], edi
    mov [rsp + 4], esi
    mov [rsp + 8], edx
    call palette_is_secret
    test eax, eax
    jnz 8f
    mov edi, [rsp]
    mov esi, [rsp + 8]
    # Dispatch the configured toggle in the editor before any asynchronous key
    # forwarding: subsequent typing must queue after the input-mode change.
    call keys_lookup
    lea rcx, [rip + cmd_toggle_chinese]
    cmp rax, rcx
    je 8f
    lea rcx, [rip + keys_chord_start]
    cmp rax, rcx
    je 8f
.Lfi_key_sync:
    call fi_sync
    cmp dword ptr [rip + fi_focus], -1
    je 8f
    cmp dword ptr [rip + fi_ready], 0
    je 8f
    mov dword ptr [rip + fi_request], 1
    mov eax, [rip + fi_generation]
    mov [rip + fi_request + 4], eax
    mov rax, [rsp]
    mov [rip + fi_request + 8], rax
    mov eax, [rsp + 8]
    mov [rip + fi_request + 16], eax
    mov eax, [rip + g_key_base]
    mov [rip + fi_request + 20], eax
    mov eax, [rip + g_key_latin]
    mov [rip + fi_request + 24], eax
    call fi_send
    mov eax, [rip + fi_ready]
    EPILOGUE
8:  xor eax, eax
    EPILOGUE

FN fcitx_active
    mov eax, [rip + fi_ready]
    ret

FN fcitx_owns_input
    # Own native IME suppression as soon as the private helper starts, including
    # English mode and startup. Release ownership on failure or disable.
    xor eax, eax
    cmp dword ptr [rip + fi_pid], 0
    setg al
    ret

FN cmd_toggle_chinese
    cmp dword ptr [rip + fi_ready], 0
    jne 1f
    lea rdi, [rip + fi_failed]
    jmp app_toast
1:  cmp dword ptr [rip + fi_host_mode], 0
    jl .Lfi_manual_toggle
    lea rdi, [rip + fi_following]
    jmp app_toast
.Lfi_manual_toggle:
    PROLOGUE
    call fi_sync
    mov dword ptr [rip + fi_request], 4
    mov eax, [rip + fi_generation]
    mov [rip + fi_request + 4], eax
    call fi_send
    EPILOGUE

# Absolute private-engine mode from the read-only WSL host observer.
FN fcitx_follow_host
    mov [rip + fi_host_mode], edi
    cmp dword ptr [rip + fi_ready], 0
    je 9f
    PROLOGUE
    mov ebx, edi
    call fi_sync
    mov dword ptr [rip + fi_request], 5
    mov eax, [rip + fi_generation]
    mov [rip + fi_request + 4], eax
    mov [rip + fi_request + 8], ebx
    call fi_send
    EPILOGUE
9:  ret

FN fcitx_host_dump
    PROLOGUE
    mov rbx, rdi
    lea rsi, [rip + fi_host_label]
    call sb_push_cstr
    mov rdi, rbx
    movsxd rsi, dword ptr [rip + fi_host_mode]
    call fi_host_number
    mov rdi, rbx
    lea rsi, [rip + fi_applied_label]
    call sb_push_cstr
    mov rdi, rbx
    movsxd rsi, dword ptr [rip + fi_host_applied]
    call fi_host_number
    EPILOGUE
fi_host_number:
    test rsi, rsi
    jns sb_push_u64
    lea rsi, [rip + fi_unknown]
    jmp sb_push_cstr
.section .rodata
fi_unknown: .asciz "unknown"
fi_host_label: .asciz " host_mode="
fi_applied_label: .asciz " private_mode="
.text

FN fcitx_select
    PROLOGUE 16
    mov [rsp], edi
    call fi_sync
    mov dword ptr [rip + fi_request], 3
    mov eax, [rip + fi_generation]
    mov [rip + fi_request + 4], eax
    mov eax, [rsp]
    mov [rip + fi_request + 8], eax
    call fi_send
    EPILOGUE

FN fcitx_cancel
    cmp dword ptr [rip + fi_ready], 0
    je 1f
    mov qword ptr [rip + fi_target], 0
    jmp fi_sync
1:  ret

FN fcitx_tick
.ifdef MACOS
    ret
.else
.ifdef WINDOWS
    ret
.else
    cmp dword ptr [rip + fi_read], -1
    jne 1f
    ret
1:  PROLOGUE 16
    call fi_sync
    call fi_flush
    mov r12d, 64
.Lfi_read_next:
    cmp dword ptr [rip + fi_read], -1
    je .Lfi_done
    mov eax, [rip + fi_used]
    mov edx, 16
    cmp eax, edx
    jb 2f
    add edx, [rip + fi_packet + 8]
2:  sub edx, eax
    lea rsi, [rip + fi_packet]
    add rsi, rax
    mov edi, [rip + fi_read]
    SYS SYS_read
    cmp eax, -EAGAIN
    je .Lfi_wait
    cmp eax, -EINTR
    je .Lfi_wait
    test eax, eax
    jle .Lfi_failed
    add [rip + fi_used], eax
    cmp dword ptr [rip + fi_used], 16
    jb .Lfi_done
    mov eax, [rip + fi_packet + 8]
    cmp eax, 4096
    ja .Lfi_failed
    add eax, 16
    cmp eax, [rip + fi_used]
    jne .Lfi_read_next
    mov dword ptr [rip + fi_used], 0
    cmp dword ptr [rip + fi_packet], 0
    jne 3f
    mov dword ptr [rip + fi_ready], 1
    call fi_sync
    mov edi, [rip + fi_host_mode]
    call fcitx_follow_host
    lea rdi, [rip + fi_available]
    call app_toast
    jmp .Lfi_continue
3:  mov eax, [rip + fi_packet + 4]
    cmp eax, [rip + fi_generation]
    jne .Lfi_continue
    mov ebx, [rip + fi_packet]
    cmp ebx, 6
    je .Lfi_host_ack
    cmp dword ptr [rip + fi_focus], -1
    je .Lfi_continue
    cmp ebx, 1
    jne 4f
    cmp dword ptr [rip + fi_packet + 8], 20
    jne .Lfi_failed
    mov eax, [rip + fi_packet + 28]
    mov [rip + g_key_base], eax
    mov eax, [rip + fi_packet + 32]
    mov [rip + g_key_latin], eax
    mov edi, [rip + fi_packet + 16]
    mov esi, [rip + fi_packet + 20]
    mov edx, [rip + fi_packet + 24]
    call app_key_direct
    mov dword ptr [rip + g_key_base], 0
    mov dword ptr [rip + g_key_latin], 0
    jmp .Lfi_continue
4:  lea rdi, [rip + fi_packet + 16]
    mov esi, [rip + fi_packet + 8]
    cmp ebx, 2
    jne 5f
    call ime_set_preedit
    jmp .Lfi_continue
5:  cmp ebx, 3
    jne 6f
    call app_on_text
    call ime_clear
    call ime_candidates_clear
    jmp .Lfi_continue
6:  cmp ebx, 4
    jne 7f
    mov edx, [rip + fi_packet + 12]
    call ime_candidates_set
    jmp .Lfi_continue
7:  cmp ebx, 5
    jne .Lfi_host_ack
    call palette_is_secret
    test eax, eax
    jnz .Lfi_continue           # don't overwrite shortcut validation with queued IME status
    lea rdi, [rip + fi_english]
    cmp dword ptr [rip + fi_packet + 12], 0
    je 8f
    lea rdi, [rip + fi_chinese]
8:  call app_toast
    jmp .Lfi_continue
.Lfi_host_ack:
    cmp ebx, 6
    jne .Lfi_continue
    mov eax, [rip + fi_packet + 12]
    mov [rip + fi_host_applied], eax
.Lfi_continue:
    call fi_sync
    dec r12d
    jnz .Lfi_read_next
    jmp .Lfi_done
.Lfi_wait:
    cmp dword ptr [rip + fi_ready], 0
    jne .Lfi_done
    call time_ms
    cmp rax, [rip + fi_deadline]
    jb .Lfi_done
.Lfi_failed:
    call fcitx_stop
    lea rdi, [rip + fi_failed]
    call app_toast
.Lfi_done:
    EPILOGUE
.endif
.endif

FN fcitx_stop
    PROLOGUE
    mov dword ptr [rip + fi_ready], 0
    mov dword ptr [rip + fi_host_applied], -1
    mov dword ptr [rip + fi_host_mode], -1
    mov edi, [rip + fi_read]
    test edi, edi
    js 1f
    SYS SYS_close
1:  mov dword ptr [rip + fi_read], -1
    mov edi, [rip + fi_write]
    test edi, edi
    js 2f
    SYS SYS_close
2:  mov dword ptr [rip + fi_write], -1
    mov edi, [rip + fi_pid]
    test edi, edi
    jle 3f
    call reap_later
3:  mov dword ptr [rip + fi_pid], 0
    mov dword ptr [rip + fi_used], 0
    mov dword ptr [rip + fi_queued], 0
    mov dword ptr [rip + fi_sent], 0
    mov qword ptr [rip + fi_target], 0
    call ime_clear
    call ime_candidates_clear
    EPILOGUE
