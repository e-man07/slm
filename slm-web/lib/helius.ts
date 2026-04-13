import { HELIUS_API_KEY, API_URLS } from "./constants"

export interface HeliusTxData {
  description: string
  type: string
  fee: number
  feePayer: string
  signature: string
  slot: number
  timestamp: number
  nativeTransfers: {
    fromUserAccount: string
    toUserAccount: string
    amount: number
  }[]
  tokenTransfers: {
    fromUserAccount: string
    toUserAccount: string
    fromTokenAccount: string
    toTokenAccount: string
    tokenAmount: number
    mint: string
    tokenStandard: string
  }[]
  instructions: {
    programId: string
    data: string
    accounts: string[]
    innerInstructions: unknown[]
  }[]
}

export async function fetchEnhancedTransaction(
  signature: string,
): Promise<HeliusTxData | null> {
  const url = `${API_URLS.HELIUS_BASE}/v0/transactions/?api-key=${HELIUS_API_KEY}`

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transactions: [signature] }),
  })

  if (!response.ok) {
    if (response.status === 404) return null
    throw new Error(`Helius API error: ${response.status}`)
  }

  const data = await response.json()
  if (!Array.isArray(data) || data.length === 0) return null

  return data[0] as HeliusTxData
}

export function formatSolAmount(lamports: number): string {
  return (lamports / 1_000_000_000).toFixed(6)
}

export function shortenAddress(address: string, chars = 4): string {
  return `${address.slice(0, chars)}...${address.slice(-chars)}`
}
