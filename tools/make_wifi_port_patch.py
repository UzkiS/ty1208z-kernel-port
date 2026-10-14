#!/usr/bin/env python3
"""Generate a hash-checked Linux 6.12 RDA USB port; no device access."""
import argparse
import difflib
from pathlib import Path
import re

from fetch_wifi import load_lock, verify

ROOT = Path(__file__).resolve().parents[1]


def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError(f"Changed RDA API anchor: {old[:100]!r}")
    return text.replace(old, new)


def function_spans(text, name):
    """Locate locked C definitions, counting braces outside strings/comments."""
    pattern = re.compile(r"^(?:static\s+)?(?:__maybe_unused\s+)?(?:inline\s+)?"
                         r"(?:int|s32|u8|u16|u64|void|bool|struct\s+\w+\s*\*)\s*"
                         + re.escape(name) + r"\s*\([^;]*?\)\s*\{", re.M)
    spans = []
    for match in pattern.finditer(text):
        start = match.end() - 1
        depth = 0
        tokens = re.finditer(r'/\*[\s\S]*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|'
                             r"'(?:\\.|[^'\\])*'|[{}]", text[start:])
        for token in tokens:
            if token.group() == "{":
                depth += 1
            elif token.group() == "}":
                depth -= 1
                if depth == 0:
                    spans.append((match.start(), start, start + token.end()))
                    break
        else:
            raise ValueError(f"Unclosed RDA function: {name}")
    if not spans:
        raise ValueError(f"Missing RDA function: {name}")
    return spans


def body(text, name, content, count=1):
    spans = function_spans(text, name)
    if len(spans) != count:
        raise ValueError(f"Unexpected definition count: {name}")
    for _, start, end in reversed(spans):
        text = text[:start] + "{\n" + content + "}\n" + text[end:]
    return text


def remove_function(text, name, count=1):
    spans = function_spans(text, name)
    if len(spans) != count:
        raise ValueError(f"Unexpected manufacturing definition count: {name}")
    for start, _, end in reversed(spans):
        text = text[:start] + text[end:]
    return text


def replace_definition(text, name):
    spans = function_spans(text, name)
    if len(spans) != 1:
        raise ValueError(f"Unexpected protocol definition count: {name}")
    replacement = (ROOT / "wifi/replacements" / (name + ".c")).read_text()
    if len(function_spans(replacement, name)) != 1:
        raise ValueError(f"Invalid project protocol replacement: {name}")
    start, _, end = spans[0]
    return text[:start] + replacement + text[end:]


def scan_result_handler(text):
    start, _, end = function_spans(text, "wland_notify_escan_handler")[0]
    operation = text[start:end]
    operation = replace(operation, '''\tstruct wland_cfg80211_info *cfg = ifp->drvr->config;

\tstruct cfg80211_scan_request *request = cfg->scan_request;
\tstruct wland_cfg80211_vif *vif = cfg->scan_info.ifp->vif;''',
                        '''\tstruct wland_cfg80211_info *cfg;
\tstruct cfg80211_scan_request *request;
\tstruct wland_cfg80211_vif *vif;''')
    operation = replace(operation, '\tstruct wland_bss_info_le bss_info_le;',
                        '\tstruct wland_bss_info_le bss_info_le = {};')
    operation = replace(operation, '\tifp = vif->ifp;', '''\tif (!ifp || !e || !ifp->drvr || !ifp->drvr->config)
\t\treturn -EINVAL;
\tcfg = ifp->drvr->config;
\tif (!cfg->scan_info.ifp || !cfg->scan_info.ifp->vif)
\t\treturn -EINVAL;
\trequest = cfg->scan_request;
\tvif = cfg->scan_info.ifp->vif;
\tif (!vif->ifp)
\t\treturn -EINVAL;
\tifp = vif->ifp;''')
    operation = replace(operation, '\t\tif (!data) {',
                        '\t\tif (!data) {\n\t\t\terr = -EINVAL;')
    operation = replace(operation, "\t\tmemset(&bss_info_le, '\\0', sizeof(struct wland_bss_info_le));\n"
                        '\t\twland_parse_network_info(&bss_info_le, (u8 *) data);',
                        '''\t\terr = wland_parse_network_info(&bss_info_le, data, e->datalen);
\t\tif (err)
\t\t\tgoto exit;''')
    operation = replace(operation, "\t\t\tmemset(&bss_info_le, '\\0', sizeof(struct wland_bss_info_le));\n", '')
    operation = replace(operation,
                        '\t\t\tWLAND_DBG(CFG80211, INFO, "receive an ap out of scan period\\n");\n'
                        '\t\t\treturn 0;',
                        '\t\t\tWLAND_DBG(CFG80211, INFO, "receive an ap out of scan period\\n");\n'
                        '\t\t\tgoto exit;')
    operation = replace(operation, '\t\t\t\tbss->time = jiffies;',
                        '''\t\t\t\t/* The existing list entry now owns the replacement IEs. */
\t\t\t\tbss_info_le.ie = NULL;
\t\t\t\tbss->time = jiffies;''')
    operation = replace(operation, '\t\t\terr = PTR_ERR(new_bss);\n\t\t}',
                        '''\t\t\terr = PTR_ERR(new_bss);
\t\t} else {
\t\t\t/* The new list entry owns the shallow-copied IE buffer. */
\t\t\tbss_info_le.ie = NULL;
\t\t}''')
    operation = replace(operation, 'exit:\n\treturn err;',
                        'exit:\n\tkfree(bss_info_le.ie);\n\treturn err;')
    operation = replace(operation, 'Ignoring IBSS result(SSID: %s).',
                        'Ignoring IBSS result(SSID: %.*s).')
    operation = replace(operation, '\t\t\t\t\tbss_info_le.SSID);',
                        '\t\t\t\t\t(int)bss_info_le.SSID_len, bss_info_le.SSID);')
    operation = replace(operation, 'SSID:\\"%s\\"', 'SSID:\\"%.*s\\"', 2)
    operation = replace(operation, '\t\t\tbss_info_le.BSSID, bss_info_le.RSSI, bss_info_le.SSID);',
                        '\t\t\tbss_info_le.BSSID, bss_info_le.RSSI,\n'
                        '\t\t\t(int)bss_info_le.SSID_len, bss_info_le.SSID);')
    operation = replace(operation, '\t\t\tbss_info_le.RSSI, bss_info_le.SSID,',
                        '\t\t\tbss_info_le.RSSI, (int)bss_info_le.SSID_len, bss_info_le.SSID,')
    return text[:start] + operation + text[end:]


def transform(files):
    result = dict(files)
    result["rdawlan/wland_defs.h"] = replace(
        files["rdawlan/wland_defs.h"],
        "#ifdef WLAND_USB_SUPPORT\n\n#define WLAND_P2P_SUPPORT",
        "#ifdef WLAND_USB_SUPPORT\n\n"
        "/* USB STA/AP use WIDs; P2P requires an unavailable named-iovar transport. */")
    result["rdawlan/wland_cfg80211.h"] = replace(
        files["rdawlan/wland_cfg80211.h"],
        "struct wland_cfg80211_connect_info {",
        "struct wland_cfg80211_connect_info {\n"
        "\t/* Work/timer/list lifetime, including partial attach rollback. */\n"
        "\tbool initialized;")
    result["rdawlan/wland_cfg80211.h"] = replace(
        result["rdawlan/wland_cfg80211.h"], "struct wland_cfg80211_vif {",
        "struct wland_cfg80211_vif {\n"
        "\t/* WID_ADD_TX_GTK selects its supplied AP group-key index. */\n"
        "\tbool tx_gtk_valid;\n\tu8 tx_gtk_index;")
    result["rdawlan/wland_fweh.h"] = replace(files["rdawlan/wland_fweh.h"],
                                            "\tu8 data[0];", "\tu8 data[];")
    result["rdawlan/wland_bus.c"] = replace(files["rdawlan/wland_bus.c"],
                                           "#include <asm/unaligned.h>", "#include <linux/unaligned.h>")
    result["rdawlan/wland_bus.c"] = replace(result["rdawlan/wland_bus.c"],
                                           "random_ether_addr(", "eth_random_addr(", 4)
    for call, step in (("ret = wland_fws_init(drvr);", "fws-init"),
                       ("drvr->config = wland_cfg80211_attach(drvr, bus_if->dev);", "cfg80211-attach"),
                       ("ret = wland_netdev_attach(ifp);", "netdev-register")):
        result["rdawlan/wland_bus.c"] = replace(
            result["rdawlan/wland_bus.c"], "\t" + call,
            '\tdev_info(dev, "RDA_STARTUP ' + step + '\\n");\n\t' + call)
    result["rdawlan/wland_utils.h"] = replace(files["rdawlan/wland_utils.h"],
                                              "prandom_u32", "get_random_u32")
    result["rdawlan/wland_fwsmgr.c"] = replace(files["rdawlan/wland_fwsmgr.c"], "strlcpy(", "strscpy(")
    text = replace(files["rdawlan/wland_rx.c"], "netif_rx_ni(skb);", "netif_rx(skb);", 2)
    text = replace(text, '#include "wland_wid.h"',
                   '#include "wland_wid.h"\n#include "wland_port_scan.h"')
    start, _, end = function_spans(text, "wland_handle_async_info")[0]
    operation = text[start:end]
    operation = replace(operation, '\tint i;', '\tint i;\n\tsize_t network_frame_length;')
    operation = replace(operation, '\twid_id = p_buffer[4] | p_buffer[5]<<8;',
                        '''\tif (!event_packet || !p_buffer)
\t\treturn -EINVAL;
\tif (event_packet->datalen < 8 ||
\t    (MAKE_WORD16(p_buffer[2], p_buffer[3])) < 8 ||
\t    (MAKE_WORD16(p_buffer[2], p_buffer[3])) > event_packet->datalen)
\t\treturn -EMSGSIZE;
\twid_id = p_buffer[4] | p_buffer[5]<<8;
\tif (wid_id == WID_NETWORK_INFO) {
\t\tret = wland_port_network_frame_length(p_buffer,
\t\t\tevent_packet->datalen, &network_frame_length);
\t\tif (ret)
\t\t\treturn ret;
\t}''')
    text = text[:start] + operation + text[end:]
    text = replace(text,
                   '\t\t\t\t\twland_get_assoc_ies_from_frame(drvr->iflist[i], p_frame, frame_len, sub_type);',
                   '\t\t\t\t\tret = wland_get_assoc_ies_from_frame(drvr->iflist[i], p_frame, frame_len, sub_type);', 2)
    text = replace(text,
                   '\t\t\t\t\twland_analysis_assoc_ies(drvr->iflist[i]);',
                   '\t\t\t\t\tif (!ret)\n\t\t\t\t\t\twland_analysis_assoc_ies(drvr->iflist[i]);')
    text = replace(text, '''\t\tbuf = skb->data;
\t\t// pull hdr from the skb''', '''\t\tif (skb->len < WID_HEADER_LEN) {
\t\t\twland_pkt_buf_free_skb(skb);
\t\t\treturn -EMSGSIZE;
\t\t}
\t\tbuf = skb->data;
\t\t// pull hdr from the skb''')
    text = replace(text, "\t\tif (rx_len > size) {", "\t\tif (rx_len < WID_HEADER_LEN || rx_len > size) {")
    text = replace(text, '''\t\t\tmsg_type = buf[2];''', '''\t\t\tif (rx_len < sizeof(struct wland_dcmd)) {
\t\t\t\twland_pkt_buf_free_skb(skb);
\t\t\t\treturn -EMSGSIZE;
\t\t\t}
\t\t\tmsg_type = buf[2];''')
    text = replace(text, '''\t\t\t\tspin_lock_bh(&rx_info->rxctl_lock);
\t\t\t\trx_info->rxctl = rx_info->rxbuf;''', '''\t\t\t\tif (!rx_info->rxbuf || rx_len > rx_info->rxblen) {
\t\t\t\t\twland_pkt_buf_free_skb(skb);
\t\t\t\t\treturn -EMSGSIZE;
\t\t\t\t}
\t\t\t\tspin_lock_bh(&rx_info->rxctl_lock);
\t\t\t\trx_info->rxctl = rx_info->rxbuf;''')
    result["rdawlan/wland_rx.c"] = text
    # Applied after the USB-only API patch; these anchors are unaffected by it.
    text = files["rdawlan/wland_usb.c"]
    text = replace(text, '#include "wland_bus.h"',
                   '#include "wland_bus.h"\n#include "wland_port_usb.h"')
    start, _, end = function_spans(text, "wland_usb_bus_txdata")[0]
    operation = text[start:end]
    begin = operation.index('\tbuf = skb->data;\n\tbuf_len = skb->len & CDC_DCMD_LEN_MASK;',
                            operation.index('#endif\n\tbuf = skb->data;'))
    finish = operation.index('\n\treq->skb = skb;', begin)
    operation = operation[:begin] + '''\tret = wland_port_usb_tx_length(skb);
\tif (ret < 0) {
\t\twland_txcomplete(dev, skb, false);
\t\twland_usb_enq(devinfo, &devinfo->tx_freeq, req,
\t\t\t&devinfo->tx_freecount, &devinfo->tx_freeq_lock);
\t\tgoto flow_ctrl;
\t}
\tbuf_len = ret;
\tbuf = skb->data;
''' + operation[finish:]
    text = text[:start] + operation + text[end:]
    text = replace(text, '''\t\tmemcpy(buf, rx_info->rxctl, min(len, rxlen));''', '''\t\tif (rxlen > len || rxlen > rx_info->rxblen || !rx_info->rxctl)
\t\t\terr = -EMSGSIZE;
\t\telse {
\t\t\tmemcpy(buf, rx_info->rxctl, rxlen);
\t\t\terr = rxlen;
\t\t}''')
    text = replace(text, "\terr = rxlen>0 ? (int)rxlen : -ETIMEDOUT;", "\tif (!rxlen)\n\t\terr = -ETIMEDOUT;")
    for call, step in (("ret = wland_bus_attach(0, dev);", "bus-attach"),
                       ("ret = wland_bus_start(dev);", "bus-start")):
        text = replace(text, "\t\t" + call,
                       '\t\tdev_info(&intf->dev, "RDA_STARTUP ' + step + '\\n");\n\t\t' + call)
    text = replace(text, '\tWLAND_DBG(USB, ERROR, "Enter\\n");',
                   '\tdev_info(&intf->dev, "RDA_STARTUP usb-probe\\n");')
    text = replace(text, "\treturn 0;\nfail1:",
                   '\tdev_info(&intf->dev, "RDA_STARTUP usb-probe-complete\\n");\n\treturn 0;\nfail1:')
    result["rdawlan/wland_usb.c"] = text
    text = files["rdawlan/wland_nvram.c"]
    text = body(text, "wland_nvram_read", '''\tstruct file *file;
\tloff_t position = offset;
\tssize_t ret;

\tif (size < 0 || offset < 0)
\t\treturn -EINVAL;
\tfile = filp_open(filename, O_RDONLY, 0);
\tif (IS_ERR(file))
\t\treturn PTR_ERR(file);
\tret = kernel_read(file, data, size, &position);
\tfilp_close(file, NULL);
\treturn ret;
''')
    for name in ("wland_nvram_write", "wland_file_write"):
        text = body(text, name, '\t/* Persistent configuration belongs to userspace. */\n\treturn -EOPNOTSUPP;\n')
    result["rdawlan/wland_nvram.c"] = text

    text = files["rdawlan/wland_cmds.c"]
    text = replace(text, '\tstruct kstat config_stat;\n\tmm_segment_t fs;\n', '\tstruct file *config_file;\n\tloff_t config_length;\n')
    text = replace(text, '''\tfs = get_fs();
\tset_fs(KERNEL_DS);
\tsnprintf(filename, 256, "%s/%s", WLAND_FIRMWARE_PATH, WIFI_POWER_SAVR_FILE_NAME);
\tret = vfs_stat(filename, &config_stat);
\tif (ret) {
\t\tWLAND_ERR("can not get config file status :%d\\n",ret);
\t\treturn ret;
\t} else {
\t\tconfig_size = (int)config_stat.size;
\t}''', '''\tsnprintf(filename, sizeof(filename), "%s/%s", WLAND_FIRMWARE_PATH, WIFI_POWER_SAVR_FILE_NAME);
\tconfig_file = filp_open(filename, O_RDONLY, 0);
\tif (IS_ERR(config_file))
\t\treturn PTR_ERR(config_file);
\tconfig_length = i_size_read(file_inode(config_file));
\tfilp_close(config_file, NULL);
\tif (config_length <= 0 || config_length > 65536)
\t\treturn -EINVAL;
\tconfig_size = config_length;''')
    text = replace(text, "\tbuf[config_size+1] = '\\0';", "\tbuf[config_size] = '\\0';", 2)
    text = replace(text, '''s32 wland_push_wid(u8 *buf, u16 WID, const void *data, u16 data_len, bool is_query)
{''', '''s32 wland_push_wid(u8 *buf, u16 WID, const void *data, u16 data_len, bool is_query)
{
\t/* No manufacturing eFuse writes, including internal batched requests. */
\tif (!is_query && (WID == WID_SET_EFUSE_ONE_PAGE ||
\t\t\t  WID == WID_EFUSE_XTAL_CAL_VAL ||
\t\t\t  WID == WID_EFUSE_PHY_TXPOW_VAL))
\t\treturn -EPERM;
''')
    text = replace(text, '''\tu8 *wid_msg = prot->buf;

\tif (drvr->bus_if->state''', '''\tu8 *wid_msg = prot->buf;

\tif (rw && (wid == WID_SET_EFUSE_ONE_PAGE ||
\t\t   wid == WID_EFUSE_XTAL_CAL_VAL ||
\t\t   wid == WID_EFUSE_PHY_TXPOW_VAL))
\t\treturn -EPERM;

\tif (drvr->bus_if->state''')
    for name in ("wland_pull_wid", "wland_wid_hdrpull", "wland_proto_cdc_cmplt"):
        text = replace_definition(text, name)
    for name in ("wland_fil_iovar_data_set", "wland_fil_iovar_data_get"):
        text = body(text, name, '''\t/* The locked source has no transport for named iovars. */
\treturn -EOPNOTSUPP;
''')
    result["rdawlan/wland_cmds.c"] = text
    text = files["rdawlan/wland_trap.c"]
    text = replace(text, '#ifdef WLAND_FIRMWARE_PATH\n',
                   '#if defined(WLAND_FIRMWARE_PATH) && !defined(WLAND_USB_SUPPORT)\n')
    text = replace(text, '\tsdesc->flags = 0x0;\n', '')
    text = replace(text, 'int wland_hash(char *name, const u8 *str, size_t len, u8 *hash)',
                   'static int wland_hash(char *name, const u8 *str, size_t len, u8 *hash)')
    text = replace(text, '\tcrypto_shash_update(sdesc, str, len);',
                   '\terr = crypto_shash_update(sdesc, str, len);\n'
                   '\tif (err)\n\t\tgoto hash_err;')
    text = replace(text, '''\trdlen = kernel_read(fp, fp->f_pos, buf, len);
\tif (rdlen > 0)
\t\tfp->f_pos += rdlen;''', '\trdlen = kernel_read(fp, buf, len, &fp->f_pos);')
    for function in ("wland_download_codefile", "wland_download_datafile"):
        _, start, _ = function_spans(text, function)[0]
        # Exact normal modes only; reject rf, arbitrary paths and prefixes.
        guard = '''
\tif (strcmp(rdawlan_firmware_path, "sta") &&
\t    strcmp(rdawlan_firmware_path, "ap") &&
\t    strcmp(rdawlan_firmware_path, "p2p"))
\t\treturn -EPERM;
'''
        # Keep declarations before statements; insert ahead of the first debug.
        insertion = text.index('\tWLAND_DBG(', start)
        text = text[:insertion] + guard + '\n' + text[insertion:]
    for component in ("CODE", "DATA"):
        branch = f'''\t\telse if (strncasecmp(rdawlan_firmware_path, "rf", strlen("rf")) == 0)
#ifdef WLAND_SDIO_SUPPORT
\t\t\tfilename = RDA5991H_SDIO_{component}_RF;
#else
\t\t\tfilename = RDA5991H_USB_{component}_RF;
#endif'''
        text = replace(text, branch, '')
    text = replace(text, '\t\tret = wland_download_image(ifp, filename, RDA5991H_CODE_ADDR);',
                   '\t\tret = wland_download_image(ifp, filename, RDA5991H_CODE_ADDR);\n'
                   '\tif (ret < 0)\n\t\treturn ret;')
    result["rdawlan/wland_trap.c"] = text

    text = files["rdawlan/wland_linux.c"]
    text = replace(text, "strlcpy(", "strscpy(", 2)
    text = replace(text, "static void wland_netdev_tx_timeout(struct net_device *dev)",
                   "static void wland_netdev_tx_timeout(struct net_device *dev, unsigned int txqueue)")
    text = replace(text, "memcpy(ndev->dev_addr, ifp->mac_addr, ETH_ALEN);", "eth_hw_addr_set(ndev, ifp->mac_addr);", 2)
    text = replace(text, "memcpy(ifp->ndev->dev_addr, ifp->mac_addr, ETH_ALEN);", "eth_hw_addr_set(ifp->ndev, ifp->mac_addr);")
    text = replace(text, "ret = wland_android_priv_cmd(ndev, ifr, cmd);", "ret = -EOPNOTSUPP;", 2)
    text = replace(text, "ret = wland_rf_test_cmd(ndev, ifr, cmd);", "ret = -EOPNOTSUPP;")
    text = body(text, "wland_check_test_mode", "\treturn 0;\n")
    text = body(text, "wland_set_test_mode", "\t/* Manufacturing/test firmware is unavailable in this port. */\n")
    text = replace(text, "static u8 wifi_in_test_mode = 0;", "/* Test mode deliberately has no mutable state. */")
    start, _, end = function_spans(text, "wland_del_if")[0]
    operation = text[start:end]
    operation = replace(operation, '\t\tunregister_netdev(ifp->ndev);',
                        '\t\t/* Keep netdev/ifp alive until cfg80211 works, timers and\n'
                        '\t\t * vif pointers are drained after netdev unregister.\n'
                        '\t\t */\n'
                        '\t\tifp->ndev->priv_destructor = NULL;\n'
                        '\t\tunregister_netdev(ifp->ndev);')
    operation = replace(operation, '\t\tdrvr->iflist[bssidx] = NULL;\n\n\t} else {',
                        '\t\tdrvr->iflist[bssidx] = NULL;\n'
                        '\t\tfree_netdev(ifp->ndev);\n\n\t} else {')
    text = text[:start] + operation + text[end:]
    result["rdawlan/wland_linux.c"] = text
    result["rdawlan/wland_wid.c"] = replace_definition(
        files["rdawlan/wland_wid.c"], "wland_start_chip")

    text = files["rdawlan/wland_android.c"]
    text = body(text, "wland_android_priv_cmd", "\treturn -EOPNOTSUPP;\n")
    result["rdawlan/wland_android.c"] = text
    text = files["rdawlan/wland_rf.c"]
    for name, count in (("wland_efuse_set_vendor_id", 1), ("wland_write_efuse_xtal_cal_val", 2),
                        ("wland_efuse_set_mac_addr", 1), ("wland_write_txpower_to_efuse", 3),
                        ("wland_rf_test_cmd", 1)):
        text = remove_function(text, name, count)
    if "WID_SET_EFUSE_ONE_PAGE" in text:
        raise ValueError("Unreviewed eFuse write survives removal")
    result["rdawlan/wland_rf.c"] = text

    text = files["rdawlan/wland_cfg80211.c"]
    text = replace_definition(text, "wland_cfg80211_change_virtual_iface")
    text = replace_definition(text, "wland_get_assoc_ies_from_frame")
    text = replace(text, '#include "wland_android.h"',
                   '#include <linux/math64.h>\n#include "wland_port_key.h"\n'
                   '#include "wland_port_key_validate.h"\n#include "wland_android.h"')
    text = body(text, "wland_get_systime_us", "\treturn div_u64(ktime_get_boottime_ns(), NSEC_PER_USEC);\n")
    for name in ("add_key", "del_key", "get_key"):
        text = replace(text, f"static s32 wland_cfg80211_{name}(struct wiphy *wiphy, struct net_device *ndev,\n\tu8 key_idx,",
                       f"static s32 wland_cfg80211_{name}(struct wiphy *wiphy, struct net_device *ndev,\n\tint link_id, u8 key_idx,")
    text = replace(text, "\tstruct net_device *ndev, u8 key_idx, bool unicast, bool multicast)",
                   "\tstruct net_device *ndev, int link_id, u8 key_idx, bool unicast, bool multicast)")
    text = replace(text, "\tstruct net_device *ndev, u8 key_idx)\n", "\tstruct net_device *ndev, int link_id, u8 key_idx)\n")
    text = replace(text, "static int wland_cfg80211_stop_ap(struct wiphy *wiphy, struct net_device *ndev)",
                   "static int wland_cfg80211_stop_ap(struct wiphy *wiphy, struct net_device *ndev, unsigned int link_id)")
    text = replace(text, '''static s32 wland_cfg80211_change_beacon(struct wiphy *wiphy, struct net_device *ndev,
\tstruct cfg80211_beacon_data *info)
{
\ts32 err = 0;''', '''static s32 wland_cfg80211_change_beacon(struct wiphy *wiphy, struct net_device *ndev,
\tstruct cfg80211_ap_update *update)
{
\tstruct cfg80211_beacon_data *info = &update->beacon;
\ts32 err = 0;''')
    start, _, end = function_spans(text, "wland_cfg80211_mgmt_frame_register")[0]
    text = text[:start] + '''static void wland_cfg80211_update_mgmt_frame_registrations(struct wiphy *wiphy,
\tstruct wireless_dev *wdev, struct mgmt_frame_regs *update)
{
\tstruct wland_cfg80211_vif *vif =
\t\tcontainer_of(wdev, struct wland_cfg80211_vif, wdev);

\tvif->mgmt_rx_reg = update->interface_stypes;
}
''' + text[end:]
    text = replace(text, ".mgmt_frame_register = wland_cfg80211_mgmt_frame_register,",
                   ".update_mgmt_frame_registrations = wland_cfg80211_update_mgmt_frame_registrations,")
    text = replace(text, "\t\t\t\tWLAN_CAPABILITY_ESS, WLAN_CAPABILITY_ESS);",
                   "\t\t\t\tIEEE80211_BSS_TYPE_ESS, IEEE80211_PRIVACY_ANY);")
    text = replace(text, "\t\tcfg80211_put_bss(wiphy, bss_internal);\n", "\t\t/* cfg80211_roamed consumes the acquired BSS reference. */\n")
    text = replace(text, "\t\t\t\t.bss = bss_internal,", "\t\t\t\t.links[0].bss = bss_internal,")
    text = replace(text, "(profile->bssid)", "is_valid_ether_addr(profile->bssid)", 2)
    for prefix, indent in (("ptkey", "\t\t"), ("gtkey", "\t")):
        start = text.index(f"{indent}memcpy({prefix}.key, params->key, 16);")
        end = text.index("\n" + indent + "}\n", start) + len("\n" + indent + "}")
        old = text[start:end]
        if old.count("params->key + 24") != 1 or old.count("params->key + 16") != 2:
            raise ValueError("Changed legacy key/MIC layout")
        new = f'''{indent}err = wland_port_copy_key({prefix}.key, params->key, params->key_len,
{indent}\tifp->vif->wdev.iftype == NL80211_IFTYPE_STATION ||
{indent}\tifp->vif->wdev.iftype == NL80211_IFTYPE_P2P_CLIENT);
{indent}if (err)
{indent}\treturn err;'''
        text = text[:start] + new + text[end:]
    text = replace(text, "\tmemcpy(gtkey.keyRSC, params->seq, params->seq_len);", '''\tif (params->seq_len < 0 || params->seq_len > sizeof(gtkey.keyRSC) ||
\t    (params->seq_len && !params->seq))
\t\treturn -EINVAL;
\tif (params->seq_len)
\t\tmemcpy(gtkey.keyRSC, params->seq, params->seq_len);''')
    for kind in ("PTK", "RX_GTK"):
        indent = '\t\t\t' if kind == "PTK" else '\t\t'
        text = replace(text, f'''{indent}WLAND_ERR("Set WID_ADD_{kind} error (%d)\\n", err);
{indent}return 0;''', f'''{indent}WLAND_ERR("Set WID_ADD_{kind} error (%d)\\n", err);
{indent}return err;''')
    text = replace(text, '''\tif (params->key_len)
\t\tWLAND_DUMP(TX_CTRL, params->key, params->key_len, "Key:\\n");''',
                   '\t/* Key material must not enter cfg80211 debug logs. */')
    for name in ("add_key", "del_key", "get_key", "config_default_key", "config_default_mgmt_key", "stop_ap"):
        _, start, _ = function_spans(text, "wland_cfg80211_" + name)[0]
        insertion = text.index('\tWLAND_DBG(', start)
        text = text[:insertion] + '\tif (link_id > 0)\n\t\treturn -EOPNOTSUPP;\n\n' + text[insertion:]
    for name in ("wland_cfg80211_add_key", "wland_add_ptkey", "wland_add_gtkey"):
        _, start, end = function_spans(text, name)[0]
        insertion = text.index('\tWLAND_DBG(', start, end)
        guard = '''\terr = wland_port_validate_key(params, key_idx);
\tif (err)
\t\treturn err;
\tif (!wland_port_key_role(ifp->vif->wdev.iftype))
\t\treturn -EOPNOTSUPP;
\tif (ifp->ndev->ieee80211_ptr->iftype != ifp->vif->wdev.iftype)
\t\treturn -EINVAL;

'''
        if name == "wland_add_ptkey":
            guard += '''\tif (!mac_addr || !is_valid_ether_addr(mac_addr))
\t\treturn -EINVAL;
\t/* This wire format has no key-index field for extended PTK slots. */
\tif (key_idx)
\t\treturn -EOPNOTSUPP;

'''
        if name == "wland_add_gtkey":
            guard += '''\tif ((ifp->vif->wdev.iftype == NL80211_IFTYPE_STATION ||
\t     ifp->vif->wdev.iftype == NL80211_IFTYPE_P2P_CLIENT) &&
\t    !is_valid_ether_addr(profile->bssid))
\t\treturn -EINVAL;

'''
        text = text[:insertion] + guard + text[insertion:]
    text = replace(text, '''#ifdef WLAND_AP_RESET
\t\tap_gtk_len = MIN(sizeof(gtkey)-offsetof(struct wland_rx_gtkey, key_idx),
\t\t\tparams->key_len+2);
#endif''', '')
    start, _, end = function_spans(text, "wland_add_gtkey")[0]
    operation = text[start:end]
    operation = replace(operation, '''\tdefault:
\t\tbreak;
\t}''', '''\tdefault:
\t\treturn -EOPNOTSUPP;
\t}''')
    operation = replace(operation, '''\tWLAND_DBG(CFG80211, TRACE, "Done.\\n");''', '''#ifdef WLAND_AP_RESET
\t/* Publish cached AP key state only after a successful firmware reply. */
\tif (ifp->vif->wdev.iftype == NL80211_IFTYPE_AP)
\t\tap_gtk_len = params->key_len + 2;
#endif
\tif (ifp->vif->wdev.iftype == NL80211_IFTYPE_AP) {
\t\tifp->vif->tx_gtk_index = key_idx;
\t\tifp->vif->tx_gtk_valid = true;
\t}
\tWLAND_DBG(CFG80211, TRACE, "Done.\\n");''')
    text = text[:start] + operation + text[end:]
    for name in ("wland_cfg80211_del_key", "wland_cfg80211_get_key",
                 "wland_cfg80211_config_default_key", "wland_cfg80211_stop_ap"):
        text = replace_definition(text, name)
    text = replace(text, '''\tWLAN_CIPHER_SUITE_CCMP,
\tWLAN_CIPHER_SUITE_AES_CMAC,
#ifdef WLAND_WAPI_SUPPORT
\tWLAN_CIPHER_SUITE_SMS4
#endif /*WLAND_WAPI_SUPPORT */''', '''\tWLAN_CIPHER_SUITE_CCMP,
\t/* No verified BIP/WAPI management-key command path. */''')
    text = replace(text, '"Done(dbm:%d)\\n", *dbm);', '"Done(err:%d)\\n", err);')
    start, _, end = function_spans(text, "wland_cfg80211_set_tx_power")[0]
    operation = text[start:end]
    operation = replace(operation, '\ts32 dbm = mbm;\n'
                        '#endif /*LINUX_VERSION_CODE >= KERNEL_VERSION(3, 8, 0) */',
                        '\ts32 dbm = mbm;\n'
                        '#endif /*LINUX_VERSION_CODE >= KERNEL_VERSION(3, 8, 0) */\n'
                        '\ts32 requested_dbm = dbm;')
    operation = replace(operation, '\tcfg->conf->tx_power = dbm;\n', '')
    operation = replace(operation, '''\terr = wland_fil_iovar_data_set(ifp, "qtxpower", &dbm, sizeof(dbm));''',
                        '''\terr = wland_fil_iovar_data_set(ifp, "qtxpower", &dbm, sizeof(dbm));
\tif (err >= 0)
\t\tcfg->conf->tx_power = requested_dbm;''')
    text = text[:start] + operation + text[end:]
    start, _, end = function_spans(text, "wland_cfg80211_up")[0]
    operation = text[start:end]
    operation = replace(operation, '''\terr = wland_dongle_roam(ifp, (cfg->roam_on ? 0 : 1),
\t\tWLAND_BEACON_TIMEOUT);
\tif (err < 0)
\t\tgoto up_exit;''', '''\t/* RDA has no named-iovar roaming transport. Host supplicant owns
\t * roaming; link-loss handling is configured by preinit's real WIDs.
\t */''')
    operation = replace(operation, '''up_exit:
\tmutex_unlock(&cfg->usr_sync);''', '''up_exit:
\t/* A failed initialization must not leave cfg80211 callbacks enabled. */
\tif (err)
\t\tclear_bit(VIF_STATUS_READY, &ifp->vif->sme_state);
\tmutex_unlock(&cfg->usr_sync);''')
    text = text[:start] + operation + text[end:]
    text = replace(text, '\tcfg->roam_on = true;\t/* roam on & off switch. we enable roam per default */',
                   '\tcfg->roam_on = false;\t/* Firmware roaming is not advertised. */')
    for name in ("wland_dongle_roam", "wland_construct_reginfo"):
        start, _, end = function_spans(text, name)[0]
        text = text[:start] + text[end:]
    text = replace_definition(text, "wland_update_wiphybands")
    start, _, end = function_spans(text, "wland_wait_for_scancmp_event")[0]
    operation = text[start:end]
    operation = replace(operation, 'cfg->scanid_wait, !(*lockvar),',
                        'cfg->scanid_wait, !READ_ONCE(*lockvar),')
    operation = replace(operation, '\treturn ret;', '''\tif (ret < 0)
\t\treturn ret;
\treturn ret ? 0 : -ETIMEDOUT;''')
    text = text[:start] + operation + text[end:]
    # Alternative preprocessor branches open the same block twice in raw C.
    # Both neighboring signatures are unique in the hash-locked source.
    begin = "static s32 wland_run_escan("
    after = "\nstatic s32 wland_do_escan("
    if text.count(begin) != 1 or text.count(after) != 1:
        raise ValueError("Changed conditional scan-function boundaries")
    start = text.index(begin)
    end = text.index(after, start)
    if not text[start:end].endswith("}\n"):
        raise ValueError("Changed scan-function terminator")
    operation = text[start:end]
    insertion = operation.index('\tWLAND_DBG(')
    operation = operation[:insertion] + '''\t/* Validate the whole directed request before arming a timer. */
\tif (!request || request->n_ssids < 0 || request->n_ssids > SCAN_NUM_MAX ||
\t    (request->n_ssids && !request->ssids))
\t\treturn -EINVAL;
\tif (request->n_ssids) {
\t\tint index;

\t\tfor (index = 0; index < request->n_ssids; index++)
\t\t\tif (request->ssids[index].ssid_len > sizeof(ssid_le.SSID))
\t\t\t\treturn -EINVAL;
\t}
\tif (wland_check_test_mode() ||
\t    !strcmp(rdawlan_firmware_path, "ap"))
\t\treturn -EOPNOTSUPP;
\tWRITE_ONCE(cfg->ctrl_scan_wait, false);

''' + operation[insertion:]
    operation = replace(operation, '''\t\t\t\terr = wland_start_scan_set(ifp, &ssid_le, true);''',
                        '''\t\t\t\t/* Publish the wait before a fast firmware completion. */
\t\t\t\tWRITE_ONCE(cfg->ctrl_scan_wait, cfg->scannum > 0);
\t\t\t\terr = wland_start_scan_set(ifp, &ssid_le, true);''')
    operation = replace(operation, '''\t\t\tif (err < 0) {
\t\t\t\tWLAND_ERR("SCAN error (%d)\\n", err);
\t\t\t} else if (cfg->scannum > 0) {
\t\t\t\tcfg->ctrl_scan_wait = true;
\t\t\t\terr = wland_wait_for_scancmp_event(cfg, &cfg->ctrl_scan_wait);
\t\t\t}''', '''\t\t\tif (err < 0) {
\t\t\t\tWLAND_ERR("SCAN error (%d)\\n", err);
\t\t\t\tgoto scan_failed;
\t\t\t}
\t\t\tif (cfg->scannum > 0) {
\t\t\t\terr = wland_wait_for_scancmp_event(cfg, &cfg->ctrl_scan_wait);
\t\t\t\tif (err < 0)
\t\t\t\t\tgoto scan_failed;
\t\t\t}''')
    operation = replace(operation, '''\treturn err;
}''', '''\treturn err;

scan_failed:
\t/* Do not let later SSIDs overwrite a firmware/timeout failure. */
\tcfg->scannum = 0;
\tWRITE_ONCE(cfg->ctrl_scan_wait, false);
\treturn err;
}''')
    operation = replace(operation,
                        'scanning ssid =\\"%s\\"\\n",\n'
                        '\t\t\t\t\t\tcfg->scannum,request->n_ssids,request->ssids[cfg->scannum].ssid);',
                        'scanning ssid =\\"%.*s\\"\\n",\n'
                        '\t\t\t\t\t\tcfg->scannum,request->n_ssids,\n'
                        '\t\t\t\t\t\trequest->ssids[cfg->scannum].ssid_len,\n'
                        '\t\t\t\t\t\trequest->ssids[cfg->scannum].ssid);')
    text = text[:start] + operation + text[end:]
    text = replace(text,
                   'request->n_ssids:%d, ssids->ssid=%s\\n",\n'
                   '\t\t\tifp->bssidx, escan_req, ssids->ssid_len, request->n_ssids, ssids->ssid);',
                   'request->n_ssids:%d, ssids->ssid=%.*s\\n",\n'
                   '\t\t\tifp->bssidx, escan_req, ssids->ssid_len, request->n_ssids,\n'
                   '\t\t\tmin_t(int, ssids->ssid_len, sizeof(ssids->ssid)), ssids->ssid);')
    text = replace(text, '\t\t\tcfg->ctrl_scan_wait = false;',
                   '\t\t\tWRITE_ONCE(cfg->ctrl_scan_wait, false);')
    for name in ("wland_init_connect_info", "wland_deinit_connect_info",
                 "wland_cfg80211_attach", "wland_free_vif", "wland_get_assoc_ies"):
        text = replace_definition(text, name)
    text = replace(text, "\t\tif (completed) {\n\t\t\t//wland_get_assoc_ies(cfg, ifp);",
                   "\t\tif (completed && wland_get_assoc_ies(cfg, ifp) < 0) {\n"
                   "\t\t\tWLAND_ERR(\"Firmware association IE query failed\\n\");\n"
                   "\t\t\tcompleted = false;\n"
                   "\t\t}\n"
                   "\t\tif (completed) {")
    text = replace(text, "\t\t\tWARN_ON(profile->rsn_cap);", "")
    for name in ("wland_cfg80211_start_ap", "wland_cfg80211_down"):
        _, start, end = function_spans(text, name)[0]
        insertion = text.index('\tWLAND_DBG(', start, end)
        text = text[:insertion] + '\tifp->vif->tx_gtk_valid = false;\n\n' + text[insertion:]
    text = replace(text, '#include "wland_wid.h"',
                   '#include "wland_wid.h"\n#include "wland_port_scan.h"')
    text = replace_definition(text, "wland_parse_network_info")
    text = scan_result_handler(text)
    result["rdawlan/wland_cfg80211.c"] = text
    return strict_scope(result)


def strict_scope(files):
    """Use shared public declarations and local linkage for audited file helpers."""
    result = dict(files)
    result["rdawlan/wland_nvram.c"] = replace(result["rdawlan/wland_nvram.c"],
                                              '#include "wland_defs.h"',
                                              '#include "wland_defs.h"\n#include "wland_port_nvram.h"')
    text = result["rdawlan/wland_dev.h"]
    for declaration in (
            "extern int wland_get_mac_address(char *buf);\n",
            "extern int wland_set_mac_address(char *buf);\n",
            "extern int wland_nvram_read(const char *filename, char *data, int size, int offset);\n",
            "extern int wland_file_write(char *filename, char *data , int size, int offset, u32 mode1, u32 mode2);\n"):
        text = replace(text, declaration, "")
    result["rdawlan/wland_dev.h"] = replace(text, "/* read/store mac address by file */",
                                           '#include "wland_port_nvram.h"\n\n/* read/store mac address by file */')
    text = replace(result["rdawlan/wland_utils.h"], "extern u8 wland_get_type(u8 * header);\n", "")
    result["rdawlan/wland_utils.h"] = replace(text, "extern u16  wland_get_beacon_period(u8 *data);\n",
                                             "extern u16  wland_get_beacon_period(u8 *data);\n"
                                             "extern u8 wland_get_type(u8 *header);\n")
    local = {
        "wland_nvram.c": ("wland_nvram_write",),
        "wland_utils.c": ("wland_get_n_cap_info", "wland_get_assoc_resp_cap_info",
                          "wland_get_asoc_status", "wland_get_asoc_id"),
        "wland_p2p.c": ("wland_p2p_run_escan",),
        "wland_fwsmgr.c": ("wland_fws_macdesc_cleanup", "wland_fws_macdesc_deinit"),
        "wland_wid.c": ("wland_chip_repower",),
        "wland_trap.c": ("wland_open_image", "wland_get_image_block", "wland_close_image"),
        "wland_linux.c": ("wland_netdev_start_xmit",),
        "wland_cfg80211.c": ("wland_wait_for_scancmp_event", "wland_wait_event_scancmp_wakeup",
                             "wland_set_mcs", "wland_cfg80211_parse_ap_settings"),
        "wland_android.c": ("wland_android_set_roam_mode",),
        "wland_rf.c": ("wland_is_old_efuse", "wland_read_efuse", "wland_efuse_canbe_overwrite",
                       "wland_buf_equals", "wland_get_rx_result", "wland_rf_phy_reg_read", "wland_md",
                       "wland_check_next_mode", "wland_start_rf_test", "wland_stop_rx_test",
                       "wland_set_sdio_pin_level", "wland_set_reg_for_one_channel",
                       "wland_dev_set_rssi_snr_config", "wland_dev_get_rssi_snr", "wland_set_data_rate",
                       "wland_set_rate", "wland_set_tbtt_cnt"),
        "wland_rx.c": ("wland_recv_indicatepkts_pkt_loss_cnt", "wland_recv_indicatepkt",
                       "wland_recv_indicatepkts_in_order", "wland_check_indicate_seq"),
    }
    optional = {"wland_nvram_write", "wland_get_n_cap_info", "wland_get_assoc_resp_cap_info",
                "wland_get_asoc_status", "wland_get_asoc_id", "wland_open_image",
                "wland_get_image_block", "wland_close_image", "wland_android_set_roam_mode"}
    for filename, names in local.items():
        relative = "rdawlan/" + filename
        text = result[relative]
        for name in names:
            # Cross-file callers must retain a public, declared interface.
            for other, contents in result.items():
                if other != relative and re.search(r"\b" + re.escape(name) + r"\b", contents):
                    raise ValueError(f"Local helper acquired an external reference: {name}: {other}")
            spans = function_spans(text, name)
            if len(spans) != 1:
                raise ValueError(f"Changed local helper definition: {name}")
            start = spans[0][0]
            qualifier = "static "
            if filename == "wland_rf.c" or name in optional:
                qualifier += "__maybe_unused "
            text = text[:start] + qualifier + text[start:]
        result[relative] = text
    for filename in ("wland_android.c", "wland_rf.c"):
        relative = "rdawlan/" + filename
        result[relative] = replace(result[relative],
                                  "#if LINUX_VERSION_CODE >= KERNEL_VERSION(4, 10, 0)\n"
                                  "#define is_compat_task()\t\t0\n#endif\n", "")
    for filename, names in {
            "wland_android.c": ("wland_cfg80211_set_country_code", "wland_cfg80211_set_wps_p2p_ie",
                                "wland_android_okc_enable", "wland_android_set_pmk",
                                "wland_android_get_p2p_dev_addr", "wland_android_get_band",
                                "wland_android_set_suspendmode", "wland_android_set_suspendopt",
                                "wland_android_get_rssi", "wland_android_get_link_speed"),
            "wland_cfg80211.c": ("wland_send_key_to_chip",),
    }.items():
        relative = "rdawlan/" + filename
        text = result[relative]
        for name in names:
            spans = function_spans(text, name)
            if len(spans) != 1 or not text[spans[0][0]:].startswith("static "):
                raise ValueError(f"Changed optional static helper: {name}")
            start = spans[0][0] + len("static ")
            text = text[:start] + "__maybe_unused " + text[start:]
        result[relative] = text
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    files = {}
    for item in load_lock()["files"]:
        if item["path"].endswith((".c", ".h")):
            data = (args.source / item["path"]).read_bytes()
            verify(item, data)
            files[item["path"]] = data.decode("utf-8")
    transformed = transform(files)
    patch = []
    for name in sorted(files):
        if transformed[name] != files[name]:
            patch.extend(difflib.unified_diff(files[name].splitlines(True),
                                             transformed[name].splitlines(True),
                                             f"a/{name}", f"b/{name}"))
    for path in sorted((ROOT / "wifi/overlay").rglob("*")):
        if path.is_file():
            name = path.relative_to(ROOT / "wifi/overlay").as_posix()
            patch.extend(difflib.unified_diff([], path.read_text().splitlines(True), "/dev/null", f"b/{name}"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(patch), encoding="utf-8", newline="\n")
    print("Generated checked RDA 6.12 API port; hardware/firmware untested")


if __name__ == "__main__":
    main()
