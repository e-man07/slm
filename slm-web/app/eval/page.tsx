import { PageLayout } from "@/components/shared/page-layout"
import evalData from "@/data/eval-results.json"

const CATEGORY_LABELS: Record<string, string> = {
  pda_derivation: "PDA Derivation",
  anchor_constraints: "Anchor Constraints",
  spl_token_ops: "SPL Token Ops",
  cpi_patterns: "CPI Patterns",
  error_handling: "Error Handling",
  adversarial: "Adversarial",
  transaction_construction: "Tx Construction",
  pda_advanced: "PDA Advanced",
  anchor_advanced: "Anchor Advanced",
  token_advanced: "Token Advanced",
  cpi_advanced: "CPI Advanced",
  error_advanced: "Error Advanced",
  tx_advanced: "Tx Advanced",
  security: "Security",
  defi: "DeFi Patterns",
  nft_metaplex: "NFT / Metaplex",
  web3_client: "Web3 Client",
  testing: "Testing",
  performance: "Performance",
  adversarial_extended: "Adversarial Ext.",
}

export default function EvalPage() {
  const { overall, categories } = evalData

  const categoryArray = Object.entries(categories).map(([name, data]) => ({
    name,
    passed: (data as { passed: number }).passed,
    total: (data as { total: number }).total,
    score: (data as { score: number }).score,
  }))

  // Sort: highest score first, adversarial last
  categoryArray.sort((a, b) => {
    if (a.name === "adversarial") return 1
    if (b.name === "adversarial") return -1
    return b.score - a.score
  })

  const percentage = Math.round(overall.score * 1000) / 10
  const metaRows = [
    { label: "Base model", value: "Qwen2.5-Coder-7B-Instruct (7B dense)" },
    { label: "Training", value: "SFT on 270K records from 500+ repos" },
    { label: "LoRA rank", value: "32 (alpha=64)" },
    { label: "HumanEval", value: "20/20 (100%)" },
    {
      label: "Eval date",
      value: new Date(evalData.timestamp).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      }),
    },
    { label: "Benchmark", value: "210-task Solana/Anchor \u00b7 13 categories" },
  ]

  return (
    <PageLayout>
      <div style={{ fontFamily: "'JetBrains Mono', monospace" }}>
        {/* ── Header ── */}
        <div className="mb-10 mt-12">
          <p
            className="eyebrow mb-3 text-[11px] uppercase tracking-[0.18em]"
            style={{ color: "oklch(0.65 0.05 130)" }}
          >
            03 / benchmark
          </p>
          <h1
            className="text-4xl font-semibold tracking-tight"
            style={{ color: "oklch(0.97 0 0)" }}
          >
            Evaluation.
          </h1>
          <p
            className="mt-2 max-w-xl text-sm leading-relaxed"
            style={{ color: "oklch(0.55 0.02 130)" }}
          >
            210-task Solana / Anchor benchmark across 13 categories. Measuring
            code generation quality for on-chain programs, CPI patterns, PDA
            derivation, and adversarial robustness.
          </p>
        </div>

        {/* ── Hero split ── */}
        <div
          className="grid grid-cols-1 md:grid-cols-[1.2fr_1fr]"
          style={{
            border: "1px solid oklch(0.30 0.02 130)",
          }}
        >
          {/* Left: giant score */}
          <div
            className="eval-hero-left flex flex-col justify-center p-5 md:p-8"
            style={{
              borderBottom: "1px solid oklch(0.30 0.02 130)",
              background: "oklch(0.13 0.01 130)",
            }}
          >
            <p
              className="mono-num leading-none font-semibold text-[clamp(64px,15vw,120px)]"
              style={{
                color: "var(--slm-accent, oklch(0.89 0.19 128))",
                fontVariantNumeric: "tabular-nums",
                letterSpacing: "-0.04em",
              }}
            >
              {percentage}%
            </p>
            <p
              className="mt-4 text-xs"
              style={{ color: "oklch(0.55 0.02 130)" }}
            >
              {overall.passed} / {overall.total} passed{" "}
              <span style={{ color: "oklch(0.40 0.02 130)" }}>&middot;</span>{" "}
              +7.5 pts vs previous 30B model{" "}
              <span style={{ color: "oklch(0.40 0.02 130)" }}>&middot;</span>{" "}
              100% HumanEval
            </p>

            {/* Progress bar */}
            <div className="relative mt-6 w-full" style={{ height: "6px" }}>
              <div
                className="absolute inset-0"
                style={{ background: "oklch(0.22 0.01 130)" }}
              />
              <div
                className="absolute inset-y-0 left-0"
                style={{
                  width: `${percentage}%`,
                  background: "var(--slm-accent, oklch(0.89 0.19 128))",
                }}
              />
              {/* Target marker at 90% */}
              <div
                className="absolute top-0 h-full"
                style={{
                  left: "90%",
                  width: "1px",
                  background: "oklch(0.55 0.02 130)",
                }}
              />
            </div>
            <div
              className="mt-1.5 flex justify-between text-[10px]"
              style={{ color: "oklch(0.45 0.02 130)" }}
            >
              <span>0</span>
              <span style={{ position: "relative", left: "40%" }}>
                target&middot;90
              </span>
              <span>100</span>
            </div>
          </div>

          {/* Right: metadata */}
          <div className="flex flex-col p-6">
            {metaRows.map((row, i) => (
              <div
                key={row.label}
                className="flex items-center justify-between py-3 text-xs"
                style={{
                  borderBottom:
                    i < metaRows.length - 1
                      ? "1px dashed oklch(0.25 0.01 130)"
                      : "none",
                }}
              >
                <span style={{ color: "oklch(0.50 0.02 130)" }}>
                  {row.label}
                </span>
                <span style={{ color: "oklch(0.80 0.02 130)" }}>
                  {row.value}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* ── Category grid ── */}
        <div className="mt-14">
          <p
            className="section-label mb-5 text-[11px] uppercase tracking-[0.18em]"
            style={{ color: "oklch(0.55 0.04 130)" }}
          >
            A &middot; By category
          </p>

          <div
            className="grid grid-cols-1 sm:grid-cols-2 gap-0"
            style={{
              border: "1px solid oklch(0.25 0.02 130)",
            }}
          >
            {categoryArray.map((cat) => {
              const pct = Math.round(cat.score * 100)
              const label = CATEGORY_LABELS[cat.name] ?? cat.name
              const isPerfect = pct === 100
              const isWeak = pct < 50
              const isAdversarial = cat.name === "adversarial"

              const scoreColor = isPerfect
                ? "var(--slm-accent, oklch(0.89 0.19 128))"
                : isWeak
                  ? "oklch(0.75 0.14 60)"
                  : "oklch(0.85 0.02 130)"

              const barColor = isPerfect
                ? "var(--slm-accent, oklch(0.89 0.19 128))"
                : isWeak
                  ? "oklch(0.75 0.14 60)"
                  : "oklch(0.60 0.08 130)"

              return (
                <div
                  key={cat.name}
                  className="eval-cat-card p-5"
                  style={{
                    gridColumn: isAdversarial ? "1 / -1" : undefined,
                    borderBottom: "1px solid oklch(0.25 0.02 130)",
                    borderRight: isAdversarial
                      ? "none"
                      : "1px solid oklch(0.25 0.02 130)",
                  }}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className="text-xs"
                      style={{ color: "oklch(0.60 0.02 130)" }}
                    >
                      {label}
                    </span>
                    <span
                      className="text-xs"
                      style={{
                        color: "oklch(0.50 0.02 130)",
                        fontVariantNumeric: "tabular-nums",
                      }}
                    >
                      {cat.passed}/{cat.total}
                    </span>
                  </div>
                  <p
                    className="mt-2 font-semibold"
                    style={{
                      fontSize: "32px",
                      color: scoreColor,
                      fontVariantNumeric: "tabular-nums",
                      lineHeight: 1,
                    }}
                  >
                    {pct}%
                  </p>
                  {/* Progress bar */}
                  <div
                    className="relative mt-3 w-full"
                    style={{ height: "4px" }}
                  >
                    <div
                      className="absolute inset-0"
                      style={{ background: "oklch(0.20 0.01 130)" }}
                    />
                    <div
                      className="absolute inset-y-0 left-0"
                      style={{ width: `${pct}%`, background: barColor }}
                    />
                  </div>
                  {isAdversarial && (
                    <p
                      className="mt-3 text-[11px] leading-relaxed"
                      style={{ color: "oklch(0.45 0.02 130)" }}
                    >
                      Tests model resistance to deprecated APIs, hallucinated
                      patterns, and known Solana anti-patterns. Low scores are
                      expected and indicate room for RLHF alignment.
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        <div className="mb-16" />
      </div>
      <style>{`
        @media (min-width: 768px) {
          .eval-hero-left {
            border-right: 1px solid oklch(0.30 0.02 130) !important;
            border-bottom: none !important;
          }
        }
        @media (max-width: 639px) {
          .eval-cat-card {
            border-right: none !important;
          }
        }
      `}</style>
    </PageLayout>
  )
}
