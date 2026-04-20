# slm-cli

Command-line interface for [Sealevel](https://slm.dev) — the Solana-specialized coding LLM.

Chat, generate Anchor programs, review code, migrate to modern patterns, decode errors, and explain transactions — all from your terminal.

## Install

```bash
pip install slm-cli
```

Or from source:

```bash
git clone https://github.com/kshitij-hash/slm && cd slm/slm-cli
pip install -e .
```

## Quick Start

```bash
# Set your API key (get one at https://slm.dev/dashboard)
slm config --api-key slm_xxxxxxxxxxxx

# Ask a question
slm chat "How do I derive a PDA for a user's token account in Anchor?"

# Interactive REPL
slm chat
```

## Commands

### Chat

```bash
slm chat "Write an Anchor counter program"       # One-shot
slm chat                                           # Interactive REPL
```

### Generate

Scaffold a new Anchor program from a description:

```bash
slm gen "escrow with atomic token swap"
slm gen "staking vault with time-based rewards" -o programs/stake/src/lib.rs
```

### Review

Security + deprecated-pattern review of a local file:

```bash
slm review programs/my_program/src/lib.rs
```

### Migrate

Rewrite old Anchor code to modern 0.30+ patterns (`declare_id!` → `declare_program!`, manual space → `InitSpace`, etc.):

```bash
slm migrate src/lib.rs            # Show migrated code
slm migrate src/lib.rs --write    # Overwrite file
```

### Tests

Generate TypeScript tests for an Anchor program:

```bash
slm tests programs/counter/src/lib.rs > tests/counter.ts
```

### Explain

```bash
slm explain --tx 5U3...abc        # Explain a transaction
slm explain --error 0x1771        # Decode an error code
```

### Config

```bash
slm config --api-key slm_xxxx     # Set API key
slm config --api-url https://...  # Custom endpoint (self-hosted)
slm config --mode quality         # 'quality' or 'fast'
slm config --show                 # Show current config
```

Config is stored at `~/.slm/config.toml`. Override with `SLM_CONFIG_DIR=/path/to/dir`.

## Environment Variables

| Variable | Purpose |
|---|---|
| `SLM_CONFIG_DIR` | Config directory (default `~/.slm/`) |

## Examples

### Review a whole crate

```bash
for f in programs/*/src/lib.rs; do
  echo "=== $f ==="
  slm review "$f"
done
```

### Generate + save + review

```bash
slm gen "NFT marketplace with royalties" -o src/lib.rs
slm review src/lib.rs
```

## Uninstall

```bash
pip uninstall slm-cli
rm -rf ~/.slm
```

## License

MIT

## Links

- [Sealevel web](https://slm.dev)
- [API docs](https://slm.dev/docs)
- [GitHub](https://github.com/kshitij-hash/slm)
