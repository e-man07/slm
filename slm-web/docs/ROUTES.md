# Project Structure & Routes

## File System

```
slm-web/
  app/
    layout.tsx                    # Root layout (fonts, ThemeProvider) [EXISTS]
    page.tsx                      # Landing page
    globals.css                   # Theme variables [EXISTS]
    favicon.ico                   # [EXISTS]

    chat/
      page.tsx                    # Chat interface

    explain/
      tx/
        page.tsx                  # Transaction explainer
      error/
        page.tsx                  # Error decoder

    docs/
      page.tsx                    # API documentation

    eval/
      page.tsx                    # Eval dashboard

    dashboard/
      page.tsx                    # API key management

    api/
      chat/
        route.ts                  # POST: streaming chat
      explain/
        tx/
          route.ts                # POST: tx explanation
        error/
          route.ts                # POST: error decoding
      health/
        route.ts                  # GET: health check

  components/
    ui/                           # shadcn/ui primitives [EXISTS]
      button.tsx                  # [EXISTS]
      input.tsx
      textarea.tsx
      card.tsx
      badge.tsx
      tabs.tsx
      table.tsx
      accordion.tsx
      toast.tsx
      tooltip.tsx
      skeleton.tsx
      separator.tsx
      scroll-area.tsx
      switch.tsx
      dialog.tsx
      dropdown-menu.tsx
      avatar.tsx
      command.tsx
    theme-provider.tsx            # [EXISTS]
    nav-bar.tsx
    footer.tsx
    chat/
      chat-message.tsx
      chat-input.tsx
      streaming-text.tsx
    explain/
      tx-signature-input.tsx
      tx-result.tsx
      error-code-input.tsx
      error-result.tsx
    eval/
      eval-score-hero.tsx
      eval-category-chart.tsx
      eval-task-table.tsx
    dashboard/
      api-key-display.tsx
    shared/
      code-block.tsx
      page-layout.tsx

  lib/
    utils.ts                      # cn() helper [EXISTS]
    constants.ts                  # System prompt, API URLs
    sse.ts                        # SSE stream parsing
    api-client.ts                 # Typed API helpers
    errors.ts                     # Error lookup table
    helius.ts                     # Helius API client

  hooks/
    use-chat.ts                   # Chat state management
    use-streaming.ts              # SSE streaming hook
    use-api-key.ts                # API key management

  data/
    eval-results.json             # Static eval data (from results/phase1/)
    error-table.json              # Static error lookup (1,914 errors)

  public/
    logo.svg                      # SLM logo/wordmark
    og-image.png                  # Social preview

  docs/                           # Product documentation (this directory)
    PRODUCT.md
    ARCHITECTURE.md
    PAGES.md
    API.md
    COMPONENTS.md
    ROUTES.md                     # This file
    DATA.md
    EXTERNAL-CLIENTS.md
    IMPLEMENTATION-ORDER.md
```

## Route Map

| URL | File | Type | Description |
|-----|------|------|-------------|
| `/` | `app/page.tsx` | Page | Landing page |
| `/chat` | `app/chat/page.tsx` | Page | Chat interface |
| `/explain/tx` | `app/explain/tx/page.tsx` | Page | Transaction explainer |
| `/explain/error` | `app/explain/error/page.tsx` | Page | Error decoder |
| `/docs` | `app/docs/page.tsx` | Page | API documentation |
| `/eval` | `app/eval/page.tsx` | Page | Eval dashboard |
| `/dashboard` | `app/dashboard/page.tsx` | Page | User dashboard |
| `/api/chat` | `app/api/chat/route.ts` | API | Chat completions |
| `/api/explain/tx` | `app/api/explain/tx/route.ts` | API | Tx explanation |
| `/api/explain/error` | `app/api/explain/error/route.ts` | API | Error decoding |
| `/api/health` | `app/api/health/route.ts` | API | Health check |
