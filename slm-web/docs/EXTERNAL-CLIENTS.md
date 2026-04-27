# External Clients

## Python CLI (`sealevel`)

### Stack
- `typer` — CLI framework + entry point
- `httpx` — HTTP client with SSE streaming
- `rich` — Terminal formatting, markdown rendering, Live streaming
- `prompt_toolkit` — Interactive input, autocomplete dropdown, ghost text, key bindings
- `keyring` — OS keyring for secure API key storage

### Authentication
```bash
slm login                    # OAuth device flow (opens browser)
slm logout                   # Clear credentials
slm config --api-key slm_xx  # Manual key paste (fallback)
```

### Interactive Session
```bash
slm                          # Start interactive session
```

Inside the session, type plain text to chat or use slash commands:

### Slash Commands (22 total)
```
/review <file>               Review Solana/Anchor code for security issues
/migrate <file> [--write]    Upgrade to modern Anchor 0.30+ patterns
/gen <description> [-o file] Generate a complete Anchor program
/tests <file> [-o out.ts]    Generate TypeScript tests
/explain-tx <signature>      Decode a Solana transaction
/explain-error <code>        Decode a Solana/Anchor error code
/status                      API health + config overview
/usage                       Token usage and limits
/login                       Authenticate via browser (from inside session)
/config [--show]             View or change settings
/sessions                    List past sessions
/resume <id>                 Resume a past session
/rename <name>               Rename current session
/rotate-key                  Rotate API key
/compact [focus]              AI-summarize old history to free context
/copy                        Copy last response to clipboard
/export [file]               Export session as markdown
/history                     Show conversation history
/search <query>              Search conversation history
/clear                       Clear conversation history (with confirmation)
/undo                        Undo last turn + restore modified files
/retry                       Redo last turn with fresh response
/agent                       Toggle agent mode — experimental
/help                        Show all commands
/exit                        Exit session
```

### Pipe Mode
```bash
slm -p "What is a PDA?"                        # One-shot
cat src/lib.rs | slm -p "review this"          # Pipe stdin
slm -c                                         # Continue last session
```

### Config
Location: `~/.sealevel/config.toml` (chmod 600)
API key: stored in OS keyring (macOS Keychain, Linux keyring, Windows Credential Locker)

```bash
slm config --show                              # View config
slm config --api-key slm_xxx                   # Set key manually
slm config --api-url https://www.sealevel.tech # Set API URL
slm config --mode quality                      # quality (temp=0.0, 4096 tokens)
slm config --mode fast                         # fast (temp=0.3, 2048 tokens)
```

### Features
- Live `/` command dropdown with autocomplete
- `@file.rs` inline file references in chat
- `SEALEVEL.md` project memory (walks cwd to root)
- Progressive markdown streaming with Rich Live
- Context-aware ghost text suggestions
- Auto-retry on 429 with exponential backoff
- Session persistence (server + local JSONL backup)
- Truncation detection (warns when response hits token limit)
- Agent mode (experimental) with 6 tools (read/write/edit files, run commands, glob, grep)
- Permission model (auto-approve reads, prompt for writes/commands)
- AI-powered `/compact` (LLM summarizes old history)
- File checkpoints (`/undo` restores modified files)
- Auto-upgrade notifications (checks PyPI on startup)
- Persistent input history across sessions
- `/retry` to redo last turn

### Package Structure
```
sealevel_cli/
  __init__.py        # version
  main.py            # typer app, login/logout, config subcommand
  client.py          # httpx API client, SSE parsing, device auth
  session.py         # interactive REPL loop, dispatch, history, checkpoints
  commands.py        # 25 slash command handlers
  display.py         # Rich formatting, streaming, brand elements
  input.py           # prompt_toolkit completer, keybindings, toolbar
  config.py          # TOML config + keyring integration
  storage.py         # local JSONL session backup
  agent.py           # agent loop orchestrator (stream → parse → execute → loop)
  tools.py           # 6 tool definitions + executors
  tool_parser.py     # parse tool calls from LLM output (XML, bare JSON, code blocks)
  permissions.py     # permission model (auto-approve, deny, prompt)
```

### Install
```bash
pip install sealevel
# Requires Python 3.10+
```

### Tests
576+ tests covering all modules (92% coverage). Run: `python -m pytest tests/ -q`

---

## VS Code Extension

### Capabilities
1. **Chat Participant** — `@slm` in Copilot chat panel
2. **Code Action** — "Explain with Sealevel" on rust-analyzer errors
3. **Diagnostic Interception** — listen for rust-analyzer errors

### Architecture
```
Extension Host (TypeScript)
  ├── Chat Participant (vscode.chat.createChatParticipant)
  │     ├── Receives user messages
  │     ├── Calls /api/chat with SSE
  │     └── Streams response via stream.markdown()
  │
  ├── Code Action Provider
  │     ├── Filters diagnostics for source: "rust-analyzer"
  │     └── Offers "Explain with Sealevel" quick fix
  │
  └── Settings
        ├── slm.apiKey
        ├── slm.apiUrl
        ├── slm.mode (fast/quality)
        └── slm.fallbackToOllama (boolean)
```

### Settings
```json
{
  "slm.apiKey": "",
  "slm.apiUrl": "https://www.sealevel.tech",
  "slm.mode": "quality",
  "slm.fallbackToOllama": false
}
```

### Fallback
If `fallbackToOllama` is true and remote API is unreachable:
- Route to `http://localhost:11434/v1/chat/completions`
- Use the locally running `slm-solana` Ollama model

### Publishing
```bash
npm install -g @vscode/vsce
vsce package       # Creates .vsix
vsce publish       # Publish to marketplace
npx ovsx publish   # Publish to Open VSX (VSCodium)
```
