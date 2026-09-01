    .intel_syntax noprefix
    .text

    .globl _photon_v6_pf_hook_load_abi
_photon_v6_pf_hook_load_abi:
    lock inc dword ptr [_photon_v6_pf_hook_inflight]
    .globl _photon_v6_pf_hook_load_counted
_photon_v6_pf_hook_load_counted:
    jmp @photon_v6_pf_hook_load_impl@12
    .globl _photon_v6_pf_hook_load_end
_photon_v6_pf_hook_load_end:

    .globl _photon_v6_pf_hook_surface_abi
_photon_v6_pf_hook_surface_abi:
    lock inc dword ptr [_photon_v6_pf_hook_inflight]
    .globl _photon_v6_pf_hook_surface_counted
_photon_v6_pf_hook_surface_counted:
    jmp @photon_v6_pf_hook_surface_impl@24
    .globl _photon_v6_pf_hook_surface_end
_photon_v6_pf_hook_surface_end:

    .globl _photon_v6_pf_hook_rect_abi
_photon_v6_pf_hook_rect_abi:
    lock inc dword ptr [_photon_v6_pf_hook_inflight]
    .globl _photon_v6_pf_hook_rect_counted
_photon_v6_pf_hook_rect_counted:
    jmp @photon_v6_pf_hook_rect_impl@24
    .globl _photon_v6_pf_hook_rect_end
_photon_v6_pf_hook_rect_end:

    /* Exact ABI mirror of PF Cr6Ti decoder callsite 0x0017F09E. */
    .globl _photon_v6_pf_hook_decode_abi
_photon_v6_pf_hook_decode_abi:
    lock inc dword ptr [_photon_v6_pf_hook_inflight]
    .globl _photon_v6_pf_hook_decode_counted
_photon_v6_pf_hook_decode_counted:
    push ebp
    mov ebp, esp
    sub esp, 16
    mov dword ptr [ebp - 4], ecx

    /* Authenticate/load the sidecar and snapshot the destination before the
       retail Cr6Ti draw mutates it.  The returned token owns both buffers. */
    push dword ptr [ebp + 32]
    push dword ptr [ebp + 28]
    push dword ptr [ebp + 24]
    push dword ptr [ebp + 20]
    push dword ptr [ebp + 16]
    push dword ptr [ebp + 12]
    push dword ptr [ebp + 8]
    push dword ptr [ebp - 4]
    call _photon_v6_pf_decode_prepare
    add esp, 32
    mov dword ptr [ebp - 16], eax

    push dword ptr [ebp + 32]
    push dword ptr [ebp + 28]
    push dword ptr [ebp + 24]
    push dword ptr [ebp + 20]
    push dword ptr [ebp + 16]
    push dword ptr [ebp + 12]
    push dword ptr [ebp + 8]
    mov ecx, dword ptr [ebp - 4]
    call _photon_v6_pf_forward_decode
    add esp, 28
    mov dword ptr [ebp - 8], eax
    mov dword ptr [ebp - 12], edx

    push dword ptr [ebp - 16]
    call _photon_v6_pf_decode_commit
    add esp, 4
    lock dec dword ptr [_photon_v6_pf_hook_inflight]
    mov eax, dword ptr [ebp - 8]
    mov edx, dword ptr [ebp - 12]
    mov esp, ebp
    pop ebp
    ret
    .globl _photon_v6_pf_hook_decode_end
_photon_v6_pf_hook_decode_end:

_photon_v6_pf_forward_decode:
    jmp dword ptr [_photon_v6_pf_real_decode_raw]

    /* Exact ABI mirror of both PF Cr6Ti kind=2 decoder callsites at RVAs
       0x0017ECEC and 0x0017EDD9.  ECX is the decoder, EDX is the immutable
       image metadata, and the caller owns four stack arguments:
       pixel-zero, decoder pitch, left/top, right/bottom. */
    .globl _photon_v6_pf_hook_alt_decode_abi
_photon_v6_pf_hook_alt_decode_abi:
    lock inc dword ptr [_photon_v6_pf_hook_inflight]
    .globl _photon_v6_pf_hook_alt_decode_counted
_photon_v6_pf_hook_alt_decode_counted:
    push ebp
    mov ebp, esp
    sub esp, 24
    mov dword ptr [ebp - 4], ecx
    mov dword ptr [ebp - 8], edx

    push dword ptr [ebp + 20]
    push dword ptr [ebp + 16]
    push dword ptr [ebp + 12]
    push dword ptr [ebp + 8]
    push dword ptr [ebp - 8]
    push dword ptr [ebp - 4]
    call _photon_v6_pf_alt_decode_prepare
    add esp, 24
    mov dword ptr [ebp - 20], eax

    push dword ptr [ebp + 20]
    push dword ptr [ebp + 16]
    push dword ptr [ebp + 12]
    push dword ptr [ebp + 8]
    mov edx, dword ptr [ebp - 8]
    mov ecx, dword ptr [ebp - 4]
    call _photon_v6_pf_forward_alt_decode
    add esp, 16
    mov dword ptr [ebp - 12], eax
    mov dword ptr [ebp - 16], edx

    push dword ptr [ebp - 20]
    call _photon_v6_pf_decode_commit
    add esp, 4
    lock dec dword ptr [_photon_v6_pf_hook_inflight]
    mov eax, dword ptr [ebp - 12]
    mov edx, dword ptr [ebp - 16]
    mov esp, ebp
    pop ebp
    ret
    .globl _photon_v6_pf_hook_alt_decode_end
_photon_v6_pf_hook_alt_decode_end:

_photon_v6_pf_forward_alt_decode:
    jmp dword ptr [_photon_v6_pf_real_alt_decode_raw]

    /* Exact ABI mirror of the independent PF CRip008 kind-3 decoder callsite
       at RVA 0x00179810.  ECX carries the compressed payload and EDX carries
       its byte count.  The caller owns eight stack arguments and performs
       add esp,0x20 after this returns. */
    .globl _photon_v6_pf_hook_crip008_decode_abi
_photon_v6_pf_hook_crip008_decode_abi:
    lock inc dword ptr [_photon_v6_pf_hook_inflight]
    .globl _photon_v6_pf_hook_crip008_decode_counted
_photon_v6_pf_hook_crip008_decode_counted:
    push ebp
    mov ebp, esp
    sub esp, 24
    mov dword ptr [ebp - 4], ecx
    mov dword ptr [ebp - 8], edx

    push dword ptr [ebp + 36]
    push dword ptr [ebp + 32]
    push dword ptr [ebp + 28]
    push dword ptr [ebp + 24]
    push dword ptr [ebp + 20]
    push dword ptr [ebp + 16]
    push dword ptr [ebp + 12]
    push dword ptr [ebp + 8]
    push dword ptr [ebp - 8]
    push dword ptr [ebp - 4]
    call _photon_v6_pf_crip008_decode_prepare
    add esp, 40
    mov dword ptr [ebp - 20], eax

    push dword ptr [ebp + 36]
    push dword ptr [ebp + 32]
    push dword ptr [ebp + 28]
    push dword ptr [ebp + 24]
    push dword ptr [ebp + 20]
    push dword ptr [ebp + 16]
    push dword ptr [ebp + 12]
    push dword ptr [ebp + 8]
    mov edx, dword ptr [ebp - 8]
    mov ecx, dword ptr [ebp - 4]
    call _photon_v6_pf_forward_crip008_decode
    add esp, 32
    mov dword ptr [ebp - 12], eax
    mov dword ptr [ebp - 16], edx

    push dword ptr [ebp - 20]
    call _photon_v6_pf_crip008_decode_commit
    add esp, 4
    lock dec dword ptr [_photon_v6_pf_hook_inflight]
    mov eax, dword ptr [ebp - 12]
    mov edx, dword ptr [ebp - 16]
    mov esp, ebp
    pop ebp
    ret
    .globl _photon_v6_pf_hook_crip008_decode_end
_photon_v6_pf_hook_crip008_decode_end:

_photon_v6_pf_forward_crip008_decode:
    jmp dword ptr [_photon_v6_pf_real_crip008_decode_raw]

    /* Exact ABI mirror of both PF CRip008 unscaled/direct decoder callsites
       at RVAs 0x001775D8 and 0x001776B1.  ECX carries the compressed payload
       and EDX carries its byte count.  The caller owns five stack arguments:
       flags-table, pixel-zero,
       decoder-pitch, target-left/top and target-right/bottom. */
    .globl _photon_v6_pf_hook_crip008_direct_decode_abi
_photon_v6_pf_hook_crip008_direct_decode_abi:
    lock inc dword ptr [_photon_v6_pf_hook_inflight]
    .globl _photon_v6_pf_hook_crip008_direct_decode_counted
_photon_v6_pf_hook_crip008_direct_decode_counted:
    push ebp
    mov ebp, esp
    sub esp, 24
    mov dword ptr [ebp - 4], ecx
    mov dword ptr [ebp - 8], edx

    push dword ptr [ebp + 24]
    push dword ptr [ebp + 20]
    push dword ptr [ebp + 16]
    push dword ptr [ebp + 12]
    push dword ptr [ebp + 8]
    push dword ptr [ebp - 8]
    push dword ptr [ebp - 4]
    call _photon_v6_pf_crip008_direct_decode_prepare
    add esp, 28
    mov dword ptr [ebp - 20], eax

    push dword ptr [ebp + 24]
    push dword ptr [ebp + 20]
    push dword ptr [ebp + 16]
    push dword ptr [ebp + 12]
    push dword ptr [ebp + 8]
    mov edx, dword ptr [ebp - 8]
    mov ecx, dword ptr [ebp - 4]
    call _photon_v6_pf_forward_crip008_direct_decode
    add esp, 20
    mov dword ptr [ebp - 12], eax
    mov dword ptr [ebp - 16], edx

    push dword ptr [ebp - 20]
    call _photon_v6_pf_crip008_decode_commit
    add esp, 4
    lock dec dword ptr [_photon_v6_pf_hook_inflight]
    mov eax, dword ptr [ebp - 12]
    mov edx, dword ptr [ebp - 16]
    mov esp, ebp
    pop ebp
    ret
    .globl _photon_v6_pf_hook_crip008_direct_decode_end
_photon_v6_pf_hook_crip008_direct_decode_end:

_photon_v6_pf_forward_crip008_direct_decode:
    jmp dword ptr [_photon_v6_pf_real_crip008_direct_decode_raw]
