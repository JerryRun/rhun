# WSLg's text-input-v1, optional: compositors without it retain the physical key path.
# Included in wayland.s to share its bounded wire writer and object ids.
.text
wl_ime_sync:
    PROLOGUE 16
    cmp dword ptr [rip + id_ti], 0
    jne .Lims_done
    call fcitx_active
    test eax, eax
    jz .Lims_native
    cmp dword ptr [rip + ime_requested], 0
    je .Lims_done
    mov dword ptr [rip + ime_requested], 0
    mov dword ptr [rip + wl_ime_entered], 0
    MSG [rip + wl_ime_id], 1
    ARG [rip + id_seat]
    END
    jmp .Lims_done
.Lims_native:
    cmp dword ptr [rip + id_text_manager], 0
    je .Lims_done
    cmp dword ptr [rip + id_surface], 0
    je .Lims_done
    cmp dword ptr [rip + id_seat], 0
    je .Lims_done
    cmp dword ptr [rip + wl_ime_id], 0
    jne 1f
    call wl_new_id
    mov [rip + wl_ime_id], eax
    MSG [rip + id_text_manager], 0
    ARG [rip + wl_ime_id]
    END
1:  xor r12d, r12d
    cmp dword ptr [rip + g_win_focused], 0
    je 2f
    mov eax, [rip + g_focus]
    cmp eax, FOCUS_EDITOR
    je 11f
    cmp eax, FOCUS_TERMINAL
    je 11f
    call focused_field
    test rax, rax
    jz 2f
11: mov r12d, 1
2:  cmp r12d, [rip + ime_requested]
    je 4f
    mov [rip + ime_requested], r12d
    test r12d, r12d
    jz 3f
    MSG [rip + wl_ime_id], 0  # activate(seat, surface)
    ARG [rip + id_seat]
    ARG [rip + id_surface]
    END
    mov dword ptr [rip + ime_focus], -1
    mov dword ptr [rip + ime_rect + 8], -1
    jmp 4f
3:  MSG [rip + wl_ime_id], 1  # deactivate(seat)
    ARG [rip + id_seat]
    END
    mov dword ptr [rip + wl_ime_entered], 0
    call ime_clear
    jmp .Lims_done
4:  test r12d, r12d
    jz .Lims_done
    call ime_target_identity
    mov r14, rax
    mov eax, [rip + g_focus]
    cmp eax, [rip + ime_focus]
.Lime_focus_compare:
    jne .Lime_target_changed
    cmp r14, [rip + ime_target]
    je 5f
.Lime_target_changed:
    mov [rip + ime_focus], eax
    mov [rip + ime_target], r14
    mov dword ptr [rip + ime_rect + 8], -1
    call ime_clear
    MSG [rip + wl_ime_id], 4  # reset: composition belongs to one focused target
    END
    xor r12d, r12d
    xor r13d, r13d
    cmp dword ptr [rip + g_focus], FOCUS_TERMINAL
    jne 41f
    mov r13d, 12              # content_purpose.terminal
41: MSG [rip + wl_ime_id], 6  # set_content_type(hint, purpose)
    ARG r12d
    ARG r13d
    END
    MSG [rip + wl_ime_id], 5  # empty surrounding text: never expose passwords
    lea rdi, [rip + .Lime_empty]
    call wl_put_str
    ARG 0
    ARG 0
    END
    call wl_ime_commit_state
    mov eax, [rip + ime_serial]
    mov [rip + ime_floor], eax
5:  cmp dword ptr [rip + g_ime_valid], 0
    je .Lims_done
    # Pixel coordinates are converted to surface-local coordinates, including fractional scale.
    mov eax, [rip + g_ime_x]
    mov [rsp], eax
    mov eax, [rip + g_ime_y]
    mov [rsp + 4], eax
    mov eax, [rip + g_ime_h]
    mov [rsp + 8], eax
    lea rbx, [rip + ime_rect]
    mov rdi, rbx
    mov rsi, rsp
    mov edx, 12
    call memeq
    test eax, eax
    jnz .Lims_done
    mov rdi, rbx
    mov rsi, rsp
    mov edx, 12
    call memcpy
    mov ecx, [rip + scale120]
    test ecx, ecx
    jnz 6f
    mov ecx, [rip + int_scale]
    imul ecx, ecx, 120
6:  test ecx, ecx
    jnz 61f
    mov ecx, 120
61: mov r13d, ecx
    xor ebx, ebx
7:  mov eax, [rsp + rbx*4]
    imul eax, eax, 120
    cdq
    idiv r13d
    mov [rsp + rbx*4], eax
    inc ebx
    cmp ebx, 3
    jb 7b
    MSG [rip + wl_ime_id], 7  # set_cursor_rectangle
    ARG [rsp]
    ARG [rsp + 4]
    ARG 1
    ARG [rsp + 8]
    END
    call wl_ime_commit_state
.Lims_done:
    EPILOGUE

wl_ime_commit_state:
    sub rsp, 8
    inc dword ptr [rip + ime_serial]
    MSG [rip + wl_ime_id], 9
    ARG [rip + ime_serial]
    END
    add rsp, 8
    ret

# wl_ime_event(opcode, bytes, length): bounds-check strings before sending UTF-8 to the app.
FN wl_ime_event
    PROLOGUE
    mov ebx, edi
    mov r12, rsi
    mov r13, rdx
    call fcitx_active
    test eax, eax
    jnz .Lime_event_done
    test ebx, ebx
    jne 1f
    cmp r13, 4
    jne .Lime_event_done
    mov dword ptr [rip + wl_ime_entered], 1
    jmp .Lime_event_done
1:  cmp ebx, 1
    jne 2f
    mov dword ptr [rip + wl_ime_entered], 0
    call ime_clear
    jmp .Lime_event_done
2:  cmp dword ptr [rip + wl_ime_entered], 0
    je .Lime_event_done
    cmp ebx, 10               # keysym: Enter, Backspace, arrows forwarded by IME
    je .Lime_keysym
    cmp ebx, 4                # preedit_string
    je 3f
    cmp ebx, 7                # commit_string
    jne .Lime_event_done
3:  cmp r13, 8
    jb .Lime_event_done
    mov eax, [r12]
    sub eax, [rip + ime_floor]
    js .Lime_event_done
    mov r14d, [r12 + 4]       # string size includes NUL
    test r14d, r14d
    jz .Lime_event_done
    cmp r14d, 4097
    ja .Lime_event_done
    lea rax, [r14 + 8]
    cmp rax, r13
    ja .Lime_event_done
    cmp byte ptr [r12 + r14 + 7], 0
    jne .Lime_event_done
    cmp ebx, 4
    jne 4f
    lea rdi, [r12 + 8]
    lea rsi, [r14 - 1]
    call ime_set_preedit
    jmp .Lime_event_done
4:  call ime_clear
    lea rdi, [r12 + 8]
    lea rsi, [r14 - 1]
    call app_on_text
    jmp .Lime_event_done
.Lime_keysym:
    cmp r13, 20
    jne .Lime_event_done
    cmp dword ptr [r12 + 12], 1
    jne .Lime_event_done
    mov eax, [r12]
    sub eax, [rip + ime_floor]
    js .Lime_event_done
    mov edi, [r12 + 8]
    call keysym_to_unicode
    mov esi, eax
    mov edi, [r12 + 8]
    xor edx, edx
    call app_on_key
.Lime_event_done:
    EPILOGUE
.section .rodata
.Lime_empty: .asciz ""
.text
