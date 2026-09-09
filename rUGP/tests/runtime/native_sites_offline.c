/* Read-only game EXE inspection. Sections are copied as non-executable data;
 * neither its entrypoint nor imports/TLS are invoked. No hooks are installed. */
#if defined(PHOTON_BUILD_PM)
#include "../../runtime/src/photon_v6_pm_native_runtime.c"
#else
#include "../../runtime/src/photon_v6_pf_native_runtime.c"
#endif
#include <stdio.h>
int selector_sites_offline(BYTE *image);

uint32_t abi_n, abi_seen[10], abi_out[6], abi_sp, abi_after;
void *abi_target;
void abi_stub(void);
void abi_call(void);
/* A synthetic decoder observes the original register/stack ABI and returns
 * distinctive EAX/EDX values. It reads no game resources. */
__asm__(
    ".intel_syntax noprefix\n"
    "_abi_stub:\n"
    "mov [_abi_seen], ecx\n mov [_abi_seen+4], edx\n xor ecx, ecx\n"
    "1:\n cmp ecx, [_abi_n]\n jae 2f\n mov eax, [esp+ecx*4+4]\n"
    "mov [_abi_seen+ecx*4+8], eax\n inc ecx\n jmp 1b\n"
    "2:\n mov eax, 0x12345678\n mov edx, 0x76543210\n ret\n"
    "_abi_call:\n push ebp\n push ebx\n push esi\n push edi\n"
    "mov [_abi_sp], esp\n mov ecx, [_abi_n]\n"
    "3:\n test ecx, ecx\n jz 4f\n mov eax, ecx\n add eax, 0x100\n push eax\n dec ecx\n jmp 3b\n"
    "4:\n mov ebx, 0x22223333\n mov esi, 0x33334444\n mov edi, 0x44445555\n mov ebp, 0x55556666\n"
    "mov ecx, 0x11112222\n mov edx, 0x66667777\n call dword ptr [_abi_target]\n"
    "mov [_abi_out], eax\n mov [_abi_out+4], edx\n mov [_abi_out+8], ebx\n"
    "mov [_abi_out+12], esi\n mov [_abi_out+16], edi\n mov [_abi_out+20], ebp\n"
    "mov eax, esp\n mov [_abi_after], eax\n mov esp, [_abi_sp]\n"
    "pop edi\n pop esi\n pop ebx\n pop ebp\n ret\n"
    ".att_syntax prefix\n");

static unsigned check_abi(void) {
    void *targets[4]={photon_v6_pf_hook_decode_abi,photon_v6_pf_hook_alt_decode_abi,
        photon_v6_pf_hook_crip008_decode_abi,photon_v6_pf_hook_crip008_direct_decode_abi};
    unsigned counts[4]={7,4,8,5}, passed=0;
    photon_v6_pf_real_decode_raw=abi_stub; photon_v6_pf_real_alt_decode_raw=abi_stub;
    photon_v6_pf_real_crip008_decode_raw=abi_stub; photon_v6_pf_real_crip008_direct_decode_raw=abi_stub;
    for (unsigned state=0;state<2;++state)
    for (unsigned i=0;i<4;++i) {
        initialized=(LONG)state; native_semantic_gate_disabled=(LONG)state;
        photon_v6_pf_hook_inflight=0;
        memset(abi_seen,0,sizeof(abi_seen)); memset(abi_out,0,sizeof(abi_out));
        abi_target=targets[i]; abi_n=counts[i]; abi_call();
        int good=abi_seen[0]==0x11112222 && (i==0 || abi_seen[1]==0x66667777) &&
            abi_out[0]==0x12345678 && abi_out[1]==0x76543210 && abi_out[2]==0x22223333 &&
            abi_out[3]==0x33334444 && abi_out[4]==0x44445555 && abi_out[5]==0x55556666 &&
            abi_after+abi_n*4==abi_sp && photon_v6_pf_hook_inflight==0;
        for (unsigned j=0;j<abi_n;++j) if (abi_seen[2+j]!=0x101+j) good=0;
        passed+=(unsigned)good;
    }
    return passed;
}

int wmain(int argc,wchar_t **argv) {
    if (argc!=2) return 2;
    FILE *f=_wfopen(argv[1],L"rb");
    if (!f) return 3;
    fseek(f,0,SEEK_END); long length=ftell(f); rewind(f);
    if (length<4096 || length>128*1024*1024) return 3;
    BYTE *raw=HeapAlloc(GetProcessHeap(),0,(size_t)length);
    if (!raw || fread(raw,1,(size_t)length,f)!=(size_t)length) return 3;
    fclose(f);
    IMAGE_DOS_HEADER *dos=(IMAGE_DOS_HEADER *)raw;
    if (dos->e_magic!=IMAGE_DOS_SIGNATURE || dos->e_lfanew<0 ||
        (size_t)dos->e_lfanew+sizeof(IMAGE_NT_HEADERS32)>(size_t)length) return 4;
    IMAGE_NT_HEADERS32 *nt=(IMAGE_NT_HEADERS32 *)(raw+dos->e_lfanew);
    if (nt->Signature!=IMAGE_NT_SIGNATURE || nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC ||
        nt->OptionalHeader.SizeOfImage!=PF_SIZE_OF_IMAGE || nt->OptionalHeader.SizeOfHeaders>(DWORD)length ||
        nt->OptionalHeader.SizeOfHeaders>nt->OptionalHeader.SizeOfImage) return 4;
    main_base=VirtualAlloc((void *)(uintptr_t)nt->OptionalHeader.ImageBase,
        nt->OptionalHeader.SizeOfImage,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if (!main_base || (uintptr_t)main_base!=nt->OptionalHeader.ImageBase) return 5;
    memcpy(main_base,raw,nt->OptionalHeader.SizeOfHeaders);
    IMAGE_SECTION_HEADER *sections=IMAGE_FIRST_SECTION(nt);
    if ((BYTE *)(sections+nt->FileHeader.NumberOfSections)>raw+length) return 4;
    for (unsigned i=0;i<nt->FileHeader.NumberOfSections;++i) {
        IMAGE_SECTION_HEADER *s=sections+i;
        if ((uint64_t)s->PointerToRawData+s->SizeOfRawData>(uint64_t)length ||
            (uint64_t)s->VirtualAddress+s->SizeOfRawData>nt->OptionalHeader.SizeOfImage) return 4;
        memcpy(main_base+s->VirtualAddress,raw+s->PointerToRawData,s->SizeOfRawData);
    }
    int image_ok=verify_image(), sites_ok=prepare_hooks();
    uint32_t sites[9]={PF_CR6_LOAD_SLOT_RVA,PF_CR6_SURFACE_SLOT_RVA,PF_CR6_RECT_SLOT_RVA,
        PF_CR6_DECODE_CALLSITE_RVA,PF_CR6_ALT_DECODE_CALLSITE0_RVA,PF_CR6_ALT_DECODE_CALLSITE1_RVA,
        PHOTON_NATIVE_CRIP008_DECODE_CALLSITE_RVA,PHOTON_NATIVE_CRIP008_DIRECT_DECODE_CALLSITE0_RVA,
        PHOTON_NATIVE_CRIP008_DIRECT_DECODE_CALLSITE1_RVA};
    unsigned rejected=0;
    puts("{\"sites\":[");
    for (unsigned i=0;i<9;++i) {
        main_base[sites[i]]^=1;
        int deny=!prepare_hooks();
        main_base[sites[i]]^=1;
        rejected+=(unsigned)deny;
        printf("%s{\"rva\":\"%08X\",\"one_byte_change_rejected\":%s}",i?",\n":"",sites[i],deny?"true":"false");
    }
    int restored=verify_image()&&prepare_hooks();
    unsigned abi_passed=check_abi();
    int selector_count=selector_sites_offline(main_base);
    int good=image_ok&&sites_ok&&rejected==9&&restored&&abi_passed==8&&
        selector_count==PHOTON_NATIVE_SELECTOR_EXPECTED_HOOK_COUNT;
    printf("\n],\"image_signature_passed\":%s,\"sites_passed\":%s,\"negative_sites_rejected\":%u,\"restored_data_passed\":%s,\"abi_passthrough_cases_passed\":%u,\"selector_positive_and_negative_sites_passed\":%d,\"passed\":%s,\"game_started\":false,\"game_code_executed\":false,\"hooks_installed\":false}\n",
        image_ok?"true":"false",sites_ok?"true":"false",rejected,restored?"true":"false",abi_passed,selector_count,good?"true":"false");
    VirtualFree(main_base,0,MEM_RELEASE); HeapFree(GetProcessHeap(),0,raw);
    return good?0:1;
}
