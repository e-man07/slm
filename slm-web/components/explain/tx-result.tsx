"use client"

import { MarkdownContent } from "@/components/shared/markdown-content"
import { shortenAddress, formatSolAmount } from "@/lib/helius"
import type { TxData } from "@/lib/sse"

interface TxInstruction {
  programId?: string
  accounts?: string[]
  data?: string
}

interface TxResultProps {
  txData: TxData | null
  explanation: string
  isStreaming: boolean
}

export function TxResult({ txData, explanation, isStreaming }: TxResultProps) {
  const instructions = (txData?.instructions ?? []) as TxInstruction[]
  const validInstructions = instructions.filter((ix) => ix.programId)

  return (
    <div className="space-y-8">
      {txData && (
        <div className="grid border border-border md:grid-cols-[1fr_1.4fr]">
          {/* Left: metadata */}
          <aside className="flex flex-col gap-5 border-b border-border p-6 md:border-b-0 md:border-r">
            {/* Status */}
            <div className="flex items-center gap-2.5 text-[11px] uppercase tracking-[0.14em] slm-accent">
              <span
                className="inline-block size-2 rounded-full"
                style={{
                  background: txData.status === "success" ? "var(--slm-accent)" : "var(--destructive)",
                  animation: "pulse-dot 2s infinite",
                }}
              />
              {txData.status === "success" ? "Success" : "Failed"} &middot; Mainnet
            </div>

            {/* Key-value rows */}
            <div>
              <KeyRow label="Type" value={txData.type} first />
              <KeyRow label="Fee" value={`${formatSolAmount(txData.fee * 1e9)} SOL`} />
              <KeyRow label="Fee Payer" value={shortenAddress(txData.feePayer, 6)} />
              <KeyRow label="Instructions" value={String(txData.instructions.length)} />
              {txData.blockTime && (
                <KeyRow
                  label="Block time"
                  value={new Date(txData.blockTime * 1000).toLocaleString()}
                />
              )}
            </div>

            {/* Token transfers */}
            {txData.tokenTransfers.length > 0 && (
              <div>
                <div className="eyebrow" style={{ color: "var(--muted-foreground)" }}>token transfers</div>
                <div className="mt-2 space-y-1">
                  {txData.tokenTransfers.map((t, i) => (
                    <div key={i} className="flex items-center justify-between text-[11px]">
                      <span className="text-muted-foreground">
                        {shortenAddress(t.fromUserAccount ?? "unknown")} &rarr;{" "}
                        {shortenAddress(t.toUserAccount ?? "unknown")}
                      </span>
                      <span className="font-medium">
                        {t.tokenAmount} {shortenAddress(t.mint)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </aside>

          {/* Right: explanation */}
          <div className="p-6">
            <div className="mb-3.5 flex items-center justify-between">
              <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Plain english</span>
              {isStreaming && (
                <span className="flex items-center gap-1.5 text-[10px] slm-accent">
                  <span
                    className="inline-block size-1.5"
                    style={{ background: "var(--slm-accent)", animation: "pulse-dot 1s infinite" }}
                  />
                  streaming
                </span>
              )}
            </div>
            <div className="text-[13.5px] leading-[1.7]">
              <MarkdownContent content={explanation} isStreaming={isStreaming} />
            </div>
          </div>
        </div>
      )}

      {/* Instructions list */}
      {txData && validInstructions.length > 0 && (
        <div className="border border-border">
          <div className="flex items-center justify-between border-b border-border px-5 py-3.5 text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
            <span>Instructions &middot; {validInstructions.length}</span>
          </div>
          {validInstructions.map((ix, i) => (
            <div
              key={i}
              className="grid items-center gap-5 border-b border-border px-5 py-4 text-[12.5px] transition-colors hover:bg-muted last:border-b-0"
              style={{ gridTemplateColumns: "32px 160px 1fr auto" }}
            >
              <span className="text-[11px] text-muted-foreground">{String(i + 1).padStart(2, "0")}</span>
              <span className="slm-accent">{shortenAddress(ix.programId!, 8)}</span>
              <span className="text-foreground">{(ix.accounts?.length ?? 0)} accounts</span>
              <span className="text-muted-foreground">&rsaquo;</span>
            </div>
          ))}
        </div>
      )}

      {/* Standalone explanation when no txData */}
      {!txData && (explanation || isStreaming) && (
        <div className="border border-border">
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <span className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">AI Explanation</span>
            {isStreaming && (
              <span className="flex items-center gap-1.5 text-[10px] slm-accent">
                <span
                  className="inline-block size-1.5"
                  style={{ background: "var(--slm-accent)", animation: "pulse-dot 1s infinite" }}
                />
                streaming
              </span>
            )}
          </div>
          <div className="p-5 text-[13.5px] leading-[1.7]">
            <MarkdownContent content={explanation} isStreaming={isStreaming} />
          </div>
        </div>
      )}
    </div>
  )
}

function KeyRow({ label, value, first }: { label: string; value: string; first?: boolean }) {
  return (
    <div className={`flex items-baseline justify-between py-2.5 text-xs ${first ? "" : "border-t border-dashed border-border"}`}>
      <span className="text-[10px] uppercase tracking-[0.08em] text-muted-foreground">{label}</span>
      <span className="mono-num">{value}</span>
    </div>
  )
}
