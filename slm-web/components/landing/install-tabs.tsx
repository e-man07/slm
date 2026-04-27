"use client"

import { useState } from "react"

const PANELS = {
  cli: {
    title: "Python CLI",
    desc: "Drop into any terminal. Streaming, syntax highlighting, session history. Works with any OpenAI-compatible endpoint.",
    items: ["pypi: sealevel", "Commands: chat \u00b7 gen \u00b7 review \u00b7 migrate", "History at ~/.slm/history", "MIT license"],
  },
  mcp: {
    title: "MCP Server",
    desc: "Use Sealevel from Claude Code, Cursor, Windsurf, or Claude Desktop via Model Context Protocol. 5 tools, security audit prompt.",
    items: ["Tools: chat \u00b7 explain-tx \u00b7 decode-error \u00b7 migrate \u00b7 review", "Prompt: security-review", "Transport: stdio or HTTP", "Works with Claude Code, Cursor, Windsurf, Codex"],
  },
} as const

type Tab = keyof typeof PANELS

function TerminalCode({ tab }: { tab: Tab }) {
  switch (tab) {
    case "cli":
      return (
        <>
          <span className="t-prompt">$</span> pip install sealevel<br />
          <span className="t-prompt">$</span> slm config --api-key slm_xxx<br />
          <span className="t-prompt">$</span> slm chat <span className="t-str">&quot;how do i derive a PDA?&quot;</span><br /><br />
          <span className="t-muted">&rarr; Streaming from slm-solana (7B)&hellip;</span><br />
          <span className="t-comment"># use Anchor 0.30+ constraint-based derivation</span><br />
          <span className="t-key">#[account</span>(seeds = [<span className="t-str">b&quot;vault&quot;</span>], bump)]<span className="cursor-blink" />
        </>
      )
    case "mcp":
      return (
        <>
          <span className="t-comment"># Claude Code</span><br />
          <span className="t-prompt">$</span> claude mcp add sealevel https://mcp.sealevel.tech/mcp<br /><br />
          <span className="t-comment"># Cursor / Windsurf — add to MCP settings:</span><br />
          {"{"}<span className="t-key">&quot;mcpServers&quot;</span>: {"{"}<br />
          &nbsp;&nbsp;<span className="t-key">&quot;sealevel&quot;</span>: {"{"} <span className="t-str">&quot;url&quot;</span>: <span className="t-str">&quot;https://mcp.sealevel.tech/mcp&quot;</span> {"}"}<br />
          {"}}"}<span className="cursor-blink" />
        </>
      )
  }
}

export function InstallTabs() {
  const [active, setActive] = useState<Tab>("cli")
  const panel = PANELS[active]

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-6 mb-6">
        <div>
          <div className="section-label" style={{ marginBottom: 6 }}>
            <span className="idx">03</span>
            <span>Get started</span>
          </div>
          <h2 className="text-[28px] font-bold tracking-[-0.02em]">Pick your surface.</h2>
        </div>
        <div className="flex border border-border">
          {(Object.keys(PANELS) as Tab[]).map((key) => (
            <button
              key={key}
              className={`border-r border-border px-3.5 py-2.5 text-xs tracking-[0.04em] transition-colors last:border-r-0 ${
                active === key ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
              onClick={() => setActive(key)}
            >
              {key.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
      <div className="grid border border-border md:grid-cols-2">
        <div className="min-h-[200px] border-b border-border p-7 text-[13px] leading-[1.8] terminal-bg md:border-b-0 md:border-r">
          <TerminalCode tab={active} />
        </div>
        <div className="p-7">
          <h3 className="text-base font-bold">{panel.title}</h3>
          <p className="mt-2.5 text-[13px] leading-relaxed text-muted-foreground">{panel.desc}</p>
          <ul className="mt-4 list-none space-y-0 p-0">
            {panel.items.map((item) => (
              <li key={item} className="flex gap-2.5 py-1.5 text-xs text-muted-foreground">
                <span className="slm-accent">&rarr;</span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
