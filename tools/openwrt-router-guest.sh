#!/bin/sh
# Runs only inside the isolated ARM QEMU guest. All topology/config writes are RAM.
set -eu
tr '\000' '\n' < /sys/firmware/devicetree/base/compatible | grep -qx linux,dummy-virt
test "$(date -u +%Y)" = 2040
cd /tmp/time64-test

modprobe veth
ip netns add qemu_client
ip netns add qemu_origin
ip link add qemu-client type veth peer name client-peer
ip link add qemu-origin type veth peer name origin-peer
ip link set client-peer netns qemu_client
ip link set origin-peer netns qemu_origin
ip -n qemu_client link set lo up
ip -n qemu_origin link set lo up
ip -n qemu_client address add 192.0.2.2/24 dev client-peer
ip -n qemu_client link set client-peer up
ip -n qemu_client route add default via 192.0.2.1
ip -n qemu_origin address add 198.51.100.2/24 dev origin-peer
ip -n qemu_origin address add 198.19.0.2/32 dev lo
ip -n qemu_origin link set origin-peer up
ip -n qemu_origin route add default via 198.51.100.1

# Require the real netifd daemon to configure both router-side links/routes.
for side in client origin; do
    uci set "network.qemu_$side=interface"
    uci set "network.qemu_$side.device=qemu-$side"
    uci set "network.qemu_$side.proto=static"
    uci set "network.qemu_$side.netmask=255.255.255.0"
done
uci set network.qemu_client.ipaddr=192.0.2.1
uci set network.qemu_origin.ipaddr=198.51.100.1
uci set network.qemu_origin_route=route
uci set network.qemu_origin_route.interface=qemu_origin
uci set network.qemu_origin_route.target=198.19.0.2/32
uci set network.qemu_origin_route.gateway=198.51.100.2
uci commit network
/etc/init.d/network reload
attempts=0
until ubus call network.interface.qemu_client status > router-client-status.json &&
        ubus call network.interface.qemu_origin status > router-origin-status.json &&
        [ "$(jsonfilter -i router-client-status.json -e '@.up')" = true ] &&
        [ "$(jsonfilter -i router-origin-status.json -e '@.up')" = true ] &&
        ip route get 198.19.0.2 | grep -q 'via 198.51.100.2'; do
    attempts=$((attempts+1))
    [ "$attempts" -lt 30 ] || exit 1
    sleep 1
done
sysctl -w net.ipv4.ip_forward=1

# Exercise fw4-generated forwarding, rather than replacing its policy with a stub.
for side in client origin; do
    uci set "firewall.qemu_$side=zone"
    uci set "firewall.qemu_$side.name=qemu_$side"
    uci set "firewall.qemu_$side.network=qemu_$side"
    uci set "firewall.qemu_$side.input=ACCEPT"
    uci set "firewall.qemu_$side.output=ACCEPT"
    uci set "firewall.qemu_$side.forward=REJECT"
done
uci set firewall.qemu_forward=forwarding
uci set firewall.qemu_forward.src=qemu_client
uci set firewall.qemu_forward.dest=qemu_origin
uci commit firewall
fw4 check
/etc/init.d/firewall reload
nft add table inet router_test
nft 'add chain inet router_test forward { type filter hook forward priority 5; policy accept; }'
nft add rule inet router_test forward iifname qemu-client ip saddr 192.0.2.2 \
    ip daddr 198.19.0.2 tcp dport 19443 counter

ip netns exec qemu_origin uhttpd -f -s 198.19.0.2:19443 -h /tmp/time64-test/www \
    -C /tmp/time64-test/valid.pem -K /tmp/time64-test/server.key > router-origin.log 2>&1 &
attempts=0
until ip netns exec qemu_client curl --noproxy '*' -fsS --max-time 3 \
        --resolve time64.test:19443:198.19.0.2 --cacert ca.pem \
        https://time64.test:19443/ > router-forward.txt 2> router-forward.log; do
    attempts=$((attempts+1))
    [ "$attempts" -lt 20 ] || exit 1
    sleep 1
done
grep -qx TY1208Z_LOCAL_PAYLOAD_2040 router-forward.txt
nft list chain inet router_test forward > router-forward-counters.txt
grep -Eq 'counter packets [1-9][0-9]*' router-forward-counters.txt
cat router-forward-counters.txt
echo OPENWRT_ROUTER_FORWARDING_TIME64_PASS

# A real UDP endpoint also verifies the reply path. Small bounded iperf
# transfers establish data delivery, never an emulated throughput claim.
ip netns exec qemu_origin iperf3 -s -B 198.19.0.2 -p 19553 \
    > router-udp-origin.log 2>&1 &
udp_origin_pid=$!
udp_transfer() {
    ip netns exec qemu_client iperf3 -c 198.19.0.2 -p 19553 -u \
        -b 128K -l 512 -t 3 --connect-timeout 2000 --rcv-timeout 4000 -J "$@"
}
attempts=0
until udp_transfer > router-udp-forward.json 2> router-udp-forward.log; do
    attempts=$((attempts+1))
    [ "$attempts" -lt 10 ] || exit 1
    sleep 1
done
test "$(jsonfilter -i router-udp-forward.json -e '@.end.sum_received.bytes')" -gt 4096
test "$(jsonfilter -i router-udp-forward.json -e '@.end.sum_received.packets')" -gt 10

# Remove forwarding. Direct HTTPS must fail before and after the proxy run;
# success while Passwall is enabled therefore cannot be ordinary forwarding.
uci delete firewall.qemu_forward
uci commit firewall
/etc/init.d/firewall reload
if ip netns exec qemu_client curl --noproxy '*' -fsS --max-time 4 \
        --resolve time64.test:19443:198.19.0.2 --cacert ca.pem \
        https://time64.test:19443/ > router-bypass.txt 2> router-bypass.log; then
    echo 'Unexpected direct forwarding before transparent proxy'
    exit 1
fi
if udp_transfer > router-udp-bypass.json 2> router-udp-bypass.log; then
    echo 'Unexpected direct UDP/control forwarding before transparent proxy'
    exit 1
fi

# Use the installed Passwall service, its generated Xray redir config, nft
# rules and policy routing. The existing fixture's VLESS/TLS server is local.
uci set 'passwall.@global[0].enabled=1'
uci set 'passwall.@global[0].node=qemu_vless_valid'
uci set 'passwall.@global[0].client_proxy=1'
uci set 'passwall.@global[0].localhost_proxy=0'
uci set 'passwall.@global[0].tcp_proxy_mode=proxy'
uci set 'passwall.@global[0].udp_proxy_mode=proxy'
uci set 'passwall.@global[0].use_direct_list=0'
uci set 'passwall.@global[0].use_proxy_list=0'
uci set 'passwall.@global[0].use_block_list=0'
uci set 'passwall.@global[0].use_gfw_list=0'
uci set 'passwall.@global[0].chn_list=0'
uci set 'passwall.@global[0].dns_redirect=0'
uci set 'passwall.@global[0].remote_dns=127.0.0.1'
uci set 'passwall.@global_forwarding[0].tcp_proxy_way=tproxy'
uci set 'passwall.@global_forwarding[0].tcp_redir_ports=19443,19553'
uci set 'passwall.@global_forwarding[0].tcp_no_redir_ports=disable'
uci set 'passwall.@global_forwarding[0].udp_redir_ports=19553'
uci set 'passwall.@global_forwarding[0].udp_no_redir_ports=disable'
uci set 'passwall.@global_forwarding[0].ipv6_tproxy=0'
uci commit passwall
/etc/init.d/passwall start > router-passwall-start.log 2>&1
attempts=0
until ip netns exec qemu_client curl --noproxy '*' -fsS --max-time 3 \
        --resolve time64.test:19443:198.19.0.2 --cacert ca.pem \
        https://time64.test:19443/ > router-tproxy.txt 2> router-tproxy.log; do
    attempts=$((attempts+1))
    [ "$attempts" -lt 20 ] || exit 1
    sleep 1
done
grep -qx TY1208Z_LOCAL_PAYLOAD_2040 router-tproxy.txt
udp_transfer > router-udp-tproxy.json 2> router-udp-tproxy.log
test "$(jsonfilter -i router-udp-tproxy.json -e '@.end.sum_received.bytes')" -gt 4096
test "$(jsonfilter -i router-udp-tproxy.json -e '@.end.sum_received.packets')" -gt 10
udp_transfer -R > router-udp-reverse.json 2> router-udp-reverse.log
test "$(jsonfilter -i router-udp-reverse.json -e '@.end.sum_received.bytes')" -gt 4096
test "$(jsonfilter -i router-udp-reverse.json -e '@.end.sum_received.packets')" -gt 10
nft list table inet passwall > router-passwall-rules.txt
grep -Eq 'counter packets [1-9][0-9]*.*tproxy ip to' router-passwall-rules.txt
grep -Eq 'udp.*counter packets [1-9][0-9]*.*tproxy ip to' router-passwall-rules.txt
ip rule > router-policy-rules.txt
grep -q 'lookup 999' router-policy-rules.txt
ip route show table 999 | grep -q 'local default dev lo'
cat router-policy-rules.txt
grep 'tproxy ip to' router-passwall-rules.txt
/etc/init.d/passwall stop > router-passwall-stop.log 2>&1
if ip netns exec qemu_client curl --noproxy '*' -fsS --max-time 4 \
        --resolve time64.test:19443:198.19.0.2 --cacert ca.pem \
        https://time64.test:19443/ > router-after-stop.txt 2> router-after-stop.log; then
    echo 'Unexpected forwarding after transparent proxy stopped'
    exit 1
fi
if udp_transfer > router-udp-after-stop.json 2> router-udp-after-stop.log; then
    echo 'Unexpected UDP/control forwarding after transparent proxy stopped'
    exit 1
fi
kill "$udp_origin_pid"
test "$(date -u +%Y)" = 2040
echo PASSWALL_TPROXY_TCP_TIME64_PASS
echo PASSWALL_TPROXY_UDP_TIME64_PASS
