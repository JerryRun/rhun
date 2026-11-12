# Editable HEAD / working-tree comparison. Alignment is view data only: blank rows never
# enter the document, undo history, clipboard, or saved file.
.include "rhun.inc"
.equ SD_ver, 0
.equ SD_count, 8
.equ SD_changed, 16
.equ SD_reverse, 24
.equ SD_doc, 32
.equ SD_nright, 40
.equ SD_DATA, 64
.equ SR_SIZE, 24
.bss
.p2align 3
.globl g_diff_active, g_diff_doc
g_diff_active: .quad 0
g_diff_doc: .quad 0
.data
.globl cfg_side_diff
cfg_side_diff: .long 1
.section .rodata
sd_head: .ascii "HEAD (read only)"
sd_head_end:
sd_work: .ascii "Working tree (editable)"
sd_work_end:
.text

FN side_base_free
    PROLOGUE
    mov rbx, rdi
    cmp [rip + g_diff_doc], rbx
    jne 1f
    call side_leave
1:  mov rdi, [rbx + DOC_side]
    call mem_free
    mov qword ptr [rbx + DOC_side], 0
    mov rdi, [rbx + DOC_gbase]
    mov qword ptr [rbx + DOC_gbase], 0
    test rdi, rdi
    jz 9f
    call doc_free
9:  EPILOGUE

# Convert the temporary visual scroll back when switching away or disabling comparison.
FN side_leave
    mov rdi, [rip + g_diff_doc]
    test rdi, rdi
    jz 1f
    mov rsi, [rdi + DOC_scrolly]
    shr rsi, 8
    push rdi
    call side_row_line
    pop rdi
    shl rax, 8
    mov [rdi + DOC_scrolly], rax
1:  mov qword ptr [rip + g_diff_active], 0
    mov qword ptr [rip + g_diff_doc], 0
    ret

FN cmd_toggle_side_diff
    xor dword ptr [rip + cfg_side_diff], 1
    call side_leave
    mov dword ptr [rip + g_dirty], 1
    ret

# Matches the document for which DOC_scrolly currently counts aligned rows. Keeps registers.
FN side_is_active
    xor eax, eax
    cmp [rip + g_diff_doc], rdi
    jne 1f
    cmp qword ptr [rip + g_diff_active], 0
    setne al
1:  ret

# A document line to its aligned row. Clamp stale maps between an edit and the next frame.
FN side_line_row
    mov rax, rsi
    cmp [rip + g_diff_doc], rdi
    jne 9f
    mov rcx, [rip + g_diff_active]
    test rcx, rcx
    jz 9f
    cmp rax, [rcx + SD_nright]
    jb 1f
    mov rax, [rcx + SD_count]
    dec rax
    ret
1:  mov rcx, [rcx + SD_reverse]
    mov rax, [rcx + rax*8]
9:  ret

# An aligned row to a real right-hand line. Empty cells select the following line (EOF: last).
FN side_row_line
    mov rax, rsi
    cmp [rip + g_diff_doc], rdi
    jne 9f
    mov rcx, [rip + g_diff_active]
    test rcx, rcx
    jz 9f
    mov r8, [rcx + SD_count]
    cmp rax, r8
    jb 1f
    lea rax, [r8 - 1]
1:  imul rdx, rax, SR_SIZE
    mov rax, [rcx + rdx + SD_DATA + 8]
    test rax, rax
    jns 9f
    add rdx, SR_SIZE
    sub r8, rsi
2:  dec r8
    jle 3f
    mov rax, [rcx + rdx + SD_DATA + 8]
    test rax, rax
    jns 9f
    add rdx, SR_SIZE
    jmp 2b
3:  mov rax, [rcx + SD_nright]
    dec rax
9:  ret

# Hash actual editor lines, including the final empty line, with the existing diff engine.
sd_hash:
    PROLOGUE
    mov rbx, rdi
    mov rdi, [rbx + DOC_nlines]
    shl rdi, 3
    call mem_alloc
    mov r12, rax
    xor r13d, r13d
1:  cmp r13, [rbx + DOC_nlines]
    jae 2f
    mov rdi, rbx
    mov rsi, r13
    call doc_line_text
    mov rdi, rax
    mov rsi, rdx
    call hash_line
    mov [r12 + r13*8], rax
    inc r13
    jmp 1b
2:  mov rax, r12
    EPILOGUE

FN side_prepare
    PROLOGUE 80
    mov rbx, rdi
    mov rax, [rbx + DOC_side]
    test rax, rax
    jz 1f
    mov rcx, [rbx + DOC_version]
    cmp [rax + SD_ver], rcx
    je .Lsd_ready
1:  mov rdi, [rbx + DOC_gbase]
    test rdi, rdi
    jz .Lsd_none
    mov rax, [rdi + DOC_nlines]
    mov [rsp], rax
    call sd_hash
    mov [rsp + 16], rax
    mov rax, [rbx + DOC_nlines]
    mov [rsp + 8], rax
    mov rdi, rbx
    call sd_hash
    mov [rsp + 24], rax
    mov rdi, [rsp]
    call mem_alloc
    mov [rsp + 32], rax
    mov rdi, [rsp + 8]
    call mem_alloc
    mov [rsp + 40], rax
    # Strip common prefix and suffix before bounded Myers, as the unified diff does.
    mov r12, [rsp + 16]
    mov r13, [rsp + 24]
    xor r14d, r14d
2:  cmp r14, [rsp]
    jae 3f
    cmp r14, [rsp + 8]
    jae 3f
    mov rax, [r12 + r14*8]
    cmp rax, [r13 + r14*8]
    jne 3f
    inc r14
    jmp 2b
3:  mov r15, [rsp]
    mov rcx, [rsp + 8]
4:  cmp r15, r14
    jbe 5f
    cmp rcx, r14
    jbe 5f
    mov rax, [r12 + r15*8 - 8]
    cmp rax, [r13 + rcx*8 - 8]
    jne 5f
    dec r15
    dec rcx
    jmp 4b
5:  mov [rsp + 48], rcx
    lea rdi, [r12 + r14*8]
    mov rsi, r15
    sub rsi, r14
    lea rdx, [r13 + r14*8]
    sub rcx, r14
    mov r8, [rsp + 32]
    add r8, r14
    mov r9, [rsp + 40]
    add r9, r14
    call diff_lines
    test eax, eax
    jnz 6f
    mov rdi, [rsp + 32]
    add rdi, r14
    mov esi, 1
    mov rdx, r15
    sub rdx, r14
    call memset
    mov rdi, [rsp + 40]
    add rdi, r14
    mov esi, 1
    mov rdx, [rsp + 48]
    sub rdx, r14
    call memset
6:  mov rdi, [rsp]
    add rdi, [rsp + 8]
    add rdi, 2
    imul rdi, SR_SIZE
    add rdi, SD_DATA
    mov [rsp + 56], rdi
    mov rax, [rsp + 8]
    lea rdi, [rdi + rax*8]
    call mem_alloc
    mov r15, rax
    add rax, [rsp + 56]
    mov [r15 + SD_reverse], rax
    mov [r15 + SD_doc], rbx
    mov rax, [rsp + 8]
    mov [r15 + SD_nright], rax
    mov rax, [rbx + DOC_version]
    mov [r15 + SD_ver], rax
    xor r12d, r12d             # left line
    xor r13d, r13d             # right line
    xor r14d, r14d             # aligned rows
.Lsd_map:
    cmp r12, [rsp]
    jb 7f
    cmp r13, [rsp + 8]
    jae .Lsd_mapped
7:  imul rax, r14, SR_SIZE
    lea rdx, [r15 + rax + SD_DATA]
    mov qword ptr [rdx], -1
    mov qword ptr [rdx + 8], -1
    xor r8d, r8d
    xor r9d, r9d
    cmp r12, [rsp]
    jae 8f
    mov rcx, [rsp + 32]
    movzx r8d, byte ptr [rcx + r12]
8:  cmp r13, [rsp + 8]
    jae 9f
    mov rcx, [rsp + 40]
    movzx r9d, byte ptr [rcx + r13]
9:  mov eax, r8d
    or eax, r9d
    jnz 11f
    # Common lines, or the remaining tail when the bounded diff fell back.
    cmp r12, [rsp]
    jae 13f
    mov [rdx], r12
    inc r12
    cmp r13, [rsp + 8]
    jae 14f
    jmp 12f
11: mov qword ptr [r15 + SD_changed], 1
    mov qword ptr [rdx + 16], 1
    test r8d, r8d
    jz 111f
    mov [rdx], r12
    inc r12
111:test r9d, r9d
    jz 14f
12: mov [rdx + 8], r13
    mov rcx, [r15 + SD_reverse]
    mov [rcx + r13*8], r14
    inc r13
    jmp 14f
13:cmp r13, [rsp + 8]
    jb 12b
14:inc r14
    jmp .Lsd_map
.Lsd_mapped:
    mov [r15 + SD_count], r14
    # Keep an existing viewport anchored to its current right-hand line after edits.
    cmp [rip + g_diff_doc], rbx
    jne 15f
    mov rdi, rbx
    mov rsi, [rbx + DOC_scrolly]
    shr rsi, 8
    call side_row_line
    mov [rsp + 64], rax
15: mov rdi, [rbx + DOC_side]
    call mem_free
    mov [rbx + DOC_side], r15
    cmp [rip + g_diff_doc], rbx
    jne 16f
    mov [rip + g_diff_active], r15
    mov rdi, rbx
    mov rsi, [rsp + 64]
    call side_line_row
    shl rax, 8
    mov [rbx + DOC_scrolly], rax
16: mov rdi, [rsp + 16]
    call mem_free
    mov rdi, [rsp + 24]
    call mem_free
    mov rdi, [rsp + 32]
    call mem_free
    mov rdi, [rsp + 40]
    call mem_free
    mov rax, r15
.Lsd_ready:
    EPILOGUE
.Lsd_none:
    xor eax, eax
    EPILOGUE

# side_draw(rect) -> 1 when comparison was drawn. Right editor retains normal commands.
FN git_side_draw
    PROLOGUE 64
    mov [rsp], edi
    mov [rsp + 4], esi
    mov [rsp + 8], edx
    mov [rsp + 12], ecx
    mov rbx, [rip + g_doc]
    cmp dword ptr [rip + cfg_side_diff], 0
    je .Lsd_plain
    mov rdi, [rip + g_tab_cur]
    test rdi, rdi
    js .Lsd_plain
    call tab_at
    test dword ptr [rax + TAB_flags], TF_SIDE_DIFF
    jz .Lsd_plain
    cmp dword ptr [rsp + 8], 360
    jl .Lsd_plain
    cmp qword ptr [rbx + DOC_diff], 0
    jne .Lsd_plain
    cmp qword ptr [rbx + DOC_gbase], 0
    je .Lsd_plain
    cmp dword ptr [rbx + DOC_gstate], GS_BASE
    jne .Lsd_plain
    mov rdi, rbx
    call side_prepare
    test rax, rax
    jz .Lsd_plain
    cmp qword ptr [rax + SD_changed], 0
    je .Lsd_plain
    mov r12, rax
    cmp [rip + g_diff_doc], rbx
    je 1f
    call side_leave
    mov [rip + g_diff_active], r12
    mov [rip + g_diff_doc], rbx
    mov rdi, rbx
    mov rsi, [rbx + DOC_scrolly]
    shr rsi, 8
    call side_line_row
    shl rax, 8
    mov [rbx + DOC_scrolly], rax
1:  mov eax, [rip + cfg_word_wrap]
    mov [rsp + 16], eax
    mov eax, [rip + cfg_folding]
    mov [rsp + 20], eax
    mov dword ptr [rip + cfg_word_wrap], 0
    mov dword ptr [rip + cfg_folding], 0
    and dword ptr [rbx + DOC_flags], ~DF_ROWS
    M r13d, MI_28
    mov eax, [rsp + 8]
    M ecx, MI_12
    sub eax, ecx
    sub eax, 1
    sar eax, 1
    mov [rsp + 24], eax        # left width
    add eax, [rsp]
    inc eax
    mov [rsp + 28], eax        # right x
    mov eax, [rsp + 4]
    add eax, r13d
    mov [rsp + 32], eax        # content y
    mov eax, [rsp + 12]
    sub eax, r13d
    mov [rsp + 36], eax        # content height
    # Scrolling over the left side controls the shared viewport too.
    mov edi, [rsp]
    mov esi, [rsp + 32]
    mov edx, [rsp + 24]
    mov ecx, [rsp + 36]
    call ui_in
    test eax, eax
    jz 2f
    call wheel_xy
    movsxd rax, edx
    shl rax, 8
    cqo
    movsxd rcx, dword ptr [rip + g_lh]
    idiv rcx
    add [rbx + DOC_scrolly], rax
2:  mov edi, [rsp + 28]
    mov esi, [rsp + 32]
    mov edx, [rsp + 24]
    mov ecx, [rsp + 36]
    call editor_draw
    # Draw baseline after right-hand input has updated the shared scroll.
    mov edi, [rsp]
    mov esi, [rsp + 32]
    mov edx, [rsp + 24]
    mov ecx, [rsp + 36]
    COLOR r8d, T_BG
    call gfx_fill
    mov edi, [rsp]
    mov esi, [rsp + 32]
    mov edx, [rsp + 24]
    mov ecx, [rsp + 36]
    call gfx_clip_push
    mov r14, [rbx + DOC_scrolly]
    mov eax, r14d
    and eax, 255
    imul eax, [rip + g_lh]
    shr eax, 8
    mov r15d, [rsp + 32]
    sub r15d, eax
    shr r14, 8
.Lsd_left:
    cmp r14, [r12 + SD_count]
    jae .Lsd_left_done
    mov eax, [rsp + 32]
    add eax, [rsp + 36]
    cmp r15d, eax
    jge .Lsd_left_done
    imul rax, r14, SR_SIZE
    lea rax, [r12 + rax + SD_DATA]
    mov rsi, [rax]
    mov [rsp + 40], rsi
    cmp qword ptr [rax + 16], 0
    je 3f
    test rsi, rsi
    js 3f
    mov edi, [rsp]
    mov esi, r15d
    mov edx, [rsp + 24]
    mov ecx, [rip + g_lh]
    COLOR r8d, T_GIT_DEL
    and r8d, 0xffffff
    or r8d, 0x22000000
    call gfx_fill
3:  mov rsi, [rsp + 40]
    test rsi, rsi
    js 4f
    lea rdi, [rsp + 48]
    inc rsi
    call fmt_u64
    lea rdi, [rip + g_face_code]
    mov esi, [rsp]
    add esi, 4
    mov edx, r15d
    add edx, [rip + g_base]
    lea rcx, [rsp + 48]
    mov r8, rax
    COLOR r9d, T_LINENO
    call text_draw
    mov rdi, [rbx + DOC_gbase]
    mov rsi, [rsp + 40]
    call doc_line_text
    mov rcx, rax
    mov r8, rdx
    lea rdi, [rip + g_face_code]
    mov esi, [rsp]
    mov eax, [rip + g_cw]
    imul eax, 7
    add esi, eax
    sub esi, [rbx + DOC_scrollx]
    mov edx, r15d
    add edx, [rip + g_base]
    COLOR r9d, T_FG
    call text_draw
4:  inc r14
    add r15d, [rip + g_lh]
    jmp .Lsd_left
.Lsd_left_done:
    call gfx_clip_pop
    # Headers and central separator.
    mov edi, [rsp]
    mov esi, [rsp + 4]
    mov edx, [rsp + 8]
    mov ecx, r13d
    COLOR r8d, T_INPUT
    call gfx_fill
    lea rdi, [rip + g_face_ui]
    mov esi, [rsp]
    add esi, 8
    mov edx, [rsp + 4]
    mov ecx, r13d
    lea r8, [rip + sd_head]
    lea r9, [rip + sd_head_end]
    sub r9, r8
    COLOR eax, T_FG
    push rax
    push rax
    call ui_text_v
    add rsp, 16
    lea rdi, [rip + g_face_ui]
    mov esi, [rsp + 28]
    add esi, 8
    mov edx, [rsp + 4]
    mov ecx, r13d
    lea r8, [rip + sd_work]
    lea r9, [rip + sd_work_end]
    sub r9, r8
    COLOR eax, T_FG
    push rax
    push rax
    call ui_text_v
    add rsp, 16
    mov edi, [rsp + 28]
    dec edi
    mov esi, [rsp + 4]
    mov edx, 1
    mov ecx, [rsp + 12]
    COLOR r8d, T_BORDER
    call gfx_fill
    # Full-file change map, outside the right editor scrollbar.
    mov edi, [rsp]
    add edi, [rsp + 8]
    M eax, MI_12
    sub edi, eax
    mov [rsp + 40], edi
    mov esi, [rsp + 32]
    mov edx, eax
    mov ecx, [rsp + 36]
    COLOR r8d, T_INPUT
    call gfx_fill
    xor r14d, r14d
.Lsd_map_draw:
    cmp r14, [r12 + SD_count]
    jae .Lsd_map_input
    imul rax, r14, SR_SIZE
    lea r15, [r12 + rax + SD_DATA]
    cmp qword ptr [r15 + 16], 0
    je 5f
    mov rax, r14
    movsxd rcx, dword ptr [rsp + 36]
    imul rax, rcx
    xor edx, edx
    div qword ptr [r12 + SD_count]
    mov esi, [rsp + 32]
    add esi, eax
    mov edi, [rsp + 40]
    M edx, MI_12
    mov ecx, 3
    COLOR r8d, T_GIT_MOD
    cmp qword ptr [r15], -1
    jne 51f
    COLOR r8d, T_GIT_ADD
51: cmp qword ptr [r15 + 8], -1
    jne 52f
    COLOR r8d, T_GIT_DEL
52: call gfx_fill
5:  inc r14
    jmp .Lsd_map_draw
.Lsd_map_input:
    mov edi, 0x735000
    mov esi, [rsp + 40]
    mov edx, [rsp + 32]
    M ecx, MI_12
    mov r8d, [rsp + 36]
    call ui_btn
    test eax, UB_PRESS
    jz 8f
    mov eax, [rip + g_my]
    sub eax, [rsp + 32]
    movsxd rax, eax
    imul rax, [r12 + SD_count]
    xor edx, edx
    movsxd rcx, dword ptr [rsp + 36]
    div rcx
    # Find the nearest changed aligned row, including pure deletions.
    mov r14, rax
    xor r15d, r15d
6:  mov rsi, r14
    sub rsi, r15
    js 61f
    imul rcx, rsi, SR_SIZE
    cmp qword ptr [r12 + rcx + SD_DATA + 16], 0
    jne 7f
61: lea rsi, [r14 + r15]
    cmp rsi, [r12 + SD_count]
    jae 62f
    imul rcx, rsi, SR_SIZE
    cmp qword ptr [r12 + rcx + SD_DATA + 16], 0
    jne 7f
62: inc r15
    cmp r15, [r12 + SD_count]
    jb 6b
    jmp 8f
7:  mov r14, rsi
    mov rdi, rbx
    call side_row_line
    mov rdi, rbx
    mov rsi, rax
    call doc_line_start
    mov [rbx + DOC_cur], rax
    mov [rbx + DOC_anchor], rax
    mov eax, [rsp + 36]
    xor edx, edx
    div dword ptr [rip + g_lh]
    shr eax, 1
    sub r14, rax
    jns 71f
    xor r14d, r14d
71: shl r14, 8
    mov [rbx + DOC_scrolly], r14
    mov dword ptr [rip + g_focus], FOCUS_EDITOR
    mov dword ptr [rip + g_dirty], 1
8:  mov eax, [rsp + 16]
    mov [rip + cfg_word_wrap], eax
    mov eax, [rsp + 20]
    mov [rip + cfg_folding], eax
    mov eax, 1
    EPILOGUE
.Lsd_plain:
    call side_leave
    xor eax, eax
    EPILOGUE
