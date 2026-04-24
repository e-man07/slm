import Link from "next/link"
import { PageLayout } from "@/components/shared/page-layout"
import { InstallTabs } from "@/components/landing/install-tabs"

const SURFACES = [
  { idx: "A / Browser", title: "Chat", desc: "Ask anything about Solana & Anchor. Streams markdown, code, citations.", href: "/chat" },
  { idx: "B / Browser", title: "Tx Explainer", desc: "Paste a signature, get human-readable breakdown with Helius data.", href: "/explain/tx" },
  { idx: "C / Browser", title: "Error Decoder", desc: "1,914 known errors across 41 programs. Instant fix suggestions.", href: "/explain/error" },
  { idx: "D / Everywhere", title: "CLI \u00b7 MCP", desc: "Python CLI for your terminal. MCP server for Claude Code, Cursor, Windsurf & Codex.", href: "/docs" },
] as const

const BENCH_ROWS = [
  { name: "Anchor Constraints", ratio: "15/15", pct: 100, level: "" },
  { name: "CPI Patterns", ratio: "10/10", pct: 100, level: "" },
  { name: "Error Handling", ratio: "10/10", pct: 100, level: "" },
  { name: "SPL Token Ops", ratio: "10/10", pct: 100, level: "" },
  { name: "Tx Construction", ratio: "9/10", pct: 90, level: "" },
  { name: "PDA Derivation", ratio: "13/15", pct: 87, level: "low" },
  { name: "Adversarial", ratio: "6/10", pct: 60, level: "weak" },
] as const


function BenchBar({ pct, level }: { pct: number; level: string }) {
  const barColor =
    level === "weak"
      ? "oklch(0.65 0.14 60)"
      : level === "low"
        ? "var(--slm-accent-dim)"
        : "var(--slm-accent)"
  return (
    <div className="relative h-1 bg-muted">
      <div className="absolute inset-y-0 left-0" style={{ width: `${pct}%`, background: barColor }} />
    </div>
  )
}

export default function Page() {
  return (
    <PageLayout>
      {/* ═══ HERO ═══ */}
      <section className="border-b border-border py-20 pb-14">
        <div className="grid items-start gap-16 md:grid-cols-[1.3fr_1fr]">
          <div>
            <div className="eyebrow">Sealevel / v1.0 / solana language model</div>
            <h1 className="mt-5 text-[clamp(36px,5.4vw,64px)] font-bold leading-[1.02] tracking-[-0.025em] text-balance">
              The Solana coding AI that{" "}
              <span className="slm-accent">actually knows Solana.</span>
            </h1>
            <p className="mt-6 max-w-[44ch] text-base leading-relaxed text-muted-foreground">
              7B model fine-tuned on 270K Solana records from 500+ repos. 91% on Solana benchmarks, 100% HumanEval. Chat, explain transactions,
              decode errors &mdash; in your browser, terminal, or editor.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/chat"
                className="inline-flex items-center gap-2 px-4 py-2.5 text-[13px] font-medium tracking-[0.02em] transition-all hover:opacity-90"
                style={{
                  background: "var(--slm-accent)",
                  color: "oklch(0.153 0.006 107.1)",
                  border: "1px solid var(--slm-accent)",
                }}
              >
                Try it now <span>&rarr;</span>
              </Link>
              <span className="inline-flex items-center gap-2 border border-[var(--slm-border-strong)] px-4 py-2.5 text-[13px] font-medium tracking-[0.02em] text-foreground transition-all hover:border-foreground hover:bg-muted">
                $ pip install slm-cli
              </span>
            </div>
          </div>

          <div>
            <div className="eyebrow">At a glance</div>
            {/* Stats grid */}
            <div className="mt-5 grid grid-cols-2 border border-border bg-card">
              <div className="border-b border-r border-border p-5">
                <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Solana eval</div>
                <div className="mono-num mt-2 text-[28px] font-bold tracking-[-0.02em] slm-accent">
                  91<span className="ml-0.5 text-sm font-normal text-muted-foreground">%</span>
                </div>
                <div className="mt-1 text-[11px] text-muted-foreground">192 / 210 tasks &middot; 13 categories</div>
              </div>
              <div className="border-b border-border p-5">
                <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">HumanEval</div>
                <div className="mono-num mt-2 text-[28px] font-bold tracking-[-0.02em]">
                  100<span className="ml-0.5 text-sm font-normal text-muted-foreground">%</span>
                </div>
                <div className="mt-1 text-[11px] text-muted-foreground">20/20 general coding</div>
              </div>
              <div className="border-r border-border p-5">
                <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Base</div>
                <div className="mt-3 text-lg font-bold">Qwen2.5-Coder-7B</div>
                <div className="mt-1 text-[11px] text-muted-foreground">QLoRA &middot; rank 32</div>
              </div>
              <div className="p-5">
                <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">Training</div>
                <div className="mono-num mt-2 text-[28px] font-bold tracking-[-0.02em]">
                  270<span className="ml-0.5 text-sm font-normal text-muted-foreground">K</span>
                </div>
                <div className="mt-1 text-[11px] text-muted-foreground">from 500+ open-source repos</div>
              </div>
            </div>

            {/* Terminal demo */}
            <div className="mt-7 border border-border terminal-bg">
              <div className="flex items-center justify-between border-b border-border px-3.5 py-2 text-[11px] text-muted-foreground">
                <span>~ slm &middot; chat</span>
                <div className="flex gap-1.5">
                  <span className="inline-block size-2" style={{ background: "var(--slm-border-strong)" }} />
                  <span className="inline-block size-2" style={{ background: "var(--slm-border-strong)" }} />
                  <span className="inline-block size-2" style={{ background: "var(--slm-border-strong)" }} />
                </div>
              </div>
              <div className="min-h-[220px] p-4 text-[12.5px] leading-[1.7]">
                <span className="t-prompt">$</span> slm chat &quot;derive a PDA for a vault&quot;
                <br /><span className="t-muted">&rarr; thinking&hellip;</span>
                <br /><br /><span className="t-comment">{"// anchor 0.30+ — constraint-based derivation"}</span>
                <br /><span className="t-key">#[derive</span>(Accounts)]
                <br />pub struct <span className="t-key">InitVault</span>&lt;&apos;info&gt; {"{"}
                <br />&nbsp;&nbsp;<span className="t-key">#[account</span>(
                <br />&nbsp;&nbsp;&nbsp;&nbsp;init, payer = authority,
                <br />&nbsp;&nbsp;&nbsp;&nbsp;seeds = [<span className="t-str">b&quot;vault&quot;</span>, authority.key().as_ref()],
                <br />&nbsp;&nbsp;&nbsp;&nbsp;bump, space = 8 + Vault::INIT_SPACE,
                <br />&nbsp;&nbsp;)]
                <br />&nbsp;&nbsp;pub vault: Account&lt;&apos;info, Vault&gt;,<span className="cursor-blink" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ SURFACES ═══ */}
      <section className="border-b border-border py-14">
        <div className="section-label">
          <span className="idx">01</span>
          <span>Surfaces</span>
          <span className="line" />
          <span>Everywhere you code</span>
        </div>
        <div className="grid border-l border-border sm:grid-cols-2 md:grid-cols-4">
          {SURFACES.map((s) => (
            <Link
              key={s.title}
              href={s.href}
              className="group relative border-b border-r border-t border-border p-6 transition-colors hover:bg-muted"
            >
              <div className="text-[10px] font-medium tracking-[0.14em] text-muted-foreground">{s.idx}</div>
              <h3 className="mt-4 text-lg font-bold tracking-[-0.01em]">{s.title}</h3>
              <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{s.desc}</p>
              <span className="absolute right-6 top-7 text-muted-foreground transition-all group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-[var(--slm-accent)]">{"\u2197"}</span>
            </Link>
          ))}
        </div>
      </section>

      {/* ═══ BENCHMARK ═══ */}
      <section className="border-b border-border py-14">
        <div className="section-label">
          <span className="idx">02</span>
          <span>Benchmark</span>
          <span className="line" />
          <span>210 tasks &middot; 13 categories</span>
        </div>
        <div className="grid items-start gap-16 md:grid-cols-[1fr_1.4fr]">
          <div className="border border-border p-6">
            <div className="eyebrow" style={{ color: "var(--muted-foreground)" }}>Overall score</div>
            <div className="mono-num text-[84px] font-bold leading-none tracking-[-0.04em] slm-accent">
              91<span className="text-4xl text-muted-foreground">%</span>
            </div>
            <div className="mt-2 text-xs text-muted-foreground">
              192 / 210 tasks &middot; 13 categories &middot; Apr 2026
            </div>
            <div className="my-5 h-px bg-border" />
            <div className="space-y-1 text-xs">
              <div className="flex justify-between py-1"><span className="text-muted-foreground">Base model</span><span>Qwen2.5-Coder-7B (dense)</span></div>
              <div className="flex justify-between py-1"><span className="text-muted-foreground">Method</span><span>QLoRA SFT &middot; r=32</span></div>
              <div className="flex justify-between py-1"><span className="text-muted-foreground">Data</span><span>270K records &middot; 500+ repos</span></div>
              <div className="flex justify-between py-1"><span className="text-muted-foreground">HumanEval</span><span className="slm-accent">100% (20/20)</span></div>
            </div>
          </div>

          <div className="grid gap-px bg-border">
            {BENCH_ROWS.map((row, i) => (
              <div
                key={row.name}
                className="grid items-center gap-4 bg-background px-4 py-3.5 text-[13px]"
                style={{ gridTemplateColumns: "32px 1fr 80px 180px 60px" }}
              >
                <span className="text-[11px] text-muted-foreground">{String(i + 1).padStart(2, "0")}</span>
                <span className="font-medium">{row.name}</span>
                <span className="mono-num text-xs text-muted-foreground">{row.ratio}</span>
                <BenchBar pct={row.pct} level={row.level} />
                <span className="mono-num text-right font-semibold">{row.pct}%</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ INSTALL ═══ */}
      <section className="border-b border-border py-14">
        <InstallTabs />
      </section>

      {/* Guardrails section removed — claims not fully backed by current model */}
    </PageLayout>
  )
}
