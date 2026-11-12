# Native Markdown file previews: independent rendered tabs and a live source/preview split.
.include "rhun.inc"
.equ MP_dc, 0
.equ MP_source, 8              # source DOC_id, never a borrowed pointer
.equ MP_version, 16            # DOC_version + 1 last parsed
.equ MP_name, 24               # owned standalone tab label, or 0
.equ MP_SIZE, 32
.equ MP_SLOT, 64               # outside extension doc-view slots
.equ ID_MP_SPLIT, 0x1b000
.bss
.p2align 3
preview_name: .zero SB_SIZE
.text

# mdpreview_is_markdown(path cstr or 0) -> 1 for Markdown filenames.
FN mdpreview_is_markdown
    PROLOGUE
    mov rbx, rdi
    test rdi, rdi
    jz 8f
    call strlen
    mov r12, rax
    mov rdi, rbx
    mov rsi, rax
    call path_basename
    mov rcx, rdx
1:  test rcx, rcx
    jz 8f
    dec rcx
    cmp byte ptr [rax + rcx], '.'
    jne 1b
    lea rbx, [rax + rcx + 1]
    sub rdx, rcx
    dec rdx
    mov r12, rdx
    mov rdi, rbx
    mov rsi, rdx
    lea rdx, [rip + .Lmd]
    call str_ieq_cstr
    test eax, eax
    jnz 9f
    mov rdi, rbx
    mov rsi, r12
    lea rdx, [rip + .Lmarkdown]
    call str_ieq_cstr
    test eax, eax
    jnz 9f
    mov rdi, rbx
    mov rsi, r12
    lea rdx, [rip + .Lmdown]
    call str_ieq_cstr
    jmp 9f
8:  xor eax, eax
9:  EPILOGUE

FN cmd_markdown_preview
    xor esi, esi
    jmp preview_current
FN cmd_markdown_preview_side
    mov esi, 1
    jmp preview_current
FN cmd_markdown_preview_close
    PROLOGUE
    mov rdi, [rip + g_tab_cur]
    test rdi, rdi
    js 1f
    call tab_at
    test dword ptr [rax + TAB_flags], TF_MD_SIDE
    jz 1f
    and dword ptr [rax + TAB_flags], ~TF_MD_SIDE
    mov dword ptr [rip + g_focus], FOCUS_EDITOR
    mov dword ptr [rip + g_dirty], 1
1:  EPILOGUE
preview_current:
    mov rdi, [rip + g_file]
    test rdi, rdi
    jz 1f
    mov rdi, [rdi + DOC_path]
    test rdi, rdi
    jz 1f
    jmp mdpreview_open_path
1:  ret

# mdpreview_open_path(path, side): the source is always the existing editable document.
FN mdpreview_open_path
    PROLOGUE
    mov r12, rdi
    mov r13d, esi
    call mdpreview_is_markdown
    test eax, eax
    jz 9f
    mov rdi, r12
    call app_open_file
    test rax, rax
    js 9f
    mov rdi, rax
    call tab_at
    cmp qword ptr [rax + TAB_kind], TAB_DOC
    jne 9f
    mov rbx, [rax + TAB_doc]
    mov r14, rax
    mov rdi, rbx
    call doc_len
    cmp rax, 1048576
    ja 8f
    test r13d, r13d
    jz .Lmp_open_tab
    or dword ptr [r14 + TAB_flags], TF_MD_SIDE
    and dword ptr [r14 + TAB_flags], ~TF_SIDE_DIFF
    mov rdi, rbx
    call preview_ensure
    mov dword ptr [rip + g_focus], FOCUS_EDITOR
    mov dword ptr [rip + g_dirty], 1
    jmp 9f
.Lmp_open_tab:
    xor r14d, r14d
1:  cmp r14, [rip + g_tabs + VEC_len]
    jae 3f
    mov rdi, r14
    call tab_at
    cmp qword ptr [rax + TAB_kind], TAB_MD_PREVIEW
    jne 2f
    mov rax, [rax + TAB_doc]
    mov rax, [rax + DOC_mdpreview]
    mov rcx, [rbx + DOC_id]
    cmp [rax + MP_source], rcx
    jne 2f
    mov rdi, r14
    call app_activate_tab
    jmp 9f
2:  inc r14
    jmp 1b
3:  call doc_new
    mov r15, rax
    mov rdi, rbx
    call preview_new
    mov r14, rax
    mov [r15 + DOC_mdpreview], rax
    lea rdi, [rip + preview_name]
    call sb_clear
    lea rdi, [rip + preview_name]
    mov rsi, [rbx + DOC_name]
    call sb_push_cstr
    lea rdi, [rip + preview_name]
    lea rsi, [rip + .Lsuffix]
    call sb_push_cstr
    lea rdi, [rip + preview_name]
    xor esi, esi
    call sb_push_byte
    mov rdi, [rip + preview_name + SB_ptr]
    call dup_cstr
    mov [r14 + MP_name], rax
    mov [r15 + DOC_name], rax
    mov rdi, r14
    call preview_refresh
    mov rdi, r15
    mov esi, TAB_MD_PREVIEW
    call app_add_tab
    jmp 9f
8:  lea rdi, [rip + .Llarge]
    call app_toast
9:  EPILOGUE

preview_ensure:
    cmp qword ptr [rdi + DOC_mdpreview], 0
    je 1f
    mov rax, [rdi + DOC_mdpreview]
    ret
1:  push rdi
    call preview_new
    pop rdi
    mov [rdi + DOC_mdpreview], rax
    ret

preview_new:                   # source DOC -> MP*
    PROLOGUE
    mov rbx, rdi
    mov edi, MP_SIZE
    call mem_alloc
    mov r12, rax
    mov rax, [rbx + DOC_id]
    mov [r12 + MP_source], rax
    mov edi, MP_SLOT
    xor esi, esi
    call mdview_new
    mov [r12 + MP_dc], rax
    mov r13, [rbx + DOC_path]
    test r13, r13
    jz 1f
    mov rdi, r13
    call strlen
    mov rdi, r13
    mov rsi, rax
    call path_dirlen
    mov rdi, [r12 + MP_dc]
    mov rsi, r13
    mov rdx, rax
    call mdview_set_base
1:  mov rax, r12
    EPILOGUE

preview_refresh:               # MP*: update from the live buffer, including unsaved edits
    PROLOGUE
    mov rbx, rdi
    mov rdi, [rbx + MP_source]
    call app_doc_by_id
    test rax, rax
    jz 9f                       # source closed: retain the last rendered snapshot safely
    mov r12, rax
    mov r13, [rax + DOC_version]
    inc r13
    cmp r13, [rbx + MP_version]
    je 9f
    mov rdi, r12
    call doc_len
    cmp rax, 1048576
    ja 8f
    mov rdi, r12
    call doc_text_copy
    mov r14, rax
    mov rdi, [rbx + MP_dc]
    mov rsi, rax
    call mdview_set_text
    mov rdi, r14
    call mem_free
    mov [rbx + MP_version], r13
    jmp 9f
8:  mov rdi, [rbx + MP_dc]
    lea rsi, [rip + .Llarge]
    mov edx, .Llarge_len
    call mdview_set_text
    mov [rbx + MP_version], r13
9:  EPILOGUE

FN mdpreview_doc_free
    PROLOGUE
    mov rbx, [rdi + DOC_mdpreview]
    mov qword ptr [rdi + DOC_mdpreview], 0
    test rbx, rbx
    jz 9f
    mov rdi, [rbx + MP_dc]
    call mdview_free
    mov rdi, [rbx + MP_name]
    call mem_free
    mov rdi, rbx
    call mem_free
9:  EPILOGUE

# Keep text input out of a standalone preview; tab switches restore ordinary editor focus.
FN mdpreview_focus_sync
    mov rdi, [rip + g_tab_cur]
    test rdi, rdi
    js 1f
    call tab_at
    cmp qword ptr [rax + TAB_kind], TAB_MD_PREVIEW
    jne 1f
    mov dword ptr [rip + g_focus], FOCUS_MD_PREVIEW
    ret
1:  cmp dword ptr [rip + g_focus], FOCUS_MD_PREVIEW
    jne 2f
    mov dword ptr [rip + g_focus], FOCUS_EDITOR
2:  ret

preview_active:                # focused MP*, or 0
    xor eax, eax
    cmp dword ptr [rip + g_focus], FOCUS_MD_PREVIEW
    jne 9f
    mov rdi, [rip + g_tab_cur]
    test rdi, rdi
    js 8f
    call tab_at
    mov rax, [rax + TAB_doc]
    test rax, rax
    jz 9f
    mov rax, [rax + DOC_mdpreview]
    ret
8:  xor eax, eax
9:  ret

FN mdpreview_key
    PROLOGUE
    mov r12d, edi
    mov r13d, esi
    mov r14d, edx
    call preview_active
    test rax, rax
    jz 8f
    test r14d, MOD_CTRL | MOD_ALT | MOD_SUPER
    jnz 8f
    cmp r12d, KEY_ESCAPE
    jne 1f
    mov rdi, [rip + g_tab_cur]
    call tab_at
    cmp qword ptr [rax + TAB_kind], TAB_MD_PREVIEW
    je 8f
    mov dword ptr [rip + g_focus], FOCUS_EDITOR
    mov eax, 1
    EPILOGUE
1:  mov rdi, [rax + MP_dc]
    mov esi, r12d
    mov edx, r13d
    mov ecx, r14d
    call mdview_key
    EPILOGUE
8:  xor eax, eax
    EPILOGUE

FN mdpreview_clip
    PROLOGUE
    mov r12d, edi
    call preview_active
    test rax, rax
    jz 8f
    mov rdi, [rax + MP_dc]
    mov esi, r12d
    call mdview_clip
    mov eax, 1
    EPILOGUE
8:  xor eax, eax
    EPILOGUE

FN mdpreview_draw_tab
    PROLOGUE 16
    mov [rsp], edi
    mov [rsp + 4], esi
    mov [rsp + 8], edx
    mov [rsp + 12], ecx
    mov rdi, [rip + g_file]
    mov rdi, [rdi + DOC_mdpreview]
    mov rbx, rdi
    call preview_refresh
    mov rdi, rbx
    mov esi, [rsp]
    mov edx, [rsp + 4]
    mov ecx, [rsp + 8]
    mov r8d, [rsp + 12]
    call preview_draw
    EPILOGUE

FN mdpreview_draw_side
    PROLOGUE 32
    mov [rsp], edi
    mov [rsp + 4], esi
    mov [rsp + 8], edx
    mov [rsp + 12], ecx
    mov rdi, [rip + g_tab_cur]
    test rdi, rdi
    js 8f
    call tab_at
    test dword ptr [rax + TAB_flags], TF_MD_SIDE
    jz 8f
    mov rbx, [rip + g_doc]
    test rbx, rbx
    jz 8f
    call side_leave
    mov rdi, rbx
    call preview_ensure
    mov r12, rax
    mov rdi, rax
    call preview_refresh
    mov eax, [rsp + 8]
    dec eax
    sar eax, 1
    mov [rsp + 16], eax         # source width
    mov [rip + g_editor_rect + 8], eax
    # Clicking the source returns keyboard focus; preview receives no source edits.
    mov edi, [rsp]
    mov esi, [rsp + 4]
    mov edx, eax
    mov ecx, [rsp + 12]
    call ui_in
    test eax, eax
    jz 1f
    test dword ptr [rip + g_pressed], 7
    jz 1f
    mov dword ptr [rip + g_focus], FOCUS_EDITOR
1:  mov rdi, rbx
    mov rsi, [rbx + DOC_scrolly]
    shr rsi, 8
    mov eax, [rsp + 12]
    xor edx, edx
    div dword ptr [rip + g_lh]
    lea rsi, [rsi + rax + 2]
    call syntax_prepare
    mov edi, [rsp]
    mov esi, [rsp + 4]
    mov edx, [rsp + 16]
    mov ecx, [rsp + 12]
    call editor_draw
    mov edi, [rsp]
    add edi, [rsp + 16]
    mov esi, [rsp + 4]
    mov edx, 1
    mov ecx, [rsp + 12]
    COLOR r8d, T_BORDER
    call gfx_fill
    # A compact preview header keeps the close control out of rendered document content.
    mov edi, [rsp]
    add edi, [rsp + 16]
    inc edi
    mov esi, [rsp + 4]
    mov edx, [rsp + 8]
    sub edx, [rsp + 16]
    dec edx
    M ecx, MI_28
    COLOR r8d, T_PANEL
    call gfx_fill
    mov esi, [rsp]
    add esi, [rsp + 16]
    add esi, [rip + g_mt + 4*MI_12]
    M edx, MI_28
    sub edx, [rip + g_face_small + FACE_ascent]
    sub edx, [rip + g_face_small + FACE_descent]
    sar edx, 1
    add edx, [rsp + 4]
    add edx, [rip + g_face_small + FACE_ascent]
    lea rdi, [rip + g_face_small]
    lea rcx, [rip + .Ltitle]
    mov r8d, 7
    COLOR r9d, T_MUTED
    call text_draw
    mov edi, ID_MP_SPLIT
    mov esi, [rsp]
    add esi, [rsp + 8]
    sub esi, [rip + g_mt + 4*MI_28]
    mov edx, [rsp + 4]
    M ecx, MI_28
    mov r8d, ecx
    mov r9d, IC_CLOSE
    call ui_icon_btn
    test eax, UB_CLICK
    jz 2f
    call cmd_markdown_preview_close
2:
    mov rdi, r12
    mov esi, [rsp]
    add esi, [rsp + 16]
    inc esi
    mov edx, [rsp + 4]
    add edx, [rip + g_mt + 4*MI_28]
    mov ecx, [rsp + 8]
    sub ecx, [rsp + 16]
    dec ecx
    mov r8d, [rsp + 12]
    sub r8d, [rip + g_mt + 4*MI_28]
    call preview_draw
    mov eax, 1
    EPILOGUE
8:  xor eax, eax
    EPILOGUE

preview_draw:                  # MP*, x,y,w,h: reuse native Markdown selection/links/scrollbar
    PROLOGUE 32
    mov rbx, rdi
    mov [rsp], esi
    mov [rsp + 4], edx
    mov [rsp + 8], ecx
    mov [rsp + 12], r8d
    mov edi, esi
    mov esi, edx
    mov edx, ecx
    mov ecx, r8d
    COLOR r8d, T_BG
    call gfx_fill
    mov edi, [rsp]
    mov esi, [rsp + 4]
    mov edx, [rsp + 8]
    mov ecx, [rsp + 12]
    call ui_in
    test eax, eax
    jz 1f
    test dword ptr [rip + g_pressed], 7
    jz 1f
    mov dword ptr [rip + g_focus], FOCUS_MD_PREVIEW
1:  mov rdi, [rbx + MP_dc]
    mov esi, [rsp]
    mov edx, [rsp + 4]
    mov ecx, [rsp + 8]
    mov r8d, [rsp + 12]
    xor r9d, r9d
    cmp dword ptr [rip + g_focus], FOCUS_MD_PREVIEW
    sete r9b
    call mdview_draw
    EPILOGUE

# mdpreview_dump(sb): rendered state for the active preview, for regression checks.
FN mdpreview_dump
    PROLOGUE
    mov r12, rdi
    mov rax, [rip + g_file]
    test rax, rax
    jz 8f
    mov rbx, [rax + DOC_mdpreview]
    test rbx, rbx
    jz 8f
    mov rdi, rbx
    call preview_refresh
    mov rdi, [rbx + MP_dc]
    mov rsi, r12
    call mdview_dump
    jmp 9f
8:  mov rdi, r12
    lea rsi, [rip + .Lnone]
    call sb_push_cstr
9:  EPILOGUE

.section .rodata
.Lnone: .asciz "preview=none\n"
.Lmd: .asciz "md"
.Lmarkdown: .asciz "markdown"
.Lmdown: .asciz "mdown"
.Lsuffix: .asciz " (Preview)"
.Ltitle: .asciz "Preview"
.Llarge: .asciz "Markdown preview supports documents up to 1 MiB."
.equ .Llarge_len, . - .Llarge - 1
