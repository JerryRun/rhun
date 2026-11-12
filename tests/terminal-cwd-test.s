# OSC 7 decoding, invalid metadata rejection, and lifecycle cleanup.
.include "rhun.inc"
.text
FN main
    PROLOGUE
    mov edi, 80
    mov esi, 24
    xor edx, edx
    call term_new
    mov rbx, rax
    lea r12, [rip + cases]
1:  mov rsi, [r12]
    test rsi, rsi
    jz 3f
    mov rdi, rsi
    call strlen
    mov rdi, rbx
    mov rsi, [r12]
    mov rdx, rax
    call term_feed
    mov rdx, [r12 + 8]
    test rdx, rdx
    jz 2f
    mov rdi, [rbx + TM_cwd + SB_ptr]
    mov rsi, [rbx + TM_cwd + SB_len]
    call str_eq_cstr
    test eax, eax
    jz 8f
    jmp 21f
2:  cmp qword ptr [rbx + TM_cwd + SB_len], 0
    jne 8f
21: add r12, 16
    jmp 1b
3:  mov rdi, rbx
    call term_free
    lea rdi, [rip + ok]
    call log_cstr
    xor eax, eax
    EPILOGUE
8:  mov eax, 1
    EPILOGUE
.section .rodata
valid: .asciz "\033]7;file://localhost/tmp/%E7%9B%AE%E5%BD%95%20space\007"
folder: .asciz "/tmp/目录 space"
title: .asciz "\033]2;arbitrary title\007"
bad: .asciz "\033]7;file:///tmp/%00\007"
truncated: .asciz "\033]7;file:///tmp/%E\007"
invalid: .asciz "\033]7;https://example.invalid/tmp\007"
ok: .asciz "ok\n"
.p2align 3
cases: .quad valid, folder, title, folder, invalid, folder, bad, 0, truncated, 0, 0, 0
