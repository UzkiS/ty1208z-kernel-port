#!/usr/bin/env python3
"""Exercise actual firmware association-body decoding and allocation rollback."""
import argparse
from pathlib import Path
import subprocess
import tempfile

from make_wifi_port_patch import function_spans

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
args = parser.parse_args()
source = (args.source / 'rdawlan/wland_cfg80211.c').read_text()
spans = function_spans(source, 'wland_get_assoc_ies')
assert len(spans) == 1
start, _, end = spans[0]
body = source[start:end]
code = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef int32_t s32;
#define WLAND_ASSOC_INFO_MAX 256
#define WID_ASSOC_REQ_INFO 1
#define WID_ASSOC_RES_INFO 2
#define GFP_KERNEL 0
#define WLAND_DBG(...) ((void)0)
struct wland_cfg80211_connect_info { u8 *req_ie, *resp_ie; u16 req_ie_len, resp_ie_len; };
struct vif { struct wland_cfg80211_connect_info conn_info; };
struct wland_if { struct vif *vif; };
struct wland_cfg80211_info { u8 extra_buf[256]; };
/* Capability's low byte 0x31 is not a length. Both bodies contain a full
 * RSN IE with zero replay-counter capability, as sent by this firmware.
 */
static const u8 rsn[] = {48,20,1,0,0,15,172,4,1,0,0,15,172,4,1,0,0,15,172,2,0,0};
static u8 request[256], response[256];
static int request_size, response_size, calls, fail_alloc, live;
static void *kmemdup(const void *p, size_t size, int flags) {
    (void)flags;
    if (++calls == fail_alloc) return NULL;
    void *copy = malloc(size); assert(copy); memcpy(copy,p,size); live++; return copy;
}
static void kfree(void *p) { if (p) { live--; free(p); } }
static int wland_fil_get_cmd_data(struct wland_if *ifp, int wid, void *out, int max) {
    (void)ifp; int size = wid == 1 ? request_size : response_size;
    if (size < 0) return size;
    assert(size <= max); memcpy(out, wid == 1 ? request : response, size); return size;
}
'''
code += body + r'''
static void setup(void) {
    request[0]=response[0]=0x31;
    request[1]=response[1]=0x84;
    request[2]=1; request[3]=0;
    memset(response+2,0,4);
    memcpy(request+4,rsn,sizeof(rsn)); memcpy(response+6,rsn,sizeof(rsn));
    request_size=4+sizeof(rsn); response_size=6+sizeof(rsn); calls=0; fail_alloc=0;
}
int main(void) {
    struct vif vif={0}; struct wland_if ifp={&vif}; struct wland_cfg80211_info cfg={0};
    struct wland_cfg80211_connect_info *info=&vif.conn_info;
    setup(); assert(wland_get_assoc_ies(&cfg,&ifp)==0);
    assert(info->req_ie_len==sizeof(rsn) && info->resp_ie_len==sizeof(rsn));
    assert(!memcmp(info->req_ie,rsn,sizeof(rsn)) && !memcmp(info->resp_ie,rsn,sizeof(rsn)));
    u8 *old_req=info->req_ie,*old_resp=info->resp_ie;
    for (int which=1;which<=2;which++) {
        setup();fail_alloc=which;assert(wland_get_assoc_ies(&cfg,&ifp)==-ENOMEM);
        assert(info->req_ie==old_req && info->resp_ie==old_resp && live==2);
    }
    for (int size=0;size<4;size++) {
        setup();request_size=size;assert(wland_get_assoc_ies(&cfg,&ifp)==-EBADMSG);assert(live==2);
    }
    for (int size=0;size<6;size++) {
        setup();response_size=size;assert(wland_get_assoc_ies(&cfg,&ifp)==-EBADMSG);assert(live==2);
    }
    setup();request_size=-EIO;assert(wland_get_assoc_ies(&cfg,&ifp)==-EIO);assert(live==2);
    setup();response_size=-ETIMEDOUT;assert(wland_get_assoc_ies(&cfg,&ifp)==-ETIMEDOUT);assert(live==2);
    setup();request_size=4;response_size=6;assert(wland_get_assoc_ies(&cfg,&ifp)==0);
    assert(!info->req_ie && !info->resp_ie && !info->req_ie_len && !info->resp_ie_len && live==0);
    puts("RDA_ASSOC_FRAME_BODY_AND_ROLLBACK_PASS");
}
'''
with tempfile.TemporaryDirectory(prefix='rda-assoc-ies-') as directory:
    path = Path(directory)
    (path / 'test.c').write_text(code)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-g',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-no-pie',
                    path / 'test.c', '-o', path / 'test'], check=True)
    subprocess.run([path / 'test'], check=True)
