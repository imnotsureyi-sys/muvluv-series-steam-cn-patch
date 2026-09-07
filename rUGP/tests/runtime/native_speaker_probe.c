#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include "photon_speaker_policy.h"

static wchar_t *read_text(FILE *f) {
    uint32_t n;
    if (fread(&n, 4, 1, f) != 1 || n > 4096) exit(21);
    wchar_t *s = calloc(n + 1, sizeof(wchar_t));
    if (!s || fread(s, 2, n, f) != n) exit(22);
    return s;
}
static int lookup(const wchar_t *name, wchar_t **aliases, int count, PhotonSpeakerMatch fn, int patched) {
    for (int i=0;i<count;i++)
        if (patched ? photon_speaker_match(name,aliases[i],fn) : fn(name,aliases[i])) return i;
    return -1;
}
int main(int argc,char **argv) {
    if(argc!=3)return 20;
    FILE *f=fopen(argv[1],"rb");
    void *code=VirtualAlloc(NULL,4096,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    if(!f||!code||fread(code,1,217,f)!=217)return 23;
    fclose(f);DWORD old;
    if(!VirtualProtect(code,4096,PAGE_EXECUTE_READ,&old))return 24;
    FlushInstructionCache(GetCurrentProcess(),code,217);
    PhotonSpeakerMatch fn=(PhotonSpeakerMatch)code;
    f=fopen(argv[2],"rb");uint32_t count,pairs;
    if(!f||fread(&count,4,1,f)!=1||count>4096)return 25;
    wchar_t **aliases=calloc(count,sizeof(*aliases));
    for(uint32_t i=0;i<count;i++)aliases[i]=read_text(f);
    if(fread(&pairs,4,1,f)!=1)return 26;
    uint32_t failed=0,recovered=0,source_unchanged=0;
    for(uint32_t i=0;i<pairs;i++) {
        wchar_t *source=read_text(f),*target=read_text(f);
        int expected=lookup(source,aliases,count,fn,0);
        int before=lookup(target,aliases,count,fn,0);
        int after=lookup(target,aliases,count,fn,1);
        if(lookup(source,aliases,count,fn,1)!=expected)failed++;
        else source_unchanged++;
        /* Also require expected == -1 to remain unmatched: no false colour. */
        if(after!=expected){failed++;printf("mismatch pair %u expected %d got %d\n",i,expected,after);}
        if(expected>=0 && before!=expected && after==expected)recovered++;
        free(source);free(target);
    }
    printf("{\"unique_speaker_pairs\":%u,\"recovered_pairs\":%u,\"source_unchanged\":%u,\"failures\":%u}\n",pairs,recovered,source_unchanged,failed);
    fclose(f);for(uint32_t i=0;i<count;i++)free(aliases[i]);free(aliases);
    return failed?1:0;
}
