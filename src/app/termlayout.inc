# Binary split layout for terminal sessions. Included in termview.s.
.equ TL_session, 0
.equ TL_left, 8
.equ TL_right, 16
.equ TL_axis, 24              # 1 left/right, 2 top/bottom
.equ TL_ratio, 28             # first child in thousandths
.equ TL_rect, 32
.equ TL_used, 48
.equ TL_SIZE, 56
.bss
.p2align 3
tl_nodes: .zero TL_SIZE * 63
tl_root: .quad 0
tl_focus: .quad 0
.data
grid_scroll_id: .long ID_TSCROLL
.text

tl_alloc:
    lea rax, [rip + tl_nodes]
    mov ecx, 63
1:  cmp dword ptr [rax + TL_used], 0
    je 2f
    add rax, TL_SIZE
    loop 1b
    xor eax, eax
    ret
2:  mov dword ptr [rax + TL_used], 1
    mov dword ptr [rax + TL_ratio], 500
    ret

tl_find:                       # session -> leaf, or zero
    lea rax, [rip + tl_nodes]
    mov ecx, 63
1:  cmp dword ptr [rax + TL_used], 1
    jne 2f
    cmp [rax + TL_session], rdi
    je 3f
2:  add rax, TL_SIZE
    loop 1b
    xor eax, eax
3:  ret

FN cmd_split_terminal_right
    mov edi, 1
    jmp tl_split
FN cmd_split_terminal_down
    mov edi, 2
tl_split:
    PROLOGUE
    mov r12d, edi
    call term_show
    call cur_sess
    test rax, rax
    jz 9f
    mov r13, rax
    cmp qword ptr [rip + tl_root], 0
    jne 1f
    call tl_alloc
    test rax, rax
    jz 9f
    mov [rip + tl_root], rax
    mov [rax + TL_session], r13
1:  mov rdi, r13
    call tl_find
    test rax, rax
    jnz 2f
    mov rax, [rip + tl_focus]
    test rax, rax
    jz 9f
    mov [rax + TL_session], r13
2:  mov r14, rax
    call tl_alloc
    test rax, rax
    jz 9f
    mov r15, rax
    call tl_alloc
    test rax, rax
    jnz 3f
    mov dword ptr [r15 + TL_used], 0
    jmp 9f
3:  mov rbx, rax
    call term_spawn
    test eax, eax
    jnz 4f
    mov dword ptr [r15 + TL_used], 0
    mov dword ptr [rbx + TL_used], 0
    jmp 9f
4:  call cur_sess
    mov [rbx + TL_session], rax
    mov [r15 + TL_session], r13
    mov [r14 + TL_left], r15
    mov [r14 + TL_right], rbx
    mov [r14 + TL_axis], r12d
    mov dword ptr [r14 + TL_used], 2
    mov qword ptr [r14 + TL_session], 0
    mov [rip + tl_focus], rbx
    call term_show
9:  EPILOGUE

FN cmd_unsplit_terminal
    lea rdi, [rip + tl_nodes]
    xor eax, eax
    mov ecx, TL_SIZE * 63 / 8
    rep stosq
    mov qword ptr [rip + tl_root], 0
    mov qword ptr [rip + tl_focus], 0
    mov dword ptr [rip + g_dirty], 1
    ret

FN cmd_next_terminal_pane
    PROLOGUE
    cmp qword ptr [rip + tl_root], 0
    je 9f
    call cur_sess
    mov rdi, rax
    call tl_find
    test rax, rax
    jz 9f
    mov rbx, rax
    mov r12d, 63
1:  add rbx, TL_SIZE
    lea rax, [rip + tl_nodes + TL_SIZE * 63]
    cmp rbx, rax
    jb 2f
    lea rbx, [rip + tl_nodes]
2:  cmp dword ptr [rbx + TL_used], 1
    je 3f
    dec r12d
    jnz 1b
    jmp 9f
3:  mov rdi, [rbx + TL_session]
    call tl_activate
    mov [rip + tl_focus], rbx
9:  EPILOGUE

tl_activate:                   # TS* -> active session index
    xor ecx, ecx
    mov rax, [rip + sessions + VEC_ptr]
1:  cmp rcx, [rip + sessions + VEC_len]
    jae 9f
    cmp [rax + rcx*8], rdi
    je 2f
    inc ecx
    jmp 1b
2:  mov [rip + cur], rcx
    mov dword ptr [rip + g_focus], FOCUS_TERMINAL
    mov dword ptr [rip + g_dirty], 1
9:  ret

term_layout_closed:             # remove a session before its allocation goes
    PROLOGUE
    mov r12, rdi
    call tl_find
    test rax, rax
    jz 9f
    mov r13, rax
    cmp rax, [rip + tl_root]
    jne 1f
    call cmd_unsplit_terminal
    jmp 9f
1:  lea rbx, [rip + tl_nodes]
    mov r14d, 63
2:  cmp dword ptr [rbx + TL_used], 2
    jne 5f
    mov r15, [rbx + TL_left]
    cmp r15, r13
    jne 3f
    mov r15, [rbx + TL_right]
    jmp 4f
3:  cmp [rbx + TL_right], r13
    jne 5f
4:  mov rdi, rbx
    mov rsi, r15
    mov edx, TL_SIZE
    call memcpy
    mov dword ptr [r15 + TL_used], 0
    mov dword ptr [r13 + TL_used], 0
    mov qword ptr [rip + tl_focus], 0
    jmp 9f
5:  add rbx, TL_SIZE
    dec r14d
    jnz 2b
9:  EPILOGUE

tl_load:                       # session's render/input state -> working registers
    mov rsi, rdi
    add rsi, TS_view
    lea rdi, [rip + gx]
    mov ecx, 10
    rep movsq
    ret
tl_save:
    add rdi, TS_view
    lea rsi, [rip + gx]
    mov ecx, 10
    rep movsq
    ret

term_layout_key_state:
    PROLOGUE
    cmp qword ptr [rip + tl_root], 0
    je 9f
    call cur_sess
    test rax, rax
    jz 9f
    mov rdi, rax
    call tl_load
9:  EPILOGUE

term_layout_draw:               # panel rectangle; header stays outside the tree
    PROLOGUE 32
    mov [rsp], edi
    mov [rsp + 4], esi
    mov [rsp + 8], edx
    mov [rsp + 12], ecx
    cmp qword ptr [rip + tl_root], 0
    jne 1f
    mov dword ptr [rip + grid_scroll_id], ID_TSCROLL
    call term_grid_draw
    jmp 9f
1:  call cur_sess
    test rax, rax
    jz 9f
    mov r12, rax
    mov rdi, rax
    call tl_find
    test rax, rax
    jnz 2f
    mov rax, [rip + tl_focus]
    test rax, rax
    jnz 11f
    mov rax, [rip + tl_root]
12: cmp dword ptr [rax + TL_used], 2
    jne 11f
    mov rax, [rax + TL_left]
    jmp 12b
11: mov [rax + TL_session], r12
2:  mov [rip + tl_focus], rax
    mov rbx, [rip + tl_root]
    mov eax, [rsp]
    mov [rbx + TL_rect], eax
    mov eax, [rsp + 4]
    add eax, [rip + g_mt + 4*MI_28]
    add eax, [rip + g_mt + 4*MI_2]
    mov [rbx + TL_rect + 4], eax
    mov eax, [rsp + 8]
    mov [rbx + TL_rect + 8], eax
    mov eax, [rsp + 12]
    sub eax, [rip + g_mt + 4*MI_28]
    sub eax, [rip + g_mt + 4*MI_2]
    mov [rbx + TL_rect + 12], eax
    mov rdi, rbx
    call tl_draw_node
    mov qword ptr [rip + draw_session], 0
    call cur_sess
    test rax, rax
    jz 9f
    mov rdi, rax
    call tl_load
9:  EPILOGUE

tl_draw_node:
    PROLOGUE 32
    mov rbx, rdi
    cmp dword ptr [rbx + TL_used], 1
    je .Ltld_leaf
    mov r12, [rbx + TL_left]
    mov r13, [rbx + TL_right]
    mov rax, [rbx + TL_rect]
    mov [r12 + TL_rect], rax
    mov [r13 + TL_rect], rax
    mov rax, [rbx + TL_rect + 8]
    mov [r12 + TL_rect + 8], rax
    mov [r13 + TL_rect + 8], rax
    mov r14d, 8                # width offset
    cmp dword ptr [rbx + TL_axis], 1
    je 1f
    mov r14d, 12               # height offset
1:  mov eax, [rbx + r14 + TL_rect]
    sub eax, [rip + g_mt + 4*MI_1]
    test eax, eax
    jns 11f
    xor eax, eax
11: imul eax, [rbx + TL_ratio]
    xor edx, edx
    mov ecx, 1000
    div ecx
    mov [r12 + r14 + TL_rect], eax
    mov ecx, [rbx + r14 + TL_rect]
    sub ecx, eax
    sub ecx, [rip + g_mt + 4*MI_1]
    jns 12f
    xor ecx, ecx
12: mov [r13 + r14 + TL_rect], ecx
    lea r15d, [r14 - 8]
    add eax, [rip + g_mt + 4*MI_1]
    add [r13 + r15 + TL_rect], eax
    # a stable divider id from its node slot
    mov rdi, rbx
    lea rax, [rip + tl_nodes]
    sub rdi, rax
    add edi, 0x18000
    mov esi, [r13 + TL_rect]
    mov edx, [r13 + TL_rect + 4]
    mov ecx, [r13 + TL_rect + 8]
    mov r8d, [r13 + TL_rect + 12]
    cmp r14d, 8
    jne 2f
    sub esi, [rip + g_mt + 4*MI_2]
    M ecx, MI_4
    jmp 3f
2:  sub edx, [rip + g_mt + 4*MI_2]
    M r8d, MI_4
3:  mov [rsp], esi
    mov [rsp + 4], edx
    mov [rsp + 8], ecx
    mov [rsp + 12], r8d
    call ui_btn
    mov r15d, eax
    test eax, UB_HOVER | UB_HELD
    jz 4f
    mov eax, CUR_EW
    cmp r14d, 8
    je 31f
    mov eax, CUR_NS
31: mov [rip + g_cursor], eax
4:  test r15d, UB_HELD
    jz 5f
    mov eax, [rip + g_mx]
    cmp r14d, 8
    je 41f
    mov eax, [rip + g_my]
41: lea ecx, [r14 - 8]
    sub eax, [rbx + rcx + TL_rect]
    imul eax, eax, 1000
    mov ecx, [rbx + r14 + TL_rect]
    test ecx, ecx
    jle 5f
    cdq
    idiv ecx
    mov ecx, 100
    cmp eax, ecx
    cmovl eax, ecx
    mov ecx, 900
    cmp eax, ecx
    cmovg eax, ecx
    mov [rbx + TL_ratio], eax
    mov dword ptr [rip + g_dirty], 1
5:  mov edi, [rsp]
    mov esi, [rsp + 4]
    mov edx, [rsp + 8]
    mov ecx, [rsp + 12]
    # Keep the drag target comfortable; paint only the standard one-pixel rule.
    cmp r14d, 8
    jne 51f
    add edi, [rip + g_mt + 4*MI_2]
    sub edi, [rip + g_mt + 4*MI_1]
    M edx, MI_1
    jmp 52f
51: add esi, [rip + g_mt + 4*MI_2]
    sub esi, [rip + g_mt + 4*MI_1]
    M ecx, MI_1
52:
    COLOR r8d, T_BORDER
    call gfx_fill
    mov rdi, r12
    call tl_draw_node
    mov rdi, r13
    call tl_draw_node
    jmp .Ltld_done
.Ltld_leaf:
    mov r12, [rbx + TL_session]
    test r12, r12
    jz .Ltld_done
    mov [rip + draw_session], r12
    mov rdi, r12
    call tl_load
    mov edi, [rbx + TL_rect]
    mov esi, [rbx + TL_rect + 4]
    mov edx, [rbx + TL_rect + 8]
    mov ecx, [rbx + TL_rect + 12]
    call ui_in
    test eax, eax
    jz 6f
    test dword ptr [rip + g_pressed], 7
    jz 6f
    mov rdi, r12
    call tl_activate
    mov [rip + tl_focus], rbx
6:  mov eax, [r12 + TS_id]
    add eax, 0x19000
    mov [rip + grid_scroll_id], eax
    mov eax, [rip + g_focus]
    mov [rsp + 16], eax
    cmp eax, FOCUS_TERMINAL
    jne 61f
    cmp rbx, [rip + tl_focus]
    je 61f
    mov dword ptr [rip + g_focus], FOCUS_EXPLORER
61:
    mov edi, [rbx + TL_rect]
    mov esi, [rbx + TL_rect + 4]
    mov edx, [rbx + TL_rect + 8]
    mov ecx, [rbx + TL_rect + 12]
    mov eax, [rip + g_mt + 4*MI_28]
    add eax, [rip + g_mt + 4*MI_2]
    sub esi, eax
    add ecx, eax
    call term_grid_draw
    mov eax, [rsp + 16]
    cmp eax, FOCUS_TERMINAL
    jne 62f
    mov [rip + g_focus], eax
62:
    mov rdi, r12
    call tl_save
.Ltld_done:
    EPILOGUE
