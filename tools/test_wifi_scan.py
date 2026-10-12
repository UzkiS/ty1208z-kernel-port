#!/usr/bin/env python3
"""Sanitize actual directed-scan dispatch and completion wait error propagation."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

from make_wifi_port_patch import function_spans

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
args = parser.parse_args()
source = args.source / "rdawlan"
files = {name: (source / name).read_text() for name in (
    "wland_cfg80211.c", "wland_cfg80211.h", "wland_defs.h", "wland_dev.h")}


def definition(name):
    text = files["wland_cfg80211.c"]
    if name == "wland_run_escan":
        begin, after = "static s32 wland_run_escan(", "\nstatic s32 wland_do_escan("
        assert text.count(begin) == text.count(after) == 1
        start = text.index(begin)
        return text[start:text.index(after, start)]
    spans = function_spans(text, name)
    assert len(spans) == 1
    start, _, end = spans[0]
    return text[start:end]


constants = ""
for name in ("SCAN_NUM_MAX", "SCAN_TIMER_INTERVAL_MS", "SCAN_CMP_TIMEOUT"):
    match = re.search(r"^#define\s+" + name + r"\s+([^\n]+)", "\n".join(files.values()), re.M)
    assert match, name
    constants += "#define " + name + " " + match[1].split("/*")[0].strip() + "\n"
ssid = re.search(r"^struct wland_ssid_le \{[\s\S]*?^\};", files["wland_dev.h"], re.M)
assert ssid
constants += "#define IEEE80211_MAX_SSID_LEN 32\n" + ssid[0] + "\n"
handler = definition("wland_notify_escan_handler")
assert "WRITE_ONCE(cfg->ctrl_scan_wait, false);" in handler
assert handler.index("WRITE_ONCE(cfg->ctrl_scan_wait, false);") < handler.index("wland_wait_event_scancmp_wakeup(cfg);")

code = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef int32_t s32;
typedef uint32_t __le32;
#define WLAND_DBG(...) ((void)0)
#define WLAND_ERR(...) ((void)0)
#define cpu_to_le32(value) ((u32)(value))
#define READ_ONCE(value) (value)
#define WRITE_ONCE(target, value) ((target) = (value))
/* CONSTANTS */
struct cfg80211_ssid { u8 ssid[32]; u8 ssid_len; };
struct cfg80211_scan_request { struct cfg80211_ssid *ssids; int n_ssids; };
struct wland_if { int bssidx; };
struct wland_cfg80211_info {
    int scan_timeout, scanid_wait, scannum;
    bool ctrl_scan_wait;
};
static struct wland_cfg80211_info config;
static struct wland_if interface;
static struct cfg80211_ssid ssids[SCAN_NUM_MAX];
static struct cfg80211_scan_request request = {ssids, SCAN_NUM_MAX};
static char rdawlan_firmware_path[16] = "sta";
static unsigned long jiffies = 1234, timer_expiry;
static int timer_calls, firmware_calls, wait_calls, replies[SCAN_NUM_MAX], waits[SCAN_NUM_MAX];
static int test_mode;
static bool fast_completion;
static struct wland_ssid_le emitted[SCAN_NUM_MAX];
static bool broadcast[SCAN_NUM_MAX];
static unsigned long msecs_to_jiffies(unsigned value) { return value; }
static void mod_timer(int *timer, unsigned long expiry) {
    assert(timer == &config.scan_timeout); timer_calls++; timer_expiry = expiry;
}
static int wland_check_test_mode(void) { return test_mode; }
static int wait_reply(bool completed, bool *waiting) {
    if (completed) return 1; /* kernel wait returns immediately after an early event */
    int reply = waits[wait_calls++];
    if (reply > 0) *waiting = false;
    return reply;
}
#define wait_event_interruptible_timeout(queue, condition, timeout) \
    ((void)(queue), assert((timeout) == SCAN_CMP_TIMEOUT), wait_reply((condition), lockvar))
static int wland_start_scan_set(struct wland_if *ifp, struct wland_ssid_le *ssid, bool enable) {
    assert(ifp == &interface && enable && firmware_calls < SCAN_NUM_MAX);
    assert(config.ctrl_scan_wait == (config.scannum > 0));
    if (ssid) emitted[firmware_calls] = *ssid;
    broadcast[firmware_calls] = !ssid;
    int reply = replies[firmware_calls++];
    if (fast_completion && reply >= 0) config.ctrl_scan_wait = false;
    return reply;
}
/* REAL WAIT */
/* REAL SCAN */
static void reset(void) {
    memset(&config, 0, sizeof(config)); memset(replies, 0, sizeof(replies));
    memset(emitted, 0, sizeof(emitted)); memset(broadcast, 0, sizeof(broadcast));
    timer_calls = firmware_calls = wait_calls = test_mode = 0; fast_completion = false;
    for (int index = 0; index < SCAN_NUM_MAX; index++) {
        waits[index] = 1; memset(ssids[index].ssid, 'A' + index, sizeof(ssids[index].ssid));
        ssids[index].ssid_len = sizeof(ssids[index].ssid) - index;
    }
    request.ssids = ssids; request.n_ssids = SCAN_NUM_MAX;
    strcpy(rdawlan_firmware_path, "sta");
}
static void valid_scans(void) {
    for (int count = 1; count <= SCAN_NUM_MAX; count++) {
        reset(); request.n_ssids = count;
        assert(!wland_run_escan(&config, &interface, &request, 0));
        assert(firmware_calls == count && wait_calls == count - 1 && timer_calls == 1);
        assert(timer_expiry == jiffies + SCAN_TIMER_INTERVAL_MS * count);
        assert(!config.scannum && !config.ctrl_scan_wait);
        for (int index = 0; index < count; index++) {
            int request_index = count - index - 1;
            assert(!broadcast[index] && emitted[index].SSID_len == ssids[request_index].ssid_len);
            assert(!memcmp(emitted[index].SSID, ssids[request_index].ssid, emitted[index].SSID_len));
        }
    }
    reset(); request.n_ssids = 0; request.ssids = NULL;
    assert(!wland_run_escan(&config, &interface, &request, 0));
    assert(firmware_calls == 1 && !wait_calls && broadcast[0] && timer_calls == 1);
    assert(timer_expiry == jiffies + SCAN_TIMER_INTERVAL_MS);
    reset(); fast_completion = true;
    assert(!wland_run_escan(&config, &interface, &request, 0));
    assert(firmware_calls == SCAN_NUM_MAX && !wait_calls && !config.ctrl_scan_wait);
}
static void request_bounds(void) {
    reset(); config.scannum = 99; config.ctrl_scan_wait = true;
    assert(wland_run_escan(&config, &interface, NULL, 0) == -EINVAL);
    request.n_ssids = -1;
    assert(wland_run_escan(&config, &interface, &request, 0) == -EINVAL);
    request.n_ssids = SCAN_NUM_MAX + 1;
    assert(wland_run_escan(&config, &interface, &request, 0) == -EINVAL);
    request.n_ssids = 1; request.ssids = NULL;
    assert(wland_run_escan(&config, &interface, &request, 0) == -EINVAL);
    request.ssids = ssids; request.n_ssids = SCAN_NUM_MAX;
    ssids[0].ssid_len = 33;
    assert(wland_run_escan(&config, &interface, &request, 0) == -EINVAL);
    assert(!firmware_calls && !wait_calls && !timer_calls && config.scannum == 99 && config.ctrl_scan_wait);
    reset(); strcpy(rdawlan_firmware_path, "ap");
    assert(wland_run_escan(&config, &interface, &request, 0) == -EOPNOTSUPP);
    assert(!firmware_calls && !wait_calls && !timer_calls);
    reset(); test_mode = 1;
    assert(wland_run_escan(&config, &interface, &request, 0) == -EOPNOTSUPP);
    assert(!firmware_calls && !wait_calls && !timer_calls);
}
static void firmware_errors(void) {
    const int errors[] = {-EIO, -EOPNOTSUPP, -ETIMEDOUT, -EPROTO};
    for (unsigned error = 0; error < sizeof(errors)/sizeof(errors[0]); error++) {
        for (int failed = 0; failed < SCAN_NUM_MAX; failed++) {
            reset(); replies[failed] = errors[error];
            assert(wland_run_escan(&config, &interface, &request, 0) == errors[error]);
            assert(firmware_calls == failed + 1 && wait_calls == failed);
            assert(!config.scannum && !config.ctrl_scan_wait);
        }
        reset(); request.n_ssids = 0; request.ssids = NULL; replies[0] = errors[error];
        assert(wland_run_escan(&config, &interface, &request, 0) == errors[error]);
        assert(firmware_calls == 1 && !wait_calls && !config.scannum && !config.ctrl_scan_wait);
    }
}
static void wait_failures(void) {
    const int errors[] = {0, -EINTR, -EIO};
    for (unsigned error = 0; error < sizeof(errors)/sizeof(errors[0]); error++)
        for (int failed = 0; failed < SCAN_NUM_MAX - 1; failed++) {
            reset(); waits[failed] = errors[error];
            int expected = errors[error] ? errors[error] : -ETIMEDOUT;
            assert(wland_run_escan(&config, &interface, &request, 0) == expected);
            assert(firmware_calls == failed + 1 && wait_calls == failed + 1);
            assert(!config.scannum && !config.ctrl_scan_wait);
        }
    reset(); config.ctrl_scan_wait = true; waits[0] = 123;
    assert(!wland_wait_for_scancmp_event(&config, &config.ctrl_scan_wait));
    assert(wait_calls == 1 && !config.ctrl_scan_wait);
}
int main(void) {
    valid_scans(); request_bounds(); firmware_errors(); wait_failures();
    puts("RDA_SCAN_FAILURE_PASS: actual dispatch/wait, ordered SSIDs, fast completion, firmware errors, timeouts and request bounds");
}
'''
code = code.replace("/* CONSTANTS */", constants)
code = code.replace("/* REAL WAIT */", definition("wland_wait_for_scancmp_event"))
code = code.replace("/* REAL SCAN */", definition("wland_run_escan"))
with tempfile.TemporaryDirectory() as directory:
    temp = Path(directory)
    (temp / "scan.c").write_text(code)
    subprocess.run(["cc", "-O1", "-g", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-Wno-unused-but-set-variable",
                    str(temp / "scan.c"), "-o", str(temp / "scan")], check=True)
    subprocess.run([str(temp / "scan")], check=True)
print("Actual scan failure regression passed; firmware replies/waits are fixtures, not radio evidence")
