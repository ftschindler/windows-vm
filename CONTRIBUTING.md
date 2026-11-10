# Contributing

## The windows-vm kit

The kit is a skill in `skills/windows-vm/` and a rule in `rules/windows-vm.md`,
laid out the way [agent-kits](https://github.com/ftschindler/agent-kits)
describes in its `CONTRIBUTING.md`. Everything the skill runs is
`skills/windows-vm/scripts/wvm.py`, which needs only [uv](https://docs.astral.sh/uv/).

```sh
make bootstrap                 # install the pre-commit hooks
make check                     # every guard, which is what CI runs
make test                      # conformance and script tests, offline
make test_live                 # wvm.py against the real VM on this host
make record_evidence KIT=windows-vm RECORD_ARGS="--model github-copilot/claude-sonnet-5"
```

Each `make` target is one `uv` line, so it can be run without make.

## Tests

- **Script tests** (`tests/test_wvm.py`) run `wvm.py` against
  `tests/fake_vboxmanage.py`, a stand-in for `VBoxManage` that answers from a
  state file and logs every call.
- **Live tests** (`tests/test_wvm_live.py`) drive the real VM. They skip
  themselves when no VM is running, and never run in CI.
- **Conformance** checks the kit is shaped the way akit finds one.
- **Evidence** (`tests/evidence/windows-vm.json`) is a recording of a real
  agent following the kit. `tests/sandbox/windows-vm.py` gives that agent the
  fake `VBoxManage`, so recording needs no running VM. Editing the skill or
  the rule means recording again; the `kit-evidence` hook says so.

## The guards

`.scripts/` holds guards copied from agent-kits at commit
`3c1a4952a1c441341fdc5125cbb90883c0b2b55f`, under their MIT notice in
[LICENSE](LICENSE). The only change is `prepare_machine()` in
`record_evidence.py`, which loads `tests/sandbox/<kit>.py`. Diff against that
commit to pick up later fixes.
