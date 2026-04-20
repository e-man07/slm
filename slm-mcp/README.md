# slm-mcp

[Model Context Protocol](https://modelcontextprotocol.io) server for [Sealevel](https://slm.dev) — gives Claude Code, Cursor, Windsurf, and Claude Desktop direct access to Solana-specific AI tooling.

## Install

### For Claude Code / Cursor / Windsurf (HTTP transport, recommended)

```bash
claude mcp add --transport http slm-solana https://slm-mcp.your-domain.com/mcp
```

Replace the URL with your deployed HTTP MCP server endpoint (see [Self-host](#self-host)).

### Local stdio (for development)

```bash
git clone https://github.com/kshitij-hash/slm && cd slm/slm-mcp
npm install && npm run build
```

Then add to your client config. For Claude Code (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "slm": {
      "command": "node",
      "args": ["/absolute/path/to/slm/slm-mcp/dist/index.js"],
      "env": {
        "SLM_API_URL": "https://slm.dev/api",
        "SLM_API_KEY": "slm_xxxxxxxxxxxx"
      }
    }
  }
}
```

## Tools

| Tool | Description |
|---|---|
| `slm_chat` | Ask Sealevel a Solana/Anchor development question |
| `slm_decode_error` | Look up a Solana/Anchor error code (name, message, program) |
| `slm_explain_tx` | Explain a Solana transaction by signature |
| `slm_migrate_code` | Migrate old Anchor code to modern 0.30+ patterns |
| `slm_review_code` | Review code for deprecated patterns + security issues |

## Prompts

| Prompt | Usage |
|---|---|
| `solana-expert` | Get expert help on a Solana topic |
| `anchor-migration` | Guided migration of a code block |
| `security-review` | Deep security audit |

## Resources

| URI | Content |
|---|---|
| `solana://errors` | Solana/Anchor/SPL error code table |
| `solana://eval-results` | Sealevel model evaluation results |
| `solana://system-prompt` | System prompt + guardrails |

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `SLM_API_URL` | `https://slm.dev/api` | Sealevel backend URL |
| `SLM_API_KEY` | — | Bearer token for authenticated requests |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `http` |
| `PORT` | `8080` | HTTP port (when `MCP_TRANSPORT=http`) |

## Self-host

### Docker

```bash
docker run -d \
  -p 8080:8080 \
  -e SLM_API_URL=https://slm.dev/api \
  -e SLM_API_KEY=slm_xxx \
  -e MCP_TRANSPORT=http \
  whyparabola/slm-mcp-server:latest
```

### Cloud Run (GCP)

```bash
gcloud run deploy slm-mcp \
  --image whyparabola/slm-mcp-server:latest \
  --region us-central1 \
  --port 8080 \
  --allow-unauthenticated \
  --set-env-vars MCP_TRANSPORT=http,SLM_API_URL=https://slm.dev/api,SLM_API_KEY=slm_xxx
```

### Akash / Fly.io / Railway

Same Docker image works — just set the env vars.

## Develop

```bash
npm install
npm run build      # compile TS
npm run dev        # watch mode (stdio)
npm test           # run vitest suite
```

HTTP mode locally:

```bash
PORT=8080 MCP_TRANSPORT=http SLM_API_URL=http://localhost:3000/api SLM_API_KEY=slm_xxx npm run dev
```

## License

MIT

## Links

- [Sealevel](https://slm.dev)
- [MCP spec](https://modelcontextprotocol.io)
- [GitHub](https://github.com/kshitij-hash/slm)
