#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# One RDA5995 radio, one WPA2-PSK/CCMP or open AP/STA interface.
# OpenWrt uses BusyBox ash local variables and compound validation conditions.
# shellcheck disable=SC1091,SC2034,SC3043,SC2015
. /lib/netifd/netifd-wireless.sh
export LC_ALL=C

init_wireless_driver "$@"

drv_rda_init_device_config() {
	config_add_string phy path country
}

drv_rda_init_iface_config() {
	config_add_string ifname
	config_add_boolean hidden
}

drv_rda_init_vlan_config() { return 0; }
drv_rda_init_station_config() { return 0; }

drv_rda_cleanup() {
	return 0
}

rda_stop() {
	local pid exe n
	if [ -f /var/run/rda-radio/pid ]; then
		read -r pid < /var/run/rda-radio/pid
		case "$pid" in ''|*[!0-9]*) return 1;; esac
		exe="$(readlink -f "/proc/$pid/exe")"
		if [ "$exe" = /usr/sbin/wpad ]; then
			kill "$pid" 2>/dev/null
			for n in 1 2 3 4 5; do
				[ "$(readlink -f "/proc/$pid/exe")" = "$exe" ] || break
				sleep 1
			done
			[ "$(readlink -f "/proc/$pid/exe")" != "$exe" ] || kill -9 "$pid"
		fi
	fi
	if [ -d /sys/module/rdawfmac ]; then
		ip link set wlan0 down 2>/dev/null
		rmmod rdawfmac || return 1
	fi
	rm -f /var/run/rda-radio/pid /var/run/rda-radio/config
}

rda_read_iface() {
	local name="$1"
	rda_count=$((rda_count + 1))
	rda_section="$name"
	json_get_var rda_bridge bridge
	json_select config
	json_get_vars mode ssid encryption key hidden ifname
	json_select ..
}

rda_fail() {
	rda_stop
	wireless_setup_failed "$1"
	return 1
}

drv_rda_setup() {
	local mode ssid encryption key hidden ifname country band htmode channel
	local rda_count=0 rda_section rda_bridge firmware n pid phy ssid_hex escaped_key

	# Serialize module lifetimes without carrying the lock into daemon children.
	exec 9>/var/run/rda-radio.lock
	flock -n 9 || { wireless_setup_failed RADIO_BUSY; return 1; }
	json_select config
	json_get_vars country band htmode channel
	json_select ..
	for_each_interface "" rda_read_iface
	[ "$rda_count" = 1 ] || { wireless_setup_failed ONE_INTERFACE_REQUIRED; return 1; }
	[ -z "$ifname" ] || [ "$ifname" = wlan0 ] || {
		wireless_setup_failed IFNAME_MUST_BE_WLAN0; return 1;
	}
	case "$mode" in ap) firmware=ap;; sta) firmware=sta;;
		*) wireless_setup_failed UNSUPPORTED_MODE; return 1;; esac
	case "$band" in ''|2g) ;; *) wireless_setup_failed ONLY_2GHZ; return 1;; esac
	case "$htmode" in ''|HT20|NONE) ;; *) wireless_setup_failed ONLY_HT20; return 1;; esac
	[ "$mode" != sta ] || [ -z "$rda_bridge" ] || {
		wireless_setup_failed STA_REQUIRES_ROUTED_NETWORK; return 1;
	}
	case "$encryption" in none|'') encryption=none;; psk2|psk2+ccmp|psk2+aes) encryption=psk2;;
		*) wireless_setup_failed USE_WPA2_CCMP; return 1;; esac
	# All config values are data. SSIDs use hex, and embedded newlines are rejected.
	[ "$(printf '%s' "$ssid$key" | tr -d '\r\n')" = "$ssid$key" ] || {
		wireless_setup_failed INVALID_NEWLINE; return 1;
	}
	[ "${#ssid}" -ge 1 ] && [ "${#ssid}" -le 32 ] || {
		wireless_setup_failed INVALID_SSID; return 1;
	}
	if [ "$encryption" = psk2 ]; then
		case "$key" in
			*[!0-9a-fA-F]*|'')
				[ "${#key}" -ge 8 ] && [ "${#key}" -le 63 ] || {
					wireless_setup_failed INVALID_WPA_KEY; return 1;
				};;
			*) [ "${#key}" = 64 ] || {
				[ "${#key}" -ge 8 ] && [ "${#key}" -le 63 ] || {
					wireless_setup_failed INVALID_WPA_KEY; return 1;
				}
			};;
		esac
	fi
	case "$country" in ''|[A-Z][A-Z]) ;; *) wireless_setup_failed INVALID_COUNTRY; return 1;; esac
	if [ "$mode" = ap ]; then
		case "$channel" in 1|2|3|4|5|6|7|8|9|10|11|12|13) ;;
			*) wireless_setup_failed FIXED_2GHZ_CHANNEL_REQUIRED; return 1;; esac
	fi

	umask 077
	mkdir -p /var/run/rda-radio
	rda_stop || { wireless_setup_failed MODULE_UNLOAD_FAILED; return 1; }
	modprobe cfg80211 || { rda_fail CFG80211_LOAD_FAILED; return 1; }
	# ubox modprobe does not pass extra arguments as module parameters.
	insmod "/lib/modules/$(uname -r)/rdawfmac.ko" firmware_path="$firmware" || {
		rda_fail MODULE_LOAD_FAILED; return 1;
	}
	for n in 1 2 3 4 5 6 7 8 9 10; do
		[ -d /sys/class/net/wlan0/phy80211 ] && break
		sleep 1
	done
	[ -d /sys/class/net/wlan0/phy80211 ] || { rda_fail NO_WLAN; return 1; }
	[ "$(cat /sys/module/rdawfmac/parameters/firmware_path)" = "$firmware" ] || {
		rda_fail WRONG_FIRMWARE; return 1;
	}
	[ -z "$country" ] || iw reg set "$country" || { rda_fail COUNTRY_FAILED; return 1; }
	ssid_hex="$(printf '%s' "$ssid" | hexdump -ve '1/1 "%02x"')"
	if [ "$mode" = ap ]; then
		{
			printf 'driver=nl80211\ninterface=wlan0\nssid2=%s\nhw_mode=g\nchannel=%s\n' "$ssid_hex" "$channel"
			printf 'ctrl_interface=/var/run/hostapd-rda\nwmm_enabled=1\nauth_algs=1\n'
			[ "$htmode" = NONE ] || printf 'ieee80211n=1\n'
			[ -z "$rda_bridge" ] || printf 'bridge=%s\n' "$rda_bridge"
			[ "$hidden" != 1 ] || printf 'ignore_broadcast_ssid=1\n'
			if [ "$encryption" = psk2 ]; then
				printf 'wpa=2\nwpa_key_mgmt=WPA-PSK\nrsn_pairwise=CCMP\nieee80211w=0\n'
				if [ "${#key}" = 64 ]; then printf 'wpa_psk=%s\n' "$key"
				else printf 'wpa_passphrase=%s\n' "$key"; fi
			fi
		} > /var/run/rda-radio/config
		hostapd /var/run/rda-radio/config </dev/null > /var/run/rda-radio/log 2>&1 9>&- &
		pid=$!
	else
		escaped_key="$(printf '%s' "$key" | sed 's/\\/\\\\/g;s/"/\\"/g')"
		{
			printf 'ctrl_interface=/var/run/wpa_supplicant-rda\nnetwork={\n ssid=%s\n scan_ssid=1\n' "$ssid_hex"
			if [ "$encryption" = psk2 ]; then
				printf ' key_mgmt=WPA-PSK\n proto=RSN\n pairwise=CCMP\n group=CCMP\n ieee80211w=0\n'
				if [ "${#key}" = 64 ]; then printf ' psk=%s\n' "$key"
				else printf ' psk="%s"\n' "$escaped_key"; fi
			else printf ' key_mgmt=NONE\n'; fi
			printf '}\n'
		} > /var/run/rda-radio/config
		wpa_supplicant -D nl80211 -i wlan0 -c /var/run/rda-radio/config </dev/null > /var/run/rda-radio/log 2>&1 9>&- &
		pid=$!
	fi
	printf '%s\n' "$pid" > /var/run/rda-radio/pid
	for n in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
		sleep 1
		kill -0 "$pid" 2>/dev/null || { rda_fail DAEMON_FAILED; return 1; }
		[ "$mode" = sta ] && break
		grep -q AP-ENABLED /var/run/rda-radio/log && break
	done
	if [ "$mode" = ap ]; then
		grep -q AP-ENABLED /var/run/rda-radio/log || { rda_fail AP_TIMEOUT; return 1; }
	fi
	phy="$(basename "$(readlink -f /sys/class/net/wlan0/phy80211)")"
	wireless_set_data phy="$phy"
	wireless_add_process "$pid" /usr/sbin/wpad 1
	wireless_add_vif "$rda_section" wlan0
	wireless_set_up
}

drv_rda_teardown() {
	exec 9>/var/run/rda-radio.lock
	flock -n 9 || return 1
	rda_stop
}

add_driver rda
