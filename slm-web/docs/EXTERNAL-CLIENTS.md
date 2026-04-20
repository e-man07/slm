# External Clients

## Python CLI (`slm-cli`)

### Stack
- `typer` — CLI framework
- `httpx` — HTTP client with SSE streaming
- `rich` — Terminal formatting, markdown, syntax highlighting

### Commands
```bash
slm chat "How do I create a PDA in Anchor?"     # One-shot chat
slm chat                                         # Interactive REPL
slm explain --tx 5UfDuX7WXY...                   # Explain transaction
slm explain --error 0x1771                        # Decode error
slm explain --error 6001 --program TokenkegQ...   # Decode with program
slm config --api-key slm_xxxxxxxxxxxx             # Set API key
slm config --api-url https://slm.dev/api          # Set API URL
```

### Config File
Location: `~/.slm/config.toml`
```toml
api_key = "slm_xxxxxxxxxxxx"
api_url = "https://slm.dev/api"
mode = "quality"  # or "fast"
```

### Package Structure
```
slm_cli/
  __init__.py
  main.py          # typer app, command definitions
  client.py        # httpx API client with SSE
  config.py        # Config file management
  display.py       # rich formatting helpers
```

### Install
```bash
pip install slm-cli
# or
pipx install slm-cli
```

### Estimated Size
~200-300 lines of Python total

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
  "slm.apiUrl": "https://slm.dev/api",
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

### Minimum Viable Extension
- Chat Participant only (~100-150 lines TypeScript)
- No code actions, no diagnostics
- Build time: ~6-8 hours
