SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help lint test-serial build test verify references references-wifi wifi-usb-audit emmc-audit emmc-ident
help:
	@echo 'make lint       - Python/shell/config repository checks'
	@echo 'make build      - download pinned sources and build RAM-only ARM candidate'
	@echo 'make test       - QEMU user/virt shell and 2040 timestamp regression'
	@echo 'make test-serial - capture and bootloader CLI integration on a Linux PTY'
	@echo 'make verify     - lint + build + test'
	@echo 'make references - download pinned SDK references for read-only source audit'
	@echo 'make references-wifi - verify/download pinned optional RDA driver code (no firmware)'
	@echo 'make wifi-usb-audit - compile one RDA USB object with a separate kernel config'
	@echo 'make emmc-audit - build a separate read-only eMMC-register RAM diagnostic'
	@echo 'make emmc-ident - build a separate restricted PIO eMMC identification image'

lint:
	python3 tools/check_repository.py
	python3 tools/fetch_wifi.py --check-lock
	shellcheck tools/*.sh initramfs/init initramfs/diag
	python3 -m ruff check tools
	python3 tools/test_baseline_collector.py

test-serial:
	python3 tools/test_serial_cli.py
	python3 tools/test_ymodem_sender.py
	python3 tools/test_board_diag_cli.py

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

emmc-audit:
	bash tools/build-emmc-audit.sh $(if $(TASKBASE),"$(TASKBASE)")

emmc-ident:
	bash tools/build-emmc-ident.sh $(if $(TASKBASE),"$(TASKBASE)")
