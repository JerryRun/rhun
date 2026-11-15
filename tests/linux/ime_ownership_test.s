# Native IME ownership while the private helper starts, runs and stops.
# Exercise production Wayland v1/v3 writers without a compositor or system changes.
.include "rhun.inc"
.bss
io_stage: .long 0
.text
FN main
    PROLOGUE
    call keys_init
    call cmd_new_file
    mov dword ptr [rip + g_focus], FOCUS_EDITOR
    mov dword ptr [rip + g_win_focused], 1
    mov dword ptr [rip + wl_ime_id], 0x300
    mov dword ptr [rip + wl_wire_seat], 0x301
    mov dword ptr [rip + wl_ime_wire_surface], 0x302
    mov dword ptr [rip + wl_ime_wire_manager], 0x303
    mov dword ptr [rip + wl_ime_wire_requested], 1
    mov dword ptr [rip + wl_ime_entered], 1
    mov dword ptr [rip + fcitx_wire_pid], 1
    mov dword ptr [rip + fcitx_wire_ready], 0
    # Startup already owns suppression, even before the helper reports ready.
    mov dword ptr [rip + io_stage], 1
    call fcitx_active
    test eax, eax
    jnz io_fail
    call fcitx_owns_input
    cmp eax, 1
    jne io_fail
    call wl_ime_sync
    cmp dword ptr [rip + wl_paste_wire_output_len], 32
    jne io_fail
    lea rbx, [rip + wl_ime_wire_output]
    cmp dword ptr [rbx], 0x300
    jne io_fail
    cmp dword ptr [rbx + 4], (8 << 16) | 3   # hide panel
    jne io_fail
    cmp dword ptr [rbx + 12], (12 << 16) | 1 # deactivate
    jne io_fail
    cmp dword ptr [rbx + 16], 0x301
    jne io_fail
    cmp dword ptr [rbx + 24], (12 << 16) | 9 # commit state
    jne io_fail
    cmp dword ptr [rip + wl_ime_entered], 0
    jne io_fail
    # No native activation during startup or English mode, and no repeated wire writes.
    mov dword ptr [rip + io_stage], 2
    call wl_ime_sync
    cmp dword ptr [rip + wl_paste_wire_output_len], 32
    jne io_fail
    mov dword ptr [rip + fcitx_wire_ready], 1
    call wl_ime_sync
    cmp dword ptr [rip + wl_paste_wire_output_len], 32
    jne io_fail
    # A stale native commit cannot type into the private destination.
    mov dword ptr [rip + wl_ime_entered], 1
    mov edi, 7
    lea rsi, [rip + io_v1_commit]
    mov edx, 16
    call wl_ime_event
    mov rdi, [rip + g_doc]
    call doc_len
    test rax, rax
    jnz io_fail
    # Disable/failure returns ownership to native input.
    mov dword ptr [rip + io_stage], 3
    mov dword ptr [rip + fcitx_wire_pid], 0
    mov dword ptr [rip + fcitx_wire_ready], 0
    mov dword ptr [rip + wl_paste_wire_output_len], 0
    call wl_ime_sync
    cmp dword ptr [rip + wl_ime_wire_requested], 1
    jne io_fail
    cmp dword ptr [rbx + 4], (16 << 16) | 0 # activate(seat, surface)
    jne io_fail
    # v3 disables and commits immediately, preserving the private preedit.
    mov dword ptr [rip + io_stage], 4
    mov dword ptr [rip + fcitx_wire_pid], 1
    mov dword ptr [rip + wl_ime_wire_ti], 0x304
    mov dword ptr [rip + wl_ime_wire_ti_on], 1
    mov dword ptr [rip + wl_ime_wire_ti_entered], 1
    mov dword ptr [rip + wl_paste_wire_output_len], 0
    lea rdi, [rip + io_preedit]
    mov esi, 3
    call ime_set_preedit
    call wl_ti_cursor
    cmp dword ptr [rip + wl_ime_wire_ti_on], 0
    jne io_fail
    cmp dword ptr [rip + wl_paste_wire_output_len], 16
    jne io_fail
    cmp dword ptr [rbx + 4], (8 << 16) | 2 # disable
    jne io_fail
    cmp dword ptr [rbx + 12], (8 << 16) | 7 # commit
    jne io_fail
    call ime_has_preedit
    cmp rax, 3
    jne io_fail
    mov edi, 3
    lea rsi, [rip + io_v3_commit]
    mov edx, 8
    call wl_ti_event
    mov edi, 5
    xor esi, esi
    xor edx, edx
    call wl_ti_event
    mov rdi, [rip + g_doc]
    call doc_len
    test rax, rax
    jnz io_fail
    call ime_has_preedit
    cmp rax, 3
    jne io_fail
    # v3 can re-enable after failure or an explicit setting change.
    mov dword ptr [rip + io_stage], 5
    mov dword ptr [rip + fcitx_wire_pid], 0
    mov dword ptr [rip + wl_paste_wire_output_len], 0
    call wl_ti_cursor
    cmp dword ptr [rip + wl_ime_wire_ti_on], 1
    jne io_fail
    cmp dword ptr [rbx + 4], (8 << 16) | 1 # enable
    jne io_fail
    mov edi, 1
    lea rsi, [rip + io_ok]
    mov edx, OFFSET IO_OK_LEN
    call write_all
    xor eax, eax
    EPILOGUE
io_fail:
    mov eax, [rip + io_stage]
    EPILOGUE
.section .rodata
io_preedit: .ascii "pin"
io_v1_commit: .long 0, 4
    .asciz "bad"
    .long 0
io_v3_commit: .long 4
    .asciz "bad"
io_ok: .ascii "ok native IME startup, English ownership, stale events and restoration\n"
.equ IO_OK_LEN, . - io_ok
