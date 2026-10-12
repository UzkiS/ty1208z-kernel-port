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
    pattern = re.compile(r"^(?:static\s+)?(?:inline\s+)?(?:int|s32|u8|u64|void|bool)\s+"
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


def transform(files):
    result = dict(files)
    result["rdawlan/wland_bus.c"] = replace(files["rdawlan/wland_bus.c"],
                                           "#include <asm/unaligned.h>", "#include <linux/unaligned.h>")
    result["rdawlan/wland_bus.c"] = replace(result["rdawlan/wland_bus.c"],
                                           "random_ether_addr(", "eth_random_addr(", 4)
    result["rdawlan/wland_utils.h"] = replace(files["rdawlan/wland_utils.h"],
                                              "prandom_u32", "get_random_u32")
    result["rdawlan/wland_fwsmgr.c"] = replace(files["rdawlan/wland_fwsmgr.c"], "strlcpy(", "strscpy(")
    text = replace(files["rdawlan/wland_rx.c"], "netif_rx_ni(skb);", "netif_rx(skb);", 2)
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
    text = replace(text, '''\t\tmemcpy(buf, rx_info->rxctl, min(len, rxlen));''', '''\t\tif (rxlen > len || rxlen > rx_info->rxblen || !rx_info->rxctl)
\t\t\terr = -EMSGSIZE;
\t\telse {
\t\t\tmemcpy(buf, rx_info->rxctl, rxlen);
\t\t\terr = rxlen;
\t\t}''')
    text = replace(text, "\terr = rxlen>0 ? (int)rxlen : -ETIMEDOUT;", "\tif (!rxlen)\n\t\terr = -ETIMEDOUT;")
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
    result["rdawlan/wland_linux.c"] = text
    text = files["rdawlan/wland_wid.c"]
    text = replace(text, '''\tif (wland_nvram_read(RDA5995_TESTMODE_FILE, NULL, 0, 0) >= 0)
\t\tstrcpy(rdawlan_firmware_path, "rf");''', '\t/* No filesystem trigger for manufacturing firmware. */')
    text = replace(text, '''\tif (strncasecmp(rdawlan_firmware_path, "rf", strlen("rf")) == 0) {
\t\tWLAND_DBG(RFTEST, INFO, "RF Test Mode!\\n");
\t\twland_set_test_mode(1);
\t} else
\t\twland_set_test_mode(0);''', '''\tif (strcmp(rdawlan_firmware_path, "sta") &&
\t    strcmp(rdawlan_firmware_path, "ap") &&
\t    strcmp(rdawlan_firmware_path, "p2p"))
\t\treturn -EPERM;''')
    result["rdawlan/wland_wid.c"] = text

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
    operation = replace(operation, '''up_exit:
\tmutex_unlock(&cfg->usr_sync);''', '''up_exit:
\t/* A failed initialization must not leave cfg80211 callbacks enabled. */
\tif (err)
\t\tclear_bit(VIF_STATUS_READY, &ifp->vif->sme_state);
\tmutex_unlock(&cfg->usr_sync);''')
    text = text[:start] + operation + text[end:]
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
    text = text[:start] + operation + text[end:]
    text = replace(text, '\t\t\tcfg->ctrl_scan_wait = false;',
                   '\t\t\tWRITE_ONCE(cfg->ctrl_scan_wait, false);')
    result["rdawlan/wland_cfg80211.c"] = text
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
