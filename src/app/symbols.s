# Built-in definition lookup. The workspace walk revalidates file snapshots on demand.
# An unchanged file keeps its symbols; only one file's source is held while parsing.
.include "rhun.inc"

.equ SYM_FILES_MAX, 16384
.equ SYM_COUNT_MAX, 150000
.equ SYM_FILE_MAX, 2097152
.equ SYM_LINE_MAX, 16384
.equ SYM_NAME_MAX, 100
.equ SYM_BUCKETS, 4096
.equ SYM_MATCH_MAX, 128

STRUCT
F SI_next, 8
F SI_path, 8
F SI_stamp, 8
F SI_doc, 8
F SI_version, 8
F SI_grammar, 8
F SI_seen, 8
F SI_filter, 8
F SI_words, SB_SIZE
F SI_symbols, VEC_SIZE
F SI_partial, 4
F SI_family, 4
ENDSTRUCT SI_SIZE

STRUCT
F SS_hash, 8
F SS_name, 4
F SS_line, 4
F SS_col, 4
ENDSTRUCT SS_SIZE

.bss
.p2align 3
buckets: .zero 8 * SYM_BUCKETS
file_count: .quad 0
symbol_count: .quad 0
scan_number: .quad 0
workspace_gen: .long 0
running: .long 0
partial: .long 0
matches: .long 0
family: .long 0
first_doc: .quad 0
query_hash: .quad 0
query_len: .quad 0
query: .zero SYM_NAME_MAX + 1
.p2align 3
file: .quad 0
source: .quad 0
source_len: .quad 0
source_pos: .quad 0
source_line: .long 0
token_state: .long 0
classes: .zero SYM_LINE_MAX
clean: .zero SYM_LINE_MAX + 1

.text

# symbols_start(doc) -> 1 when an on-demand lookup was started.
FN symbols_start
    PROLOGUE
    cmp dword ptr [rip + cfg_builtin_definitions], 0
    je 9f
    cmp dword ptr [rip + g_remote], 0
    jne 9f
    mov rbx, rdi
    cmp qword ptr [rbx + DOC_uri], 0
    jne 9f
    cmp qword ptr [rbx + DOC_path], 0
    je 9f
    mov rdi, [rbx + DOC_lang]
    call symbol_family
    test eax, eax
    jz 9f
    mov r14d, eax
    mov rdi, rbx
    mov rsi, [rbx + DOC_cur]
    mov edx, r14d
    call word_for_family
    mov r12, rax
    mov r13, rdx
    cmp r12, r13
    jae 9f
    sub r13, r12
    cmp r13, SYM_NAME_MAX
    ja 9f
    mov rdi, rbx
    mov rsi, r12
    mov rdx, r13
    lea rcx, [rip + query]
    call doc_copy
    lea rdi, [rip + query]
    mov byte ptr [rdi + r13], 0
    mov rsi, r13
    call hash_line
    mov [rip + query_hash], rax
    mov [rip + query_len], r13
    call symbols_workspace_changed
    call filesearch_symbols_start
    test rax, rax
    jnz 9f
    inc qword ptr [rip + scan_number]
    mov [rip + family], r14d
    mov rax, [rbx + DOC_id]
    mov [rip + first_doc], rax
    mov dword ptr [rip + matches], 0
    mov dword ptr [rip + partial], 0
    mov dword ptr [rip + running], 1
    mov eax, 1
    EPILOGUE
9:  xor eax, eax
    EPILOGUE

# GAS .L labels are local to their file.
FN symbols_local_only
    xor eax, eax
    cmp dword ptr [rip + family], SYMBOL_ASM
    jne 9f
    cmp word ptr [rip + query], 0x4c2e
    sete al
9:  ret

# symbols_word(doc, pos) -> as word_at, with assembler dots and JavaScript dollars.
FN symbols_word
    push rdi
    push rsi
    sub rsp, 8
    mov rdi, [rdi + DOC_lang]
    call symbol_family
    mov edx, eax
    add rsp, 8
    pop rsi
    pop rdi
word_for_family:
    cmp edx, SYMBOL_ASM
    je 1f
    cmp edx, SYMBOL_JS
    jne word_at
    mov edx, '$'
    jmp 2f
1:  mov edx, '.'
2:  PROLOGUE
    mov rbx, rdi
    mov r12, rsi
    mov r13, rsi
    mov r14d, edx
3:  test r12, r12
    jz 5f
    mov rdi, rbx
    lea rsi, [r12 - 1]
    call doc_byte
    cmp eax, r14d
    je 4f
    mov edi, eax
    call is_ident
    test eax, eax
    jz 5f
4:  dec r12
    jmp 3b
5:  mov rdi, rbx
    call doc_len
    mov r15, rax
6:  cmp r13, r15
    jae 8f
    mov rdi, rbx
    mov rsi, r13
    call doc_byte
    cmp eax, r14d
    je 7f
    mov edi, eax
    call is_ident
    test eax, eax
    jz 8f
7:  inc r13
    jmp 6b
8:  mov rax, r12
    mov rdx, r13
    EPILOGUE

# A cancelled or interrupted file has no committed snapshot.
FN symbols_cancel
    cmp dword ptr [rip + running], 0
    je 9f
    PROLOGUE
    mov dword ptr [rip + running], 0
    call filesearch_symbols_cancel
    mov rbx, [rip + file]
    test rbx, rbx
    jz 1f
    call clear_entries
    mov qword ptr [rbx + SI_grammar], 0
1:  call release_source
    EPILOGUE
9:  ret

FN symbols_apply_settings
    cmp dword ptr [rip + cfg_builtin_definitions], 0
    jne 9f
    cmp qword ptr [rip + file_count], 0
    jne reset_index
    cmp dword ptr [rip + running], 0
    jne reset_index
9:  ret

FN symbols_workspace_changed
    mov eax, [rip + g_ws_gen]
    cmp eax, [rip + workspace_gen]
    je 9f
    mov [rip + workspace_gen], eax
    jmp reset_index
9:  ret

reset_index:
    PROLOGUE
    call langfeat_symbols_cancel
    cmp qword ptr [rip + file_count], 0
    je 9f
    xor edi, edi
    call prune
9:  EPILOGUE

# prune(keep scan number, or 0 for all): remove paths missing from a complete walk.
prune:
    PROLOGUE
    mov r13, rdi
    lea r12, [rip + buckets]
    lea r14, [r12 + 8 * SYM_BUCKETS]
1:  mov r15, r12
2:  mov rbx, [r15]
    test rbx, rbx
    jz 4f
    test r13, r13
    jz 3f
    mov eax, [rip + family]
    cmp [rbx + SI_family], eax
    jne 21f
    cmp [rbx + SI_seen], r13
    jne 3f
21:
    lea r15, [rbx + SI_next]
    jmp 2b
3:  mov rax, [rbx + SI_next]
    mov [r15], rax
    call clear_entries
    mov rdi, [rbx + SI_path]
    call mem_free
    mov rdi, rbx
    call mem_free
    dec qword ptr [rip + file_count]
    jmp 2b
4:  add r12, 8
    cmp r12, r14
    jb 1b
    EPILOGUE

# clear_entries() with rbx the file.
clear_entries:
    PROLOGUE
    mov rax, [rbx + SI_symbols + VEC_len]
    sub [rip + symbol_count], rax
    lea rdi, [rbx + SI_symbols]
    call vec_free
    lea rdi, [rbx + SI_words]
    call sb_free
    mov qword ptr [rbx + SI_filter], 0
    mov dword ptr [rbx + SI_partial], 0
    EPILOGUE

# symbols_file(path): consider a file from the walk. Open buffers override the disk.
FN symbols_file
    PROLOGUE 32
    mov r12, rdi
    call strlen
    mov [rsp], rax
    mov rdi, r12
    mov rsi, rax
    call path_basename
    mov rdi, rax
    mov rsi, rdx
    call symbol_path_family
    cmp eax, [rip + family]
    jne 9f
    mov rdi, r12
    call app_find_tab
    xor r13d, r13d
    test rax, rax
    js 1f
    mov rdi, rax
    call tab_at
    mov r13, [rax + TAB_doc]
    test r13, r13
    jz 1f
    cmp qword ptr [r13 + DOC_uri], 0
    jne 9f
    mov rdi, [r13 + DOC_lang]
    call symbol_family
    cmp eax, [rip + family]
    jne 9f
    jmp 2f
1:  mov rdi, r12
    call disk_stamp
    test eax, eax
    jz 9f
    cmp qword ptr [rip + vfs_statbuf + 48], SYM_FILE_MAX
    ja .Lfile_limit
    mov [rsp + 8], rdx
2:  mov rdi, r12
    mov rsi, [rsp]
    call cache_find
    mov rbx, rax
    test rbx, rbx
    jnz 5f
    mov r14, rdx
    cmp qword ptr [rip + file_count], SYM_FILES_MAX
    jae .Lfile_limit
    mov edi, SI_SIZE
    call mem_alloc
    mov rbx, rax
    mov rdi, r12
    mov rsi, [rsp]
    call mem_dup
    mov [rbx + SI_path], rax
    mov rax, [r14]
    mov [rbx + SI_next], rax
    mov [r14], rbx
    inc qword ptr [rip + file_count]
5:  mov rax, [rip + scan_number]
    cmp [rbx + SI_seen], rax
    je 9f
    mov [rbx + SI_seen], rax
    mov eax, [rip + family]
    mov [rbx + SI_family], eax
    test r13, r13
    jz .Lfile_disk
    mov r14, [r13 + DOC_lang]
    cmp [rbx + SI_grammar], r14
    jne .Lfile_buffer
    mov rax, [r13 + DOC_id]
    cmp [rbx + SI_doc], rax
    jne .Lfile_buffer
    mov rax, [r13 + DOC_version]
    cmp [rbx + SI_version], rax
    je .Lfile_cached
.Lfile_buffer:
    call clear_entries
    mov [rbx + SI_grammar], r14
    mov rax, [r13 + DOC_id]
    mov [rbx + SI_doc], rax
    mov rax, [r13 + DOC_version]
    mov [rbx + SI_version], rax
    mov rdi, r13
    call doc_len
    cmp rax, SYM_FILE_MAX
    ja .Lfile_too_large
    mov r15, rax
    lea rdi, [rax + 1]
    call mem_alloc
    mov [rip + source], rax
    mov rcx, rax
    mov rdi, r13
    xor esi, esi
    mov rdx, r15
    call doc_copy
    jmp .Lfile_scan
.Lfile_disk:
    cmp qword ptr [rbx + SI_doc], 0
    jne 6f
    cmp qword ptr [rbx + SI_grammar], 0
    je 6f
    mov rax, [rsp + 8]
    cmp [rbx + SI_stamp], rax
    je .Lfile_cached
6:  call clear_entries
    mov qword ptr [rbx + SI_doc], 0
    mov qword ptr [rbx + SI_grammar], 0
    mov rdi, r12
    mov rsi, [rsp]
    call path_basename
    mov rdi, rax
    mov rsi, rdx
    call syntax_for_name
    mov r14, rax
    mov rdi, rax
    call symbol_family
    cmp eax, [rip + family]
    jne 9f
    mov rdi, r12
    mov esi, SYM_FILE_MAX
    call vfs_read_limited
    test rax, rax
    jz .Lfile_limit
    mov [rip + source], rax
    mov r15, rdx
    mov rax, [rsp + 8]
    mov [rbx + SI_stamp], rax
    mov [rbx + SI_grammar], r14
    # Binary files with a source suffix are ignored.
    mov rdi, [rip + source]
    mov rcx, r15
    mov eax, 8192
    cmp rcx, rax
    cmova rcx, rax
    test rcx, rcx
    jz .Lfile_scan
    xor eax, eax
    repne scasb
    jne .Lfile_scan
    call release_source
    jmp 9f
.Lfile_scan:
    mov rdi, r14
    call syntax_ready
    mov [rip + source_len], r15
    mov qword ptr [rip + source_pos], 0
    mov dword ptr [rip + source_line], 1
    mov dword ptr [rip + token_state], 0
    mov [rip + file], rbx
    call symbol_rules_reset
    jmp 9f
.Lfile_too_large:
    mov dword ptr [rbx + SI_partial], 1
.Lfile_limit:
    mov dword ptr [rip + partial], 1
    jmp 9f
.Lfile_cached:
    call collect
9:  EPILOGUE

# cache_find(path, len) -> rax file or 0, rdx the bucket's address.
cache_find:
    PROLOGUE
    mov r12, rdi
    call hash_line
    and eax, SYM_BUCKETS - 1
    lea r13, [rip + buckets]
    lea r13, [r13 + rax*8]
    mov rbx, [r13]
1:  test rbx, rbx
    jz 9f
    mov rdi, [rbx + SI_path]
    mov rsi, r12
    call strcmp_eq
    test eax, eax
    jnz 9f
    mov rbx, [rbx + SI_next]
    jmp 1b
9:  mov rax, rbx
    mov rdx, r13
    EPILOGUE

# disk_stamp(path) -> eax 1 for a regular file, with its stamp in rdx.
disk_stamp:
    push rbx
    call vfs_lstat
    test rax, rax
    js 8f
    mov eax, [rip + vfs_statbuf + 24]
    and eax, 0xf000
    cmp eax, 0x8000
    jne 8f
    mov rdx, [rip + vfs_statbuf + 88]
    imul rdx, rdx, 1000000000
    add rdx, [rip + vfs_statbuf + 96]
    mov rcx, [rip + vfs_statbuf + 48]
    rol rcx, 32
    xor rdx, rcx
    xor rdx, [rip + vfs_statbuf + 8]
    mov eax, 1
    pop rbx
    ret
8:  xor eax, eax
    pop rbx
    ret

# A candidate can outlive the scan. Check its snapshot again before navigating.
FN symbols_location_current
    PROLOGUE
    mov eax, [rip + g_ws_gen]
    cmp eax, [rip + workspace_gen]
    jne 8f
    mov r12, rdi
    call strlen
    mov rdi, r12
    mov rsi, rax
    call cache_find
    test rax, rax
    jz 8f
    mov rbx, rax
    mov rdi, r12
    call app_find_tab
    test rax, rax
    js 1f
    mov rdi, rax
    call tab_at
    mov rax, [rax + TAB_doc]
    test rax, rax
    jz 1f
    mov rcx, [rbx + SI_doc]
    test rcx, rcx
    jz 2f
    cmp [rax + DOC_id], rcx
    jne 8f
    mov rcx, [rax + DOC_version]
    cmp [rbx + SI_version], rcx
    jne 8f
    mov rcx, [rax + DOC_lang]
    cmp [rbx + SI_grammar], rcx
    jne 8f
    jmp 9f
2:  cmp qword ptr [rax + DOC_version], 0
    jne 8f
1:  cmp qword ptr [rbx + SI_doc], 0
    jne 8f
    mov rdi, r12
    call disk_stamp
    test eax, eax
    jz 8f
    cmp [rbx + SI_stamp], rdx
    jne 8f
9:  mov eax, 1
    EPILOGUE
8:  xor eax, eax
    EPILOGUE

# symbols_step() -> 1 after doing work, 0 when the walk can take the next path.
FN symbols_step
    PROLOGUE
    mov rbx, [rip + file]
    test rbx, rbx
    jnz 1f
    mov rdi, [rip + first_doc]
    test rdi, rdi
    jz 8f
    mov qword ptr [rip + first_doc], 0
    call extproto_doc
    test rax, rax
    jz 8f
    mov rdi, [rax + DOC_path]
    test rdi, rdi
    jz 8f
    call symbols_file
    jmp 9f
1:  mov r12, [rip + source]
    add r12, [rip + source_pos]
    mov r13, [rip + source_len]
    sub r13, [rip + source_pos]
    jbe 6f
    mov rdi, r12
    mov rsi, r13
    mov eax, SYM_LINE_MAX + 1
    cmp rsi, rax
    cmova rsi, rax
    lea rdx, [rip + newline]
    mov ecx, 1
    call str_find
    test rax, rax
    jns 2f
    cmp r13, SYM_LINE_MAX
    ja 5f
    add [rip + source_pos], r13
    jmp 3f
2:  mov r13, rax
    lea rax, [r13 + 1]
    add [rip + source_pos], rax
3:  mov rdi, [rbx + SI_grammar]
    mov rsi, r12
    mov rdx, r13
    mov ecx, [rip + token_state]
    lea r8, [rip + classes]
    call tokenize
    mov [rip + token_state], eax
    # Mask non-code while keeping byte columns, including tabs and UTF-8.
    lea rdi, [rip + clean]
    lea rsi, [rip + classes]
    xor ecx, ecx
4:  cmp rcx, r13
    jae 41f
    mov al, [r12 + rcx]
    mov dl, [rsi + rcx]
    cmp dl, C_COMMENT
    je 40f
    cmp dl, C_STRING
    je 40f
    cmp dl, C_ESCAPE
    jne 42f
40: mov al, ' '
42: mov [rdi + rcx], al
    inc rcx
    jmp 4b
41: mov byte ptr [rdi + r13], 0
    mov esi, [rip + family]
    mov edx, [rip + source_line]
    call symbol_rules_line
    test eax, eax
    jnz 5f
    inc dword ptr [rip + source_line]
    jmp 9f
5:  # Later lines may be part of a comment or scope started in this one.
    mov dword ptr [rbx + SI_partial], 1
6:  call collect
    call release_source
    jmp 9f
8:  xor eax, eax
    EPILOGUE
9:  mov eax, 1
    EPILOGUE

release_source:
    PROLOGUE
    mov rdi, [rip + source]
    call mem_free
    mov qword ptr [rip + source], 0
    mov qword ptr [rip + file], 0
    EPILOGUE

# symbols_emit(name, len, line, byte column): called by the language rules.
FN symbols_emit
    PROLOGUE
    mov rbx, [rip + file]
    test rsi, rsi
    jz 9f
    cmp rsi, SYM_NAME_MAX
    ja 9f
    cmp qword ptr [rip + symbol_count], SYM_COUNT_MAX
    jae 8f
    mov r12, rdi
    mov r13, rsi
    mov r14d, edx
    mov r15d, ecx
    call hash_line
    mov ecx, eax
    and ecx, 63
    bts qword ptr [rbx + SI_filter], rcx
    push rax
    push rax
    lea rdi, [rbx + SI_symbols]
    mov esi, SS_SIZE
    call vec_push
    pop rdx
    pop rdx
    mov [rax + SS_hash], rdx
    mov rdx, [rbx + SI_words + SB_len]
    mov [rax + SS_name], edx
    mov [rax + SS_line], r14d
    mov [rax + SS_col], r15d
    lea rdi, [rbx + SI_words]
    mov rsi, r12
    mov rdx, r13
    call sb_push
    lea rdi, [rbx + SI_words]
    xor esi, esi
    call sb_push_byte
    inc qword ptr [rip + symbol_count]
    jmp 9f
8:  mov dword ptr [rbx + SI_partial], 1
9:  EPILOGUE

# collect() with rbx the file: emit exact matches from this snapshot.
collect:
    PROLOGUE
    mov eax, [rbx + SI_partial]
    or [rip + partial], eax
    mov r14, [rip + query_hash]
    mov rax, [rbx + SI_filter]
    bt rax, r14
    jnc 9f
    mov r12, [rbx + SI_symbols + VEC_ptr]
    imul r13, [rbx + SI_symbols + VEC_len], SS_SIZE
    add r13, r12
1:  cmp r12, r13
    jae 9f
    cmp [r12 + SS_hash], r14
    jne 3f
    mov edx, [r12 + SS_name]
    add rdx, [rbx + SI_words + SB_ptr]
    mov rsi, [rip + query_len]
    lea rdi, [rip + query]
    call str_eq_cstr
    test eax, eax
    jz 3f
    cmp dword ptr [rip + matches], SYM_MATCH_MAX
    jae 8f
    mov rdi, [rbx + SI_path]
    mov esi, [r12 + SS_line]
    mov edx, [r12 + SS_col]
    mov ecx, [rip + query_len]
    call langfeat_symbols_match
    inc dword ptr [rip + matches]
3:  add r12, SS_SIZE
    jmp 1b
8:  mov dword ptr [rip + partial], 1
9:  EPILOGUE

FN symbols_finish
    PROLOGUE
    mov ebx, edi
    mov dword ptr [rip + running], 0
    mov eax, [rip + workspace_gen]
    cmp eax, [rip + g_ws_gen]
    jne 8f
    test ebx, ebx
    jnz 1f
    call symbols_local_only
    test eax, eax
    jnz 1f
    mov rdi, [rip + scan_number]
    call prune
1:  or ebx, [rip + partial]
    mov edi, ebx
    call langfeat_symbols_done
    EPILOGUE
8:  call langfeat_symbols_cancel
    EPILOGUE

.section .rodata
newline: .byte 10
