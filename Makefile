SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help lint test-serial build test verify references
help:
	@echo 'make lint       - Python/shell/config repository checks'
	@echo 'make build      - download pinned sources and build RAM-only ARM candidate'
	@echo 'make test       - QEMU user/virt shell and 2040 timestamp regression'
	@echo 'make test-serial - capture and bootloader CLI integration on a Linux PTY'
	@echo 'make verify     - lint + build + test'
	@echo 'make references - download pinned SDK references for read-only source audit'

lint:
	python3 tools/check_repository.py
	shellcheck tools/*.sh initramfs/init initramfs/diag
	python3 -m ruff check tools
	python3 tools/test_baseline_collector.py

test-serial:
	python3 tools/test_serial_cli.py

build:
	bash tools/build-diagnostic.sh $(if $(TASKBASE),"$(TASKBASE)")

test:
	bash tools/test-qemu.sh

verify: lint build test

references:
	python3 tools/fetch_references.py
