#!/bin/sh
# Actual OpenWrt procd/fw4/Docker composition, isolated QEMU RAM only.
set -eu
tr '\000' '\n' < /sys/firmware/devicetree/base/compatible | grep -qx linux,dummy-virt
grep -qw 'ty1208z.qemu_container_apps=1' /proc/cmdline
test "$(date -u +%Y)" = 2040
cd /tmp/time64-test
docker() { /usr/bin/docker -H unix:///var/run/docker.sock "$@"; }
fixture=/opt/qemu-container-fixtures

case "${1:-}" in
setup)
    grep -q ' / tmpfs ' /proc/mounts
    echo CONTAINER_APPLICATIONS_QEMU_NATIVE_TMPFS_ROOT_PASS
    test -x /usr/bin/dockerd
    test -x /sbin/fw4
    # Official firewall4 supplies an fw3 compatibility symlink. Reject an
    # independent legacy binary, while accepting that exact native alias.
    if [ -e /sbin/fw3 ]; then
        test -L /sbin/fw3
        test "$(readlink -f /sbin/fw3)" = /sbin/fw4
    fi
    test ! -e /etc/init.d/firewall3
    mkdir -p /sys/fs/cgroup
    if ! grep -q ' /sys/fs/cgroup cgroup2 ' /proc/mounts; then
        mount -t cgroup2 -o nsdelegate cgroup2 /sys/fs/cgroup
    fi
    cp /etc/config/dockerd /tmp/combined-dockerd-original
    cp /etc/config/network /tmp/combined-network-original
    cp /etc/config/firewall /tmp/combined-firewall-original
    /etc/init.d/dockerd stop
    mkdir -p /tmp/combined-docker-data /tmp/combined-docker-exec
    cat >/tmp/combined-docker-daemon.json <<'JSON'
{"features":{"containerd-snapshotter":false},"data-root":"/tmp/combined-docker-data","exec-root":"/tmp/combined-docker-exec","hosts":["unix:///var/run/docker.sock"],"storage-driver":"overlay2","exec-opts":["native.cgroupdriver=cgroupfs"],"iptables":true,"ip6tables":false,"userland-proxy":false,"init-path":"/usr/bin/tini"}
JSON
    uci set dockerd.globals.alt_config_file=/tmp/combined-docker-daemon.json
    uci commit dockerd
    /etc/init.d/dockerd uciadd
    /etc/init.d/dockerd start
    attempts=0
    until docker info >combined-docker-info.json 2>combined-docker-start.log; do
        attempts=$((attempts+1))
        [ "$attempts" -lt 30 ] || exit 1
        sleep 2
    done
    /etc/init.d/dockerd running
    ubus call service list '{"name":"dockerd"}' >combined-docker-procd.json
    test "$(jsonfilter -i combined-docker-procd.json -e '@.dockerd.instances.instance1.running')" = true
    test "$(docker info --format '{{.Driver}}')" = overlay2
    test "$(docker info --format '{{.CgroupVersion}}')" = 2
    test "$(docker info --format '{{.Architecture}}')" = armv7l
    docker load -i "$fixture/container-image.tar"
    docker run --rm --network none --memory 64m --cpus 0.5 --pids-limit 32 \
        ty1208z-busybox:local /bin/busybox sh -c '
        set -eu
        test "$$" = 1
        test "$(/bin/busybox cat /sys/fs/cgroup/memory.max)" = 67108864
        test "$(/bin/busybox cat /sys/fs/cgroup/cpu.max)" = "50000 100000"
        test "$(/bin/busybox cat /sys/fs/cgroup/pids.max)" = 32
        /bin/busybox grep -Eq "^Seccomp:[[:space:]]+2$" /proc/self/status
        /bin/resource-probe cpu
        /bin/busybox awk '\''$1 == "nr_throttled" { found=1; if ($2 == 0) exit 1 } END { if (!found) exit 1 }'\'' /sys/fs/cgroup/cpu.stat
        echo future >/writable-file
        test "$(/bin/busybox stat -c %Y /writable-file)" -ge 2208988800'
    docker create --name combined-oom --network none --memory 32m ty1208z-busybox:local /bin/resource-probe oom
    if docker start -a combined-oom; then exit 1; else result=$?; test "$result" = 137; fi
    test "$(docker inspect --format '{{.State.OOMKilled}}' combined-oom)" = true
    docker rm combined-oom
    docker run --init --rm --network none ty1208z-busybox:local /bin/busybox sh -c '
        set -eu
        /bin/busybox grep -Eq "^Name:[[:space:]]+docker-init$" /proc/1/status'
    echo OPENWRT_DOCKER_PROCD_OVERLAY_CGROUP_PASS

    docker network create --driver bridge --subnet 172.30.0.0/24 combined-test
    docker run -d --name combined-http --network combined-test --network-alias service \
        --memory 64m -p 18090:8080 ty1208z-busybox:local /bin/busybox sh -c '
        set -eu
        /bin/busybox mkdir -p /tmp/www
        echo combined-container-http >/tmp/www/index.html
        /bin/busybox httpd -f -p 8080 -h /tmp/www &
        child=$!
        trap "kill $child; wait $child || true; exit 0" TERM
        wait "$child"'
    docker run -d --name combined-proxy-client --network combined-test --memory 64m \
        ty1208z-busybox:local /bin/busybox sh -c 'trap "exit 0" TERM; while :; do /bin/busybox sleep 1; done'
    bridge=$(docker network inspect --format '{{.Id}}' combined-test | cut -c1-12)
    test -e "/sys/class/net/br-$bridge"
    uci add_list firewall.docker.device=docker0
    uci add_list "firewall.docker.device=br-$bridge"
    ip netns add qemu_docker_ext
    ip link add docker-ext type veth peer name docker-peer
    ip link set docker-peer netns qemu_docker_ext
    ip -n qemu_docker_ext link set lo up
    ip -n qemu_docker_ext addr add 198.18.0.2/30 dev docker-peer
    ip -n qemu_docker_ext link set docker-peer up
    ip -n qemu_docker_ext route add default via 198.18.0.1
    uci set network.qemu_docker_ext=interface
    uci set network.qemu_docker_ext.device=docker-ext
    uci set network.qemu_docker_ext.proto=static
    uci set network.qemu_docker_ext.ipaddr=198.18.0.1
    uci set network.qemu_docker_ext.netmask=255.255.255.252
    uci set firewall.qemu_docker_ext=zone
    uci set firewall.qemu_docker_ext.name=qemu_docker_ext
    uci set firewall.qemu_docker_ext.network=qemu_docker_ext
    uci set firewall.qemu_docker_ext.input=ACCEPT
    uci set firewall.qemu_docker_ext.output=ACCEPT
    uci set firewall.qemu_docker_ext.forward=REJECT
    for direction in out in; do
        uci set "firewall.qemu_docker_$direction=forwarding"
    done
    uci set firewall.qemu_docker_out.src=docker
    uci set firewall.qemu_docker_out.dest=qemu_docker_ext
    uci set firewall.qemu_docker_in.src=qemu_docker_ext
    uci set firewall.qemu_docker_in.dest=docker
    uci commit network
    uci commit firewall
    /etc/init.d/network reload
    attempts=0
    until ip addr show dev docker-ext | grep -q '198.18.0.1/30'; do
        attempts=$((attempts+1))
        [ "$attempts" -lt 20 ] || exit 1
        sleep 1
    done
    fw4 check
    /etc/init.d/firewall reload
    nft list table inet fw4 >combined-fw4-generated.txt
    grep -q 'br-' combined-fw4-generated.txt
    mkdir -p /tmp/combined-external/cgi-bin
    cat >/tmp/combined-external/cgi-bin/peer <<'CGI'
#!/bin/sh
printf 'Content-Type: text/plain\r\n\r\n%s\n' "$REMOTE_ADDR"
CGI
    chmod 755 /tmp/combined-external/cgi-bin/peer
    ip netns exec qemu_docker_ext /qemu-helper/busybox httpd -f -p 198.18.0.2:8080 -h /tmp/combined-external \
        >combined-external-http.log 2>&1 &
    echo "$!" >/tmp/combined-external-http.pid
    sleep 1
    docker exec combined-proxy-client /bin/busybox nslookup service 127.0.0.11
    test "$(docker exec combined-proxy-client /bin/busybox wget -T 5 -q -O - http://service:8080/index.html)" = combined-container-http
    test "$(docker exec combined-proxy-client /bin/busybox wget -T 5 -q -O - http://198.18.0.2:8080/cgi-bin/peer)" = 198.18.0.1
    test "$(docker run --rm --network bridge ty1208z-busybox:local /bin/busybox wget -T 5 -q -O - http://198.18.0.2:8080/cgi-bin/peer)" = 198.18.0.1
    test "$(ip netns exec qemu_docker_ext curl --noproxy '*' -fsS --max-time 5 http://198.18.0.1:18090/index.html)" = combined-container-http
    echo OPENWRT_DOCKER_FW4_DNS_NAT_PASS
    ;;
verify-cleanup)
    /etc/init.d/dockerd running
    fw4 check
    docker exec combined-proxy-client /bin/busybox nslookup service 127.0.0.11
    test "$(docker exec combined-proxy-client /bin/busybox wget -T 5 -q -O - http://service:8080/index.html)" = combined-container-http
    test "$(docker exec combined-proxy-client /bin/busybox wget -T 5 -q -O - http://198.18.0.2:8080/cgi-bin/peer)" = 198.18.0.1
    test "$(ip netns exec qemu_docker_ext curl --noproxy '*' -fsS --max-time 5 http://198.18.0.1:18090/index.html)" = combined-container-http
    echo OPENWRT_DOCKER_AFTER_PASSWALL_FW4_RELOAD_PASS
    for container in combined-http combined-proxy-client; do
        docker stop --timeout 10 "$container"
        test "$(docker inspect --format '{{.State.ExitCode}}' "$container")" = 0
        docker rm "$container"
    done
    docker network rm combined-test
    test -z "$(docker ps -aq)"
    kill "$(cat /tmp/combined-external-http.pid)"
    ip link del docker-ext
    ip netns del qemu_docker_ext
    /etc/init.d/dockerd stop
    attempts=0
    while pidof dockerd containerd >/dev/null; do
        attempts=$((attempts+1))
        [ "$attempts" -lt 20 ] || exit 1
        sleep 1
    done
    if /etc/init.d/dockerd running; then exit 1; fi
    test ! -e /sys/class/net/docker-ext
    test ! -e /var/run/netns/qemu_docker_ext
    cp /tmp/combined-dockerd-original /etc/config/dockerd
    cp /tmp/combined-network-original /etc/config/network
    cp /tmp/combined-firewall-original /etc/config/firewall
    /etc/init.d/network reload
    /etc/init.d/firewall reload
    fw4 check
    echo OPENWRT_DOCKER_CLEAN_SHUTDOWN_PASS
    ;;
*) exit 2 ;;
esac
