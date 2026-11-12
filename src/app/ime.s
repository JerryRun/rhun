# Input-method text is committed separately from physical shortcut keys.
.include "rhun.inc"
.bss
.p2align 3
ime_inline_preedit: .zero SB_SIZE
ime_candidates: .zero SB_SIZE
ime_selected: .long 0
ime_rows: .long 0
ime_row_ptr: .zero 88
ime_row_len: .zero 88
ime_box: .zero 16
ime_pointer_held: .long 0
.globl g_ime_x, g_ime_y, g_ime_h, g_ime_valid
g_ime_x: .long 0
g_ime_y: .long 0
g_ime_h: .long 0
g_ime_valid: .long 0
.text
FN ime_has_preedit
    mov rax, [rip + ime_inline_preedit + SB_len]
    ret

# Identity for resetting a composition when focus moves between documents, panes or fields.
FN ime_target_identity
    sub rsp, 8
    call focused_field
    test rax, rax
    jnz 9f
    cmp dword ptr [rip + g_focus], FOCUS_TERMINAL
    jne 1f
    call term_clip_identity
    jmp 9f
1:  mov rax, [rip + g_doc]
    test rax, rax
    jz 9f
    mov rax, [rax + DOC_id]
9:  add rsp, 8
    ret


# app_on_text(ptr, len): committed UTF-8; retain each focused component's typing semantics.
FN app_on_text
    PROLOGUE
    mov r12, rdi
    lea r13, [rdi + rsi]
1:  cmp r12, r13
    jae 9f
    mov rdi, r12
    mov rsi, r13
    sub rsi, r12
    call utf8_decode
    add r12, rdx
    cmp eax, 32
    jb 1b
    cmp eax, 127
    je 1b
    mov esi, eax
    mov edi, eax
    cmp eax, 256
    jb 2f
    or edi, 0x1000000
2:  xor edx, edx
    call app_key_direct
    jmp 1b
9:  EPILOGUE

FN ime_set_preedit
    PROLOGUE
    mov r12, rdi
    mov r13, rsi
    lea rdi, [rip + ime_inline_preedit]
    call sb_clear
    cmp r13, 4096
    ja 9f
    lea rdi, [rip + ime_inline_preedit]
    mov rsi, r12
    mov rdx, r13
    call sb_push
9:  mov dword ptr [rip + g_dirty], 1
    EPILOGUE

FN ime_clear
    lea rdi, [rip + ime_inline_preedit]
    jmp sb_clear

FN ime_candidates_clear
    mov dword ptr [rip + ime_rows], 0
    mov dword ptr [rip + ime_box + 12], 0
    mov dword ptr [rip + g_dirty], 1
    lea rdi, [rip + ime_candidates]
    jmp sb_clear

# UTF-8 rows separated by LF, bounded to eleven display rows.
FN ime_candidates_set
    PROLOGUE
    mov r12, rdi
    mov r13, rsi
    mov [rip + ime_selected], edx
    call ime_candidates_clear
    cmp r13, 4096
    ja 9f
    lea rdi, [rip + ime_candidates]
    mov rsi, r12
    mov rdx, r13
    call sb_push
    mov r12, [rip + ime_candidates + SB_ptr]
    lea r13, [r12 + r13]
    xor ebx, ebx
1:  cmp r12, r13
    jae 8f
    cmp ebx, 11
    jae 8f
    lea rax, [rip + ime_row_ptr]
    mov [rax + rbx*8], r12
    mov r14, r12
2:  cmp r12, r13
    jae 3f
    cmp byte ptr [r12], 10
    je 3f
    inc r12
    jmp 2b
3:  mov rax, r12
    sub rax, r14
    lea rdx, [rip + ime_row_len]
    mov [rdx + rbx*8], rax
    inc ebx
    inc r12
    jmp 1b
8:  mov [rip + ime_rows], ebx
9:  EPILOGUE

# Consume candidate clicks before the document can move its caret.
FN ime_pointer
    cmp edi, BTN_LEFT
    jne .Lime_pointer_no
    test esi, esi
    jnz .Lime_pointer_down
    xor eax, eax
    xchg eax, [rip + ime_pointer_held]
    ret
.Lime_pointer_down:
    cmp dword ptr [rip + ime_box + 12], 0
    je .Lime_pointer_no
    mov eax, [rip + g_mx]
    sub eax, [rip + ime_box]
    cmp eax, [rip + ime_box + 8]
    jae .Lime_pointer_cancel
    mov eax, [rip + g_my]
    sub eax, [rip + ime_box + 4]
    cmp eax, [rip + ime_box + 12]
    jae .Lime_pointer_cancel
    xor edx, edx
    div dword ptr [rip + g_mt + 4*MI_28]
    dec eax
    js .Lime_pointer_yes
    cmp eax, [rip + ime_rows]
    jae .Lime_pointer_yes
    mov edi, eax
    sub rsp, 8
    call fcitx_select
    add rsp, 8
.Lime_pointer_yes:
    mov dword ptr [rip + ime_pointer_held], 1
    mov eax, 1
    ret
.Lime_pointer_cancel:
    sub rsp, 8
    call fcitx_cancel
    add rsp, 8
.Lime_pointer_no:
    xor eax, eax
    ret

# Draw composition outside the document: it must never become an edit before commit.
FN ime_draw
    PROLOGUE 32
    mov dword ptr [rip + ime_box + 12], 0
    cmp qword ptr [rip + ime_inline_preedit + SB_len], 0
    je 9f
    cmp dword ptr [rip + g_ime_valid], 0
    je 9f
    lea rdi, [rip + g_face_ui]
    mov rsi, [rip + ime_inline_preedit + SB_ptr]
    mov rdx, [rip + ime_inline_preedit + SB_len]
    call text_width
    mov r14d, eax
    xor ebx, ebx
.Lime_measure:
    cmp ebx, [rip + ime_rows]
    jae .Lime_measured
    lea rax, [rip + ime_row_ptr]
    mov rsi, [rax + rbx*8]
    lea rax, [rip + ime_row_len]
    mov rdx, [rax + rbx*8]
    lea rdi, [rip + g_face_ui]
    call text_width
    cmp eax, r14d
    cmovg r14d, eax
    inc ebx
    jmp .Lime_measure
.Lime_measured:
    add r14d, [rip + g_mt + 4*MI_12]
    mov eax, [rip + g_cv + CV_w]
    cmp r14d, eax
    cmovg r14d, eax
    mov r12d, [rip + g_ime_x]
    sub eax, r14d
    cmp r12d, eax
    cmovg r12d, eax
    xor eax, eax
    cmp r12d, eax
    cmovl r12d, eax
    mov r15d, [rip + ime_rows]
    inc r15d
    imul r15d, [rip + g_mt + 4*MI_28]
    mov eax, [rip + g_ime_y]
    add eax, [rip + g_ime_h]
    mov r13d, eax
    add eax, r15d
    cmp eax, [rip + g_cv + CV_h]
    jle .Lime_place
    mov r13d, [rip + g_ime_y]
    sub r13d, r15d
.Lime_place:
    xor eax, eax
    cmp r13d, eax
    cmovl r13d, eax
    mov [rip + ime_box], r12d
    mov [rip + ime_box + 4], r13d
    mov [rip + ime_box + 8], r14d
    mov [rip + ime_box + 12], r15d
    mov edi, r12d
    mov esi, r13d
    mov edx, r14d
    mov ecx, r15d
    COLOR r8d, T_INPUT
    call gfx_fill
    mov edi, r12d
    mov esi, r13d
    add esi, r15d
    mov edx, r14d
    M ecx, MI_2
    COLOR r8d, T_ACCENT
    call gfx_fill
    lea rdi, [rip + g_face_ui]
    mov esi, r12d
    add esi, [rip + g_mt + 4*MI_6]
    mov edx, r13d
    M ecx, MI_28
    mov r8, [rip + ime_inline_preedit + SB_ptr]
    mov r9, [rip + ime_inline_preedit + SB_len]
    COLOR eax, T_FG
    push rax
    push rax
    call ui_text_v
    add rsp, 16
    xor ebx, ebx
.Lime_row:
    cmp ebx, [rip + ime_rows]
    jae 9f
    add r13d, [rip + g_mt + 4*MI_28]
    cmp ebx, [rip + ime_selected]
    jne .Lime_row_text
    mov edi, r12d
    mov esi, r13d
    mov edx, r14d
    M ecx, MI_28
    COLOR r8d, T_HOVER
    call gfx_fill
.Lime_row_text:
    lea rdi, [rip + g_face_ui]
    mov esi, r12d
    add esi, [rip + g_mt + 4*MI_6]
    mov edx, r13d
    M ecx, MI_28
    lea rax, [rip + ime_row_ptr]
    mov r8, [rax + rbx*8]
    lea rax, [rip + ime_row_len]
    mov r9, [rax + rbx*8]
    COLOR eax, T_FG
    push rax
    push rax
    call ui_text_v
    add rsp, 16
    inc ebx
    jmp .Lime_row
9:  EPILOGUE
