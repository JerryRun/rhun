# Declaration patterns for the built-in workspace index. Input retains byte columns;
# the syntax tokenizer has already removed strings and comments.
.include "rhun.inc"

.equ TOKEN_MAX, 512
.equ TOKEN_SIZE, 16               # first and end byte pointers
.equ DECL_NAME_MAX, 100

.bss
.p2align 3
tokens: .zero TOKEN_SIZE * (TOKEN_MAX + 3)
braces: .long 0
go_group: .long 0
c_name_len: .long 0
c_line: .long 0
c_col: .long 0
c_parens: .long 0
c_name: .zero DECL_NAME_MAX

.text

# symbol_family(grammar or 0) -> supported language family, or 0.
FN symbol_family
    test rdi, rdi
    jz .Lfamily_none
    PROLOGUE
    mov rbx, [rdi + GR_name]
    lea r12, [rip + .Lgrammar_families]
1:  mov rsi, [r12]
    test rsi, rsi
    jz 2f
    mov rdi, rbx
    call strcmp_eq
    add r12, 16
    test eax, eax
    jz 1b
    mov eax, [r12 - 8]
2:  EPILOGUE
.Lfamily_none:
    xor eax, eax
    ret

# symbol_path_family(name, len): inexpensive suffix filter before looking up a file's grammar.
FN symbol_path_family
    PROLOGUE
    mov rbx, rdi
    mov r12, rsi
    lea rax, [rbx + r12]
1:  cmp rax, rbx
    je 2f
    dec rax
    cmp byte ptr [rax], '.'
    jne 1b
    sub r12, rax
    add r12, rbx
    mov rbx, rax
2:  lea r13, [rip + .Lpath_families]
3:  mov r14, [r13]
    test r14, r14
    jz 4f
31: cmp byte ptr [r14], 0
    je 32f
    mov rdi, rbx
    mov rsi, r12
    mov rdx, r14
    call str_eq_cstr
    test eax, eax
    jnz 33f
    mov rdi, r14
    call strlen
    lea r14, [r14 + rax + 1]
    jmp 31b
32: add r13, 16
    jmp 3b
33: mov eax, [r13 + 8]
    jmp 5f
4:  xor eax, eax
5:  EPILOGUE

FN symbol_rules_reset
    mov dword ptr [rip + braces], 0
    mov dword ptr [rip + go_group], 0
    mov dword ptr [rip + c_name_len], 0
    ret

# declaration_start(byte): is_ident without digits. Assembly and JS handle their extra prefixes.
declaration_start:
    lea eax, [rdi - '0']
    cmp eax, 9
    jbe 1f
    jmp is_ident
1:  xor eax, eax
    ret

# symbol_rules_line(clean cstr, family, line) -> 1 if the line exceeded the token budget.
# Keep token pointers for the language rules so their results use the original byte columns.
FN symbol_rules_line
    PROLOGUE
    mov rbx, rdi
    mov r14d, esi
    mov r15d, edx
    mov r13, rdi
    lea r12, [rip + tokens]
1:  movzx edi, byte ptr [r13]
    test edi, edi
    jz 6f
    cmp edi, ' '
    je 2f
    cmp edi, 9
    je 2f
    cmp edi, 13
    jne 3f
2:  inc r13
    jmp 1b
3:  lea rax, [rip + tokens + TOKEN_SIZE * TOKEN_MAX]
    cmp r12, rax
    jae .Ltoken_limit
    mov [r12], r13
    cmp r14d, SYMBOL_ASM
    jne 31f
    cmp edi, '.'
    je 4f
31: cmp r14d, SYMBOL_JS
    jne 32f
    cmp edi, '$'
    je 4f
32: call is_ident
    test eax, eax
    jnz 4f
    inc r13
    jmp 5f
4:  inc r13
    movzx edi, byte ptr [r13]
    cmp r14d, SYMBOL_ASM
    jne 41f
    cmp edi, '.'
    je 4b
41: cmp r14d, SYMBOL_JS
    jne 42f
    cmp edi, '$'
    je 4b
42: call is_ident
    test eax, eax
    jnz 4b
5:  mov [r12 + 8], r13
    add r12, TOKEN_SIZE
    cmp r14d, SYMBOL_ASM
    jne 1b
    lea rax, [rip + tokens + 2 * TOKEN_SIZE]
    cmp r12, rax                 # each assembler definition fits in its first two tokens
    je 6f
    jmp 1b
6:  mov r13, r12                # the exclusive end of the token array
    lea rdx, [rip + .Lno_token]
    mov ecx, 3                  # lookahead can read the sentinel
7:  mov [r12], rdx
    mov [r12 + 8], rdx
    add r12, TOKEN_SIZE
    dec ecx
    jnz 7b
    lea r12, [rip + tokens]
    cmp r12, r13
    je 9f
    # A C preprocessor line is handled separately; its replacement never changes brace depth.
    cmp r14d, SYMBOL_C
    jne 8f
    mov rax, [r12]
    cmp byte ptr [rax], '#'
    jne 8f
    lea rdi, [r12 + TOKEN_SIZE]
    lea rsi, [rip + .Ldefine]
    call token_eq
    test eax, eax
    jz 9f
    lea rdi, [r12 + 2 * TOKEN_SIZE]
    call emit_token
    jmp 9f
8:  lea rax, [rip + .Lrules]
    call [rax + r14*8 - 8]
    # C, Go, JS and Rust use braces for declaration scope; only real code reaches here.
    cmp r14d, SYMBOL_ASM
    je 9f
    cmp r14d, SYMBOL_PYTHON
    je 9f
    lea rcx, [rip + tokens]
    mov eax, [rip + braces]
81: cmp rcx, r13
    jae 89f
    mov rdx, [rcx]
    add rcx, TOKEN_SIZE
    cmp byte ptr [rdx], '{'
    je 82f
    cmp byte ptr [rdx], '}'
    jne 81b
    test eax, eax
    jz 81b
    dec eax
    jmp 81b
82: inc eax
    jmp 81b
89: mov [rip + braces], eax
9:  xor eax, eax
    EPILOGUE
.Ltoken_limit:
    mov eax, 1
    EPILOGUE

# token_eq(token, cstr) -> bool.
token_eq:
    mov rdx, rsi
    mov rsi, [rdi + 8]
    mov rdi, [rdi]
    sub rsi, rdi
    jmp str_eq_cstr

# Whether token starts with a valid declaration name (the caller's language is r14d).
token_is_name:
    mov rax, [rdi]
    movzx edi, byte ptr [rax]
    cmp r14d, SYMBOL_ASM
    jne 1f
    cmp edi, '.'
    jne 1f
    movzx edi, byte ptr [rax + 1]
1:  cmp r14d, SYMBOL_JS
    jne declaration_start
    cmp edi, '$'
    jne declaration_start
    mov eax, 1
    ret

# emit_token(token): line in r15d, original byte columns relative to rbx.
emit_token:
    push rdi
    call token_is_name
    pop rdi
    test eax, eax
    jz 9f
    mov rsi, [rdi + 8]
    mov rdi, [rdi]
    sub rsi, rdi
    mov ecx, edi
    sub ecx, ebx
    inc ecx
    mov edx, r15d
    jmp symbols_emit
9:  ret

# skip_parens(token, end) -> after the matching ')', or end.
skip_parens:
    xor ecx, ecx
1:  cmp rdi, rsi
    jae 4f
    mov rdx, [rdi]
    add rdi, TOKEN_SIZE
    cmp byte ptr [rdx], '('
    je 2f
    cmp byte ptr [rdx], ')'
    jne 1b
    dec ecx
    jz 4f
    jmp 1b
2:  inc ecx
    jmp 1b
4:  mov rax, rdi
    ret

# match_keyword(token, table of cstr pointers) -> eax 1 for a match.
match_keyword:
    PROLOGUE
    mov rbx, rdi
    mov r12, rsi
1:  mov rsi, [r12]
    test rsi, rsi
    jz 9f
    mov rdi, rbx
    call token_eq
    add r12, 8
    test eax, eax
    jz 1b
9:  EPILOGUE

# Assembly supports rhun's FN macro, GAS data/constants and ordinary named labels.
parse_asm:
    PROLOGUE
    mov rax, [r12 + TOKEN_SIZE]
    cmp byte ptr [rax], ':'
    je 1f
    mov rdi, r12
    lea rsi, [rip + .Lasm_decl]
    call match_keyword
    test eax, eax
    jz 9f
    lea rdi, [r12 + TOKEN_SIZE]
    call emit_token
    jmp 9f
1:  mov rdi, r12
    call emit_token
9:  EPILOGUE

parse_python:
    PROLOGUE
    mov rdi, r12
    lea rsi, [rip + .Lasync]
    call token_eq
    test eax, eax
    jz 1f
    add r12, TOKEN_SIZE
1:  mov rdi, r12
    lea rsi, [rip + .Lpy_decl]
    call match_keyword
    test eax, eax
    jz 2f
    lea rdi, [r12 + TOKEN_SIZE]
    call emit_token
    jmp 9f
2:  cmp [r12], rbx             # module assignment, not an indented local or member
    jne 9f
    mov rax, [r12 + TOKEN_SIZE]
    cmp byte ptr [rax], '='
    jne 3f
    cmp byte ptr [rax + 1], '='
    je 9f
    jmp 4f
3:  cmp byte ptr [rax], ':'
    jne 9f
    mov rax, [r12 + 2 * TOKEN_SIZE]
    cmp byte ptr [rax], 0
    je 9f
    cmp byte ptr [rax], '='      # walrus is not an annotation
    je 9f
4:  mov rdi, r12
    call emit_token
9:  EPILOGUE

parse_go:
    PROLOGUE
    cmp dword ptr [rip + braces], 0
    jne 9f
    cmp dword ptr [rip + go_group], 0
    je 2f
    mov rax, [r12]
    cmp byte ptr [rax], ')'
    jne 1f
    mov dword ptr [rip + go_group], 0
    jmp 9f
1:  mov rdi, r12
    call emit_token
    jmp 9f
2:  mov rdi, r12
    lea rsi, [rip + .Lfunc]
    call token_eq
    test eax, eax
    jz 4f
    lea rdi, [r12 + TOKEN_SIZE]
    mov rax, [rdi]
    cmp byte ptr [rax], '('
    jne 3f
    mov rsi, r13
    call skip_parens             # method receiver
    mov rdi, rax
3:  call emit_token
    jmp 9f
4:  mov rdi, r12
    lea rsi, [rip + .Lgo_decl]
    call match_keyword
    test eax, eax
    jz 9f
    lea rdi, [r12 + TOKEN_SIZE]
    mov rax, [rdi]
    cmp byte ptr [rax], '('
    jne 5f
    mov dword ptr [rip + go_group], 1
    add rdi, TOKEN_SIZE
    cmp rdi, r13
    je 9f
    mov rax, [r13 - TOKEN_SIZE]
    cmp byte ptr [rax], ')'
    jne 5f
    mov dword ptr [rip + go_group], 0
5:  call emit_token
9:  EPILOGUE

parse_rust:
    PROLOGUE
    cmp dword ptr [rip + braces], 0
    jne 9f
    mov rdi, r12
    lea rsi, [rip + .Lpub]
    call token_eq
    test eax, eax
    jz 2f
    add r12, TOKEN_SIZE
    mov rax, [r12]
    cmp byte ptr [rax], '('
    jne 2f
    mov rdi, r12
    mov rsi, r13
    call skip_parens
    mov r12, rax
2:  mov rdi, r12
    lea rsi, [rip + .Lrust_prefix]
    call match_keyword
    test eax, eax
    jz 3f
    add r12, TOKEN_SIZE
    jmp 2b
3:  mov rdi, r12
    lea rsi, [rip + .Lrust_decl]
    call match_keyword
    test eax, eax
    jz 9f
    add r12, TOKEN_SIZE
    mov rdi, r12
    lea rsi, [rip + .Lmut]
    call token_eq
    test eax, eax
    jnz 4f
    mov rdi, r12
    lea rsi, [rip + .Lfn]
    call token_eq
    test eax, eax
    jz 5f
4:  add r12, TOKEN_SIZE         # static mut or const fn
5:  mov rdi, r12
    call emit_token
9:  EPILOGUE

parse_js:
    PROLOGUE
    cmp dword ptr [rip + braces], 0
    jne 9f
1:  mov rdi, r12
    lea rsi, [rip + .Ljs_prefix]
    call match_keyword
    test eax, eax
    jz 2f
    add r12, TOKEN_SIZE
    jmp 1b
2:  mov rdi, r12
    lea rsi, [rip + .Ljs_decl]
    call match_keyword
    test eax, eax
    jz 9f
    lea rdi, [r12 + TOKEN_SIZE]
    mov rax, [rdi]
    cmp byte ptr [rax], '*'
    jne 3f
    add rdi, TOKEN_SIZE
3:  call emit_token
9:  EPILOGUE

# The common C/C++ cases: top-level definitions starting with a type or other
# declaration specifier, excluding prototypes and extern/typedef declarations.
parse_c:
    PROLOGUE
    cmp dword ptr [rip + c_name_len], 0
    jne c_continue
    cmp dword ptr [rip + braces], 0
    jne 9f
    mov rdi, r12
    call token_is_name
    test eax, eax
    jz 9f
    mov rdi, r12
    lea rsi, [rip + .Lc_skip]
    call match_keyword
    test eax, eax
    jnz 9f
    mov rdi, r12
    lea rsi, [rip + .Lextern]
    call token_eq
    test eax, eax
    setnz al
    movzx r8d, al
    lea r9, [r12 + 2 * TOKEN_SIZE]
    # No specifier and name before this point, so e.g. a bare call is not a definition.
    mov r10, [r12 + TOKEN_SIZE]
    cmp byte ptr [r10], '('
    je 9f
1:  cmp r9, r13
    jae 9f
    mov r10, [r9]
    movzx eax, byte ptr [r10]
    cmp eax, '('
    je 4f
    cmp eax, '='
    je 3f
    cmp eax, ';'
    je 2f
    cmp eax, '['
    je 2f
    cmp eax, ','
    je 2f
    cmp eax, '{'
    je 9f
    add r9, TOKEN_SIZE
    jmp 1b
2:  test r8d, r8d
    jnz 9f
3:  lea rdi, [r9 - TOKEN_SIZE]
    lea rsi, [rip + .Lc_nonnames]
    mov r12, rdi
    call match_keyword
    test eax, eax
    jnz 9f
    mov rdi, r12
    call emit_token
    jmp 9f
4:  lea r12, [r9 - TOKEN_SIZE]
    mov rdi, r12
    call token_is_name
    test eax, eax
    jz 9f
    mov rsi, [r12]
    mov rcx, [r12 + 8]
    sub rcx, rsi
    cmp rcx, DECL_NAME_MAX
    ja 9f
    mov [rip + c_name_len], ecx
    mov [rip + c_line], r15d
    mov eax, esi
    sub eax, ebx
    inc eax
    mov [rip + c_col], eax
    mov dword ptr [rip + c_parens], 0
    lea rdi, [rip + c_name]
    rep movsb
    mov r12, r9
c_continue:
    mov ecx, [rip + c_parens]
5:  cmp r12, r13
    jae 8f
    mov rax, [r12]
    add r12, TOKEN_SIZE
    movzx eax, byte ptr [rax]
    cmp eax, '('
    je 6f
    cmp eax, ')'
    je 7f
    test ecx, ecx
    jnz 5b
    cmp eax, ';'
    je 51f
    cmp eax, '='
    je 51f
    cmp eax, '{'
    jne 5b
    lea rdi, [rip + c_name]
    mov esi, [rip + c_name_len]
    mov edx, [rip + c_line]
    mov ecx, [rip + c_col]
    call symbols_emit
51: mov dword ptr [rip + c_name_len], 0
    jmp 9f
6:  inc ecx
    jmp 5b
7:  test ecx, ecx
    jz 5b
    dec ecx
    jmp 5b
8:  mov [rip + c_parens], ecx
9:  EPILOGUE

.section .rodata
.p2align 3
.Lrules:
    .quad parse_asm, parse_c, parse_python, parse_go, parse_rust, parse_js
.Lgrammar_families:
    .quad .Lasm, SYMBOL_ASM, .Lc, SYMBOL_C, .Lcpp, SYMBOL_C, .Lpython, SYMBOL_PYTHON
    .quad .Lgo, SYMBOL_GO, .Lrust, SYMBOL_RUST, .Ljs, SYMBOL_JS, .Lts, SYMBOL_JS, 0
.Lasm: .asciz "Assembly"
.Lc: .asciz "C"
.Lcpp: .asciz "C++"
.Lpython: .asciz "Python"
.Lgo: .asciz "Go"
.Lrust: .asciz "Rust"
.Ljs: .asciz "JavaScript"
.Lts: .asciz "TypeScript"
.p2align 3
.Lpath_families:
    .quad .Lasm_files, SYMBOL_ASM, .Lc_files, SYMBOL_C, .Lpy_files, SYMBOL_PYTHON
    .quad .Lgo_files, SYMBOL_GO, .Lrust_files, SYMBOL_RUST, .Ljs_files, SYMBOL_JS, 0
.Lasm_files: .asciz ".s", ".S", ".asm", ".inc", ".nasm", ""
.Lc_files: .asciz ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".ipp", ".tpp", ".cppm", ".ixx", ""
.Lpy_files: .asciz ".py", ".pyw", ".pyi", "SConstruct", "SConscript", ""
.Lgo_files: .asciz ".go", ""
.Lrust_files: .asciz ".rs", ""
.Ljs_files: .asciz ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".mts", ".cts", ""
.p2align 3
.Lasm_decl: .quad .Lasm_fn, .Lequ, .Lset, .Lequiv, .Lmacro, .Lcomm, .Llcomm, 0
.Lpy_decl: .quad .Ldef, .Lclass, 0
.Lgo_decl: .quad .Lvar, .Lconst, .Ltype, 0
.Lrust_prefix: .quad .Lasync, .Lunsafe, .Lextern, 0
.Lrust_decl: .quad .Lfn, .Lconst, .Lstatic, .Lstruct, .Lenum, .Ltype, .Ltrait, .Lmod, .Lunion, 0
.Ljs_prefix: .quad .Lexport, .Ldefault, .Lasync, .Labstract, 0
.Ljs_decl: .quad .Lfunction, .Lclass, .Lvar, .Llet, .Lconst, .Ltype, .Linterface, .Lenum, 0
.Lc_skip: .quad .Ltypedef, .Lusing, .Lreturn, .Lstatic_assert, .Lc_static_assert, 0
.Lc_nonnames: .quad .Lvoid, .Lint, .Llong, .Lshort, .Lchar, .Lfloat, .Ldouble, .Lbool, .Lunsigned, .Lsigned, 0
.Lno_token: .byte 0
.Lasm_fn: .asciz "FN"
.Lequ: .asciz ".equ"
.Lset: .asciz ".set"
.Lequiv: .asciz ".equiv"
.Lmacro: .asciz ".macro"
.Lcomm: .asciz ".comm"
.Llcomm: .asciz ".lcomm"
.Ldefine: .asciz "define"
.Ldef: .asciz "def"
.Lfn: .asciz "fn"
.Lfunc: .asciz "func"
.Lfunction: .asciz "function"
.Lclass: .asciz "class"
.Lvar: .asciz "var"
.Llet: .asciz "let"
.Lconst: .asciz "const"
.Ltype: .asciz "type"
.Linterface: .asciz "interface"
.Lpub: .asciz "pub"
.Lasync: .asciz "async"
.Lunsafe: .asciz "unsafe"
.Lextern: .asciz "extern"
.Lstatic: .asciz "static"
.Lmut: .asciz "mut"
.Lstruct: .asciz "struct"
.Lenum: .asciz "enum"
.Ltrait: .asciz "trait"
.Lmod: .asciz "mod"
.Lunion: .asciz "union"
.Lexport: .asciz "export"
.Ldefault: .asciz "default"
.Labstract: .asciz "abstract"
.Ltypedef: .asciz "typedef"
.Lusing: .asciz "using"
.Lreturn: .asciz "return"
.Lstatic_assert: .asciz "static_assert"
.Lc_static_assert: .asciz "_Static_assert"
.Lvoid: .asciz "void"
.Lint: .asciz "int"
.Llong: .asciz "long"
.Lshort: .asciz "short"
.Lchar: .asciz "char"
.Lfloat: .asciz "float"
.Ldouble: .asciz "double"
.Lbool: .asciz "bool"
.Lunsigned: .asciz "unsigned"
.Lsigned: .asciz "signed"
