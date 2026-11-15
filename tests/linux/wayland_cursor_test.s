# Exercise production cursor request ordering and native-motion recovery.
.include "rhun.inc"
.section .rodata
wc_ok: .ascii "ok Wayland cursor role, refresh and shape caching\n"
.equ WC_OK_LEN, . - wc_ok
.data
wc_stage: .long 1
.text
wc_fail:
    mov edi, [rip + wc_stage]
    SYS SYS_exit_group
.globl main
main:
    mov dword ptr [rip + wl_cursor_wire_compositor], 0x400
    mov dword ptr [rip + wl_cursor_wire_pointer], 0x401
    mov dword ptr [rip + wl_wire_next_id], 0x500
    # Initial painting must not create a cursor without pointer-enter authority.
    mov edi, CUR_TEXT
    call wl_set_cursor
    cmp dword ptr [rip + wl_paste_wire_output_len], 0
    jne wc_fail
    mov dword ptr [rip + wl_cursor_wire_enter_serial], 77
    mov dword ptr [rip + g_dpi_scale], 0x3f800000
    mov dword ptr [rip + wl_cursor_wire_cur_bs], 1
    mov dword ptr [rip + wl_cursor_wire_cur_ids + CUR_TEXT*4], 0x600
    mov dword ptr [rip + wl_cursor_wire_cur_hx + CUR_TEXT*4], 5
    mov dword ptr [rip + wl_cursor_wire_cur_hy + CUR_TEXT*4], 7
    mov edi, CUR_TEXT
    call wl_set_cursor
    cmp dword ptr [rip + wl_paste_wire_output_len], 100
    jne wc_fail
    lea rbx, [rip + wl_ime_wire_output]
    cmp dword ptr [rbx], 0x400
    jne wc_fail
    cmp dword ptr [rbx + 4], (12 << 16) | 0
    jne wc_fail
    cmp dword ptr [rbx + 8], 0x500
    jne wc_fail
    # Cursor role must precede buffer attach and first commit.
    cmp dword ptr [rbx + 12], 0x401
    jne wc_fail
    cmp dword ptr [rbx + 16], (24 << 16) | 0
    jne wc_fail
    cmp dword ptr [rbx + 20], 77
    jne wc_fail
    cmp dword ptr [rbx + 24], 0x500
    jne wc_fail
    cmp dword ptr [rbx + 28], 5
    jne wc_fail
    cmp dword ptr [rbx + 32], 7
    jne wc_fail
    cmp dword ptr [rbx + 52], (20 << 16) | 1
    jne wc_fail
    cmp dword ptr [rbx + 56], 0x600
    jne wc_fail
    cmp dword ptr [rbx + 96], (8 << 16) | 6
    jne wc_fail
    # Frames with no native motion keep the cached shape.
    inc dword ptr [rip + wc_stage]
    mov dword ptr [rip + wl_paste_wire_output_len], 0
    mov edi, CUR_TEXT
    call wl_set_cursor
    cmp dword ptr [rip + wl_paste_wire_output_len], 0
    jne wc_fail
    # Native motion must restore an unchanged image with full damage + commit.
    inc dword ptr [rip + wc_stage]
    call wl_cursor_refresh
    mov edi, CUR_TEXT
    call wl_set_cursor
    cmp dword ptr [rip + wl_paste_wire_output_len], 88
    jne wc_fail
    cmp dword ptr [rbx], 0x401
    jne wc_fail
    cmp dword ptr [rbx + 4], (24 << 16) | 0
    jne wc_fail
    cmp dword ptr [rbx + 76], 4096
    jne wc_fail
    cmp dword ptr [rbx + 84], (8 << 16) | 6
    jne wc_fail
    mov edi, 1
    lea rsi, [rip + wc_ok]
    mov edx, WC_OK_LEN
    call write_all
    xor edi, edi
    call sys_exit
