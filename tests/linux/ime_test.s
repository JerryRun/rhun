# Production text-input-v1: preedit stays transient, commits insert editable Unicode.
.include "rhun.inc"
.bss
.p2align 3
im_copy: .zero 64
.text
FN main
    PROLOGUE
    call keys_init
    call cmd_new_file
    mov rbx, [rip + g_doc]
    mov dword ptr [rip + g_focus], FOCUS_EDITOR
    mov dword ptr [rip + wl_ime_entered], 1
    mov edi, 4
    lea rsi, [rip + im_preedit]
    mov edx, OFFSET FLAT:im_preedit_len
    call wl_ime_event
    call ime_has_preedit
    cmp rax, 6
    jne im_fail
    mov rdi, rbx
    call doc_len
    test rax, rax
    jnz im_fail
    mov edi, 7
    lea rsi, [rip + im_commit]
    mov edx, 11
    call wl_ime_event
    mov rdi, rbx
    call doc_len
    test rax, rax
    jnz im_fail
    mov edi, 7
    lea rsi, [rip + im_commit]
    mov edx, OFFSET FLAT:im_commit_len
    call wl_ime_event
    call ime_has_preedit
    test rax, rax
    jnz im_fail
    mov rdi, rbx
    call doc_len
    cmp rax, 10
    jne im_fail
    mov rdi, rbx
    xor esi, esi
    mov edx, 10
    lea rcx, [rip + im_copy]
    call doc_copy
    lea rdi, [rip + im_copy]
    lea rsi, [rip + im_commit + 8]
    mov edx, 10
    call memeq
    test eax, eax
    jz im_fail
    mov edi, 1
    xor esi, esi
    xor edx, edx
    call wl_ime_event
    mov edi, 7
    lea rsi, [rip + im_commit]
    mov edx, OFFSET FLAT:im_commit_len
    call wl_ime_event
    mov rdi, rbx
    call doc_len
    cmp rax, 10
    jne im_fail
    lea rdi, [rip + im_ok]
    call log_cstr
    xor eax, eax
    EPILOGUE
im_fail:
    mov eax, 1
    EPILOGUE
.section .rodata
im_preedit:
    .long 0, 7
    .asciz "zhongw"
    .byte 0
    .long 1, 0
.equ im_preedit_len, . - im_preedit
im_commit:
    .long 0, 11
    .asciz "中文😀"
    .byte 0
.equ im_commit_len, . - im_commit
im_ok: .asciz "ok IME preedit and committed Unicode\n"
