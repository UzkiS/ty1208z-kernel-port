#!/bin/sh
# Test fixture executed only by the isolated QEMU harness; all writes are in RAM.
set -eu
tr '\000' '\n' < /sys/firmware/devicetree/base/compatible | grep -qx linux,dummy-virt

finish() {
    result=$?
    trap - EXIT
    # Preserve all failure diagnostics and reach poweroff even if a service
    # failed to start or a diagnostic command itself returns an error.
    set +e
    if [ "$result" -eq 0 ]; then
        echo OPENWRT_APPLICATIONS_QEMU_PASS
    else
        echo "OPENWRT_APPLICATIONS_QEMU_FAIL status=$result"
        cat /tmp/time64-test/*.log /tmp/etc/passwall/*.log 2>/dev/null || true
        cat /tmp/etc/passwall/vless-*.json 2>/dev/null || true
        ps w
        cat /tmp/time64-test/luci.txt 2>/dev/null || true
        curl --noproxy '*' -v --max-time 5 http://127.0.0.1/cgi-bin/luci/ 2>&1 || true
        logread | tail -n 40
        uci show uhttpd
        cat /tmp/time64-test/router-*.log /tmp/time64-test/router-*.txt 2>/dev/null || true
        cat /tmp/log/passwall.log 2>/dev/null || true
    fi
    poweroff -f
}
trap finish EXIT

wait_http() {
    attempts=0
    until curl --noproxy '*' -fsS --max-time 2 "$1" > "$2" 2>/dev/null; do
        attempts=$((attempts+1))
        [ "$attempts" -lt 30 ] || return 1
        sleep 1
    done
}

wait_luci_login() {
    attempts=0
    while :; do
        # Current LuCI returns 403 with its login form to unauthenticated users.
        # Require that exact response instead of treating every HTTP error as OK.
        status=$(curl --noproxy '*' -sS --max-time 3 -D luci.headers \
            -o luci.txt -w '%{http_code}' http://127.0.0.1/cgi-bin/luci/ 2>/dev/null) || status=000
        if [ "$status" = 403 ] && grep -qi '^x-luci-login-required: yes' luci.headers \
                && grep -q 'bootstrap.sysauth' luci.txt \
                && grep -q 'name="luci_password"' luci.txt; then
            return 0
        fi
        attempts=$((attempts+1))
        [ "$attempts" -lt 30 ] || return 1
        sleep 1
    done
}

reject_expired_proxy() {
    attempts=0
    while :; do
        if curl --noproxy '' -fsS --max-time 5 --socks5-hostname "127.0.0.1:$1" \
                --cacert ca.pem https://time64.test:18443/ > "$3.txt" 2> "$3-client.log"; then
            echo "Proxy on port $1 accepted an expired TLS certificate"
            return 1
        fi
        # A failed connection alone is insufficient. Wait for the core's real
        # expiry error; startup/log scheduling must not masquerade as success.
        if grep -qi 'certificate has expired' "$2" 2>/dev/null; then return 0; fi
        attempts=$((attempts+1))
        [ "$attempts" -lt 10 ] || return 1
        sleep 1
    done
}

mkdir -p /tmp/time64-test/www /tmp/log
cd /tmp/time64-test
attempts=0
until ubus call system board > board.json 2>/dev/null && [ -S /dev/log ]; do
    attempts=$((attempts+1))
    [ "$attempts" -lt 30 ] || exit 1
    sleep 1
done

# Passwall's boot handler runs asynchronously after its configured delay and
# clears TMP_PATH on restart. Let it finish before starting fixture instances.
attempts=0
until [ -f /var/lock/passwall_ready.lock ]; do
    attempts=$((attempts+1))
    [ "$attempts" -lt 120 ] || exit 1
    sleep 1
done
/etc/init.d/passwall stop > passwall-stop.log 2>&1
echo PASSWALL_BOOT_READY
# Check startup before clock synchronization as well as the future TLS tests.
# This script is guarded to the isolated QEMU guest above.
date -u -s @0
xray version > xray-unsynchronized.txt 2>&1
grep -q '^Xray 26\.10\.10 ' xray-unsynchronized.txt
echo XRAY_UNSYNCHRONIZED_CLOCK_PASS
sh /tmp/ntp-runtime-test.sh

# A valid CA spans both dates. An old leaf certificate must expire in 2040.
date -u -s @1791676800
openssl req -x509 -newkey rsa:2048 -nodes -keyout ca.key -out ca.pem \
    -subj /CN=TY1208Z-QEMU-Test-CA -days 6000 > cert.log 2>&1
openssl req -newkey rsa:2048 -nodes -keyout server.key -out server.csr \
    -subj /CN=time64.test >> cert.log 2>&1
printf '%s\n' 'subjectAltName=DNS:time64.test' > leaf.ext
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial \
    -out expired.pem -days 1 -extfile leaf.ext >> cert.log 2>&1
time64-probe --set-clock-2040
test "$(date -u +%Y)" = 2040
touch stamp
test "$(stat -c %Y stamp)" -ge 2208988800
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial \
    -out valid.pem -days 365 -extfile leaf.ext >> cert.log 2>&1
openssl verify -CAfile ca.pem valid.pem
if openssl verify -CAfile ca.pem expired.pem >> cert.log 2>&1; then
    echo 'Expired certificate was accepted'
    exit 1
fi
echo CERTIFICATE_TIME64_PASS

unzip -v > unzip-version.txt
grep -q 'UnZip 6.00' unzip-version.txt
LC_ALL=C.UTF-8 unzip -t /tmp/unzip-fixture.zip > unzip-test.log
LC_ALL=C.UTF-8 unzip -q /tmp/unzip-fixture.zip -d unzip-output
(cd unzip-output && sha256sum -c SHA256SUMS)
test "$(stat -c %Y unzip-output/deflated.txt)" = 2208988800
test -f 'unzip-output/中文目录/中文文件.txt'
test ! -s unzip-output/empty.txt
echo UNZIP_ARCHIVE_TIME64_PASS

# Use the installed dnsmasq implementation without external DNS or a WAN.
/etc/init.d/dnsmasq stop
attempts=0
until ! pidof dnsmasq > /dev/null; do
    attempts=$((attempts+1))
    [ "$attempts" -lt 10 ] || exit 1
    sleep 1
done
dnsmasq --keep-in-foreground --conf-file=/dev/null --no-resolv --no-hosts \
    --listen-address=127.0.0.1 --bind-interfaces --address=/time64.test/127.0.0.1 \
    --local=/time64.test/ \
    --pid-file=/tmp/time64-test/dnsmasq.pid > dnsmasq.log 2>&1 &
dns_fixture_pid=$!
printf 'nameserver 127.0.0.1\n' > /tmp/resolv.conf
attempts=0
until resolveip -4 -t 2 time64.test > dns.txt 2>/dev/null; do
    kill -0 "$dns_fixture_pid" || exit 1
    attempts=$((attempts+1))
    [ "$attempts" -lt 20 ] || exit 1
    sleep 1
done
kill -0 "$dns_fixture_pid"
grep -qx 127.0.0.1 dns.txt
echo DNS_TIME64_PASS
echo '=== resolver immediately before TLS ==='
cat /etc/resolv.conf
resolveip -4 -t 2 time64.test
curl --version > curl-version.txt
cat curl-version.txt
grep -q 'Features:.*AsynchDNS' curl-version.txt

printf 'TY1208Z_LOCAL_PAYLOAD_2040\n' > www/index.html
uhttpd -f -p 127.0.0.1:18080 -s 127.0.0.1:18443 -h /tmp/time64-test/www \
    -C /tmp/time64-test/valid.pem -K /tmp/time64-test/server.key > uhttpd.log 2>&1 &
uhttpd -f -s 127.0.0.1:18444 -h /tmp/time64-test/www \
    -C /tmp/time64-test/expired.pem -K /tmp/time64-test/server.key > expired.log 2>&1 &
wait_http http://127.0.0.1:18080/ direct.txt
grep -qx TY1208Z_LOCAL_PAYLOAD_2040 direct.txt
if ! curl --noproxy '*' -fvS --max-time 10 --cacert ca.pem \
        https://time64.test:18443/ > tls.txt 2> tls-client.log; then
    curl -4 --noproxy '*' -fvS --max-time 10 --cacert ca.pem \
        https://time64.test:18443/ > tls-ipv4.txt 2> tls-ipv4.log || true
    exit 1
fi
grep -qx TY1208Z_LOCAL_PAYLOAD_2040 tls.txt
if curl --noproxy '*' -fsS --max-time 10 https://time64.test:18443/ > /dev/null 2> untrusted.log; then
    echo 'Untrusted certificate was accepted'
    exit 1
else
    test "$?" -eq 60
fi
if curl --noproxy '*' -fsS --max-time 10 --cacert ca.pem \
        https://time64.test:18444/ > /dev/null 2> expired-tls.log; then
    echo 'Expired HTTPS certificate was accepted'
    exit 1
else
    test "$?" -eq 60
fi
echo HTTPS_TIME64_PASS

uci set uhttpd.main.redirect_https=0
uci commit uhttpd
/etc/init.d/uhttpd restart
echo LUCI_PAGE_CHECK_START
wait_luci_login
test "$(uci get luci.main.lang)" = zh_cn
grep -q 'lang="zh-cn"' luci.txt
grep -q '用户名' luci.txt
grep -q '密码' luci.txt
echo LUCI_CHINESE_DEFAULT_PASS
echo RPCD_SESSION_CHECK_START
ubus call session create '{"timeout":60}' > session.json
jsonfilter -i session.json -e @.ubus_rpc_session | grep -Eq '^[0-9a-f]{32}$'
echo PASSWALL_LUA_CHECK_START
lua -e 'assert(require("luci.passwall.api"))'
status=$(curl --noproxy '*' -sS --max-time 30 -D empty-login.headers -c empty-login.cookies \
    --data-urlencode luci_username=root --data-urlencode luci_password= \
    -o empty-login.html -w '%{http_code}' http://127.0.0.1/cgi-bin/luci/admin/services/passwall)
test "$status" = 302
grep -qi '^set-cookie: sysauth_http=' empty-login.headers
curl --noproxy '*' -fsS --max-time 30 -b empty-login.cookies \
    http://127.0.0.1/cgi-bin/luci/admin/services/passwall > empty-passwall-page.html
grep -qi passwall empty-passwall-page.html
if grep -q 'bootstrap.sysauth' empty-passwall-page.html; then exit 1; fi
echo LUCI_EMPTY_ROOT_LOGIN_PASS
# This fixture password exists only in the diskless, network-isolated guest.
printf 'qemu-fixture-only\nqemu-fixture-only\n' | passwd root > passwd.log 2>&1
status=$(curl --noproxy '*' -sS --max-time 30 -D login.headers -c login.cookies \
    --data-urlencode luci_username=root --data-urlencode luci_password=qemu-fixture-only \
    -o login.html -w '%{http_code}' http://127.0.0.1/cgi-bin/luci/admin/services/passwall)
test "$status" = 302
grep -qi '^set-cookie: sysauth_http=' login.headers
curl --noproxy '*' -fsS --max-time 30 -b login.cookies \
    http://127.0.0.1/cgi-bin/luci/admin/services/passwall > passwall-page.html
grep -qi passwall passwall-page.html
if grep -q 'bootstrap.sysauth' passwall-page.html; then
    echo 'Authenticated Passwall page returned the login form'
    exit 1
fi
echo PASSWALL_LUCI_AUTH_TIME64_PASS
echo LUCI_RPCD_TIME64_PASS

# Exercise real Passwall Lua/config/start logic, Xray and a local upstream SOCKS.
# This validates the controller's SOCKS path; board/WAN TPROXY is a separate gate.
microsocks -i 127.0.0.1 -p 18081 > microsocks.log 2>&1 &
uci set passwall.qemu=nodes
uci set passwall.qemu.type=Xray
uci set passwall.qemu.protocol=socks
uci set passwall.qemu.address=127.0.0.1
uci set passwall.qemu.port=18081
uci set passwall.qemu.remarks=QEMU-local-only
uci commit passwall
mkdir -p /tmp/etc/passwall/bin /tmp/etc/passwall/script_func /tmp/etc/passwall/acl
controller_status=0
sh /usr/share/passwall/app.sh run_socks flag=time64 node=qemu bind=127.0.0.1 \
    socks_port=18082 config_file=qemu.json log_file=qemu.log > controller.log 2>&1 || controller_status=$?
# The pinned run_socks ends with a conditional direct_node_list append, which
# returns 1 for loopback Xray nodes. Require a real config and working payload
# below; the controller's exit status alone cannot establish success.
case "$controller_status" in 0|1) ;; *) cat controller.log; exit 1 ;; esac
test -s /tmp/etc/passwall/qemu.json
xray run -test -c /tmp/etc/passwall/qemu.json > xray-test.log 2>&1
attempts=0
until curl --noproxy '' -fsS --max-time 3 --socks5-hostname 127.0.0.1:18082 \
        --cacert ca.pem https://time64.test:18443/ > proxy.txt 2> proxy.log; do
    attempts=$((attempts+1))
    [ "$attempts" -lt 20 ] || exit 1
    sleep 1
done
grep -qx TY1208Z_LOCAL_PAYLOAD_2040 proxy.txt
echo PASSWALL_XRAY_SOCKS_TIME64_PASS

# Exercise Xray's own TLS time checks, independently of curl's endpoint TLS.
# Xray defaults to its embedded root bundle. Supply the fixture CA through
# Passwall's real custom-CA option; keep hostname/date verification enabled.
for server in valid expired; do
    # Xray's server freedom default blocks loopback targets. Allow the isolated
    # local fixture endpoint; this guest exposes no disks or host network.
    if [ "$server" = valid ]; then listen_port=18445; else listen_port=18446; fi
    cat > "vless-$server.json" <<EOF
{"log":{"loglevel":"debug"},"inbounds":[{"listen":"127.0.0.1","port":$listen_port,
"protocol":"vless","settings":{"clients":[{"id":"e38831d8-39ba-4ad8-a96d-3ef6988a7803"}],"decryption":"none"},
"streamSettings":{"network":"tcp","security":"tls","tlsSettings":{"certificates":[{
"certificateFile":"/tmp/time64-test/$server.pem","keyFile":"/tmp/time64-test/server.key"}]}}}],
"outbounds":[{"protocol":"freedom","settings":{"finalRules":[{"action":"allow"}]}}]}
EOF
    xray run -test -c "vless-$server.json" > "vless-$server-test.log" 2>&1
    xray run -c "vless-$server.json" > "vless-$server-server.log" 2>&1 &
    node=qemu_vless_$server
    if [ "$server" = valid ]; then socks_port=18083; else socks_port=18084; fi
    uci set "passwall.$node=nodes"
    uci set "passwall.$node.type=Xray"
    uci set "passwall.$node.protocol=vless"
    uci set "passwall.$node.address=127.0.0.1"
    uci set "passwall.$node.port=$listen_port"
    uci set "passwall.$node.uuid=e38831d8-39ba-4ad8-a96d-3ef6988a7803"
    uci set "passwall.$node.encryption=none"
    uci set "passwall.$node.transport=tcp"
    uci set "passwall.$node.tls=1"
    uci set "passwall.$node.tls_serverName=time64.test"
    uci set "passwall.$node.tls_certificate=1"
    uci set "passwall.$node.tls_certificate_pem=$(cat ca.pem)"
    uci commit passwall
    controller_status=0
    sh /usr/share/passwall/app.sh run_socks "flag=vless_$server" "node=$node" bind=127.0.0.1 \
        "socks_port=$socks_port" "config_file=vless-$server.json" "log_file=vless-$server.log" loglevel=debug \
        > "vless-$server-controller.log" 2>&1 || controller_status=$?
    case "$controller_status" in 0|1) ;; *) exit 1 ;; esac
    test -s "/tmp/etc/passwall/vless-$server.json"
    xray run -test -c "/tmp/etc/passwall/vless-$server.json" > "vless-$server-client-test.log" 2>&1
    echo "PASSWALL_VLESS_CONFIG_READY server=$server status=$controller_status"
done
attempts=0
until curl --noproxy '' -fsS --max-time 3 --socks5-hostname 127.0.0.1:18083 \
        --cacert ca.pem https://time64.test:18443/ > vless.txt 2> vless-client.log; do
    attempts=$((attempts+1))
    [ "$attempts" -lt 20 ] || exit 1
    sleep 1
done
grep -qx TY1208Z_LOCAL_PAYLOAD_2040 vless.txt
reject_expired_proxy 18084 /tmp/etc/passwall/vless-expired.log vless-expired
echo PASSWALL_XRAY_TLS_TIME64_PASS

# Use Passwall's real sing-box generator/controller and the same local fixtures.
sing-box version > sing-box-version.txt
grep -q '^sing-box version 1\.14\.3' sing-box-version.txt
uci set passwall.qemu_singbox=nodes
uci set passwall.qemu_singbox.type=sing-box
uci set passwall.qemu_singbox.protocol=socks
uci set passwall.qemu_singbox.address=127.0.0.1
uci set passwall.qemu_singbox.port=18081
uci set passwall.qemu_singbox.remarks=QEMU-sing-box-local-only
uci commit passwall
controller_status=0
sh /usr/share/passwall/app.sh run_socks flag=singbox_time64 node=qemu_singbox bind=127.0.0.1 \
    socks_port=18085 config_file=singbox.json log_file=singbox.log > singbox-controller.log 2>&1 || controller_status=$?
case "$controller_status" in 0|1) ;; *) cat singbox-controller.log; exit 1 ;; esac
test -s /tmp/etc/passwall/singbox.json
sing-box check -c /tmp/etc/passwall/singbox.json > singbox-check.log 2>&1
attempts=0
until curl --noproxy '' -fsS --max-time 3 --socks5-hostname 127.0.0.1:18085 \
        --cacert ca.pem https://time64.test:18443/ > singbox-proxy.txt 2> singbox-proxy.log; do
    attempts=$((attempts+1))
    [ "$attempts" -lt 20 ] || exit 1
    sleep 1
done
grep -qx TY1208Z_LOCAL_PAYLOAD_2040 singbox-proxy.txt
echo PASSWALL_SINGBOX_SOCKS_TIME64_PASS

for server in valid expired; do
    node=qemu_singbox_vless_$server
    if [ "$server" = valid ]; then listen_port=18445; socks_port=18086
    else listen_port=18446; socks_port=18087; fi
    uci set "passwall.$node=nodes"
    uci set "passwall.$node.type=sing-box"
    uci set "passwall.$node.protocol=vless"
    uci set "passwall.$node.address=127.0.0.1"
    uci set "passwall.$node.port=$listen_port"
    uci set "passwall.$node.uuid=e38831d8-39ba-4ad8-a96d-3ef6988a7803"
    uci set "passwall.$node.transport=tcp"
    uci set "passwall.$node.tls=1"
    uci set "passwall.$node.tls_serverName=time64.test"
    uci set "passwall.$node.tls_certificate=1"
    uci set "passwall.$node.tls_certificate_pem=$(cat ca.pem)"
    uci commit passwall
    controller_status=0
    sh /usr/share/passwall/app.sh run_socks "flag=singbox_vless_$server" "node=$node" bind=127.0.0.1 \
        "socks_port=$socks_port" "config_file=singbox-vless-$server.json" \
        "log_file=singbox-vless-$server.log" loglevel=debug \
        > "singbox-vless-$server-controller.log" 2>&1 || controller_status=$?
    case "$controller_status" in 0|1) ;; *) exit 1 ;; esac
    test -s "/tmp/etc/passwall/singbox-vless-$server.json"
    sing-box check -c "/tmp/etc/passwall/singbox-vless-$server.json" \
        > "singbox-vless-$server-check.log" 2>&1
done
attempts=0
until curl --noproxy '' -fsS --max-time 3 --socks5-hostname 127.0.0.1:18086 \
        --cacert ca.pem https://time64.test:18443/ > singbox-vless.txt 2> singbox-vless-client.log; do
    attempts=$((attempts+1))
    [ "$attempts" -lt 20 ] || exit 1
    sleep 1
done
grep -qx TY1208Z_LOCAL_PAYLOAD_2040 singbox-vless.txt
reject_expired_proxy 18087 /tmp/etc/passwall/singbox-vless-expired.log singbox-expired
echo PASSWALL_SINGBOX_TLS_TIME64_PASS
# Release these extra processes before the independent router/TPROXY fixture.
killall sing-box

# Confirm real kernel rules/counters and socket/TPROXY expression availability.
nft add table inet time64
nft 'add chain inet time64 output { type filter hook output priority 0; policy accept; }'
nft add rule inet time64 output tcp dport 18080 counter
curl --noproxy '*' -fsS --max-time 10 http://127.0.0.1:18080/ > /dev/null
nft list chain inet time64 output > nft.txt
grep -Eq 'counter packets [1-9][0-9]*' nft.txt
nft 'add chain inet time64 prerouting { type filter hook prerouting priority mangle; policy accept; }'
nft add rule inet time64 prerouting meta l4proto tcp socket transparent 1 counter
nft add rule inet time64 prerouting tcp dport 19000 tproxy to :19001 meta mark set 1 accept
nft list table inet time64
nft delete table inet time64
echo NFT_EXPRESSIONS_AND_COUNTER_PASS
if [ -f /opt/qemu-container-fixtures/guest.sh ]; then
    sh /opt/qemu-container-fixtures/guest.sh setup
fi
if [ -f /tmp/router-runtime-test.sh ]; then
    sh /tmp/router-runtime-test.sh
fi
if [ -f /opt/qemu-container-fixtures/guest.sh ]; then
    sh /opt/qemu-container-fixtures/guest.sh verify-cleanup
fi
logger -t time64 OPENWRT_APPLICATIONS_LOG_2040
sleep 1
logread -e OPENWRT_APPLICATIONS_LOG_2040 | grep 2040
test "$(date -u +%Y)" = 2040
