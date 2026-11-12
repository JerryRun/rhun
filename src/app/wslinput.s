# Explicit Windows-host input fallback, asynchronous and bound to its original target.
.include "rhun.inc"
.data
wi_fd: .long -1
wi_pid: .long 0
.bss
.p2align 3
wi_out: .zero SB_SIZE
wi_focus: .long 0
.p2align 3
wi_target: .quad 0
wi_until: .quad 0
.section .rodata
wi_override: .asciz "RHUN_WSL_INPUT_HELPER"
wi_powershell: .asciz "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
wi_noprofile: .asciz "-NoProfile"
wi_sta: .asciz "-STA"
wi_command: .asciz "-Command"
wi_unavailable: .asciz "Windows IME input requires WSL with Windows PowerShell."
wi_choose: .asciz "Focus the editor, a terminal, or a text field first."
wi_busy: .asciz "A Windows IME input window is already open."
wi_changed: .asciz "Input target changed; Windows IME text was discarded."
wi_error: .asciz "Windows IME input failed or exceeded its limit."
wi_opened: .asciz "Type with Windows IME; Ctrl+Enter inserts, Esc cancels."
.text
FN wsl_input_timeout
    mov eax, -1
    cmp dword ptr [rip + wi_pid], 0
    je 1f
    mov eax, 25
1:  ret

FN cmd_input_chinese
.ifdef MACOS
    lea rdi, [rip + wi_unavailable]
    jmp app_toast
.else
.ifdef WINDOWS
    lea rdi, [rip + wi_unavailable]
    jmp app_toast
.else
    PROLOGUE 64
    cmp dword ptr [rip + wi_pid], 0
    jne .Lwi_busy
    call focused_field
    mov rbx, rax
    mov eax, [rip + g_focus]
    mov [rip + wi_focus], eax
    test rbx, rbx
    jnz .Lwi_target
    cmp eax, FOCUS_EDITOR
    jne 1f
    mov rax, [rip + g_doc]
    test rax, rax
    jz .Lwi_choose
    mov rbx, [rax + DOC_id]
    jmp .Lwi_target
1:  cmp eax, FOCUS_TERMINAL
    jne .Lwi_choose
    call term_clip_identity
    test rax, rax
    jz .Lwi_choose
    mov rbx, rax
.Lwi_target:
    mov [rip + wi_target], rbx
    lea rdi, [rip + wi_override]
    call getenv
    test rax, rax
    jnz 2f
    lea rax, [rip + wi_powershell]
2:  mov [rsp], rax
    mov rdi, rax
    mov esi, 1                  # executable
    SYS SYS_access
    test eax, eax
    js .Lwi_unavailable
    lea rax, [rip + wi_noprofile]
    mov [rsp + 8], rax
    lea rax, [rip + wi_sta]
    mov [rsp + 16], rax
    lea rax, [rip + wi_command]
    mov [rsp + 24], rax
    lea rax, [rip + wsl_input_script]
    mov [rsp + 32], rax
    mov qword ptr [rsp + 40], 0
    mov rdi, rsp
    mov rsi, [rip + g_envp]
    xor edx, edx
    xor ecx, ecx
    xor r8d, r8d
    xor r9d, r9d               # no extension confinement for Windows interop
    call run_piped_input
    test eax, eax
    js .Lwi_unavailable
    mov [rip + wi_pid], eax
    mov [rip + wi_fd], edx
    lea rdi, [rip + wi_out]
    call sb_clear
    call time_ms
    add rax, 900000
    mov [rip + wi_until], rax
    lea rdi, [rip + wi_opened]
    jmp .Lwi_toast
.Lwi_busy:
    lea rdi, [rip + wi_busy]
    jmp .Lwi_toast
.Lwi_choose:
    lea rdi, [rip + wi_choose]
    jmp .Lwi_toast
.Lwi_unavailable:
    lea rdi, [rip + wi_unavailable]
.Lwi_toast:
    call app_toast
    EPILOGUE
.endif
.endif

FN wsl_input_tick
.ifdef MACOS
    ret
.else
.ifdef WINDOWS
    ret
.else
    PROLOGUE 4096
    cmp dword ptr [rip + wi_pid], 0
    je .Lwi_done
    call time_ms
    cmp rax, [rip + wi_until]
    ja .Lwi_over
    mov edi, [rip + wi_fd]
    mov rsi, rsp
    mov edx, 4096
    SYS SYS_read
    cmp rax, -EAGAIN
    je .Lwi_done
    cmp rax, -EINTR
    je .Lwi_done
    test rax, rax
    js .Lwi_over
    jz .Lwi_eof
    mov rdx, rax
    add rax, [rip + wi_out + SB_len]
    cmp rax, 65536
    ja .Lwi_over
    lea rdi, [rip + wi_out]
    mov rsi, rsp
    call sb_push
    jmp .Lwi_done
.Lwi_eof:
    mov edi, [rip + wi_pid]
    mov esi, 1
    call proc_wait
    cmp eax, -1
    je .Lwi_done
    test eax, eax
    jnz .Lwi_over
    mov edi, [rip + wi_fd]
    SYS SYS_close
    mov dword ptr [rip + wi_fd], -1
    mov dword ptr [rip + wi_pid], 0
    cmp qword ptr [rip + wi_out + SB_len], 0
    je .Lwi_clear
    mov eax, [rip + g_focus]
    cmp eax, [rip + wi_focus]
    jne .Lwi_changed
    call focused_field
    test rax, rax
    jz 1f
    cmp rax, [rip + wi_target]
    jne .Lwi_changed
    jmp .Lwi_insert
1:  cmp dword ptr [rip + wi_focus], FOCUS_TERMINAL
    je 2f
    mov rax, [rip + g_doc]
    test rax, rax
    jz .Lwi_changed
    mov rax, [rax + DOC_id]
    jmp 3f
2:  call term_clip_identity
3:  cmp rax, [rip + wi_target]
    jne .Lwi_changed
.Lwi_insert:
    mov rdi, [rip + wi_out + SB_ptr]
    mov rsi, [rip + wi_out + SB_len]
    call app_on_paste
    jmp .Lwi_clear
.Lwi_changed:
    lea rdi, [rip + wi_changed]
    call app_toast
    jmp .Lwi_clear
.Lwi_over:
    mov edi, [rip + wi_pid]
    mov esi, SIGKILL
    call proc_kill
    mov edi, [rip + wi_pid]
    call reap_later
    mov edi, [rip + wi_fd]
    SYS SYS_close
    mov dword ptr [rip + wi_fd], -1
    mov dword ptr [rip + wi_pid], 0
    lea rdi, [rip + wi_error]
    call app_toast
.Lwi_clear:
    lea rdi, [rip + wi_out]
    call sb_free
.Lwi_done:
    EPILOGUE
.endif
.endif
