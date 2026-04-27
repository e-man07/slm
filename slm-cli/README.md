# Sealevel CLI

Command-line interface for [Sealevel](https://sealevel.tech) — the Solana-specialized coding AI.

Interactive terminal session with agent mode, slash commands, and Solana/Anchor developer tools.

## Install

```bash
pip install sealevel
```

Requires Python 3.10+.

## Quick Start

```bash
slm login              # Authenticate via browser (OAuth device flow)
slm                    # Start interactive session
```

Or set your key manually:

```bash
slm config --api-key slm_xxxxxxxxxxxx
```

## Interactive Session

```
❯ How do I derive a PDA in Anchor?
◆ SEALEVEL
[streaming response with markdown rendering]

❯ /review @src/lib.rs
◆ REVIEWING  src/lib.rs
[security + deprecated pattern analysis]

❯ /explain-error 0x1771
[error decode + fix suggestion]

❯ /gen escrow with atomic token swap -o src/lib.rs
✓ WROTE  src/lib.rs
```

## Agent Mode

Toggle with `/agent` — the LLM can read, edit, and create files, and run commands:

```
❯ /agent
✓ Agent mode ON

❯ read src/lib.rs and add an authority check to increment
╭─ read_file ──────────────╮
│  path: src/lib.rs        │
│  ✓ 38 lines              │
╰──────────────────────────╯
╭─ edit_file ──────────────╮
│  path: src/lib.rs        │
│  -2 / +5 lines           │
╰──────────────────────────╯
▸ Allow edit? [y/N/a] y
✓ EDITED  src/lib.rs

Done. Added authority check.
```

Tools: `read_file`, `write_file`, `edit_file`, `run_command`, `glob_files`, `grep_files`. Read-only tools auto-approve. Write/execute asks permission. Type `a` to approve all.

## Features

- **@file references** — `@src/lib.rs` inlines file content into chat
- **Project memory** — `SEALEVEL.md` in project root auto-injects context
- **AI-powered `/compact`** — summarizes old conversation to free context
- **Auto-upgrade** — notifies when newer version is available
- **File checkpoints** — `/undo` restores files modified by agent
- **Persistent history** — input history persists across sessions (Ctrl+R to search)
- **Progressive streaming** — live markdown rendering with Rich

## Modes

```bash
slm                    # Interactive session (default)
slm -p "prompt"        # One-shot pipe mode
slm -c                 # Continue most recent session
slm login              # Authenticate via browser
slm logout             # Clear credentials
slm config --show      # View configuration
```

### Pipe mode

```bash
slm -p "What is a PDA?"
cat src/lib.rs | slm -p "review this code"
```

## Slash Commands

Type `/` for live dropdown. 25 commands:

### Code

| Command | Description |
|---------|-------------|
| `/review <file>` | Security + deprecation review |
| `/migrate <file> [--write]` | Migrate to Anchor 0.30+ |
| `/gen <description> [-o file]` | Generate Anchor program |
| `/tests <file> [-o out.ts]` | Generate TypeScript tests |

### Explain

| Command | Description |
|---------|-------------|
| `/explain-tx <signature>` | Decode a Solana transaction |
| `/explain-error <code>` | Decode an error code |

### Session

| Command | Description |
|---------|-------------|
| `/sessions` | List past sessions |
| `/resume <id>` | Resume a past session |
| `/rename <name>` | Rename current session |
| `/history` | Show conversation history |
| `/search <query>` | Search conversation |
| `/compact [focus]` | AI-summarize old history |
| `/export [file]` | Export as markdown |
| `/clear` | Clear history (with confirmation) |
| `/undo` | Undo last turn + restore files |
| `/retry` | Redo last turn |

### Info

| Command | Description |
|---------|-------------|
| `/status` | API health + config |
| `/usage` | Token usage + limits |
| `/copy` | Copy last response to clipboard |

### System

| Command | Description |
|---------|-------------|
| `/agent` | Toggle agent mode |
| `/login` | Authenticate via browser |
| `/config [--show]` | View/set config |
| `/rotate-key` | Rotate API key |
| `/help` | Show all commands |
| `/exit` | Exit session |

## Configuration

```bash
slm config --api-key slm_xxxx     # Set API key
slm config --api-url https://...  # Custom endpoint
slm config --mode quality         # 'quality' (temp=0.0, 4096 tokens) or 'fast' (temp=0.3, 2048)
slm config --show                 # Show current config
```

Config: `~/.sealevel/config.toml` (chmod 600). API key: OS keyring.

## License

MIT

## Links

- [Sealevel](https://sealevel.tech)
- [Docs](https://sealevel.tech/docs)
- [PyPI](https://pypi.org/project/sealevel/)
