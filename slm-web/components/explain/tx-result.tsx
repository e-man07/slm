"use client"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { StreamingText } from "@/components/chat/streaming-text"
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

function InstructionsList({ instructions }: { instructions: TxInstruction[] }) {
  // Only show instructions that have at least a programId
  const validInstructions = instructions.filter((ix) => ix.programId)
  if (validInstructions.length === 0) return null

  return (
    <>
      <Separator />
      <div>
        <span className="text-muted-foreground">Instructions</span>
        <Accordion type="multiple" className="mt-2">
          {validInstructions.map((ix, i) => {
            const accounts = ix.accounts ?? []
            return (
              <AccordionItem key={i} value={`ix-${i}`}>
                <AccordionTrigger>
                  <div className="flex flex-col items-start gap-1">
                    <span className="font-mono text-xs">
                      {shortenAddress(ix.programId!)}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {accounts.length} {accounts.length === 1 ? "account" : "accounts"}
                    </span>
                  </div>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="space-y-2 text-xs">
                    <div>
                      <span className="text-muted-foreground">Program ID: </span>
                      <span className="font-mono">{ix.programId}</span>
                    </div>
                    {accounts.length > 0 && (
                      <div>
                        <span className="text-muted-foreground">Accounts: </span>
                        <span className="font-mono">
                          {accounts.map((a) => shortenAddress(a)).join(", ")}
                        </span>
                      </div>
                    )}
                    {ix.data && (
                      <div>
                        <span className="text-muted-foreground">Data: </span>
                        <span className="font-mono break-all">
                          {ix.data.length > 64
                            ? `${ix.data.slice(0, 64)}...`
                            : ix.data}
                        </span>
                      </div>
                    )}
                  </div>
                </AccordionContent>
              </AccordionItem>
            )
          })}
        </Accordion>
      </div>
    </>
  )
}

export function TxResult({ txData, explanation, isStreaming }: TxResultProps) {
  return (
    <div className="space-y-4">
      {txData && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Transaction Details</CardTitle>
              <Badge variant={txData.status === "success" ? "default" : "destructive"}>
                {txData.status}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <span className="text-muted-foreground">Type</span>
                <p className="font-medium">{txData.type}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Fee</span>
                <p className="font-medium">{formatSolAmount(txData.fee * 1e9)} SOL</p>
              </div>
              <div>
                <span className="text-muted-foreground">Fee Payer</span>
                <p className="font-mono text-xs">{shortenAddress(txData.feePayer, 6)}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Instructions</span>
                <p className="font-medium">{txData.instructions.length}</p>
              </div>
              {txData.blockTime && (
                <div>
                  <span className="text-muted-foreground">Block Time</span>
                  <p className="font-medium">
                    {new Date(txData.blockTime * 1000).toLocaleString()}
                  </p>
                </div>
              )}
            </div>

            {txData.tokenTransfers.length > 0 && (
              <>
                <Separator />
                <div>
                  <span className="text-muted-foreground">Token Transfers</span>
                  <div className="mt-1 space-y-1">
                    {txData.tokenTransfers.map((t, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="font-mono">
                          {shortenAddress(t.fromUserAccount ?? "unknown")} →{" "}
                          {shortenAddress(t.toUserAccount ?? "unknown")}
                        </span>
                        <span className="font-medium">
                          {t.tokenAmount} {shortenAddress(t.mint)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}

            <InstructionsList
              instructions={txData.instructions as TxInstruction[]}
            />
          </CardContent>
        </Card>
      )}

      {(explanation || isStreaming) && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">AI Explanation</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm leading-relaxed">
              <StreamingText text={explanation} isStreaming={isStreaming} />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
