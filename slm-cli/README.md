# Sealevel CLI

Command-line interface for [Sealevel](https://sealevel.tech) — the Solana-specialized coding AI.

Interactive session with slash commands for chatting, generating Anchor programs, reviewing code, migrating to modern patterns, decoding errors, and explaining transactions.

## Install

```bash
pip install sealevel
```

## Quick Start

```bash
# Set your API key (get one at https://sealevel.tech/dashboard)
slm config --api-key slm_xxxxxxxxxxxx

# Start interactive session
slm
```

Inside the session, type to chat or use `/` commands:

```
❯ How do I derive a PDA in Anchor?
◆ SEALEVEL
[streaming response with markdown rendering]

❯ /review src/lib.rs
◆ REVIEWING  src/lib.rs
[security + deprecated pattern analysis]

❯ /explain-error 0x1771
[error decode + fix suggestion]

❯ /gen "escrow with atomic token swap"
[generates full Anchor program]
```

## Modes

```bash
slm                    # Interactive session (default)
slm -p "prompt"        # One-shot mode — print response and exit
slm -c                 # Continue most recent session
slm config --show      # View configuration
```

### Pipe mode

```bash
slm -p "What is a PDA?"
cat src/lib.rs | slm -p "review this code"
echo "0x1771" | slm -p "explain this Solana error"
```

## Session Commands

Type `/` to see all commands with live filtering. Type `/help` for the full list.

### Chat & Code

| Command | Description |
|---------|-------------|
| (plain text) | Chat with Sealevel |
| `/review <file>` | Review code for security issues |
| `/migrate <file> [--write]` | Migrate to modern Anchor 0.30+ |
| `/gen "description" [-o file]` | Generate an Anchor program |
| `/tests <file>` | Generate TypeScript tests |

### Explain

| Command | Description |
|---------|-------------|
| `/explain-tx <signature>` | Explain a Solana transaction |
| `/explain-error <code>` | Decode an error code |

### Session

| Command | Description |
|---------|-------------|
| `/sessions` | List past sessions |
| `/resume <id>` | Resume a past session |
| `/rename <name>` | Rename current session |
| `/compact [N]` | Trim history to last N turns |
| `/export [file]` | Export session as markdown |
| `/history` | Show conversation history |
| `/clear` | Clear conversation |

### System

| Command | Description |
|---------|-------------|
| `/status` | Show API health and config |
| `/usage` | Show token usage and limits |
| `/copy` | Copy last response to clipboard |
| `/rotate-key` | Rotate API key |
| `/config [--show]` | View or set configuration |
| `/help` | Show all commands |
| `/exit` | Exit session |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `/` | Open command dropdown (live filter as you type) |
| `Tab` | Accept suggestion |
| `Ctrl+R` | Search input history |
| `Ctrl+L` | Clear screen |
| `Ctrl+J` | Newline (multiline input) |
| `Esc Esc` | Undo last turn |
| `Ctrl+C` | Cancel current operation |
| `Ctrl+D` | Exit |

## Configuration

```bash
slm config --api-key slm_xxxx     # Set API key
slm config --api-url https://...  # Custom endpoint
slm config --mode quality         # 'quality' or 'fast'
slm config --show                 # Show current config
```

Config stored at `~/.sealevel/config.toml`. API key stored in OS keyring (macOS Keychain / Windows Credential Locker / GNOME Keyring).

Override config dir: `SEALEVEL_CONFIG_DIR=/path/to/dir`

## Uninstall

```bash
pip uninstall sealevel
rm -rf ~/.sealevel
```

## License

MIT

## Links

- [Sealevel](https://sealevel.tech)
- [API docs](https://sealevel.tech/docs)
