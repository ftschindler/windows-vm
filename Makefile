.DEFAULT_GOAL := help

## Show available targets
help:
	@grep -B1 '^[a-z][a-z_-]*:' $(MAKEFILE_LIST) \
		| grep -A1 '^##' \
		| awk '/^##/{d=substr($$0,4)} /^[a-z]/{split($$0,a,":"); printf "  %-20s %s\n", a[1], d}'

guard-%:
	@command -v $* >/dev/null 2>&1 || { \
		printf 'error: required tool %s not found on PATH.\n' '$*' >&2; \
		exit 1; \
	}

## Run the conformance and script tests (offline)
test: test_conformance test_scripts

## Check the kit is shaped the way akit discovers one
test_conformance: | guard-uv
	uv run .scripts/run-tests.py conformance

## Test wvm.py against a fake VBoxManage, and the guards
test_scripts: | guard-uv
	uv run .scripts/run-tests.py scripts

## Test wvm.py against the real VM on this host
test_live: | guard-uv
	uv run .scripts/run-tests.py live

## Record evidence for one kit against your own assistant (KIT=<name>)
record_evidence: | guard-uv
	@test -n "$(KIT)" || { printf 'usage: make record_evidence KIT=<name>\n' >&2; exit 1; }
	uv run --script .scripts/record_evidence.py $(KIT) $(RECORD_ARGS)

## Run the full pre-commit guard suite against all files
check: | guard-uvx
	uvx prek run --all-files

## Install the pre-commit hooks into this clone
bootstrap: | guard-git guard-uvx
	uvx prek install

.PHONY: help test test_conformance test_scripts test_live record_evidence check bootstrap
