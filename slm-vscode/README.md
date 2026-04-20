# Sealevel — Solana Language Model for VS Code

Solana-specialized AI assistant in your editor. Chat, autocomplete, and Solana-aware code help powered by [Sealevel](https://slm.dev) — fine-tuned on 731K Solana/Anchor records.

## Features

### `@slm` Chat Participant
Ask Solana/Anchor questions directly in the VS Code chat panel:

```
@slm how do I derive a PDA for a user's token account?
@slm review this code for security issues
@slm explain this CPI pattern
```

### Inline Autocomplete
Debounced ghost-text suggestions as you type in `.rs`, `.ts`, `.tsx`, `.toml` files. No keystroke latency — suggestions appear 1.5 s after you pause.

### Commands
- **Sealevel: Explain Error Code** — paste an error code (hex or decimal), get a plain-English explanation
- **Sealevel: Explain Transaction** — paste a signature, get a breakdown

Access via `Cmd+Shift+P` → "Sealevel".

## Install

### Marketplace
Search for **Sealevel - Solana Language Model** and install.

### .vsix (manual)
```bash
code --install-extension slm-vscode-0.1.0.vsix
```

## Setup

1. Get an API key at [slm.dev/dashboard](https://slm.dev/dashboard)
2. Open Settings (`Cmd+,`), search for "Sealevel"
3. Set **Slm: Api Key** to your key

## Settings

| Setting | Default | Description |
|---|---|---|
| `slm.apiKey` | — | Your Sealevel API key |
| `slm.apiUrl` | `https://slm.dev/api` | Backend URL (change for self-hosted) |
| `slm.mode` | `quality` | `quality` (best) or `fast` (lower latency) |
| `slm.autocomplete.enabled` | `true` | Enable inline completions |
| `slm.autocomplete.debounceMs` | `1500` | Typing pause before triggering |

## Requirements
- VS Code `>= 1.93.0`
- Active internet connection to reach `slm.dev` (or self-hosted endpoint)

## Privacy
Prompts are sent to your configured `apiUrl`. No code is stored unless you use `slm.dev` with a signed-in account (chat history is saved for your account only — see [slm.dev/docs](https://slm.dev/docs)).

## Development

```bash
git clone https://github.com/kshitij-hash/slm && cd slm/slm-vscode
npm install
npm run compile
code --extensionDevelopmentPath=$PWD
```

Package `.vsix`:

```bash
npm run package  # needs vsce: npm i -g @vscode/vsce
```

## License

MIT

## Links

- [Sealevel](https://slm.dev)
- [GitHub](https://github.com/kshitij-hash/slm)
- [Report a bug](https://github.com/kshitij-hash/slm/issues)
