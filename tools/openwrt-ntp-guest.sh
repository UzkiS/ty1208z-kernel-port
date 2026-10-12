#!/bin/sh
# Actual installed ntpd client, loopback-only fixture, QEMU RAM and clock only.
set -eu
tr '\000' '\n' < /sys/firmware/devicetree/base/compatible | grep -qx linux,dummy-virt
cd /tmp/time64-test
/etc/init.d/sysntpd stop
attempts=0
until ! pidof ntpd > /dev/null; do
    attempts=$((attempts+1))
    [ "$attempts" -lt 10 ] || exit 1
    sleep 1
done
test -x /usr/sbin/ntpd
test -x /tmp/ntp-qemu-fixture

for scenario in era0 era1 time32 future2040; do
    case "$scenario" in
        era0) seed=2085978100; target=2085978400 ;;
        era1) seed=2085978296; target=2085978596 ;;
        time32) seed=2147483468; target=2147483768 ;;
        future2040) seed=1791676800; target=2208988800 ;;
    esac
    date -u -s "@$seed"
    before=$(date -u +%s)
    /tmp/ntp-qemu-fixture "$target" > "ntp-$scenario-server.log" 2>&1 &
    fixture_pid=$!
    attempts=0
    until grep -q '^NTP_FIXTURE_READY ' "ntp-$scenario-server.log"; do
        attempts=$((attempts+1))
        [ "$attempts" -lt 10 ] || exit 1
        sleep 1
    done
    timeout 35 /usr/sbin/ntpd -n -q -p 127.0.0.1 > "ntp-$scenario-client.log" 2>&1
    after=$(date -u +%s)
    kill "$fixture_pid"
    wait "$fixture_pid"
    test "$before" -lt "$target"
    test "$after" -ge "$target"
    test "$after" -le "$((target + 40))"
    grep -q '^NTP_FIXTURE_COMPLETE responses=' "ntp-$scenario-server.log"
    echo "NTP_CASE_PASS name=$scenario before=$before target=$target after=$after"
    cat "ntp-$scenario-server.log"
    cat "ntp-$scenario-client.log"
done
test "$(date -u +%Y)" = 2040
echo NTP_ERA_TIME64_PASS
