# Live string edits and reloads must replace allocations, including aliased input
# and a theme selected from the picker after a configured theme was loaded.
.include "rhun.inc"
.text
FN main
    PROLOGUE
    call assign_all
    mov r12, [rip + g_mem_live]
    mov r13d, 64
1:  call assign_all
    cmp [rip + g_mem_live], r12
    jne .Lfail
    dec r13d
    jnz 1b
    # Theme picks point at the theme table, rather than an owned config value.
    lea rax, [rip + value]
    mov [rip + cfg_theme], rax
    call assign_all
    cmp [rip + g_mem_live], r12
    jne .Lfail
    lea rdi, [rip + ok]
    call log_cstr
    xor eax, eax
    EPILOGUE
.Lfail:
    mov eax, 1
    EPILOGUE

assign_all:
    PROLOGUE
    lea rbx, [rip + g_settings]
1:  cmp qword ptr [rbx + SET_key], 0
    je 9f
    mov eax, [rbx + SET_type]
    cmp eax, ST_STR
    je 2f
    cmp eax, ST_THEME
    jne 8f
2:  # code actions on save take source kinds only (tests/save-actions.py checks them)
    lea rax, [rip + cfg_save_actions]
    cmp [rbx + SET_ptr], rax
    je 8f
    lea rax, [rip + cfg_chinese_toggle_key]
    cmp [rbx + SET_ptr], rax
    je 8f                       # shortcut validation has dedicated UI/input tests
    lea rsi, [rip + value]
    mov edx, 5
    lea rax, [rip + cfg_term_copy_key]
    cmp [rbx + SET_ptr], rax
    je .Lshortcut_value
    lea rax, [rip + cfg_term_paste_key]
    cmp [rbx + SET_ptr], rax
    jne .Lassign_value
.Lshortcut_value:
    lea rsi, [rip + shortcut]
    mov edx, 10                 # validated shortcut strings still exercise allocation ownership
.Lassign_value:
    mov r14, rsi
    mov r15, rdx
    mov rdi, rbx
    call setting_assign
    # Self assignment must read the input before releasing the previous value.
    mov rax, [rbx + SET_ptr]
    mov rdi, rbx
    mov rsi, [rax]
    mov rdx, r15
    call setting_assign
    mov rax, [rbx + SET_ptr]
    mov rdi, [rax]
    mov rsi, r15
    mov rdx, r14
    call str_eq_cstr
    test eax, eax
    jz .Lassign_fail
8:  add rbx, SET_SIZE
    jmp 1b
9:  EPILOGUE
.Lassign_fail:
    mov edi, 1
    jmp sys_exit
.section .rodata
value: .asciz "value"
shortcut: .asciz "ctrl+alt+p"
ok: .asciz "ok\n"
