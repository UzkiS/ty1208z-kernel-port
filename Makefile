SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help lint test-serial build test verify references references-wifi wifi-usb-audit wifi-port emmc-audit emmc-ident emmc-read ethernet-audit ethernet-clock-id openwrt-config openwrt-toolchain openwrt-ram openwrt-app-config openwrt-applications
help:
	@echo 'make lint       - Python/shell/config repository checks'
	@echo 'make build      - download pinned sources and build RAM-only ARM candidate'
	@echo 'make test       - QEMU user/virt shell and 2040 timestamp regression'
	@echo 'make test-serial - capture and bootloader CLI integration on a Linux PTY'
	@echo 'make verify     - lint + build + test'
	@echo 'make references - download pinned SDK references for read-only source audit'
	@echo 'make references-wifi - verify/download pinned optional RDA driver code (no firmware)'
	@echo 'make wifi-usb-audit - compile one RDA USB object with a separate kernel config'
	@echo 'make wifi-port - link the optional RDA USB module and test production guards'
	@echo 'make emmc-audit - build a separate read-only eMMC-register RAM diagnostic'
	@echo 'make emmc-ident - build a separate restricted PIO eMMC identification image'
	@echo 'make emmc-read - build fixed four-sector read-only samples (no block device)'
	@echo 'make ethernet-audit - inspect inherited clocks/PHY IDs without network or reset writes'
	@echo 'make ethernet-clock-id - temporarily enable the measured MAC clock bit, read PHY ID, restore'
	@echo 'make ethernet-net - build inherited-PHY Ethernet RAM candidate (storage disabled)'
	@echo 'make openwrt-config - resolve the independent pinned native RAM target'
	@echo 'make openwrt-toolchain - build the native target toolchain as a regular user'
	@echo 'make openwrt-ram - build native OpenWrt RAM userspace/image (hardware untested)'
	@echo 'make openwrt-app-config - resolve pinned Passwall/Xray/LuCI in an isolated tree'
	@echo 'make openwrt-applications - build and emulate applications (no board image)'
	@echo 'make openwrt-net - build independent native Ethernet RAM candidate with traffic tools'
	@echo 'make usb-audit - build standalone read-only host0 control/capability RAM audit'
	@echo 'make restart - build isolated SP805 explicit restart RAM experiment'
	@echo 'make openwrt-app-ram - validate applications with a 240-MiB usable budget and package separate RAM initrd'
	@echo 'make openwrt-router - build isolated applications plus measured Ethernet for RAM validation'

lint:
	python3 tools/check_repository.py
	python3 tools/fetch_wifi.py --check-lock
	shellcheck tools/*.sh initramfs/init initramfs/diag initramfs/ethernet-diag initramfs/ethernet-dhcp
	python3 -m ruff check tools
	python3 tools/test_baseline_collector.py

test-serial:
	python3 tools/test_serial_cli.py
	python3 tools/test_ymodem_sender.py
	python3 tools/test_board_diag_cli.py
	python3 tools/test_ethernet_board_cli.py
	python3 tools/test_openwrt_ethernet_board_cli.py
	python3 tools/test_board_restart_cli.py

build:
	bash tools/build-diagnostic.sh $(if $(TASKBASE),"$(TASKBASE)")

test:
	bash tools/test-qemu.sh
	python3 tools/test_ram_boot_cli.py

verify: lint build test

references:
	python3 tools/fetch_references.py

references-wifi:
	python3 tools/fetch_wifi.py

wifi-usb-audit:
	bash tools/build-wifi-usb-audit.sh $(if $(TASKBASE),"$(TASKBASE)")

wifi-port:
	bash tools/build-wifi-port.sh $(if $(TASKBASE),"$(TASKBASE)")

emmc-audit:
	bash tools/build-emmc-audit.sh $(if $(TASKBASE),"$(TASKBASE)")

emmc-ident:
	bash tools/build-emmc-ident.sh $(if $(TASKBASE),"$(TASKBASE)")

emmc-read:
	bash tools/build-emmc-ident.sh "$(if $(TASKBASE),$(TASKBASE),$(CURDIR)/.work)" read

ethernet-audit:
	bash tools/build-ethernet-audit.sh $(if $(TASKBASE),"$(TASKBASE)")

ethernet-clock-id:
	bash tools/build-ethernet-audit.sh "$(if $(TASKBASE),$(TASKBASE),$(CURDIR)/.work)" clock-id

.PHONY: ethernet-net
ethernet-net:
	bash tools/build-ethernet-net.sh $(if $(TASKBASE),"$(TASKBASE)")

openwrt-config:
	bash tools/build-openwrt-ram.sh "$(if $(TASKBASE),$(TASKBASE),$(CURDIR)/.work)" config

openwrt-toolchain:
	bash tools/build-openwrt-ram.sh "$(if $(TASKBASE),$(TASKBASE),$(CURDIR)/.work)" toolchain

openwrt-ram:
	bash tools/build-openwrt-ram.sh "$(if $(TASKBASE),$(TASKBASE),$(CURDIR)/.work)" build

openwrt-app-config:
	bash tools/build-openwrt-applications.sh "$(if $(TASKBASE),$(TASKBASE),$(CURDIR)/.work)" config

openwrt-applications:
	bash tools/build-openwrt-applications.sh "$(if $(TASKBASE),$(TASKBASE),$(CURDIR)/.work)" build

.PHONY: openwrt-net-config openwrt-net
openwrt-net-config:
	bash tools/build-openwrt-ethernet.sh "$(if $(TASKBASE),$(TASKBASE),$(CURDIR)/.work)" config

openwrt-net:
	bash tools/build-openwrt-ethernet.sh "$(if $(TASKBASE),$(TASKBASE),$(CURDIR)/.work)" build

.PHONY: usb-audit
usb-audit:
	bash tools/build-usb-audit.sh "$(if $(TASKBASE),$(TASKBASE),$(CURDIR)/.work)"

.PHONY: restart
restart:
	bash tools/build-restart.sh "$(if $(TASKBASE),$(TASKBASE),$(CURDIR)/.work)"

.PHONY: openwrt-app-ram
openwrt-app-ram:
	bash tools/build-openwrt-applications.sh "$(if $(TASKBASE),$(TASKBASE),$(CURDIR)/.work)" ram

.PHONY: openwrt-router
openwrt-router:
	bash tools/build-openwrt-applications.sh "$(if $(TASKBASE),$(TASKBASE),$(CURDIR)/.work)" network
