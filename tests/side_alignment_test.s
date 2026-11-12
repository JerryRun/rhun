# Alignment invariants, cache invalidation and ownership.
.include "rhun.inc"
.text
FN main
    PROLOGUE
    mov r15, [rip + g_mem_live]
sa_again:
    call doc_new
    mov rbx, rax
    call doc_new
    mov [rbx + DOC_gbase], rax
    mov rdi, rax
    xor esi, esi
    lea rdx, [rip + sa_old]
    mov ecx, OFFSET FLAT:sa_old_len
    call raw_insert
    mov rdi, rbx
    xor esi, esi
    lea rdx, [rip + sa_new]
    mov ecx, OFFSET FLAT:sa_new_len
    call raw_insert
    mov rdi, rbx
    call side_prepare
    mov r12, rax
    cmp qword ptr [r12 + 8], 9
    jne sa_fail
    cmp qword ptr [r12 + 16], 1
    jne sa_fail
    mov [rip + g_diff_doc], rbx
    mov [rip + g_diff_active], r12
    lea r13, [rip + sa_expected]
    xor r14d, r14d
1:  cmp r14, 9
    jae 2f
    imul rax, r14, 24
    mov rcx, [r12 + rax + 64]
    cmp rcx, [r13]
    jne sa_fail
    mov rcx, [r12 + rax + 72]
    cmp rcx, [r13 + 8]
    jne sa_fail
    inc r14
    add r13, 16
    jmp 1b
2:  mov rdi, rbx
    mov esi, 3
    call side_line_row
    cmp rax, 5
    jne sa_fail
    mov rdi, rbx
    mov esi, 1
    call side_row_line
    cmp rax, 1
    jne sa_fail
    mov rdi, rbx
    call side_prepare
    cmp rax, r12
    jne sa_fail
    mov rdi, rbx
    xor esi, esi
    lea rdx, [rip + sa_more]
    mov ecx, 2
    call raw_insert
    mov rdi, rbx
    call side_prepare
    mov rdi, rbx
    mov esi, 4
    call side_line_row
    mov rdi, rbx
    mov rsi, rax
    call side_row_line
    cmp rax, 4
    jne sa_fail
    mov rdi, rbx
    call doc_free
    cmp qword ptr [rip + g_diff_active], 0
    jne sa_fail
    cmp qword ptr [rip + g_diff_doc], 0
    jne sa_fail
    test r15, r15
    jnz 3f
    mov r15, [rip + g_mem_live]   # the diff engine retains three shared scratch buffers
    jmp sa_again
3:
    cmp r15, [rip + g_mem_live]
    jne sa_fail
    lea rdi, [rip + sa_ok]
    call log_cstr
    xor eax, eax
    EPILOGUE
sa_fail:
    mov eax, 1
    EPILOGUE
.section .rodata
sa_old: .ascii "alpha\ndelete one\ndelete two\nbeta\nold\ngamma\nlast\n"
.equ sa_old_len, . - sa_old
sa_new: .ascii "alpha\nbeta\nnew\nextra\ngamma\nlast\n"
.equ sa_new_len, . - sa_new
sa_more: .ascii "x\n"
sa_expected: .quad 0,0, 1,-1, 2,-1, 3,1, 4,2, -1,3, 5,4, 6,5, 7,6
sa_ok: .asciz "ok aligned diff mapping, cache and ownership\n"
