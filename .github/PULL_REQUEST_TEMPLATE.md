## Purpose

Describe the behavior, defect, or capability changed.

## Validation

- [ ] Python compiles
- [ ] Unit tests pass
- [ ] Shell syntax passes where applicable
- [ ] Docker Compose validates where applicable
- [ ] Security scans pass or findings are explained

## Boundary impact

- [ ] No trust boundary changed
- [ ] Control-plane / MCP boundary changed
- [ ] Runner / hosted execution boundary changed
- [ ] Filesystem / managed-root boundary changed
- [ ] Training-range isolation changed
- [ ] Recovery / wake path changed

Explain any checked boundary change and why it remains safe.

## Compatibility

- [ ] No compatibility contract changed
- [ ] `dpsr`, `DPSR_*`, `dpsr.toml`, persisted state, or generated-project behavior changed and migration is documented

## Public surface

- [ ] APOTHEON ONE identity remains correct
- [ ] Documentation was updated when behavior changed
- [ ] No credentials, runtime evidence, or generated secrets were committed
