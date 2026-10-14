#!/usr/bin/env python3
"""Check actual USB padding helper, including allocation failure ownership."""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
args = parser.parse_args()
header = args.source / "rdawlan/wland_port_usb.h"
code = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CDC_DCMD_LEN_MASK 0xfff
struct sk_buff { unsigned int len; unsigned char *data; };
static bool fail;
static int __skb_pad(struct sk_buff *skb, int pad, bool free_on_error) {
    assert(!free_on_error && pad > 0);
    if (fail) return -ENOMEM;
    skb->data = realloc(skb->data, skb->len + pad);
    assert(skb->data);
    memset(skb->data + skb->len, 0, pad);
    return 0;
}
/* HELPER */
int main(void) {
    const unsigned lengths[] = {0, 64, 65, 137, 511, 512, 513, 1024, 1536, 1537, 4095, 4096};
    const int expected[] = {-EMSGSIZE, 64, 516, 516, 516, 516, 513, 1028, 1540, 1537, 4095, -EMSGSIZE};
    for (unsigned i = 0; i < sizeof(lengths)/sizeof(lengths[0]); i++) {
        struct sk_buff skb = {lengths[i], malloc(lengths[i] + 1)};
        assert(skb.data); memset(skb.data, 0xa5, lengths[i]);
        assert(wland_port_usb_tx_length(&skb) == expected[i]);
        assert(skb.len == lengths[i]);
        for (unsigned j = 0; j < skb.len; j++) assert(skb.data[j] == 0xa5);
        for (int j = skb.len; j < expected[i]; j++) assert(skb.data[j] == 0);
        free(skb.data);
    }
    struct sk_buff skb = {137, malloc(137)};
    unsigned char *old = skb.data; fail = true;
    assert(wland_port_usb_tx_length(&skb) == -ENOMEM);
    assert(skb.data == old && skb.len == 137); free(skb.data);
    puts("RDA_USB_TX_PADDING_AND_OWNERSHIP_PASS");
}
'''.replace("/* HELPER */", header.read_text())
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "padding.c").write_text(code)
    subprocess.run(["cc", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", str(root / "padding.c"),
                    "-o", str(root / "padding")], check=True)
    subprocess.run([str(root / "padding")], check=True)
