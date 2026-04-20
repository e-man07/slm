#!/usr/bin/env python3
"""Generate expert-level Solana Q&A SFT records for training.

Template-based generation (no LLM API calls) producing 2000-5000 high-quality
Q&A pairs covering the full spectrum of Solana development: transactions,
client-side TS, security, Token Extensions, DeFi, architecture, testing,
NFTs, internals, and error handling.

Usage:
    python scripts/gen_expert_qa.py                # generate all
    python scripts/gen_expert_qa.py --dry-run      # count only
    python scripts/gen_expert_qa.py --seed 42      # deterministic
    python scripts/gen_expert_qa.py --categories transaction,security
"""

from __future__ import annotations

import json
import random
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from schema import Record, today_str, write_jsonl

app = typer.Typer(invoke_without_command=True)
console = Console()

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_FILE = OUTPUT_DIR / "expert-qa-sft.jsonl"

SYSTEM_PROMPT = (
    "You are Sealevel, an expert Solana and Anchor development assistant. "
    "Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ "
    "patterns (solana-foundation/anchor, InitSpace, ctx.bumps.field_name). "
    "When uncertain, say so rather than guessing. Never suggest reentrancy "
    "guards (Solana prevents reentrancy via CPI depth limits). Never reference "
    "coral-xyz/anchor or declare_id! — these are deprecated."
)


# ---------------------------------------------------------------------------
# Template data structure
# ---------------------------------------------------------------------------

@dataclass
class QATemplate:
    """A single Q&A template that can produce multiple records via variations."""

    questions: list[str]
    answer: str
    language: str = "rust"
    category: str = ""
    variations: list[dict] | None = None

    def expand(self, rng: random.Random) -> list[dict]:
        """Return list of (question, answer) dicts from this template."""
        results = []
        if self.variations:
            for var in self.variations:
                answer = self.answer
                for k, v in var.items():
                    answer = answer.replace(f"{{{k}}}", v)
                for q in self.questions:
                    for k, v in var.items():
                        q = q.replace(f"{{{k}}}", v)
                    results.append({"question": q, "answer": answer})
        else:
            for q in self.questions:
                results.append({"question": q, "answer": self.answer})
        return results


# ---------------------------------------------------------------------------
# Question augmentation — generates extra phrasings from base questions
# ---------------------------------------------------------------------------

AUGMENT_PREFIXES = [
    "Can you explain ",
    "I need help with ",
    "Please show me ",
    "What's the best approach for ",
    "I'm trying to figure out ",
    "Could you walk me through ",
    "Help me understand ",
    "Explain to me ",
    "I want to learn about ",
    "Give me an example of ",
    "What's the recommended way to handle ",
    "Can you demonstrate ",
    "I'm stuck on ",
    "Walk me through ",
    "Teach me about ",
]

AUGMENT_SUFFIXES = [
    " Please include code examples.",
    " With a complete example.",
    " In Anchor.",
    " For a production app.",
    " Step by step.",
    " With best practices.",
    " Show me the code.",
    " Using TypeScript.",
    " With error handling.",
    " For a beginner.",
    " With detailed explanation.",
    " In a Solana program.",
    " Using modern patterns.",
]


def augment_questions(
    questions: list[str], rng: random.Random, target: int = 20
) -> list[str]:
    """Generate additional question phrasings from base questions."""
    augmented = list(questions)  # keep originals
    base = questions[0].lower()

    # Strip leading "how to" / "what" etc to get the core topic
    for prefix in ["how do i ", "how to ", "what is ", "what are ", "show me ",
                    "how does ", "what does ", "how can i ", "when should i "]:
        if base.startswith(prefix):
            core = base[len(prefix):].rstrip("?").rstrip(".")
            break
    else:
        core = base.rstrip("?").rstrip(".")

    # Generate augmented versions
    candidates = []
    for pfx in AUGMENT_PREFIXES:
        candidates.append(f"{pfx}{core}?")
    for sfx in AUGMENT_SUFFIXES:
        candidates.append(f"{questions[0].rstrip('?')}{sfx}")
    # Cross-combine: prefix + suffix for extra volume
    for pfx in AUGMENT_PREFIXES[:5]:
        for sfx in AUGMENT_SUFFIXES[:4]:
            candidates.append(f"{pfx}{core}{sfx}")

    rng.shuffle(candidates)
    for c in candidates:
        if c not in augmented and len(augmented) < target:
            augmented.append(c)

    return augmented


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY 1: TRANSACTION CONSTRUCTION
# ═══════════════════════════════════════════════════════════════════════════

TRANSACTION_TEMPLATES: list[QATemplate] = [
    # -- Versioned transaction with ALT --
    QATemplate(
        questions=[
            "How do I create a versioned transaction with address lookup tables?",
            "Show me how to use address lookup tables in a Solana transaction.",
            "What is the pattern for VersionedTransaction with lookup tables?",
        ],
        answer=textwrap.dedent("""\
            Address Lookup Tables (ALTs) allow you to reference up to 256 accounts in a single transaction by storing addresses in an on-chain table and referencing them by index. This compresses transaction size significantly.

            ```typescript
            import {
              Connection,
              PublicKey,
              TransactionMessage,
              VersionedTransaction,
              AddressLookupTableAccount,
              SystemProgram,
              Keypair,
            } from "@solana/web3.js";

            async function buildWithALT(
              connection: Connection,
              payer: Keypair,
              lookupTableAddress: PublicKey
            ): Promise<VersionedTransaction> {
              // 1. Fetch the lookup table account
              const lookupTableAccount = (
                await connection.getAddressLookupTable(lookupTableAddress)
              ).value;
              if (!lookupTableAccount) throw new Error("Lookup table not found");

              // 2. Build instructions (example: transfer to many accounts)
              const instructions = [
                SystemProgram.transfer({
                  fromPubkey: payer.publicKey,
                  toPubkey: new PublicKey("11111111111111111111111111111112"),
                  lamports: 1_000_000,
                }),
              ];

              // 3. Create a v0 message referencing the ALT
              const { blockhash } = await connection.getLatestBlockhash();
              const messageV0 = new TransactionMessage({
                payerKey: payer.publicKey,
                recentBlockhash: blockhash,
                instructions,
              }).compileToV0Message([lookupTableAccount]);

              // 4. Create and sign the versioned transaction
              const tx = new VersionedTransaction(messageV0);
              tx.sign([payer]);
              return tx;
            }
            ```

            Key points:
            - Use `TransactionMessage.compileToV0Message()` with the lookup table accounts array.
            - The lookup table must be activated (takes ~1 slot after creation) before use.
            - Each ALT can hold up to 256 addresses and can be extended over time."""),
        language="ts",
    ),
    # -- Priority fees --
    QATemplate(
        questions=[
            "How do I set compute unit price and limit for priority fees?",
            "How to add priority fees to a Solana transaction?",
            "What is the correct way to set compute budget for a transaction?",
        ],
        answer=textwrap.dedent("""\
            Priority fees are set via two Compute Budget instructions: one to set the compute unit limit, and one to set the compute unit price (in micro-lamports per CU). Higher prices give your transaction priority in the leader's scheduler.

            ```typescript
            import {
              Connection,
              Keypair,
              Transaction,
              SystemProgram,
              ComputeBudgetProgram,
              sendAndConfirmTransaction,
            } from "@solana/web3.js";

            async function sendWithPriorityFee(
              connection: Connection,
              payer: Keypair,
              destination: PublicKey,
              lamports: number
            ) {
              const tx = new Transaction();

              // Set compute unit limit (default is 200_000 per instruction)
              tx.add(
                ComputeBudgetProgram.setComputeUnitLimit({
                  units: 100_000,
                })
              );

              // Set compute unit price in micro-lamports (1 lamport = 1_000_000 micro-lamports)
              tx.add(
                ComputeBudgetProgram.setComputeUnitPrice({
                  microLamports: 50_000, // 0.05 lamports per CU
                })
              );

              // Add your actual instruction(s)
              tx.add(
                SystemProgram.transfer({
                  fromPubkey: payer.publicKey,
                  toPubkey: destination,
                  lamports,
                })
              );

              const sig = await sendAndConfirmTransaction(connection, tx, [payer]);
              console.log("Transaction confirmed:", sig);
              return sig;
            }
            ```

            Tips:
            - Always place ComputeBudgetProgram instructions first in the transaction.
            - Use `getRecentPrioritizationFees()` to estimate a competitive price.
            - Total priority fee = compute units consumed × micro-lamport price / 1_000_000.
            - Setting a lower compute unit limit than you actually need will cause the transaction to fail."""),
        language="ts",
    ),
    # -- Durable nonce --
    QATemplate(
        questions=[
            "How to send a transaction with a durable nonce?",
            "What are durable nonces and how do I use them in Solana?",
            "How to create an offline-signed transaction with durable nonce?",
        ],
        answer=textwrap.dedent("""\
            Durable nonces replace the recent blockhash with a stored nonce value, allowing transactions to be signed offline and submitted later without expiring after ~60 seconds.

            ```typescript
            import {
              Connection,
              Keypair,
              NONCE_ACCOUNT_LENGTH,
              NonceAccount,
              SystemProgram,
              Transaction,
              sendAndConfirmTransaction,
            } from "@solana/web3.js";

            // Step 1: Create the nonce account
            async function createNonceAccount(
              connection: Connection,
              payer: Keypair,
              nonceKeypair: Keypair,
              authority: PublicKey
            ) {
              const rent = await connection.getMinimumBalanceForRentExemption(
                NONCE_ACCOUNT_LENGTH
              );
              const tx = new Transaction().add(
                SystemProgram.createAccount({
                  fromPubkey: payer.publicKey,
                  newAccountPubkey: nonceKeypair.publicKey,
                  lamports: rent,
                  space: NONCE_ACCOUNT_LENGTH,
                  programId: SystemProgram.programId,
                }),
                SystemProgram.nonceInitialize({
                  noncePubkey: nonceKeypair.publicKey,
                  authorizedPubkey: authority,
                })
              );
              await sendAndConfirmTransaction(connection, tx, [payer, nonceKeypair]);
            }

            // Step 2: Use the nonce in a transaction
            async function sendWithNonce(
              connection: Connection,
              payer: Keypair,
              nonceAccountPubkey: PublicKey,
              nonceAuthority: Keypair
            ) {
              // Fetch the nonce value
              const nonceAccountInfo = await connection.getAccountInfo(nonceAccountPubkey);
              if (!nonceAccountInfo) throw new Error("Nonce account not found");
              const nonceAccount = NonceAccount.fromAccountData(nonceAccountInfo.data);

              const tx = new Transaction();
              // MUST be the first instruction
              tx.add(
                SystemProgram.nonceAdvance({
                  noncePubkey: nonceAccountPubkey,
                  authorizedPubkey: nonceAuthority.publicKey,
                })
              );
              tx.add(
                SystemProgram.transfer({
                  fromPubkey: payer.publicKey,
                  toPubkey: new PublicKey("11111111111111111111111111111112"),
                  lamports: 1_000_000,
                })
              );
              // Use nonce value instead of recent blockhash
              tx.recentBlockhash = nonceAccount.nonce;
              tx.feePayer = payer.publicKey;
              tx.sign(payer, nonceAuthority);

              const sig = await connection.sendRawTransaction(tx.serialize());
              return sig;
            }
            ```

            Key points:
            - The `nonceAdvance` instruction MUST be the first instruction in the transaction.
            - The nonce authority must sign the transaction.
            - Durable nonce transactions never expire — they remain valid until the nonce is advanced."""),
        language="ts",
    ),
    # -- Batch instructions --
    QATemplate(
        questions=[
            "How to batch multiple instructions in one transaction?",
            "Can I send multiple instructions in a single Solana transaction?",
            "How to combine several operations into one atomic transaction?",
        ],
        answer=textwrap.dedent("""\
            Solana transactions can contain multiple instructions that execute atomically — if any instruction fails, the entire transaction rolls back. This is a core advantage of Solana's programming model.

            ```typescript
            import {
              Connection,
              Keypair,
              PublicKey,
              Transaction,
              SystemProgram,
              sendAndConfirmTransaction,
            } from "@solana/web3.js";
            import {
              createTransferInstruction,
              getAssociatedTokenAddress,
              createAssociatedTokenAccountInstruction,
              TOKEN_PROGRAM_ID,
            } from "@solana/spl-token";

            async function batchInstructions(
              connection: Connection,
              payer: Keypair,
              mint: PublicKey,
              recipient: PublicKey
            ) {
              const tx = new Transaction();

              // Instruction 1: SOL transfer
              tx.add(
                SystemProgram.transfer({
                  fromPubkey: payer.publicKey,
                  toPubkey: recipient,
                  lamports: 100_000_000, // 0.1 SOL
                })
              );

              // Instruction 2: Create associated token account if needed
              const recipientATA = await getAssociatedTokenAddress(mint, recipient);
              tx.add(
                createAssociatedTokenAccountInstruction(
                  payer.publicKey, // payer
                  recipientATA,    // ATA address
                  recipient,       // owner
                  mint             // mint
                )
              );

              // Instruction 3: Transfer SPL tokens
              const payerATA = await getAssociatedTokenAddress(mint, payer.publicKey);
              tx.add(
                createTransferInstruction(
                  payerATA,       // source
                  recipientATA,   // destination
                  payer.publicKey, // owner/authority
                  1_000_000       // amount (in smallest unit)
                )
              );

              const sig = await sendAndConfirmTransaction(connection, tx, [payer]);
              console.log("Batch transaction confirmed:", sig);
              return sig;
            }
            ```

            Important limits:
            - Max transaction size: 1232 bytes (serialized).
            - Max compute units: 1.4M (can be raised to 1.4M with ComputeBudgetProgram).
            - Max accounts per transaction: 64 (or 256 with versioned transactions + ALTs).
            - All instructions are atomic — partial execution is impossible."""),
        language="ts",
    ),
    # -- Transaction confirmation and retries --
    QATemplate(
        questions=[
            "How to handle transaction confirmation and retries?",
            "What is the best pattern for reliable transaction sending on Solana?",
            "How to implement transaction retry logic?",
        ],
        answer=textwrap.dedent("""\
            Solana transactions can be dropped by the network, so robust applications need retry logic. The key is to reuse the same blockhash and re-send the same signed transaction rather than creating a new one.

            ```typescript
            import {
              Connection,
              Keypair,
              Transaction,
              TransactionConfirmationStrategy,
              SendTransactionError,
            } from "@solana/web3.js";

            async function sendWithRetry(
              connection: Connection,
              transaction: Transaction,
              signers: Keypair[],
              maxRetries = 3,
              commitment: "confirmed" | "finalized" = "confirmed"
            ): Promise<string> {
              // Get a fresh blockhash with its validity window
              const { blockhash, lastValidBlockHeight } =
                await connection.getLatestBlockhash(commitment);
              transaction.recentBlockhash = blockhash;
              transaction.feePayer = signers[0].publicKey;
              transaction.sign(...signers);

              const rawTx = transaction.serialize();

              for (let attempt = 0; attempt < maxRetries; attempt++) {
                try {
                  const signature = await connection.sendRawTransaction(rawTx, {
                    skipPreflight: false,
                    maxRetries: 0, // we handle retries ourselves
                  });

                  // Wait for confirmation with timeout
                  const confirmationStrategy: TransactionConfirmationStrategy = {
                    signature,
                    blockhash,
                    lastValidBlockHeight,
                  };

                  const result = await connection.confirmTransaction(
                    confirmationStrategy,
                    commitment
                  );

                  if (result.value.err) {
                    throw new Error(
                      `Transaction failed: ${JSON.stringify(result.value.err)}`
                    );
                  }
                  return signature;
                } catch (error) {
                  if (error instanceof SendTransactionError) {
                    console.error(`Attempt ${attempt + 1} failed:`, error.message);
                  }
                  // Check if blockhash is still valid
                  const blockHeight = await connection.getBlockHeight();
                  if (blockHeight > lastValidBlockHeight) {
                    throw new Error("Blockhash expired, transaction cannot land");
                  }
                }
              }
              throw new Error(`Transaction failed after ${maxRetries} attempts`);
            }
            ```

            Best practices:
            - Always use `confirmTransaction` with the blockhash-based strategy (not the deprecated signature-only method).
            - Re-send the same serialized transaction — never re-sign with a new blockhash during retries.
            - Use `skipPreflight: false` during development, `skipPreflight: true` in production for speed.
            - For critical transactions, poll `getSignatureStatuses` in parallel with `confirmTransaction`."""),
        language="ts",
    ),
    # -- Simulate transaction --
    QATemplate(
        questions=[
            "How to simulate a transaction before sending it?",
            "Can I preview what a Solana transaction will do before submitting?",
            "How to use simulateTransaction?",
        ],
        answer=textwrap.dedent("""\
            Simulating a transaction lets you check if it will succeed and inspect logs, return data, and compute usage — without actually landing it on-chain. This is invaluable for debugging and UX.

            ```typescript
            import {
              Connection,
              Keypair,
              Transaction,
              SystemProgram,
              PublicKey,
            } from "@solana/web3.js";

            async function simulateTx(connection: Connection, payer: Keypair) {
              const tx = new Transaction().add(
                SystemProgram.transfer({
                  fromPubkey: payer.publicKey,
                  toPubkey: new PublicKey("11111111111111111111111111111112"),
                  lamports: 1_000_000_000,
                })
              );

              const { blockhash } = await connection.getLatestBlockhash();
              tx.recentBlockhash = blockhash;
              tx.feePayer = payer.publicKey;
              tx.sign(payer);

              const simulation = await connection.simulateTransaction(tx);

              if (simulation.value.err) {
                console.error("Simulation failed:", simulation.value.err);
                console.error("Logs:", simulation.value.logs);
              } else {
                console.log("Simulation succeeded!");
                console.log("Logs:", simulation.value.logs);
                console.log("Units consumed:", simulation.value.unitsConsumed);
              }

              return simulation;
            }
            ```

            Notes:
            - Simulation runs against the current bank state — results may differ if state changes before the real transaction lands.
            - Use `simulation.value.unitsConsumed` to set a tight compute unit limit.
            - `simulation.value.returnData` contains data returned via `sol_set_return_data` (Anchor's return values)."""),
        language="ts",
    ),
    # -- Jito bundles --
    QATemplate(
        questions=[
            "How to use Jito bundles for MEV protection?",
            "How do I submit a Jito bundle on Solana?",
            "What is the pattern for sending transactions via Jito?",
        ],
        answer=textwrap.dedent("""\
            Jito bundles let you submit multiple transactions that execute atomically and in order, with tip-based priority. This protects against sandwich attacks and ensures transaction ordering.

            ```typescript
            import {
              Connection,
              Keypair,
              PublicKey,
              SystemProgram,
              Transaction,
              VersionedTransaction,
              TransactionMessage,
            } from "@solana/web3.js";

            const JITO_TIP_ACCOUNTS = [
              "96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5",
              "HFqU5x63VTqvQss8hp11i4bVqkfRtQ7NmXwkiY8et9ut",
              "Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY",
              "ADaUMid9yfUytqMBgopwjb2DTLSLfjWRdrMi2SUAiDj6",
              "DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh",
              "ADuUkR4vqLUMWXxW9gh6D6L8pMSawimctcNZ5pGwDcEt",
              "DttWaMuVvTiduZRnguLF7jNxTgiMBZ1hyAumKUiL2KRL",
              "3AVi9Tg9Uo68tJfuvoKvqKNWKkC5wPdSSdeBnizKZ6jT",
            ];

            async function sendJitoBundle(
              connection: Connection,
              payer: Keypair,
              transactions: Transaction[],
              tipLamports: number = 10_000 // 0.00001 SOL tip
            ) {
              // Pick a random tip account
              const tipAccount = new PublicKey(
                JITO_TIP_ACCOUNTS[Math.floor(Math.random() * JITO_TIP_ACCOUNTS.length)]
              );

              // Add a tip instruction to the last transaction
              const tipIx = SystemProgram.transfer({
                fromPubkey: payer.publicKey,
                toPubkey: tipAccount,
                lamports: tipLamports,
              });
              transactions[transactions.length - 1].add(tipIx);

              // Sign all transactions
              const { blockhash } = await connection.getLatestBlockhash();
              const serializedTxs: string[] = [];
              for (const tx of transactions) {
                tx.recentBlockhash = blockhash;
                tx.feePayer = payer.publicKey;
                tx.sign(payer);
                serializedTxs.push(
                  Buffer.from(tx.serialize()).toString("base64")
                );
              }

              // Submit to Jito Block Engine
              const response = await fetch(
                "https://mainnet.block-engine.jito.wtf/api/v1/bundles",
                {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    jsonrpc: "2.0",
                    id: 1,
                    method: "sendBundle",
                    params: [serializedTxs],
                  }),
                }
              );

              const result = await response.json();
              console.log("Bundle ID:", result.result);
              return result.result;
            }
            ```

            Key points:
            - A bundle can contain up to 5 transactions.
            - All transactions in a bundle execute sequentially and atomically.
            - The tip goes to the Jito validator and incentivizes bundle inclusion.
            - Use Jito for DEX trades, liquidations, and any MEV-sensitive operations."""),
        language="ts",
    ),
    # -- web3.js v2 pipe pattern --
    QATemplate(
        questions=[
            "How do I build a transaction using @solana/kit (web3.js v2)?",
            "Show me the pipe pattern for @solana/web3.js v2 transactions.",
            "How to use the new functional API in @solana/kit?",
        ],
        answer=textwrap.dedent("""\
            The @solana/kit (web3.js v2) uses a functional, tree-shakeable API with a pipe pattern. This is a significant departure from the class-based v1 API.

            ```typescript
            import {
              createSolanaRpc,
              createSolanaRpcSubscriptions,
              generateKeyPairSigner,
              pipe,
              createTransactionMessage,
              setTransactionMessageFeePayer,
              setTransactionMessageLifetimeUsingBlockhash,
              appendTransactionMessageInstruction,
              signTransactionMessageWithSigners,
              sendAndConfirmTransactionFactory,
              getTransferSolInstruction,
              lamports,
              address,
            } from "@solana/kit";

            async function transferSolV2() {
              const rpc = createSolanaRpc("https://api.mainnet-beta.solana.com");
              const rpcSubscriptions = createSolanaRpcSubscriptions(
                "wss://api.mainnet-beta.solana.com"
              );

              const sender = await generateKeyPairSigner();
              const recipient = address("11111111111111111111111111111112");

              // Get a blockhash for the transaction lifetime
              const { value: blockhash } = await rpc
                .getLatestBlockhash()
                .send();

              // Build transaction using the pipe pattern
              const transactionMessage = pipe(
                createTransactionMessage({ version: 0 }),
                (msg) => setTransactionMessageFeePayer(sender.address, msg),
                (msg) =>
                  setTransactionMessageLifetimeUsingBlockhash(blockhash, msg),
                (msg) =>
                  appendTransactionMessageInstruction(
                    getTransferSolInstruction({
                      source: sender,
                      destination: recipient,
                      amount: lamports(1_000_000n),
                    }),
                    msg
                  )
              );

              // Sign and send
              const signedTx =
                await signTransactionMessageWithSigners(transactionMessage);
              const sendAndConfirm = sendAndConfirmTransactionFactory({
                rpc,
                rpcSubscriptions,
              });
              const signature = await sendAndConfirm(signedTx, {
                commitment: "confirmed",
              });

              console.log("Transaction confirmed:", signature);
            }
            ```

            Key differences from v1:
            - Functions instead of classes — better tree-shaking.
            - `pipe()` composes transaction building steps.
            - Signers are embedded in instructions, so `signTransactionMessageWithSigners` collects them automatically.
            - All numeric amounts use `bigint` (e.g., `lamports(1_000_000n)`).
            - RPC methods return sendable objects — call `.send()` to execute."""),
        language="ts",
    ),
    # -- Partial sign / multisig tx --
    QATemplate(
        questions=[
            "How to partially sign a transaction in Solana?",
            "How to implement a multisig transaction flow?",
            "How to collect multiple signatures for a Solana transaction?",
        ],
        answer=textwrap.dedent("""\
            Partial signing is useful for multi-party transactions where different signers sign at different times. Each signer adds their signature to the transaction independently.

            ```typescript
            import {
              Connection,
              Keypair,
              Transaction,
              SystemProgram,
              PublicKey,
            } from "@solana/web3.js";

            async function partialSignFlow(connection: Connection) {
              // Two parties: Alice pays fees, Bob also signs
              const alice = Keypair.generate();
              const bob = Keypair.generate();
              const recipient = new PublicKey("11111111111111111111111111111112");

              const tx = new Transaction().add(
                SystemProgram.transfer({
                  fromPubkey: alice.publicKey,
                  toPubkey: recipient,
                  lamports: 1_000_000,
                })
              );

              const { blockhash } = await connection.getLatestBlockhash();
              tx.recentBlockhash = blockhash;
              tx.feePayer = alice.publicKey;

              // Alice partially signs
              tx.partialSign(alice);

              // Serialize for transport (e.g., send to Bob)
              const serialized = tx.serialize({
                requireAllSignatures: false,
              });

              // Bob receives, deserializes, and adds his signature
              const recovered = Transaction.from(serialized);
              recovered.partialSign(bob);

              // Now fully signed — send it
              const sig = await connection.sendRawTransaction(recovered.serialize());
              console.log("Sent:", sig);
            }
            ```

            Notes:
            - Use `tx.serialize({ requireAllSignatures: false })` when not all signatures are present yet.
            - The serialized form can be base64-encoded and passed between parties via any channel.
            - For on-chain multisig, consider Squads Protocol (formerly Squads Multisig) which manages signing on-chain."""),
        language="ts",
    ),
    # -- Compute budget estimation --
    QATemplate(
        questions=[
            "How to estimate compute units for a Solana transaction?",
            "How to find the right compute unit limit?",
            "How to optimize compute budget settings?",
        ],
        answer=textwrap.dedent("""\
            You can estimate compute units by simulating the transaction first, then setting the limit with a small buffer. This saves costs (lower CU limit = lower priority fee) and avoids overpaying.

            ```typescript
            import {
              Connection,
              Transaction,
              Keypair,
              ComputeBudgetProgram,
            } from "@solana/web3.js";

            async function estimateAndSetCU(
              connection: Connection,
              transaction: Transaction,
              payer: Keypair
            ): Promise<Transaction> {
              // First, simulate without a CU limit to see actual usage
              const { blockhash } = await connection.getLatestBlockhash();
              transaction.recentBlockhash = blockhash;
              transaction.feePayer = payer.publicKey;
              transaction.sign(payer);

              const simulation = await connection.simulateTransaction(transaction);
              if (simulation.value.err) {
                throw new Error(`Simulation failed: ${JSON.stringify(simulation.value.err)}`);
              }

              const unitsConsumed = simulation.value.unitsConsumed ?? 200_000;
              // Add 10% buffer for safety
              const cuLimit = Math.ceil(unitsConsumed * 1.1);

              // Rebuild transaction with the estimated CU limit
              const optimizedTx = new Transaction();
              optimizedTx.add(
                ComputeBudgetProgram.setComputeUnitLimit({ units: cuLimit })
              );
              // Re-add all original instructions (skip any existing CU instructions)
              for (const ix of transaction.instructions) {
                const programId = ix.programId.toBase58();
                if (programId !== ComputeBudgetProgram.programId.toBase58()) {
                  optimizedTx.add(ix);
                }
              }

              console.log(`Estimated CU: ${unitsConsumed}, setting limit: ${cuLimit}`);
              return optimizedTx;
            }
            ```

            Tips:
            - Simulation-based estimation is the most accurate method.
            - A 10-20% buffer accounts for state changes between simulation and execution.
            - The default limit is 200,000 CU per instruction if not explicitly set.
            - Maximum total per transaction is 1,400,000 CU."""),
        language="ts",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY 2: CLIENT-SIDE TYPESCRIPT
# ═══════════════════════════════════════════════════════════════════════════

CLIENT_TS_TEMPLATES: list[QATemplate] = [
    QATemplate(
        questions=[
            "How to connect to a Solana RPC endpoint?",
            "How do I create a connection to Solana?",
            "What is the basic setup for a Solana TypeScript client?",
        ],
        answer=textwrap.dedent("""\
            The `Connection` class is your gateway to the Solana network. You can connect to mainnet, devnet, testnet, or a custom RPC endpoint.

            ```typescript
            import { Connection, clusterApiUrl, Keypair } from "@solana/web3.js";

            // Connect to devnet
            const devnetConnection = new Connection(
              clusterApiUrl("devnet"),
              "confirmed"
            );

            // Connect to mainnet with a custom RPC (recommended for production)
            const mainnetConnection = new Connection(
              "https://your-rpc-provider.com",
              {
                commitment: "confirmed",
                wsEndpoint: "wss://your-rpc-provider.com",
                confirmTransactionInitialTimeout: 60_000,
              }
            );

            // Check connection
            async function checkConnection(connection: Connection) {
              const version = await connection.getVersion();
              console.log("Solana version:", version["solana-core"]);

              const slot = await connection.getSlot();
              console.log("Current slot:", slot);

              const balance = await connection.getBalance(Keypair.generate().publicKey);
              console.log("Balance:", balance / 1e9, "SOL");
            }
            ```

            Best practices:
            - Always use a dedicated RPC provider (Helius, Triton, QuickNode) for production — public endpoints are rate-limited.
            - Set `commitment: "confirmed"` for a good balance of speed and safety.
            - Use `"finalized"` commitment for irreversible state (e.g., deposits).
            - Configure `wsEndpoint` for WebSocket subscriptions."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to fetch and deserialize an Anchor account?",
            "How do I read Anchor program accounts from TypeScript?",
            "How to use the Anchor IDL to fetch accounts?",
        ],
        answer=textwrap.dedent("""\
            Anchor generates an IDL (Interface Definition Language) that the TypeScript client uses to automatically deserialize account data. Use `@coral-xyz/anchor` (or `@project-serum/anchor` for older projects).

            ```typescript
            import { Connection, PublicKey } from "@solana/web3.js";
            import { AnchorProvider, Program, Idl, BN } from "@coral-xyz/anchor";
            import { Wallet } from "@coral-xyz/anchor";
            // Import your program's IDL (generated by `anchor build`)
            import idl from "./idl/my_program.json";

            // Define the account type (matches your Rust #[account] struct)
            interface VaultAccount {
              authority: PublicKey;
              balance: BN;
              bump: number;
            }

            async function fetchAnchorAccount(
              connection: Connection,
              wallet: Wallet,
              programId: PublicKey,
              accountAddress: PublicKey
            ) {
              const provider = new AnchorProvider(connection, wallet, {
                commitment: "confirmed",
              });
              const program = new Program(idl as Idl, provider);

              // Fetch a single account — Anchor deserializes it automatically
              const vault = await program.account.vault.fetch(accountAddress);
              console.log("Authority:", vault.authority.toBase58());
              console.log("Balance:", vault.balance.toString());

              // Fetch all accounts of a type
              const allVaults = await program.account.vault.all();
              console.log("Total vaults:", allVaults.length);

              // Fetch with filters (memcmp on account data)
              const myVaults = await program.account.vault.all([
                {
                  memcmp: {
                    offset: 8, // skip 8-byte discriminator
                    bytes: wallet.publicKey.toBase58(),
                  },
                },
              ]);
              console.log("My vaults:", myVaults.length);

              return vault;
            }
            ```

            Key points:
            - The 8-byte account discriminator is the first 8 bytes of `sha256("account:<AccountName>")`.
            - `program.account.<name>.fetch()` automatically verifies the discriminator.
            - `BN` (big number) is used for u64/i64 fields — call `.toString()` or `.toNumber()` to convert.
            - The IDL JSON is generated by `anchor build` in `target/idl/`."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to subscribe to account changes via WebSocket?",
            "How do I listen for real-time account updates on Solana?",
            "How to use onAccountChange for live data?",
        ],
        answer=textwrap.dedent("""\
            Solana's WebSocket API lets you subscribe to account changes, program events, logs, and slot updates in real time. This is more efficient than polling.

            ```typescript
            import { Connection, PublicKey, AccountInfo } from "@solana/web3.js";

            function subscribeToAccount(
              connection: Connection,
              accountPubkey: PublicKey
            ): number {
              // Subscribe to any changes on this account
              const subscriptionId = connection.onAccountChange(
                accountPubkey,
                (accountInfo: AccountInfo<Buffer>, context) => {
                  console.log("Account changed at slot:", context.slot);
                  console.log("Data length:", accountInfo.data.length);
                  console.log("Lamports:", accountInfo.lamports);
                  console.log("Owner:", accountInfo.owner.toBase58());

                  // Deserialize the data as needed
                  // For example, reading a u64 at offset 8:
                  if (accountInfo.data.length >= 16) {
                    const value = accountInfo.data.readBigUInt64LE(8);
                    console.log("Value:", value.toString());
                  }
                },
                "confirmed"
              );

              console.log("Subscription ID:", subscriptionId);
              return subscriptionId;
            }

            // Subscribe to all accounts owned by a program
            function subscribeToProgramAccounts(
              connection: Connection,
              programId: PublicKey
            ): number {
              return connection.onProgramAccountChange(
                programId,
                (keyedAccountInfo, context) => {
                  console.log("Account:", keyedAccountInfo.accountId.toBase58());
                  console.log("Slot:", context.slot);
                },
                "confirmed",
                [
                  { dataSize: 165 }, // optional: filter by account size
                ]
              );
            }

            // Subscribe to transaction logs
            function subscribeToLogs(
              connection: Connection,
              programId: PublicKey
            ): number {
              return connection.onLogs(
                programId,
                (logs, context) => {
                  console.log("Signature:", logs.signature);
                  for (const log of logs.logs) {
                    console.log("  ", log);
                  }
                  if (logs.err) {
                    console.error("Error:", logs.err);
                  }
                },
                "confirmed"
              );
            }

            // Don't forget to unsubscribe when done
            async function cleanup(connection: Connection, subId: number) {
              await connection.removeAccountChangeListener(subId);
            }
            ```

            Notes:
            - WebSocket connections require the `wsEndpoint` to be configured on the `Connection`.
            - Always call the appropriate `remove*Listener` method to clean up subscriptions.
            - For high-throughput applications, consider using gRPC (Yellowstone/Geyser) instead of WebSocket."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to use getProgramAccounts with filters?",
            "How do I query all accounts for a Solana program?",
            "How to filter program accounts by data fields?",
        ],
        answer=textwrap.dedent("""\
            `getProgramAccounts` (GPA) fetches all accounts owned by a program. Without filters it can be very expensive, so always add `dataSize` and `memcmp` filters to narrow results.

            ```typescript
            import {
              Connection,
              PublicKey,
              GetProgramAccountsFilter,
            } from "@solana/web3.js";
            import { TOKEN_PROGRAM_ID } from "@solana/spl-token";
            import bs58 from "bs58";

            async function getFilteredAccounts(connection: Connection) {
              // Example 1: Get all SPL token accounts for a specific owner
              const owner = new PublicKey("YourWalletAddressHere...");

              const tokenAccounts = await connection.getProgramAccounts(
                TOKEN_PROGRAM_ID,
                {
                  filters: [
                    { dataSize: 165 }, // SPL Token account size
                    {
                      memcmp: {
                        offset: 32, // Owner field offset in SPL Token account
                        bytes: owner.toBase58(),
                      },
                    },
                  ],
                  encoding: "base64",
                }
              );

              console.log(`Found ${tokenAccounts.length} token accounts`);

              for (const { pubkey, account } of tokenAccounts) {
                const data = account.data as Buffer;
                const mint = new PublicKey(data.subarray(0, 32));
                const amount = data.readBigUInt64LE(64);
                console.log(`Account: ${pubkey.toBase58()}`);
                console.log(`  Mint: ${mint.toBase58()}`);
                console.log(`  Amount: ${amount.toString()}`);
              }

              // Example 2: Get Anchor accounts with a specific discriminator
              const PROGRAM_ID = new PublicKey("YourProgramId...");
              // Anchor discriminator = first 8 bytes of SHA256("account:VaultAccount")
              const discriminator = Buffer.from([/* 8 bytes */]);

              const vaultAccounts = await connection.getProgramAccounts(
                PROGRAM_ID,
                {
                  filters: [
                    {
                      memcmp: {
                        offset: 0,
                        bytes: bs58.encode(discriminator),
                      },
                    },
                  ],
                }
              );

              return { tokenAccounts, vaultAccounts };
            }

            // For large result sets, use getProgramAccounts with dataSlice
            // to fetch only the fields you need
            async function getAccountsSliced(
              connection: Connection,
              programId: PublicKey
            ) {
              const accounts = await connection.getProgramAccounts(programId, {
                dataSlice: {
                  offset: 0,
                  length: 40, // only fetch first 40 bytes
                },
                filters: [{ dataSize: 200 }],
              });

              return accounts;
            }
            ```

            Performance tips:
            - Always use `dataSize` filter if you know the account size — this dramatically reduces RPC load.
            - Use `dataSlice` to fetch only the bytes you need.
            - For very large programs (millions of accounts), use Geyser plugins or specialized indexers instead of GPA.
            - The `memcmp` filter uses base58-encoded bytes by default."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to parse transaction logs in Solana?",
            "How to decode Anchor events from transaction logs?",
            "How to extract program logs from a confirmed transaction?",
        ],
        answer=textwrap.dedent("""\
            Transaction logs contain program output (`msg!()` / Anchor events). You can fetch them from confirmed transactions and parse structured data from them.

            ```typescript
            import { Connection, PublicKey } from "@solana/web3.js";
            import { BorshCoder, EventParser, Idl } from "@coral-xyz/anchor";
            import idl from "./idl/my_program.json";

            async function parseTransactionLogs(
              connection: Connection,
              signature: string
            ) {
              // Fetch the transaction with metadata
              const tx = await connection.getTransaction(signature, {
                commitment: "confirmed",
                maxSupportedTransactionVersion: 0,
              });

              if (!tx?.meta?.logMessages) {
                console.log("No logs found");
                return;
              }

              // Print raw logs
              console.log("=== Raw Logs ===");
              for (const log of tx.meta.logMessages) {
                console.log(log);
              }

              // Parse Anchor events from logs
              const coder = new BorshCoder(idl as Idl);
              const eventParser = new EventParser(
                new PublicKey("YourProgramId..."),
                coder
              );

              const events = eventParser.parseLogs(tx.meta.logMessages);
              for (const event of events) {
                console.log("Event:", event.name);
                console.log("Data:", event.data);
              }

              // Check for errors
              if (tx.meta.err) {
                console.error("Transaction error:", tx.meta.err);
                // Extract custom program error code
                const err = tx.meta.err as any;
                if (err?.InstructionError?.[1]?.Custom !== undefined) {
                  const errorCode = err.InstructionError[1].Custom;
                  console.error("Custom error code:", errorCode);
                  // Anchor error codes start at 6000
                  if (errorCode >= 6000) {
                    const anchorError = errorCode - 6000;
                    console.error("Anchor error index:", anchorError);
                  }
                }
              }
            }
            ```

            Key points:
            - Use `maxSupportedTransactionVersion: 0` to support versioned transactions.
            - Anchor events are base64-encoded in log lines prefixed with `Program data:`.
            - Anchor custom errors start at code 6000 — subtract 6000 to get the index into your `#[error_code]` enum.
            - Built-in Anchor errors (constraint violations) are in the 2000-2999 range."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to generate a keypair from a seed phrase?",
            "How to derive a Solana wallet from a mnemonic?",
            "How to import a wallet using BIP39 seed phrase in TypeScript?",
        ],
        answer=textwrap.dedent("""\
            Solana wallets use Ed25519 key pairs. You can derive them from BIP39 mnemonics using the BIP44 derivation path `m/44'/501'/0'/0'`.

            ```typescript
            import { Keypair } from "@solana/web3.js";
            import * as bip39 from "bip39";
            import { derivePath } from "ed25519-hd-key";

            // Generate a new mnemonic
            function generateMnemonic(): string {
              return bip39.generateMnemonic(256); // 24 words
            }

            // Derive a keypair from mnemonic (Phantom/Solflare compatible)
            function keypairFromMnemonic(
              mnemonic: string,
              accountIndex: number = 0
            ): Keypair {
              const seed = bip39.mnemonicToSeedSync(mnemonic);
              const path = `m/44'/501'/${accountIndex}'/0'`;
              const derived = derivePath(path, seed.toString("hex"));
              return Keypair.fromSeed(derived.key);
            }

            // Derive multiple accounts from same mnemonic
            function deriveMultipleAccounts(
              mnemonic: string,
              count: number
            ): Keypair[] {
              const accounts: Keypair[] = [];
              for (let i = 0; i < count; i++) {
                accounts.push(keypairFromMnemonic(mnemonic, i));
              }
              return accounts;
            }

            // From raw seed bytes (e.g., from a file)
            function keypairFromSeedFile(seedBytes: Uint8Array): Keypair {
              // Solana CLI keypair files contain 64 bytes: 32-byte secret + 32-byte public
              return Keypair.fromSecretKey(seedBytes);
            }

            // Example usage
            const mnemonic = generateMnemonic();
            console.log("Mnemonic:", mnemonic);

            const wallet = keypairFromMnemonic(mnemonic);
            console.log("Public key:", wallet.publicKey.toBase58());
            ```

            Security notes:
            - NEVER log or expose mnemonics or secret keys in production code.
            - Use `Keypair.fromSecretKey()` with the 64-byte format used by `solana-keygen`.
            - The derivation path `m/44'/501'/0'/0'` is the standard used by Phantom, Solflare, and other wallets.
            - For different account indices, increment the third component: `m/44'/501'/1'/0'`, etc."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to sign a message for authentication in Solana?",
            "How to implement Sign-In With Solana (SIWS)?",
            "How to verify a signed message from a Solana wallet?",
        ],
        answer=textwrap.dedent("""\
            Message signing allows off-chain authentication — proving wallet ownership without a transaction. This is the Solana equivalent of "Sign-In With Ethereum."

            ```typescript
            import { Keypair } from "@solana/web3.js";
            import nacl from "tweetnacl";
            import bs58 from "bs58";

            // Server-side: create a challenge message
            function createSignInMessage(
              domain: string,
              publicKey: string,
              nonce: string
            ): string {
              const now = new Date().toISOString();
              return [
                `${domain} wants you to sign in with your Solana account:`,
                publicKey,
                "",
                `Nonce: ${nonce}`,
                `Issued At: ${now}`,
              ].join("\\n");
            }

            // Client-side: sign the message
            function signMessage(message: string, keypair: Keypair): Uint8Array {
              const messageBytes = new TextEncoder().encode(message);
              const signature = nacl.sign.detached(messageBytes, keypair.secretKey);
              return signature;
            }

            // Server-side: verify the signature
            function verifySignature(
              message: string,
              signature: Uint8Array,
              publicKeyBase58: string
            ): boolean {
              const messageBytes = new TextEncoder().encode(message);
              const publicKeyBytes = bs58.decode(publicKeyBase58);
              return nacl.sign.detached.verify(
                messageBytes,
                signature,
                publicKeyBytes
              );
            }

            // Full flow example
            function authenticationFlow() {
              const keypair = Keypair.generate();
              const nonce = Math.random().toString(36).substring(2);

              // 1. Server creates challenge
              const message = createSignInMessage(
                "myapp.com",
                keypair.publicKey.toBase58(),
                nonce
              );

              // 2. Client signs
              const signature = signMessage(message, keypair);
              console.log("Signature:", bs58.encode(signature));

              // 3. Server verifies
              const isValid = verifySignature(
                message,
                signature,
                keypair.publicKey.toBase58()
              );
              console.log("Valid signature:", isValid); // true
            }
            ```

            Notes:
            - Use `tweetnacl` for Ed25519 signing/verification — it's the standard in Solana ecosystem.
            - In browser wallets (Phantom, Solflare), use `wallet.signMessage(encodedMessage)`.
            - Always include a nonce and timestamp to prevent replay attacks.
            - The SIWS standard (EIP-4361 equivalent) provides a structured message format."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to get the token balance of a wallet?",
            "How to fetch all SPL token holdings for an address?",
            "How to check token balances on Solana?",
        ],
        answer=textwrap.dedent("""\
            You can fetch token balances using `getTokenAccountsByOwner` which returns all SPL token accounts for a given wallet address, or use `getTokenAccountBalance` for a specific token account.

            ```typescript
            import {
              Connection,
              PublicKey,
            } from "@solana/web3.js";
            import {
              TOKEN_PROGRAM_ID,
              TOKEN_2022_PROGRAM_ID,
              AccountLayout,
              getAssociatedTokenAddress,
            } from "@solana/spl-token";

            interface TokenBalance {
              mint: string;
              amount: bigint;
              decimals: number;
              uiAmount: number;
            }

            async function getAllTokenBalances(
              connection: Connection,
              owner: PublicKey
            ): Promise<TokenBalance[]> {
              const balances: TokenBalance[] = [];

              // Fetch SPL Token accounts
              const tokenAccounts = await connection.getTokenAccountsByOwner(owner, {
                programId: TOKEN_PROGRAM_ID,
              });

              // Also fetch Token-2022 accounts
              const token2022Accounts = await connection.getTokenAccountsByOwner(owner, {
                programId: TOKEN_2022_PROGRAM_ID,
              });

              const allAccounts = [
                ...tokenAccounts.value,
                ...token2022Accounts.value,
              ];

              for (const { account } of allAccounts) {
                const data = AccountLayout.decode(account.data);
                const mint = new PublicKey(data.mint);

                // Get mint info for decimals
                const mintInfo = await connection.getTokenSupply(mint);
                const decimals = mintInfo.value.decimals;
                const amount = data.amount;
                const uiAmount = Number(amount) / Math.pow(10, decimals);

                if (amount > 0n) {
                  balances.push({
                    mint: mint.toBase58(),
                    amount,
                    decimals,
                    uiAmount,
                  });
                }
              }

              return balances;
            }

            // Get balance for a specific token
            async function getSpecificTokenBalance(
              connection: Connection,
              owner: PublicKey,
              mint: PublicKey
            ): Promise<number> {
              const ata = await getAssociatedTokenAddress(mint, owner);
              try {
                const balance = await connection.getTokenAccountBalance(ata);
                return Number(balance.value.uiAmount);
              } catch {
                return 0; // Account doesn't exist
              }
            }
            ```

            Tips:
            - `getTokenAccountsByOwner` returns raw account data — use `AccountLayout.decode()` to parse.
            - Remember to check both `TOKEN_PROGRAM_ID` and `TOKEN_2022_PROGRAM_ID` for full coverage.
            - For production UIs, use `getTokenAccountBalance` with the ATA address for specific tokens.
            - The `uiAmount` in RPC responses is already adjusted for decimals."""),
        language="ts",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY 3: SECURITY BEST PRACTICES
# ═══════════════════════════════════════════════════════════════════════════

SECURITY_TEMPLATES: list[QATemplate] = [
    QATemplate(
        questions=[
            "What are the most common Solana program vulnerabilities?",
            "What security issues should I watch for in Solana programs?",
            "What are the top Solana smart contract attack vectors?",
        ],
        answer=textwrap.dedent("""\
            The most common vulnerabilities in Solana programs fall into several categories. Understanding these is critical for writing secure on-chain code.

            **1. Missing Owner Checks**
            Failing to verify that an account is owned by the expected program allows attackers to pass in fake accounts with crafted data.

            ```rust
            // VULNERABLE: No owner check
            let data_account = &ctx.accounts.data_account;
            let data = DataAccount::try_from_slice(&data_account.data.borrow())?;

            // SECURE: Anchor handles this automatically with #[account]
            #[derive(Accounts)]
            pub struct SecureInstruction<'info> {
                #[account(
                    has_one = authority,
                    owner = crate::ID, // explicit owner check (Anchor does this by default)
                )]
                pub data_account: Account<'info, DataAccount>,
                pub authority: Signer<'info>,
            }
            ```

            **2. Missing Signer Checks**
            Not verifying that a required party actually signed the transaction.

            ```rust
            // VULNERABLE: authority is just AccountInfo, not Signer
            pub authority: AccountInfo<'info>,

            // SECURE: Use Signer type
            pub authority: Signer<'info>,
            ```

            **3. Arithmetic Overflow/Underflow**
            Using unchecked arithmetic that wraps around.

            ```rust
            // VULNERABLE
            let result = amount_a + amount_b;

            // SECURE
            let result = amount_a.checked_add(amount_b)
                .ok_or(ErrorCode::MathOverflow)?;
            ```

            **4. Account Reloading (Stale Data)**
            Reading account data before a CPI that modifies it, then using stale values.

            ```rust
            // After CPI that modifies vault_account, reload:
            ctx.accounts.vault_account.reload()?;
            ```

            **5. PDA Substitution**
            Not verifying PDA seeds, allowing attackers to substitute a different PDA.

            ```rust
            // SECURE: Verify seeds
            #[account(
                seeds = [b"vault", authority.key().as_ref()],
                bump = vault.bump,
            )]
            pub vault: Account<'info, Vault>,
            ```

            **6. Closing Accounts Insecurely**
            Not zeroing data before closing, allowing "revival attacks."

            ```rust
            // SECURE: Use Anchor's close constraint
            #[account(
                mut,
                close = authority, // zeroes data and transfers lamports
            )]
            pub account_to_close: Account<'info, MyAccount>,
            ```

            Always use Anchor's constraint system — it eliminates most of these vulnerabilities by default."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How to prevent account confusion attacks?",
            "What is an account substitution attack in Solana?",
            "How to make sure accounts can't be swapped maliciously?",
        ],
        answer=textwrap.dedent("""\
            Account confusion (or substitution) attacks occur when an attacker passes an unexpected account that satisfies type constraints but contains different data. This is especially dangerous with similar account structures.

            ```rust
            use anchor_lang::prelude::*;

            // BAD: Two pools have the same structure — attacker could swap them
            #[derive(Accounts)]
            pub struct SwapVulnerable<'info> {
                #[account(mut)]
                pub pool_a: Account<'info, Pool>,
                #[account(mut)]
                pub pool_b: Account<'info, Pool>,
            }

            // GOOD: Use seeds constraints to pin each account
            #[derive(Accounts)]
            pub struct SwapSecure<'info> {
                #[account(
                    mut,
                    seeds = [b"pool", token_a_mint.key().as_ref()],
                    bump = pool_a.bump,
                )]
                pub pool_a: Account<'info, Pool>,
                #[account(
                    mut,
                    seeds = [b"pool", token_b_mint.key().as_ref()],
                    bump = pool_b.bump,
                    constraint = pool_a.key() != pool_b.key() @ ErrorCode::DuplicatePool,
                )]
                pub pool_b: Account<'info, Pool>,
                pub token_a_mint: Account<'info, Mint>,
                pub token_b_mint: Account<'info, Mint>,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct Pool {
                pub mint: Pubkey,
                pub reserve: u64,
                pub bump: u8,
            }

            #[error_code]
            pub enum ErrorCode {
                #[msg("Duplicate pool accounts")]
                DuplicatePool,
            }
            ```

            Prevention strategies:
            - **Use PDA seeds** to cryptographically bind accounts to expected values.
            - **Use `has_one`** to validate relationships: `#[account(has_one = mint)]`.
            - **Use `constraint`** for custom validation: `#[account(constraint = a.key() != b.key())]`.
            - **Use `Signer`** type for any account that must authorize the action.
            - **Add explicit checks** when two accounts of the same type are passed."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How to safely handle arithmetic overflow in token calculations?",
            "Why should I use checked_add instead of + in Solana programs?",
            "How to do safe math in Solana Rust programs?",
        ],
        answer=textwrap.dedent("""\
            Arithmetic overflow in token calculations can lead to catastrophic loss of funds. In release mode, Rust integers wrap on overflow (u64::MAX + 1 = 0), so you must always use checked arithmetic.

            ```rust
            use anchor_lang::prelude::*;

            #[error_code]
            pub enum ErrorCode {
                #[msg("Math overflow")]
                MathOverflow,
                #[msg("Math underflow")]
                MathUnderflow,
                #[msg("Division by zero")]
                DivisionByZero,
            }

            /// Safe math helper trait
            pub trait SafeMath: Sized {
                fn safe_add(self, rhs: Self) -> Result<Self>;
                fn safe_sub(self, rhs: Self) -> Result<Self>;
                fn safe_mul(self, rhs: Self) -> Result<Self>;
                fn safe_div(self, rhs: Self) -> Result<Self>;
            }

            impl SafeMath for u64 {
                fn safe_add(self, rhs: u64) -> Result<u64> {
                    self.checked_add(rhs).ok_or_else(|| error!(ErrorCode::MathOverflow))
                }
                fn safe_sub(self, rhs: u64) -> Result<u64> {
                    self.checked_sub(rhs).ok_or_else(|| error!(ErrorCode::MathUnderflow))
                }
                fn safe_mul(self, rhs: u64) -> Result<u64> {
                    self.checked_mul(rhs).ok_or_else(|| error!(ErrorCode::MathOverflow))
                }
                fn safe_div(self, rhs: u64) -> Result<u64> {
                    self.checked_div(rhs).ok_or_else(|| error!(ErrorCode::DivisionByZero))
                }
            }

            impl SafeMath for u128 {
                fn safe_add(self, rhs: u128) -> Result<u128> {
                    self.checked_add(rhs).ok_or_else(|| error!(ErrorCode::MathOverflow))
                }
                fn safe_sub(self, rhs: u128) -> Result<u128> {
                    self.checked_sub(rhs).ok_or_else(|| error!(ErrorCode::MathUnderflow))
                }
                fn safe_mul(self, rhs: u128) -> Result<u128> {
                    self.checked_mul(rhs).ok_or_else(|| error!(ErrorCode::MathOverflow))
                }
                fn safe_div(self, rhs: u128) -> Result<u128> {
                    self.checked_div(rhs).ok_or_else(|| error!(ErrorCode::DivisionByZero))
                }
            }

            // Usage in a swap calculation:
            pub fn calculate_swap_output(
                input_amount: u64,
                input_reserve: u64,
                output_reserve: u64,
                fee_bps: u64, // basis points (e.g., 30 = 0.3%)
            ) -> Result<u64> {
                // Apply fee: effective_input = input * (10000 - fee) / 10000
                let fee_factor = (10_000u64).safe_sub(fee_bps)?;
                let input_with_fee = (input_amount as u128)
                    .safe_mul(fee_factor as u128)?;

                // Constant product: output = (input_with_fee * output_reserve)
                //                           / (input_reserve * 10000 + input_with_fee)
                let numerator = input_with_fee
                    .safe_mul(output_reserve as u128)?;
                let denominator = (input_reserve as u128)
                    .safe_mul(10_000u128)?
                    .safe_add(input_with_fee)?;

                let output = numerator.safe_div(denominator)?;
                Ok(output as u64)
            }
            ```

            Rules:
            - **Never use `+`, `-`, `*`, `/`** for token amounts — always use `checked_*` or a safe math wrapper.
            - **Cast to u128** before multiplying two u64 values to avoid intermediate overflow.
            - **Cast back to u64** only after division, and verify the result fits.
            - Consider using the `uint` crate for U256 if you need larger intermediate values (common in DeFi)."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How to validate account ownership in a Solana program?",
            "How to check that an account belongs to the right program?",
            "How does Anchor validate account owners?",
        ],
        answer=textwrap.dedent("""\
            Every Solana account has an `owner` field indicating which program can modify it. Failing to check ownership lets attackers pass in accounts from different programs with crafted data.

            ```rust
            use anchor_lang::prelude::*;
            use anchor_spl::token::{Token, TokenAccount, Mint};

            #[derive(Accounts)]
            pub struct SecureTransfer<'info> {
                // Anchor's Account<'info, T> automatically verifies:
                // 1. The account owner matches the expected program
                // 2. The account data deserializes correctly as type T
                // 3. The discriminator is correct (for Anchor accounts)

                #[account(
                    mut,
                    // has_one ensures vault.authority == authority.key()
                    has_one = authority,
                    // seeds ensures this is the right PDA
                    seeds = [b"vault", authority.key().as_ref()],
                    bump = vault.bump,
                )]
                pub vault: Account<'info, Vault>,

                // Token accounts are automatically verified as owned by TOKEN_PROGRAM_ID
                #[account(
                    mut,
                    // Verify this token account belongs to the vault PDA
                    constraint = vault_token.owner == vault.key(),
                    // Verify it's the right mint
                    constraint = vault_token.mint == mint.key(),
                )]
                pub vault_token: Account<'info, TokenAccount>,

                #[account(mut)]
                pub user_token: Account<'info, TokenAccount>,

                pub mint: Account<'info, Mint>,
                pub authority: Signer<'info>,
                pub token_program: Program<'info, Token>,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct Vault {
                pub authority: Pubkey,
                pub bump: u8,
            }

            // In native (non-Anchor) programs, you must check manually:
            // if account.owner != &expected_program_id {
            //     return Err(ProgramError::IncorrectProgramId);
            // }
            ```

            Anchor's type system provides these checks automatically:
            - `Account<'info, T>` — checks owner matches T's program, deserializes data
            - `Program<'info, T>` — checks the account is the expected program's executable
            - `Signer<'info>` — checks `is_signer` flag is true
            - `SystemAccount<'info>` — checks owner is System Program
            - `UncheckedAccount<'info>` — NO checks (use with `/// CHECK:` doc comment explaining why it's safe)"""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How to safely close accounts and prevent rent drain?",
            "What is the correct way to close a PDA account in Anchor?",
            "How to prevent account revival attacks when closing?",
        ],
        answer=textwrap.dedent("""\
            When closing an account, you must zero out all data, transfer lamports to the recipient, and ensure the account can't be "revived" by sending it lamports again in the same transaction.

            ```rust
            use anchor_lang::prelude::*;

            #[derive(Accounts)]
            pub struct CloseAccount<'info> {
                #[account(
                    mut,
                    // close = recipient zeroes data + transfers all lamports
                    close = recipient,
                    has_one = authority,
                    seeds = [b"user_data", authority.key().as_ref()],
                    bump = user_data.bump,
                )]
                pub user_data: Account<'info, UserData>,

                #[account(mut)]
                pub authority: Signer<'info>,

                /// CHECK: This is the account receiving the rent lamports
                #[account(mut)]
                pub recipient: AccountInfo<'info>,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct UserData {
                pub authority: Pubkey,
                pub value: u64,
                pub bump: u8,
            }

            // What Anchor's `close` constraint does under the hood:
            // 1. Transfers all lamports from the account to the recipient
            // 2. Sets the account data to the CLOSED_ACCOUNT_DISCRIMINATOR
            // 3. Sets data length to 0
            //
            // This prevents revival because if someone sends lamports to the
            // account address, the System Program now owns it (empty account)
            // and the discriminator check will fail if someone tries to use it
            // as a program account again.

            // For native programs, you'd do this manually:
            // fn close_account_manual(
            //     account: &AccountInfo,
            //     destination: &AccountInfo,
            // ) -> ProgramResult {
            //     // Transfer lamports
            //     let dest_starting_lamports = destination.lamports();
            //     **destination.lamports.borrow_mut() = dest_starting_lamports
            //         .checked_add(account.lamports())
            //         .ok_or(ProgramError::InvalidArgument)?;
            //     **account.lamports.borrow_mut() = 0;
            //
            //     // Zero out data
            //     let mut data = account.data.borrow_mut();
            //     for byte in data.iter_mut() {
            //         *byte = 0;
            //     }
            //     Ok(())
            // }
            ```

            Security notes:
            - Always use Anchor's `close` constraint — it handles the discriminator guard.
            - Be careful with closing accounts inside loops or CPIs — ensure the recipient account is correct.
            - PDAs with deterministic seeds can be re-initialized — consider adding an `is_initialized` flag if re-creation should be prevented.
            - Never send lamports to an account you're about to close in the same transaction."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How to prevent frontrunning in a DEX program?",
            "What is a sandwich attack on Solana and how to prevent it?",
            "How to protect swaps from MEV on Solana?",
        ],
        answer=textwrap.dedent("""\
            Frontrunning/sandwich attacks involve a malicious actor seeing your pending swap, placing a buy before it (driving up the price), and then selling after (capturing the difference). Solana's fast block times reduce but don't eliminate this risk.

            ```rust
            use anchor_lang::prelude::*;

            #[derive(Accounts)]
            pub struct SecureSwap<'info> {
                #[account(mut)]
                pub pool: Account<'info, Pool>,
                #[account(mut)]
                pub user_token_in: Account<'info, TokenAccount>,
                #[account(mut)]
                pub user_token_out: Account<'info, TokenAccount>,
                #[account(mut)]
                pub pool_token_in: Account<'info, TokenAccount>,
                #[account(mut)]
                pub pool_token_out: Account<'info, TokenAccount>,
                pub user: Signer<'info>,
                pub token_program: Program<'info, Token>,
            }

            pub fn swap(
                ctx: Context<SecureSwap>,
                amount_in: u64,
                // KEY: minimum output amount — this is the primary defense
                minimum_amount_out: u64,
                // OPTIONAL: deadline — reject if too much time has passed
                deadline: Option<i64>,
            ) -> Result<()> {
                // Check deadline
                if let Some(deadline) = deadline {
                    let clock = Clock::get()?;
                    require!(
                        clock.unix_timestamp <= deadline,
                        ErrorCode::DeadlineExceeded
                    );
                }

                // Calculate output using constant product formula
                let pool = &ctx.accounts.pool;
                let output_amount = calculate_output(
                    amount_in,
                    pool.reserve_in,
                    pool.reserve_out,
                    pool.fee_bps,
                )?;

                // CRITICAL: Slippage protection
                require!(
                    output_amount >= minimum_amount_out,
                    ErrorCode::SlippageExceeded
                );

                // Execute the swap via CPI transfers...
                // (transfer tokens in, transfer tokens out)

                Ok(())
            }

            #[error_code]
            pub enum ErrorCode {
                #[msg("Output amount less than minimum")]
                SlippageExceeded,
                #[msg("Transaction deadline exceeded")]
                DeadlineExceeded,
            }

            use anchor_spl::token::{Token, TokenAccount};

            #[account]
            pub struct Pool {
                pub reserve_in: u64,
                pub reserve_out: u64,
                pub fee_bps: u64,
            }

            fn calculate_output(
                input: u64, reserve_in: u64, reserve_out: u64, fee_bps: u64
            ) -> Result<u64> {
                let input_128 = input as u128;
                let fee_factor = (10_000u128).checked_sub(fee_bps as u128).unwrap();
                let input_with_fee = input_128.checked_mul(fee_factor).unwrap();
                let numerator = input_with_fee.checked_mul(reserve_out as u128).unwrap();
                let denominator = (reserve_in as u128)
                    .checked_mul(10_000u128).unwrap()
                    .checked_add(input_with_fee).unwrap();
                Ok(numerator.checked_div(denominator).unwrap() as u64)
            }
            ```

            Defense layers:
            1. **`minimum_amount_out`** (slippage protection) — most important defense.
            2. **Deadline parameter** — reject stale transactions.
            3. **Jito bundles** — submit swaps via Jito to ensure atomic execution without public mempool exposure.
            4. **Commit-reveal schemes** — for high-value operations, commit a hash first, then reveal.
            5. On the client side, set tight slippage (0.5-1%) and use `skipPreflight: true` to avoid leaking intent."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "What is the signer privilege escalation attack?",
            "How can signer checks be bypassed in Solana programs?",
            "How to ensure proper authorization in CPI calls?",
        ],
        answer=textwrap.dedent("""\
            Signer privilege escalation occurs when a program makes a CPI (cross-program invocation) that requires a signer, and the calling program inadvertently signs on behalf of an unauthorized party — typically through PDA signing.

            ```rust
            use anchor_lang::prelude::*;

            // VULNERABLE: The program signs as the PDA for any caller
            pub fn vulnerable_withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
                // This PDA signature is granted to anyone who calls this instruction!
                let seeds = &[b"vault".as_ref(), &[ctx.accounts.vault.bump]];
                let signer_seeds = &[&seeds[..]];

                // CPI transfer from vault — anyone can drain it
                anchor_spl::token::transfer(
                    CpiContext::new_with_signer(
                        ctx.accounts.token_program.to_account_info(),
                        anchor_spl::token::Transfer {
                            from: ctx.accounts.vault_token.to_account_info(),
                            to: ctx.accounts.user_token.to_account_info(),
                            authority: ctx.accounts.vault.to_account_info(),
                        },
                        signer_seeds,
                    ),
                    amount,
                )?;
                Ok(())
            }

            // SECURE: Verify the caller is the authorized authority
            #[derive(Accounts)]
            pub struct SecureWithdraw<'info> {
                #[account(
                    seeds = [b"vault", authority.key().as_ref()],
                    bump = vault.bump,
                    has_one = authority, // ensures vault.authority == authority.key()
                )]
                pub vault: Account<'info, Vault>,

                #[account(mut)]
                pub vault_token: Account<'info, TokenAccount>,

                #[account(mut)]
                pub user_token: Account<'info, TokenAccount>,

                // The authorized party MUST sign
                pub authority: Signer<'info>,
                pub token_program: Program<'info, Token>,
            }

            pub fn secure_withdraw(ctx: Context<SecureWithdraw>, amount: u64) -> Result<()> {
                // Now the PDA seeds include the authority's key,
                // AND we verified authority is a signer
                let authority_key = ctx.accounts.authority.key();
                let seeds = &[
                    b"vault".as_ref(),
                    authority_key.as_ref(),
                    &[ctx.accounts.vault.bump],
                ];
                let signer_seeds = &[&seeds[..]];

                anchor_spl::token::transfer(
                    CpiContext::new_with_signer(
                        ctx.accounts.token_program.to_account_info(),
                        anchor_spl::token::Transfer {
                            from: ctx.accounts.vault_token.to_account_info(),
                            to: ctx.accounts.user_token.to_account_info(),
                            authority: ctx.accounts.vault.to_account_info(),
                        },
                        signer_seeds,
                    ),
                    amount,
                )?;
                Ok(())
            }

            use anchor_spl::token::{Token, TokenAccount};

            #[account]
            #[derive(InitSpace)]
            pub struct Vault {
                pub authority: Pubkey,
                pub bump: u8,
            }
            ```

            Key defenses:
            - **Include the authority's key in PDA seeds** — so each authority has a unique PDA.
            - **Use `has_one` constraint** — verifies the stored authority matches the signer.
            - **Use `Signer<'info>`** for any account that must authorize the action.
            - **Audit all CPI calls** — every `invoke_signed` / `CpiContext::new_with_signer` should have a corresponding authorization check."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How to prevent type cosplay attacks in Anchor?",
            "What is account type confusion in Solana?",
            "How does Anchor's discriminator prevent account type attacks?",
        ],
        answer=textwrap.dedent("""\
            Type cosplay (account type confusion) occurs when an attacker passes an account of one type where a different type is expected. If both types have similar data layouts, the attacker can manipulate the program by providing crafted data.

            ```rust
            use anchor_lang::prelude::*;

            // Anchor prevents type cosplay with 8-byte discriminators.
            // Each account type gets a unique discriminator = SHA256("account:<Name>")[..8]

            // These two accounts have different discriminators, so Anchor
            // will reject if you pass a User where an Admin is expected:

            #[account]
            #[derive(InitSpace)]
            pub struct Admin {
                pub authority: Pubkey, // offset 8 (after discriminator)
                pub level: u8,        // offset 40
            }

            #[account]
            #[derive(InitSpace)]
            pub struct User {
                pub wallet: Pubkey,   // offset 8 (same position as Admin.authority!)
                pub points: u8,      // offset 40 (same position as Admin.level!)
            }

            #[derive(Accounts)]
            pub struct AdminAction<'info> {
                // Anchor checks:
                // 1. account.owner == program_id
                // 2. account.data[..8] == SHA256("account:Admin")[..8]
                // 3. Deserializes remaining data as Admin
                // An attacker CANNOT pass a User account here.
                #[account(has_one = authority)]
                pub admin: Account<'info, Admin>,
                pub authority: Signer<'info>,
            }

            // In NATIVE programs (no Anchor), you must implement this yourself:
            // pub const ADMIN_DISCRIMINATOR: [u8; 8] = [0x01, 0x00, 0x00, ...];
            // pub const USER_DISCRIMINATOR: [u8; 8] = [0x02, 0x00, 0x00, ...];
            //
            // fn validate_admin(account: &AccountInfo) -> ProgramResult {
            //     let data = account.data.borrow();
            //     if data[..8] != ADMIN_DISCRIMINATOR {
            //         return Err(ProgramError::InvalidAccountData);
            //     }
            //     if account.owner != program_id {
            //         return Err(ProgramError::IncorrectProgramId);
            //     }
            //     Ok(())
            // }
            ```

            Prevention:
            - **Use Anchor** — discriminators are automatic and checked on every deserialization.
            - For native programs, **add a type tag** as the first field of every account struct.
            - **Never use raw `AccountInfo`** without explicit type validation.
            - If you must use `UncheckedAccount`, add `/// CHECK:` documentation explaining your manual validation."""),
        language="rust",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY 4: TOKEN-2022 / TOKEN EXTENSIONS
# ═══════════════════════════════════════════════════════════════════════════

TOKEN_EXTENSIONS_TEMPLATES: list[QATemplate] = [
    QATemplate(
        questions=[
            "How to create a token with transfer fees using Token-2022?",
            "How to add transfer fees to an SPL token?",
            "How does the transfer fee extension work in Token Extensions?",
        ],
        answer=textwrap.dedent("""\
            Token-2022's transfer fee extension lets you automatically collect fees on every token transfer. The fee is withheld in the destination account and can be harvested by the fee authority.

            ```typescript
            import {
              Connection,
              Keypair,
              SystemProgram,
              Transaction,
              sendAndConfirmTransaction,
            } from "@solana/web3.js";
            import {
              ExtensionType,
              TOKEN_2022_PROGRAM_ID,
              createInitializeMintInstruction,
              createInitializeTransferFeeConfigInstruction,
              getMintLen,
              createMint,
            } from "@solana/spl-token";

            async function createTokenWithTransferFee(
              connection: Connection,
              payer: Keypair,
              mintAuthority: Keypair,
              decimals: number = 9,
              feeBasisPoints: number = 100, // 1%
              maxFee: bigint = BigInt(1_000_000_000) // max fee per transfer
            ) {
              const mintKeypair = Keypair.generate();

              // Calculate space needed for mint with transfer fee extension
              const mintLen = getMintLen([ExtensionType.TransferFeeConfig]);
              const lamports = await connection.getMinimumBalanceForRentExemption(mintLen);

              const tx = new Transaction().add(
                // Create the account
                SystemProgram.createAccount({
                  fromPubkey: payer.publicKey,
                  newAccountPubkey: mintKeypair.publicKey,
                  space: mintLen,
                  lamports,
                  programId: TOKEN_2022_PROGRAM_ID,
                }),
                // Initialize transfer fee config BEFORE mint
                createInitializeTransferFeeConfigInstruction(
                  mintKeypair.publicKey,
                  payer.publicKey,      // transfer fee config authority
                  payer.publicKey,      // withdraw withheld authority
                  feeBasisPoints,       // fee in basis points
                  maxFee,              // maximum fee per transfer
                  TOKEN_2022_PROGRAM_ID
                ),
                // Initialize the mint
                createInitializeMintInstruction(
                  mintKeypair.publicKey,
                  decimals,
                  mintAuthority.publicKey,
                  null, // freeze authority
                  TOKEN_2022_PROGRAM_ID
                )
              );

              await sendAndConfirmTransaction(connection, tx, [payer, mintKeypair]);
              console.log("Mint with transfer fee:", mintKeypair.publicKey.toBase58());
              return mintKeypair.publicKey;
            }
            ```

            Key points:
            - Extension instructions must come BEFORE `initializeMint`.
            - Fees are withheld in the recipient's token account (not sent to a separate address).
            - Use `harvestWithheldTokensToMint` to collect fees from all accounts to the mint.
            - Use `withdrawWithheldTokensFromMint` to withdraw collected fees.
            - `feeBasisPoints` of 100 = 1% fee; `maxFee` caps the fee per transfer."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to create a non-transferable token (soulbound) with Token-2022?",
            "How to make a soulbound token on Solana?",
            "How to prevent token transfers using Token Extensions?",
        ],
        answer=textwrap.dedent("""\
            The `NonTransferable` extension in Token-2022 creates tokens that cannot be transferred between wallets — they're permanently bound to the initial recipient. These are commonly called "soulbound tokens."

            ```typescript
            import {
              Connection,
              Keypair,
              SystemProgram,
              Transaction,
              sendAndConfirmTransaction,
            } from "@solana/web3.js";
            import {
              ExtensionType,
              TOKEN_2022_PROGRAM_ID,
              createInitializeMintInstruction,
              createInitializeNonTransferableMintInstruction,
              getMintLen,
              createAssociatedTokenAccountInstruction,
              createMintToInstruction,
              getAssociatedTokenAddressSync,
            } from "@solana/spl-token";

            async function createSoulboundToken(
              connection: Connection,
              payer: Keypair,
              recipient: PublicKey
            ) {
              const mintKeypair = Keypair.generate();
              const decimals = 0; // NFT-like: no decimals

              // Calculate space for mint with NonTransferable extension
              const mintLen = getMintLen([ExtensionType.NonTransferable]);
              const lamports = await connection.getMinimumBalanceForRentExemption(mintLen);

              // Create and initialize mint
              const createMintTx = new Transaction().add(
                SystemProgram.createAccount({
                  fromPubkey: payer.publicKey,
                  newAccountPubkey: mintKeypair.publicKey,
                  space: mintLen,
                  lamports,
                  programId: TOKEN_2022_PROGRAM_ID,
                }),
                createInitializeNonTransferableMintInstruction(
                  mintKeypair.publicKey,
                  TOKEN_2022_PROGRAM_ID
                ),
                createInitializeMintInstruction(
                  mintKeypair.publicKey,
                  decimals,
                  payer.publicKey,
                  null,
                  TOKEN_2022_PROGRAM_ID
                )
              );

              await sendAndConfirmTransaction(connection, createMintTx, [
                payer,
                mintKeypair,
              ]);

              // Create ATA and mint to recipient
              const ata = getAssociatedTokenAddressSync(
                mintKeypair.publicKey,
                recipient,
                false,
                TOKEN_2022_PROGRAM_ID
              );

              const mintToTx = new Transaction().add(
                createAssociatedTokenAccountInstruction(
                  payer.publicKey,
                  ata,
                  recipient,
                  mintKeypair.publicKey,
                  TOKEN_2022_PROGRAM_ID
                ),
                createMintToInstruction(
                  mintKeypair.publicKey,
                  ata,
                  payer.publicKey,
                  1, // mint exactly 1
                  [],
                  TOKEN_2022_PROGRAM_ID
                )
              );

              await sendAndConfirmTransaction(connection, mintToTx, [payer]);
              console.log("Soulbound token minted:", mintKeypair.publicKey.toBase58());

              // Any attempt to transfer this token will now fail with:
              // "Transfer is disabled for this mint"
              return mintKeypair.publicKey;
            }
            ```

            Use cases:
            - Proof of attendance (POAP)
            - KYC/verification badges
            - Achievement tokens in games
            - Governance eligibility tokens
            - Non-transferable membership/access tokens"""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to implement a transfer hook with Token-2022?",
            "What is a transfer hook in Token Extensions?",
            "How to add custom logic to token transfers using Token-2022?",
        ],
        answer=textwrap.dedent("""\
            Transfer hooks let you execute custom on-chain logic every time a token is transferred. The hook program is invoked via CPI automatically by the Token-2022 program during any transfer instruction.

            ```rust
            use anchor_lang::prelude::*;
            use anchor_spl::token_interface::{Mint, TokenAccount};
            use spl_transfer_hook_interface::instruction::ExecuteInstruction;

            declare_id!("YourTransferHookProgramId111111111111111");

            #[program]
            pub mod transfer_hook {
                use super::*;

                /// This is called automatically during every Token-2022 transfer
                /// for tokens that have this program set as their transfer hook.
                pub fn transfer_hook(ctx: Context<TransferHook>, amount: u64) -> Result<()> {
                    // Example: enforce a transfer cooldown
                    let transfer_state = &mut ctx.accounts.transfer_state;
                    let clock = Clock::get()?;

                    require!(
                        clock.unix_timestamp >= transfer_state.last_transfer + 60,
                        ErrorCode::CooldownNotExpired
                    );

                    transfer_state.last_transfer = clock.unix_timestamp;
                    transfer_state.total_transferred = transfer_state
                        .total_transferred
                        .checked_add(amount)
                        .ok_or(ErrorCode::Overflow)?;

                    msg!("Transfer hook executed: {} tokens", amount);
                    Ok(())
                }

                /// Initialize the extra account meta list for the hook.
                /// This tells Token-2022 which additional accounts the hook needs.
                pub fn initialize_extra_account_meta_list(
                    ctx: Context<InitializeExtraAccountMetaList>,
                ) -> Result<()> {
                    // Define additional accounts the hook requires
                    // These are passed automatically during transfers
                    let extra_metas = &[
                        // PDA for transfer state
                        ExtraAccountMeta::new_with_seeds(
                            &[
                                Seed::Literal { bytes: b"state".to_vec() },
                                Seed::AccountKey { index: 0 }, // source account
                            ],
                            false, // is_signer
                            true,  // is_writable
                        )?,
                    ];

                    // Write the extra account metas to the validation account
                    let account_info = ctx.accounts.extra_account_meta_list.to_account_info();
                    let mut data = account_info.try_borrow_mut_data()?;
                    ExtraAccountMetaList::init::<ExecuteInstruction>(
                        &mut data,
                        extra_metas,
                    )?;

                    Ok(())
                }
            }

            #[derive(Accounts)]
            pub struct TransferHook<'info> {
                #[account(token::mint = mint)]
                pub source_token: InterfaceAccount<'info, TokenAccount>,
                pub mint: InterfaceAccount<'info, Mint>,
                #[account(token::mint = mint)]
                pub destination_token: InterfaceAccount<'info, TokenAccount>,
                /// CHECK: source token owner
                pub owner: AccountInfo<'info>,
                /// CHECK: extra account meta list PDA
                pub extra_account_meta_list: AccountInfo<'info>,
                #[account(
                    mut,
                    seeds = [b"state", source_token.key().as_ref()],
                    bump,
                )]
                pub transfer_state: Account<'info, TransferState>,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct TransferState {
                pub last_transfer: i64,
                pub total_transferred: u64,
            }

            #[error_code]
            pub enum ErrorCode {
                #[msg("Transfer cooldown not expired")]
                CooldownNotExpired,
                #[msg("Arithmetic overflow")]
                Overflow,
            }

            use spl_transfer_hook_interface::collect_extra_account_metas_signer_seeds;
            use spl_tlv_account_resolution::{
                account::ExtraAccountMeta, seeds::Seed, state::ExtraAccountMetaList,
            };

            #[derive(Accounts)]
            pub struct InitializeExtraAccountMetaList<'info> {
                #[account(mut)]
                pub payer: Signer<'info>,
                /// CHECK: validated in CPI
                #[account(mut)]
                pub extra_account_meta_list: AccountInfo<'info>,
                pub mint: InterfaceAccount<'info, Mint>,
                pub system_program: Program<'info, System>,
            }
            ```

            Transfer hook flow:
            1. Create a program implementing the `spl-transfer-hook-interface`.
            2. Initialize the "extra account meta list" — tells Token-2022 which accounts to pass to your hook.
            3. Create the mint with the `TransferHook` extension pointing to your program.
            4. Every `transfer`/`transfer_checked` call on that mint will automatically CPI into your hook."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "What's the difference between SPL Token and Token-2022?",
            "When should I use Token-2022 vs the original Token program?",
            "What are Token Extensions in Solana?",
        ],
        answer=textwrap.dedent("""\
            Token-2022 (also called Token Extensions) is the next-generation token program on Solana. It's backward-compatible with SPL Token but adds powerful extensions that the original program doesn't support.

            **Key differences:**

            | Feature | SPL Token | Token-2022 |
            |---------|-----------|------------|
            | Program ID | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` | `TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb` |
            | Transfer Fees | No | Yes |
            | Transfer Hooks | No | Yes |
            | Confidential Transfers | No | Yes |
            | Non-Transferable (Soulbound) | No | Yes |
            | Interest-Bearing | No | Yes |
            | Default Account State | No | Yes (frozen by default) |
            | Permanent Delegate | No | Yes |
            | CPI Guard | No | Yes |
            | Metadata | Requires Metaplex | Built-in extension |
            | Group/Member | No | Yes |
            | Memo on Transfer | Optional | Can be required |

            ```typescript
            import {
              TOKEN_PROGRAM_ID,        // Original SPL Token
              TOKEN_2022_PROGRAM_ID,   // Token-2022
            } from "@solana/spl-token";

            // Creating a standard token (SPL Token)
            import { createMint } from "@solana/spl-token";
            const standardMint = await createMint(
              connection,
              payer,
              mintAuthority.publicKey,
              freezeAuthority.publicKey,
              9, // decimals
              undefined,
              undefined,
              TOKEN_PROGRAM_ID // explicit: original program
            );

            // Creating a Token-2022 token (no extensions)
            const token2022Mint = await createMint(
              connection,
              payer,
              mintAuthority.publicKey,
              freezeAuthority.publicKey,
              9,
              undefined,
              undefined,
              TOKEN_2022_PROGRAM_ID // Token-2022 program
            );
            ```

            When to use each:
            - **SPL Token**: maximum compatibility with existing DeFi protocols, wallets, and DEXes.
            - **Token-2022**: when you need extensions (transfer fees, hooks, metadata, confidential transfers).
            - Most new projects should evaluate Token-2022 first — ecosystem support has matured significantly.
            - You can use both in the same application — they're different programs with different token accounts."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to add metadata directly on-chain with Token-2022?",
            "How to use the metadata extension in Token Extensions?",
            "How to create a token with built-in metadata on Solana?",
        ],
        answer=textwrap.dedent("""\
            Token-2022's metadata extension stores token metadata (name, symbol, URI, custom fields) directly in the mint account — no separate Metaplex metadata account needed.

            ```typescript
            import {
              Connection,
              Keypair,
              SystemProgram,
              Transaction,
              sendAndConfirmTransaction,
            } from "@solana/web3.js";
            import {
              ExtensionType,
              TOKEN_2022_PROGRAM_ID,
              createInitializeMintInstruction,
              getMintLen,
              createInitializeMetadataPointerInstruction,
              TYPE_SIZE,
              LENGTH_SIZE,
            } from "@solana/spl-token";
            import {
              createInitializeInstruction,
              createUpdateFieldInstruction,
              pack,
              TokenMetadata,
            } from "@solana/spl-token-metadata";

            async function createTokenWithMetadata(
              connection: Connection,
              payer: Keypair,
              name: string,
              symbol: string,
              uri: string
            ) {
              const mintKeypair = Keypair.generate();
              const decimals = 9;

              // Define the metadata
              const metadata: TokenMetadata = {
                mint: mintKeypair.publicKey,
                name,
                symbol,
                uri,
                updateAuthority: payer.publicKey,
                additionalMetadata: [
                  ["description", "A token with on-chain metadata"],
                  ["website", "https://example.com"],
                ],
              };

              // Calculate space: mint + metadata pointer extension + metadata
              const mintLen = getMintLen([ExtensionType.MetadataPointer]);
              const metadataLen = TYPE_SIZE + LENGTH_SIZE + pack(metadata).length;
              const totalLen = mintLen + metadataLen;
              const lamports = await connection.getMinimumBalanceForRentExemption(totalLen);

              const tx = new Transaction().add(
                // Create account
                SystemProgram.createAccount({
                  fromPubkey: payer.publicKey,
                  newAccountPubkey: mintKeypair.publicKey,
                  space: mintLen, // initial space (metadata added later)
                  lamports,
                  programId: TOKEN_2022_PROGRAM_ID,
                }),
                // Initialize metadata pointer (points to self)
                createInitializeMetadataPointerInstruction(
                  mintKeypair.publicKey,
                  payer.publicKey,
                  mintKeypair.publicKey, // metadata lives in the mint itself
                  TOKEN_2022_PROGRAM_ID
                ),
                // Initialize mint
                createInitializeMintInstruction(
                  mintKeypair.publicKey,
                  decimals,
                  payer.publicKey,
                  null,
                  TOKEN_2022_PROGRAM_ID
                ),
                // Initialize metadata
                createInitializeInstruction({
                  programId: TOKEN_2022_PROGRAM_ID,
                  mint: mintKeypair.publicKey,
                  metadata: mintKeypair.publicKey,
                  name: metadata.name,
                  symbol: metadata.symbol,
                  uri: metadata.uri,
                  mintAuthority: payer.publicKey,
                  updateAuthority: payer.publicKey,
                }),
                // Add custom fields
                createUpdateFieldInstruction({
                  programId: TOKEN_2022_PROGRAM_ID,
                  metadata: mintKeypair.publicKey,
                  updateAuthority: payer.publicKey,
                  field: "description",
                  value: "A token with on-chain metadata",
                })
              );

              await sendAndConfirmTransaction(connection, tx, [payer, mintKeypair]);
              console.log("Token with metadata:", mintKeypair.publicKey.toBase58());
              return mintKeypair.publicKey;
            }
            ```

            Advantages over Metaplex:
            - No separate metadata account — lower rent cost.
            - No dependency on Metaplex program.
            - Custom key-value fields via `additionalMetadata`.
            - Can be updated by the `updateAuthority`."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to create an interest-bearing token with Token-2022?",
            "What is the interest-bearing extension in Token Extensions?",
            "How to make a rebasing token on Solana?",
        ],
        answer=textwrap.dedent("""\
            The interest-bearing extension adds a display multiplier to token balances based on a configurable interest rate. The actual balance doesn't change — only the UI amount is scaled by accumulated interest.

            ```typescript
            import {
              Connection,
              Keypair,
              SystemProgram,
              Transaction,
              sendAndConfirmTransaction,
            } from "@solana/web3.js";
            import {
              ExtensionType,
              TOKEN_2022_PROGRAM_ID,
              createInitializeMintInstruction,
              createInitializeInterestBearingMintInstruction,
              getMintLen,
            } from "@solana/spl-token";

            async function createInterestBearingToken(
              connection: Connection,
              payer: Keypair,
              rate: number = 500, // 5% annual rate (in basis points)
            ) {
              const mintKeypair = Keypair.generate();
              const decimals = 9;

              const mintLen = getMintLen([ExtensionType.InterestBearingConfig]);
              const lamports = await connection.getMinimumBalanceForRentExemption(mintLen);

              const tx = new Transaction().add(
                SystemProgram.createAccount({
                  fromPubkey: payer.publicKey,
                  newAccountPubkey: mintKeypair.publicKey,
                  space: mintLen,
                  lamports,
                  programId: TOKEN_2022_PROGRAM_ID,
                }),
                createInitializeInterestBearingMintInstruction(
                  mintKeypair.publicKey,
                  payer.publicKey, // rate authority (can update rate)
                  rate,            // interest rate in basis points
                  TOKEN_2022_PROGRAM_ID
                ),
                createInitializeMintInstruction(
                  mintKeypair.publicKey,
                  decimals,
                  payer.publicKey,
                  null,
                  TOKEN_2022_PROGRAM_ID
                )
              );

              await sendAndConfirmTransaction(connection, tx, [payer, mintKeypair]);
              console.log("Interest-bearing token:", mintKeypair.publicKey.toBase58());
              return mintKeypair.publicKey;
            }

            // Reading the interest-adjusted amount:
            // import { amountToUiAmount } from "@solana/spl-token";
            // const uiAmount = await amountToUiAmount(
            //   connection,
            //   payer,
            //   mintAddress,
            //   rawAmount,
            //   TOKEN_2022_PROGRAM_ID
            // );
            ```

            Important notes:
            - The extension only affects **display amounts** — actual on-chain balances don't change.
            - Interest accrues continuously based on Unix timestamp.
            - The rate authority can update the interest rate at any time.
            - This is useful for stablecoin yield, savings tokens, or bond-like instruments.
            - Rate is in basis points: 100 = 1%, 500 = 5%, 10000 = 100%."""),
        language="ts",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY 5: DEFI PATTERNS
# ═══════════════════════════════════════════════════════════════════════════

DEFI_TEMPLATES: list[QATemplate] = [
    QATemplate(
        questions=[
            "How to implement a constant product AMM (x*y=k) on Solana?",
            "How to build a simple swap pool in Anchor?",
            "Show me an Anchor AMM implementation.",
        ],
        answer=textwrap.dedent("""\
            A constant product AMM maintains the invariant x * y = k, where x and y are the reserves of two tokens. When a user swaps, the product must remain constant (minus fees).

            ```rust
            use anchor_lang::prelude::*;
            use anchor_spl::token::{self, Token, TokenAccount, Mint, Transfer};

            declare_id!("AMMProgram111111111111111111111111111111111");

            #[program]
            pub mod amm {
                use super::*;

                pub fn initialize_pool(
                    ctx: Context<InitializePool>,
                    fee_bps: u16,
                ) -> Result<()> {
                    let pool = &mut ctx.accounts.pool;
                    pool.token_a_mint = ctx.accounts.token_a_mint.key();
                    pool.token_b_mint = ctx.accounts.token_b_mint.key();
                    pool.token_a_vault = ctx.accounts.token_a_vault.key();
                    pool.token_b_vault = ctx.accounts.token_b_vault.key();
                    pool.lp_mint = ctx.accounts.lp_mint.key();
                    pool.fee_bps = fee_bps;
                    pool.authority = ctx.accounts.authority.key();
                    pool.bump = ctx.bumps.pool;
                    Ok(())
                }

                pub fn swap(
                    ctx: Context<Swap>,
                    amount_in: u64,
                    minimum_amount_out: u64,
                    a_to_b: bool,
                ) -> Result<()> {
                    let (vault_in, vault_out) = if a_to_b {
                        (
                            &ctx.accounts.token_a_vault,
                            &ctx.accounts.token_b_vault,
                        )
                    } else {
                        (
                            &ctx.accounts.token_b_vault,
                            &ctx.accounts.token_a_vault,
                        )
                    };

                    let reserve_in = vault_in.amount;
                    let reserve_out = vault_out.amount;

                    // Constant product formula with fee
                    let fee_factor = 10_000u128 - ctx.accounts.pool.fee_bps as u128;
                    let amount_in_with_fee = (amount_in as u128)
                        .checked_mul(fee_factor)
                        .ok_or(ErrorCode::MathOverflow)?;
                    let numerator = amount_in_with_fee
                        .checked_mul(reserve_out as u128)
                        .ok_or(ErrorCode::MathOverflow)?;
                    let denominator = (reserve_in as u128)
                        .checked_mul(10_000u128)
                        .ok_or(ErrorCode::MathOverflow)?
                        .checked_add(amount_in_with_fee)
                        .ok_or(ErrorCode::MathOverflow)?;
                    let amount_out = numerator
                        .checked_div(denominator)
                        .ok_or(ErrorCode::MathOverflow)? as u64;

                    require!(
                        amount_out >= minimum_amount_out,
                        ErrorCode::SlippageExceeded
                    );

                    // Transfer tokens in from user
                    let (user_in, user_out) = if a_to_b {
                        (&ctx.accounts.user_token_a, &ctx.accounts.user_token_b)
                    } else {
                        (&ctx.accounts.user_token_b, &ctx.accounts.user_token_a)
                    };

                    token::transfer(
                        CpiContext::new(
                            ctx.accounts.token_program.to_account_info(),
                            Transfer {
                                from: user_in.to_account_info(),
                                to: vault_in.to_account_info(),
                                authority: ctx.accounts.user.to_account_info(),
                            },
                        ),
                        amount_in,
                    )?;

                    // Transfer tokens out from vault (PDA signs)
                    let pool_key = ctx.accounts.pool.key();
                    let seeds = &[b"pool".as_ref(), pool_key.as_ref(), &[ctx.accounts.pool.bump]];
                    let signer = &[&seeds[..]];

                    token::transfer(
                        CpiContext::new_with_signer(
                            ctx.accounts.token_program.to_account_info(),
                            Transfer {
                                from: vault_out.to_account_info(),
                                to: user_out.to_account_info(),
                                authority: ctx.accounts.pool.to_account_info(),
                            },
                            signer,
                        ),
                        amount_out,
                    )?;

                    msg!("Swapped {} in for {} out", amount_in, amount_out);
                    Ok(())
                }
            }

            #[derive(Accounts)]
            pub struct InitializePool<'info> {
                #[account(
                    init,
                    payer = authority,
                    space = 8 + Pool::INIT_SPACE,
                    seeds = [b"pool", token_a_mint.key().as_ref(), token_b_mint.key().as_ref()],
                    bump,
                )]
                pub pool: Account<'info, Pool>,
                pub token_a_mint: Account<'info, Mint>,
                pub token_b_mint: Account<'info, Mint>,
                #[account(mut)]
                pub token_a_vault: Account<'info, TokenAccount>,
                #[account(mut)]
                pub token_b_vault: Account<'info, TokenAccount>,
                pub lp_mint: Account<'info, Mint>,
                #[account(mut)]
                pub authority: Signer<'info>,
                pub system_program: Program<'info, System>,
                pub token_program: Program<'info, Token>,
            }

            #[derive(Accounts)]
            pub struct Swap<'info> {
                #[account(
                    seeds = [b"pool", pool.token_a_mint.as_ref(), pool.token_b_mint.as_ref()],
                    bump = pool.bump,
                )]
                pub pool: Account<'info, Pool>,
                #[account(mut, constraint = token_a_vault.key() == pool.token_a_vault)]
                pub token_a_vault: Account<'info, TokenAccount>,
                #[account(mut, constraint = token_b_vault.key() == pool.token_b_vault)]
                pub token_b_vault: Account<'info, TokenAccount>,
                #[account(mut)]
                pub user_token_a: Account<'info, TokenAccount>,
                #[account(mut)]
                pub user_token_b: Account<'info, TokenAccount>,
                pub user: Signer<'info>,
                pub token_program: Program<'info, Token>,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct Pool {
                pub token_a_mint: Pubkey,
                pub token_b_mint: Pubkey,
                pub token_a_vault: Pubkey,
                pub token_b_vault: Pubkey,
                pub lp_mint: Pubkey,
                pub fee_bps: u16,
                pub authority: Pubkey,
                pub bump: u8,
            }

            #[error_code]
            pub enum ErrorCode {
                #[msg("Math overflow")]
                MathOverflow,
                #[msg("Slippage tolerance exceeded")]
                SlippageExceeded,
            }
            ```

            This is a simplified AMM — production implementations also need:
            - LP token minting/burning for add/remove liquidity
            - Protocol fee separation
            - TWAP oracle for price feeds
            - Flash loan protection"""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How to create a vault program with deposit/withdraw in Anchor?",
            "How to implement a token vault on Solana?",
            "Show me a simple vault pattern in Anchor.",
        ],
        answer=textwrap.dedent("""\
            A vault program lets users deposit tokens into a PDA-controlled account and withdraw them later. This is a fundamental DeFi building block used in lending, staking, and yield aggregation.

            ```rust
            use anchor_lang::prelude::*;
            use anchor_spl::token::{self, Token, TokenAccount, Mint, Transfer, MintTo, Burn};
            use anchor_spl::associated_token::AssociatedToken;

            declare_id!("Vault11111111111111111111111111111111111111");

            #[program]
            pub mod vault {
                use super::*;

                pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
                    let vault = &mut ctx.accounts.vault;
                    vault.authority = ctx.accounts.authority.key();
                    vault.token_mint = ctx.accounts.token_mint.key();
                    vault.vault_token_account = ctx.accounts.vault_token_account.key();
                    vault.receipt_mint = ctx.accounts.receipt_mint.key();
                    vault.total_deposits = 0;
                    vault.bump = ctx.bumps.vault;
                    Ok(())
                }

                pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
                    require!(amount > 0, ErrorCode::ZeroAmount);

                    let vault = &mut ctx.accounts.vault;
                    let receipt_supply = ctx.accounts.receipt_mint.supply;

                    // Calculate receipt tokens to mint (share-based)
                    let receipt_amount = if receipt_supply == 0 || vault.total_deposits == 0 {
                        amount // 1:1 for first deposit
                    } else {
                        (amount as u128)
                            .checked_mul(receipt_supply as u128)
                            .ok_or(ErrorCode::MathOverflow)?
                            .checked_div(vault.total_deposits as u128)
                            .ok_or(ErrorCode::MathOverflow)? as u64
                    };

                    // Transfer tokens from user to vault
                    token::transfer(
                        CpiContext::new(
                            ctx.accounts.token_program.to_account_info(),
                            Transfer {
                                from: ctx.accounts.user_token_account.to_account_info(),
                                to: ctx.accounts.vault_token_account.to_account_info(),
                                authority: ctx.accounts.user.to_account_info(),
                            },
                        ),
                        amount,
                    )?;

                    // Mint receipt tokens to user
                    let vault_key = vault.key();
                    let seeds = &[b"vault".as_ref(), vault_key.as_ref(), &[vault.bump]];
                    let signer = &[&seeds[..]];

                    token::mint_to(
                        CpiContext::new_with_signer(
                            ctx.accounts.token_program.to_account_info(),
                            MintTo {
                                mint: ctx.accounts.receipt_mint.to_account_info(),
                                to: ctx.accounts.user_receipt_account.to_account_info(),
                                authority: vault.to_account_info(),
                            },
                            signer,
                        ),
                        receipt_amount,
                    )?;

                    vault.total_deposits = vault
                        .total_deposits
                        .checked_add(amount)
                        .ok_or(ErrorCode::MathOverflow)?;

                    msg!("Deposited {} tokens, minted {} receipt tokens", amount, receipt_amount);
                    Ok(())
                }

                pub fn withdraw(ctx: Context<Withdraw>, receipt_amount: u64) -> Result<()> {
                    require!(receipt_amount > 0, ErrorCode::ZeroAmount);

                    let vault = &ctx.accounts.vault;
                    let receipt_supply = ctx.accounts.receipt_mint.supply;

                    // Calculate tokens to return based on share
                    let withdraw_amount = (receipt_amount as u128)
                        .checked_mul(vault.total_deposits as u128)
                        .ok_or(ErrorCode::MathOverflow)?
                        .checked_div(receipt_supply as u128)
                        .ok_or(ErrorCode::MathOverflow)? as u64;

                    // Burn receipt tokens
                    token::burn(
                        CpiContext::new(
                            ctx.accounts.token_program.to_account_info(),
                            Burn {
                                mint: ctx.accounts.receipt_mint.to_account_info(),
                                from: ctx.accounts.user_receipt_account.to_account_info(),
                                authority: ctx.accounts.user.to_account_info(),
                            },
                        ),
                        receipt_amount,
                    )?;

                    // Transfer tokens from vault to user
                    let vault_key = ctx.accounts.vault.key();
                    let bump = ctx.accounts.vault.bump;
                    let seeds = &[b"vault".as_ref(), vault_key.as_ref(), &[bump]];
                    let signer = &[&seeds[..]];

                    token::transfer(
                        CpiContext::new_with_signer(
                            ctx.accounts.token_program.to_account_info(),
                            Transfer {
                                from: ctx.accounts.vault_token_account.to_account_info(),
                                to: ctx.accounts.user_token_account.to_account_info(),
                                authority: ctx.accounts.vault.to_account_info(),
                            },
                            signer,
                        ),
                        withdraw_amount,
                    )?;

                    let vault = &mut ctx.accounts.vault;
                    vault.total_deposits = vault
                        .total_deposits
                        .checked_sub(withdraw_amount)
                        .ok_or(ErrorCode::MathOverflow)?;

                    msg!("Withdrew {} tokens, burned {} receipt tokens", withdraw_amount, receipt_amount);
                    Ok(())
                }
            }

            #[derive(Accounts)]
            pub struct Initialize<'info> {
                #[account(
                    init,
                    payer = authority,
                    space = 8 + Vault::INIT_SPACE,
                    seeds = [b"vault", token_mint.key().as_ref()],
                    bump,
                )]
                pub vault: Account<'info, Vault>,
                pub token_mint: Account<'info, Mint>,
                #[account(
                    init,
                    payer = authority,
                    token::mint = token_mint,
                    token::authority = vault,
                )]
                pub vault_token_account: Account<'info, TokenAccount>,
                #[account(
                    init,
                    payer = authority,
                    mint::decimals = token_mint.decimals,
                    mint::authority = vault,
                )]
                pub receipt_mint: Account<'info, Mint>,
                #[account(mut)]
                pub authority: Signer<'info>,
                pub system_program: Program<'info, System>,
                pub token_program: Program<'info, Token>,
                pub rent: Sysvar<'info, Rent>,
            }

            #[derive(Accounts)]
            pub struct Deposit<'info> {
                #[account(
                    mut,
                    seeds = [b"vault", vault.token_mint.as_ref()],
                    bump = vault.bump,
                )]
                pub vault: Account<'info, Vault>,
                #[account(mut, constraint = vault_token_account.key() == vault.vault_token_account)]
                pub vault_token_account: Account<'info, TokenAccount>,
                #[account(mut, constraint = receipt_mint.key() == vault.receipt_mint)]
                pub receipt_mint: Account<'info, Mint>,
                #[account(mut)]
                pub user_token_account: Account<'info, TokenAccount>,
                #[account(mut)]
                pub user_receipt_account: Account<'info, TokenAccount>,
                pub user: Signer<'info>,
                pub token_program: Program<'info, Token>,
            }

            #[derive(Accounts)]
            pub struct Withdraw<'info> {
                #[account(
                    mut,
                    seeds = [b"vault", vault.token_mint.as_ref()],
                    bump = vault.bump,
                )]
                pub vault: Account<'info, Vault>,
                #[account(mut, constraint = vault_token_account.key() == vault.vault_token_account)]
                pub vault_token_account: Account<'info, TokenAccount>,
                #[account(mut, constraint = receipt_mint.key() == vault.receipt_mint)]
                pub receipt_mint: Account<'info, Mint>,
                #[account(mut)]
                pub user_token_account: Account<'info, TokenAccount>,
                #[account(mut)]
                pub user_receipt_account: Account<'info, TokenAccount>,
                pub user: Signer<'info>,
                pub token_program: Program<'info, Token>,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct Vault {
                pub authority: Pubkey,
                pub token_mint: Pubkey,
                pub vault_token_account: Pubkey,
                pub receipt_mint: Pubkey,
                pub total_deposits: u64,
                pub bump: u8,
            }

            #[error_code]
            pub enum ErrorCode {
                #[msg("Amount must be greater than zero")]
                ZeroAmount,
                #[msg("Math overflow")]
                MathOverflow,
            }
            ```

            This vault uses a share-based accounting model (like ERC-4626):
            - First depositor gets 1:1 receipt tokens.
            - Subsequent depositors get proportional shares.
            - If the vault earns yield (from external strategies), each share represents more underlying tokens."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How to implement a staking program with rewards distribution?",
            "How to build token staking on Solana with Anchor?",
            "How to create a staking pool that distributes rewards?",
        ],
        answer=textwrap.dedent("""\
            A staking program lets users lock tokens and earn rewards over time. The key is efficient per-user reward tracking using the "reward per token" accumulator pattern (similar to Synthetix StakingRewards).

            ```rust
            use anchor_lang::prelude::*;
            use anchor_spl::token::{self, Token, TokenAccount, Mint, Transfer, MintTo};

            declare_id!("Stake11111111111111111111111111111111111111");

            const PRECISION: u128 = 1_000_000_000_000; // 1e12

            #[program]
            pub mod staking {
                use super::*;

                pub fn initialize_pool(
                    ctx: Context<InitializePool>,
                    reward_rate: u64, // rewards per second
                ) -> Result<()> {
                    let pool = &mut ctx.accounts.pool;
                    pool.authority = ctx.accounts.authority.key();
                    pool.staking_mint = ctx.accounts.staking_mint.key();
                    pool.reward_rate = reward_rate;
                    pool.reward_per_token_stored = 0;
                    pool.last_update_time = Clock::get()?.unix_timestamp;
                    pool.total_staked = 0;
                    pool.bump = ctx.bumps.pool;
                    Ok(())
                }

                pub fn stake(ctx: Context<Stake>, amount: u64) -> Result<()> {
                    require!(amount > 0, ErrorCode::ZeroAmount);

                    // Update global reward state
                    let pool = &mut ctx.accounts.pool;
                    let clock = Clock::get()?;
                    update_rewards(pool, &mut ctx.accounts.user_stake, clock.unix_timestamp)?;

                    // Transfer tokens to pool vault
                    token::transfer(
                        CpiContext::new(
                            ctx.accounts.token_program.to_account_info(),
                            Transfer {
                                from: ctx.accounts.user_token_account.to_account_info(),
                                to: ctx.accounts.pool_vault.to_account_info(),
                                authority: ctx.accounts.user.to_account_info(),
                            },
                        ),
                        amount,
                    )?;

                    pool.total_staked = pool.total_staked
                        .checked_add(amount)
                        .ok_or(ErrorCode::MathOverflow)?;

                    let user_stake = &mut ctx.accounts.user_stake;
                    user_stake.amount = user_stake.amount
                        .checked_add(amount)
                        .ok_or(ErrorCode::MathOverflow)?;
                    user_stake.user = ctx.accounts.user.key();

                    msg!("Staked {} tokens", amount);
                    Ok(())
                }

                pub fn claim_rewards(ctx: Context<ClaimRewards>) -> Result<()> {
                    let pool = &mut ctx.accounts.pool;
                    let clock = Clock::get()?;
                    update_rewards(pool, &mut ctx.accounts.user_stake, clock.unix_timestamp)?;

                    let user_stake = &mut ctx.accounts.user_stake;
                    let rewards = user_stake.pending_rewards;
                    require!(rewards > 0, ErrorCode::NoRewards);

                    user_stake.pending_rewards = 0;

                    // Transfer rewards from reward vault
                    let pool_key = pool.key();
                    let seeds = &[b"pool".as_ref(), pool_key.as_ref(), &[pool.bump]];
                    let signer = &[&seeds[..]];

                    token::transfer(
                        CpiContext::new_with_signer(
                            ctx.accounts.token_program.to_account_info(),
                            Transfer {
                                from: ctx.accounts.reward_vault.to_account_info(),
                                to: ctx.accounts.user_reward_account.to_account_info(),
                                authority: pool.to_account_info(),
                            },
                            signer,
                        ),
                        rewards,
                    )?;

                    msg!("Claimed {} reward tokens", rewards);
                    Ok(())
                }
            }

            fn update_rewards(
                pool: &mut Account<Pool>,
                user_stake: &mut Account<UserStake>,
                current_time: i64,
            ) -> Result<()> {
                // Calculate new reward per token
                if pool.total_staked > 0 {
                    let time_delta = (current_time - pool.last_update_time) as u128;
                    let reward_increment = time_delta
                        .checked_mul(pool.reward_rate as u128)
                        .ok_or(ErrorCode::MathOverflow)?
                        .checked_mul(PRECISION)
                        .ok_or(ErrorCode::MathOverflow)?
                        .checked_div(pool.total_staked as u128)
                        .ok_or(ErrorCode::MathOverflow)?;
                    pool.reward_per_token_stored = pool.reward_per_token_stored
                        .checked_add(reward_increment)
                        .ok_or(ErrorCode::MathOverflow)?;
                }
                pool.last_update_time = current_time;

                // Calculate user's pending rewards
                if user_stake.amount > 0 {
                    let earned = (user_stake.amount as u128)
                        .checked_mul(
                            pool.reward_per_token_stored
                                .checked_sub(user_stake.reward_per_token_paid)
                                .ok_or(ErrorCode::MathOverflow)?
                        )
                        .ok_or(ErrorCode::MathOverflow)?
                        .checked_div(PRECISION)
                        .ok_or(ErrorCode::MathOverflow)? as u64;

                    user_stake.pending_rewards = user_stake.pending_rewards
                        .checked_add(earned)
                        .ok_or(ErrorCode::MathOverflow)?;
                }
                user_stake.reward_per_token_paid = pool.reward_per_token_stored;

                Ok(())
            }

            #[derive(Accounts)]
            pub struct InitializePool<'info> {
                #[account(
                    init, payer = authority,
                    space = 8 + Pool::INIT_SPACE,
                    seeds = [b"pool", staking_mint.key().as_ref()],
                    bump,
                )]
                pub pool: Account<'info, Pool>,
                pub staking_mint: Account<'info, Mint>,
                #[account(mut)]
                pub authority: Signer<'info>,
                pub system_program: Program<'info, System>,
            }

            #[derive(Accounts)]
            pub struct Stake<'info> {
                #[account(mut, seeds = [b"pool", pool.staking_mint.as_ref()], bump = pool.bump)]
                pub pool: Account<'info, Pool>,
                #[account(
                    init_if_needed, payer = user,
                    space = 8 + UserStake::INIT_SPACE,
                    seeds = [b"stake", pool.key().as_ref(), user.key().as_ref()],
                    bump,
                )]
                pub user_stake: Account<'info, UserStake>,
                #[account(mut)]
                pub pool_vault: Account<'info, TokenAccount>,
                #[account(mut)]
                pub user_token_account: Account<'info, TokenAccount>,
                #[account(mut)]
                pub user: Signer<'info>,
                pub token_program: Program<'info, Token>,
                pub system_program: Program<'info, System>,
            }

            #[derive(Accounts)]
            pub struct ClaimRewards<'info> {
                #[account(mut, seeds = [b"pool", pool.staking_mint.as_ref()], bump = pool.bump)]
                pub pool: Account<'info, Pool>,
                #[account(
                    mut,
                    seeds = [b"stake", pool.key().as_ref(), user.key().as_ref()],
                    bump,
                    has_one = user,
                )]
                pub user_stake: Account<'info, UserStake>,
                #[account(mut)]
                pub reward_vault: Account<'info, TokenAccount>,
                #[account(mut)]
                pub user_reward_account: Account<'info, TokenAccount>,
                pub user: Signer<'info>,
                pub token_program: Program<'info, Token>,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct Pool {
                pub authority: Pubkey,
                pub staking_mint: Pubkey,
                pub reward_rate: u64,
                pub reward_per_token_stored: u128,
                pub last_update_time: i64,
                pub total_staked: u64,
                pub bump: u8,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct UserStake {
                pub user: Pubkey,
                pub amount: u64,
                pub reward_per_token_paid: u128,
                pub pending_rewards: u64,
            }

            #[error_code]
            pub enum ErrorCode {
                #[msg("Amount must be greater than zero")]
                ZeroAmount,
                #[msg("No rewards to claim")]
                NoRewards,
                #[msg("Math overflow")]
                MathOverflow,
            }
            ```

            This uses the accumulator pattern:
            - `reward_per_token_stored` tracks cumulative rewards per staked token globally.
            - Each user's `reward_per_token_paid` tracks when they last claimed.
            - The difference, multiplied by the user's stake, gives their pending rewards.
            - This is O(1) per operation regardless of the number of stakers."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How to use oracle price feeds from Pyth on Solana?",
            "How to get price data from Pyth Network in an Anchor program?",
            "How to integrate Pyth oracle into a Solana DeFi program?",
        ],
        answer=textwrap.dedent("""\
            Pyth Network provides high-frequency price feeds on Solana. You can read prices directly from Pyth price accounts in your Anchor program to power DeFi functionality like lending, perps, or liquidations.

            ```rust
            use anchor_lang::prelude::*;
            use pyth_solana_receiver_sdk::price_update::PriceUpdateV2;

            declare_id!("Oracle11111111111111111111111111111111111111");

            const MAX_PRICE_AGE_SECONDS: u64 = 30; // reject stale prices
            const SOL_USD_FEED_ID: [u8; 32] = [
                // Pyth SOL/USD price feed ID (hex)
                0xef, 0x0d, 0x8b, 0x6f, 0xda, 0x2c, 0xeb, 0xa4,
                0x1d, 0xa1, 0x5d, 0x40, 0x95, 0xd1, 0xda, 0x39,
                0x2a, 0x0d, 0x2f, 0x8e, 0xd0, 0xc6, 0xc7, 0xbc,
                0x0f, 0x4c, 0xfa, 0xc8, 0xc2, 0x80, 0xb5, 0x6d,
            ];

            #[program]
            pub mod oracle_consumer {
                use super::*;

                pub fn check_collateral(
                    ctx: Context<CheckCollateral>,
                    collateral_amount: u64, // in lamports
                    borrow_amount: u64,     // in USD (6 decimals)
                    min_collateral_ratio: u64, // e.g., 150 for 150%
                ) -> Result<()> {
                    // Read the price from Pyth
                    let price_update = &ctx.accounts.price_feed;
                    let price = price_update.get_price_no_older_than(
                        &Clock::get()?,
                        MAX_PRICE_AGE_SECONDS,
                        &SOL_USD_FEED_ID,
                    )?;

                    // price.price is the price with price.exponent decimals
                    // e.g., price = 15000000000, exponent = -8 means $150.00
                    let sol_price = price.price as u128;
                    let exponent = price.exponent; // negative number like -8

                    // Calculate collateral value in USD
                    // collateral_value = collateral_amount * sol_price / 10^(9 + |exponent|)
                    // Then scale to 6 decimal USD
                    let collateral_value_usd = (collateral_amount as u128)
                        .checked_mul(sol_price)
                        .ok_or(ErrorCode::MathOverflow)?
                        .checked_mul(1_000_000) // scale to 6 decimals
                        .ok_or(ErrorCode::MathOverflow)?
                        .checked_div(
                            10u128.pow((9 + exponent.unsigned_abs()) as u32)
                        )
                        .ok_or(ErrorCode::MathOverflow)? as u64;

                    // Check collateral ratio
                    let required_collateral = (borrow_amount as u128)
                        .checked_mul(min_collateral_ratio as u128)
                        .ok_or(ErrorCode::MathOverflow)?
                        .checked_div(100)
                        .ok_or(ErrorCode::MathOverflow)? as u64;

                    require!(
                        collateral_value_usd >= required_collateral,
                        ErrorCode::InsufficientCollateral
                    );

                    msg!(
                        "Collateral value: ${}, required: ${}",
                        collateral_value_usd as f64 / 1_000_000.0,
                        required_collateral as f64 / 1_000_000.0,
                    );

                    Ok(())
                }
            }

            #[derive(Accounts)]
            pub struct CheckCollateral<'info> {
                pub price_feed: Account<'info, PriceUpdateV2>,
                pub user: Signer<'info>,
            }

            #[error_code]
            pub enum ErrorCode {
                #[msg("Insufficient collateral")]
                InsufficientCollateral,
                #[msg("Math overflow")]
                MathOverflow,
            }
            ```

            Add to Cargo.toml:
            ```toml
            [dependencies]
            pyth-solana-receiver-sdk = "0.4"
            ```

            Key points:
            - Use `get_price_no_older_than` to reject stale prices.
            - Pyth prices have a confidence interval — for lending, use `price - conf` for collateral valuation.
            - Price exponents are negative (e.g., -8 means 8 decimal places).
            - Always validate the feed ID matches the expected asset pair.
            - Consider using Pyth's pull oracle for the latest prices (push model may have latency)."""),
        language="rust",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY 6: ARCHITECTURE & DESIGN
# ═══════════════════════════════════════════════════════════════════════════

ARCHITECTURE_TEMPLATES: list[QATemplate] = [
    QATemplate(
        questions=[
            "How to structure a large Anchor program with multiple files?",
            "What is the best project layout for a complex Anchor program?",
            "How to organize an Anchor workspace?",
        ],
        answer=textwrap.dedent("""\
            For large programs, split your code across multiple files using Rust modules. Anchor supports this well — your `lib.rs` declares the program, and instruction handlers, account structs, state, and errors live in separate files.

            ```
            programs/my_program/src/
            ├── lib.rs                  # Program entry point + #[program] mod
            ├── instructions/
            │   ├── mod.rs              # pub mod for each instruction
            │   ├── initialize.rs       # initialize handler + accounts
            │   ├── deposit.rs          # deposit handler + accounts
            │   └── withdraw.rs         # withdraw handler + accounts
            ├── state/
            │   ├── mod.rs              # pub mod for each account type
            │   ├── pool.rs             # Pool account struct
            │   └── user_position.rs    # UserPosition account struct
            ├── errors.rs               # #[error_code] enum
            ├── constants.rs            # Program constants
            └── utils.rs                # Helper functions (math, validation)
            ```

            ```rust
            // lib.rs
            use anchor_lang::prelude::*;

            pub mod constants;
            pub mod errors;
            pub mod instructions;
            pub mod state;
            pub mod utils;

            use instructions::*;

            declare_id!("MyProgram111111111111111111111111111111111");

            #[program]
            pub mod my_program {
                use super::*;

                pub fn initialize(ctx: Context<Initialize>, params: InitParams) -> Result<()> {
                    instructions::initialize::handler(ctx, params)
                }

                pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
                    instructions::deposit::handler(ctx, amount)
                }

                pub fn withdraw(ctx: Context<Withdraw>, amount: u64) -> Result<()> {
                    instructions::withdraw::handler(ctx, amount)
                }
            }
            ```

            ```rust
            // instructions/mod.rs
            pub mod initialize;
            pub mod deposit;
            pub mod withdraw;

            pub use initialize::*;
            pub use deposit::*;
            pub use withdraw::*;
            ```

            ```rust
            // instructions/deposit.rs
            use anchor_lang::prelude::*;
            use anchor_spl::token::{Token, TokenAccount};
            use crate::state::Pool;
            use crate::errors::ErrorCode;

            #[derive(Accounts)]
            pub struct Deposit<'info> {
                #[account(
                    mut,
                    seeds = [b"pool", pool.mint.as_ref()],
                    bump = pool.bump,
                )]
                pub pool: Account<'info, Pool>,
                #[account(mut)]
                pub user_token_account: Account<'info, TokenAccount>,
                #[account(mut)]
                pub pool_vault: Account<'info, TokenAccount>,
                pub user: Signer<'info>,
                pub token_program: Program<'info, Token>,
            }

            pub fn handler(ctx: Context<Deposit>, amount: u64) -> Result<()> {
                require!(amount > 0, ErrorCode::ZeroAmount);
                // ... deposit logic
                Ok(())
            }
            ```

            ```rust
            // state/pool.rs
            use anchor_lang::prelude::*;

            #[account]
            #[derive(InitSpace)]
            pub struct Pool {
                pub authority: Pubkey,
                pub mint: Pubkey,
                pub total_deposits: u64,
                pub bump: u8,
            }
            ```

            ```rust
            // errors.rs
            use anchor_lang::prelude::*;

            #[error_code]
            pub enum ErrorCode {
                #[msg("Amount must be greater than zero")]
                ZeroAmount,
                #[msg("Unauthorized")]
                Unauthorized,
                #[msg("Math overflow")]
                MathOverflow,
            }
            ```

            Benefits of this structure:
            - Each instruction is self-contained with its accounts struct and handler.
            - State definitions are reusable across instructions.
            - Easy to review — auditors can focus on one file at a time.
            - Scales well to 20+ instructions."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "When should I use zero-copy accounts vs regular accounts?",
            "What is zero-copy deserialization in Anchor?",
            "How to use AccountLoader for large Solana accounts?",
        ],
        answer=textwrap.dedent("""\
            Zero-copy accounts use memory-mapped deserialization, reading fields directly from the account data without copying it into a Rust struct. This is essential for large accounts (>1KB) because regular Borsh deserialization copies the entire account into memory, consuming compute units.

            ```rust
            use anchor_lang::prelude::*;

            // Regular account — Borsh deserialized (copied into memory)
            // Good for small accounts (<1KB)
            #[account]
            #[derive(InitSpace)]
            pub struct SmallAccount {
                pub authority: Pubkey,
                pub value: u64,
                pub bump: u8,
            }

            // Zero-copy account — memory-mapped (no copy)
            // Required for large accounts, especially with arrays
            #[account(zero_copy)]
            #[repr(C)] // Required for zero-copy: C-compatible memory layout
            pub struct LargeAccount {
                pub authority: Pubkey,    // 32 bytes
                pub total_entries: u64,   // 8 bytes
                pub entries: [Entry; 500], // 500 * 40 = 20,000 bytes
            }

            #[zero_copy]
            #[repr(C)]
            pub struct Entry {
                pub key: Pubkey,  // 32 bytes
                pub value: u64,   // 8 bytes
            }

            // Using zero-copy in instruction accounts:
            #[derive(Accounts)]
            pub struct UpdateLarge<'info> {
                // Use AccountLoader instead of Account for zero-copy
                #[account(mut)]
                pub large_account: AccountLoader<'info, LargeAccount>,
                pub authority: Signer<'info>,
            }

            pub fn update_entry(
                ctx: Context<UpdateLarge>,
                index: u32,
                new_value: u64,
            ) -> Result<()> {
                // load_mut() gives mutable access without copying
                let mut account = ctx.accounts.large_account.load_mut()?;

                require!(
                    account.authority == ctx.accounts.authority.key(),
                    ErrorCode::Unauthorized
                );

                let idx = index as usize;
                require!(idx < 500, ErrorCode::IndexOutOfBounds);

                account.entries[idx].value = new_value;
                account.total_entries += 1;

                Ok(())
            }

            // Initializing a zero-copy account:
            #[derive(Accounts)]
            pub struct InitializeLarge<'info> {
                #[account(
                    init,
                    payer = authority,
                    space = 8 + std::mem::size_of::<LargeAccount>(),
                    // Note: no InitSpace for zero-copy, use std::mem::size_of
                )]
                pub large_account: AccountLoader<'info, LargeAccount>,
                #[account(mut)]
                pub authority: Signer<'info>,
                pub system_program: Program<'info, System>,
            }

            #[error_code]
            pub enum ErrorCode {
                #[msg("Unauthorized")]
                Unauthorized,
                #[msg("Index out of bounds")]
                IndexOutOfBounds,
            }
            ```

            When to use zero-copy:
            - **Account size > 1KB**: regular Borsh deserialization becomes expensive.
            - **Fixed-size arrays**: zero-copy works with `[T; N]` but NOT `Vec<T>`.
            - **Frequent partial reads**: if you only access a few fields, zero-copy avoids deserializing the rest.

            Limitations:
            - Must use `#[repr(C)]` — Rust's default layout is not guaranteed stable.
            - No `Vec`, `String`, or `HashMap` — only fixed-size types.
            - All types must implement `Pod` (plain old data) — no references, no enums with data.
            - Max account size is 10MB (Solana limit)."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "When to use PDAs vs keypair accounts?",
            "What are PDAs and when should I use them?",
            "How do I decide between a PDA and a regular account?",
        ],
        answer=textwrap.dedent("""\
            Program Derived Addresses (PDAs) are deterministic addresses derived from seeds and a program ID that don't lie on the Ed25519 curve — meaning no private key exists for them. Only the program that derived them can sign for them via CPI.

            **Use PDAs when:**
            - The account should be controlled by the program (no external signer needed)
            - You need deterministic, findable addresses (e.g., user-specific accounts)
            - You need the program to sign CPIs (e.g., transferring tokens from a vault)

            **Use keypair accounts when:**
            - The account is a user's wallet
            - You need an externally owned account
            - The account is a one-time-use (e.g., mint keypair)

            ```rust
            use anchor_lang::prelude::*;

            declare_id!("PDA11111111111111111111111111111111111111111");

            #[program]
            pub mod pda_example {
                use super::*;

                pub fn create_user_profile(
                    ctx: Context<CreateProfile>,
                    username: String,
                ) -> Result<()> {
                    let profile = &mut ctx.accounts.profile;
                    profile.user = ctx.accounts.user.key();
                    profile.username = username;
                    profile.bump = ctx.bumps.profile;
                    Ok(())
                }
            }

            #[derive(Accounts)]
            pub struct CreateProfile<'info> {
                // PDA: deterministic address derived from seeds
                // Anyone can find this address given the user's pubkey
                #[account(
                    init,
                    payer = user,
                    space = 8 + Profile::INIT_SPACE,
                    seeds = [b"profile", user.key().as_ref()],
                    bump,
                )]
                pub profile: Account<'info, Profile>,

                #[account(mut)]
                pub user: Signer<'info>,
                pub system_program: Program<'info, System>,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct Profile {
                pub user: Pubkey,
                #[max_len(32)]
                pub username: String,
                pub bump: u8,
            }
            ```

            Common PDA seed patterns:
            ```rust
            // User-specific account
            seeds = [b"account", user.key().as_ref()]

            // Token vault for a pool
            seeds = [b"vault", pool.key().as_ref(), mint.key().as_ref()]

            // Config / global state (singleton)
            seeds = [b"config"]

            // Counter per category
            seeds = [b"counter", category.as_bytes()]

            // Multi-level hierarchy
            seeds = [b"order", market.key().as_ref(), &order_id.to_le_bytes()]
            ```

            How PDAs work internally:
            - `Pubkey::find_program_address(&seeds, &program_id)` hashes `seeds || program_id || bump` using SHA-256.
            - The bump is decremented from 255 until the result is NOT on the Ed25519 curve.
            - This guarantees no private key exists — only the program can sign.
            - Store the bump in the account to avoid recomputing it on every instruction."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How to optimize compute units in a Solana program?",
            "How to reduce CU usage in Anchor?",
            "What techniques lower compute cost on Solana?",
        ],
        answer=textwrap.dedent("""\
            Compute unit optimization matters for transaction landing, priority fee costs, and staying within the 1.4M CU transaction limit. Here are proven techniques:

            **1. Use zero-copy for large accounts:**
            ```rust
            // Instead of Account<'info, LargeStruct> (copies all data)
            pub large: AccountLoader<'info, LargeStruct>,
            // Access: let data = ctx.accounts.large.load()?;
            ```

            **2. Avoid unnecessary account deserialization:**
            ```rust
            // If you only need the key, use UncheckedAccount
            /// CHECK: Only used for its key, not deserialized
            pub reference_account: UncheckedAccount<'info>,
            ```

            **3. Use `Box` for large accounts structs:**
            ```rust
            #[derive(Accounts)]
            pub struct BigInstruction<'info> {
                // Box moves the account to heap, avoiding stack overflow
                #[account(mut)]
                pub big_account: Box<Account<'info, BigState>>,
            }
            ```

            **4. Minimize logging:**
            ```rust
            // BAD: String formatting is expensive
            msg!("Deposited {} tokens from user {} to vault {}", amount, user, vault);

            // GOOD: Log only essential data
            msg!("deposit: {}", amount);

            // BEST: Use Anchor events (emitted as base64, no formatting)
            emit!(DepositEvent { amount, user: ctx.accounts.user.key() });
            ```

            **5. Cache account loads:**
            ```rust
            // BAD: Reloading account multiple times
            let balance1 = ctx.accounts.vault.amount;
            ctx.accounts.vault.reload()?;
            let balance2 = ctx.accounts.vault.amount;

            // GOOD: Load once, use references
            let vault = &ctx.accounts.vault;
            let balance = vault.amount;
            ```

            **6. Use const for known values:**
            ```rust
            // Compute PDA at compile time when possible
            const SEED: &[u8] = b"vault";

            // Pre-compute fixed discriminators
            const VAULT_DISCRIMINATOR: [u8; 8] = [/* ... */];
            ```

            **7. Minimize allocations:**
            ```rust
            // BAD: Dynamic allocation
            let mut data = Vec::new();
            data.push(item);

            // GOOD: Fixed-size arrays
            let mut data = [0u8; 64];
            ```

            **8. Use Pinocchio for CU-critical programs:**
            Pinocchio is a zero-abstraction framework that can save 50-80% CU compared to Anchor by eliminating deserialization overhead entirely.

            Typical CU costs:
            - Simple SOL transfer: ~300 CU
            - Anchor account deserialization: ~2,000-5,000 CU per account
            - SPL Token transfer CPI: ~4,000 CU
            - SHA-256 hash: ~100 CU per 64 bytes
            - PDA derivation: ~1,500 CU
            - `msg!()` with formatting: ~200-500 CU"""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "Anchor vs Pinocchio vs native: when to use each?",
            "What are the tradeoffs between Anchor and Pinocchio?",
            "Should I use Anchor or write native Solana programs?",
        ],
        answer=textwrap.dedent("""\
            Each framework serves different needs. Here's a practical comparison:

            **Anchor** — The standard choice for most programs
            ```rust
            use anchor_lang::prelude::*;

            #[program]
            pub mod counter {
                use super::*;

                pub fn increment(ctx: Context<Increment>) -> Result<()> {
                    ctx.accounts.counter.count += 1;
                    Ok(())
                }
            }

            #[derive(Accounts)]
            pub struct Increment<'info> {
                #[account(mut, has_one = authority)]
                pub counter: Account<'info, Counter>,
                pub authority: Signer<'info>,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct Counter {
                pub authority: Pubkey,
                pub count: u64,
            }
            // ~6,000 CU
            ```

            **Pinocchio** — For CU-critical hotpaths
            ```rust
            use pinocchio::{
                account_info::AccountInfo,
                entrypoint,
                program_error::ProgramError,
                ProgramResult,
            };

            entrypoint!(process_instruction);

            fn process_instruction(
                _program_id: &pinocchio::pubkey::Pubkey,
                accounts: &[AccountInfo],
                _data: &[u8],
            ) -> ProgramResult {
                let counter = &accounts[0];
                // Manual: check owner, signer, writable
                if !counter.is_writable() {
                    return Err(ProgramError::InvalidArgument);
                }
                let mut data = counter.try_borrow_mut_data()?;
                // Read u64 at offset 8 (skip discriminator), increment, write back
                let count = u64::from_le_bytes(data[8..16].try_into().unwrap());
                data[8..16].copy_from_slice(&(count + 1).to_le_bytes());
                Ok(())
            }
            // ~1,200 CU — 5x cheaper!
            ```

            **Native (solana-program)** — For maximum control
            ```rust
            use solana_program::{
                account_info::{next_account_info, AccountInfo},
                entrypoint,
                entrypoint::ProgramResult,
                pubkey::Pubkey,
            };

            entrypoint!(process_instruction);

            fn process_instruction(
                program_id: &Pubkey,
                accounts: &[AccountInfo],
                data: &[u8],
            ) -> ProgramResult {
                let accounts_iter = &mut accounts.iter();
                let counter = next_account_info(accounts_iter)?;

                if counter.owner != program_id {
                    return Err(solana_program::program_error::ProgramError::IncorrectProgramId);
                }

                let mut account_data = counter.try_borrow_mut_data()?;
                let mut count = u64::from_le_bytes(account_data[0..8].try_into().unwrap());
                count += 1;
                account_data[0..8].copy_from_slice(&count.to_le_bytes());
                Ok(())
            }
            // ~2,000 CU
            ```

            **Decision guide:**
            | Factor | Anchor | Pinocchio | Native |
            |--------|--------|-----------|--------|
            | CU cost | High (~6K/ix) | Lowest (~1K/ix) | Medium (~2K/ix) |
            | Safety | Highest (auto-checks) | Lowest (manual) | Low (manual) |
            | Dev speed | Fastest | Slowest | Slow |
            | IDL/Client gen | Automatic | Manual | Manual |
            | Ecosystem support | Best | Growing | Good |
            | Audit cost | Lower | Higher | Higher |

            **Recommendation:**
            - Start with Anchor for 90% of programs — safety and developer productivity matter most.
            - Use Pinocchio only for programs where CU is the bottleneck (DEX routers, liquidation bots).
            - Avoid native unless you have specific reasons — Anchor adds minimal overhead for most use cases."""),
        language="rust",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY 7: TESTING & DEBUGGING
# ═══════════════════════════════════════════════════════════════════════════

TESTING_TEMPLATES: list[QATemplate] = [
    QATemplate(
        questions=[
            "How to write integration tests for an Anchor program?",
            "How to test an Anchor program with TypeScript?",
            "Show me the testing pattern for Anchor programs.",
        ],
        answer=textwrap.dedent("""\
            Anchor generates a TypeScript test scaffolding that uses `@coral-xyz/anchor` to interact with your program on a local validator. Tests run against `solana-test-validator` or Bankrun.

            ```typescript
            import * as anchor from "@coral-xyz/anchor";
            import { Program } from "@coral-xyz/anchor";
            import { MyProgram } from "../target/types/my_program";
            import { expect } from "chai";
            import {
              Keypair,
              PublicKey,
              SystemProgram,
              LAMPORTS_PER_SOL,
            } from "@solana/web3.js";
            import {
              createMint,
              getAssociatedTokenAddress,
              createAssociatedTokenAccount,
              mintTo,
            } from "@solana/spl-token";

            describe("my_program", () => {
              const provider = anchor.AnchorProvider.env();
              anchor.setProvider(provider);

              const program = anchor.workspace.MyProgram as Program<MyProgram>;
              const authority = provider.wallet as anchor.Wallet;
              let mint: PublicKey;
              let vaultPda: PublicKey;
              let vaultBump: number;

              before(async () => {
                // Create a test mint
                mint = await createMint(
                  provider.connection,
                  authority.payer,
                  authority.publicKey,
                  null,
                  9
                );

                // Derive PDA
                [vaultPda, vaultBump] = PublicKey.findProgramAddressSync(
                  [Buffer.from("vault"), mint.toBuffer()],
                  program.programId
                );
              });

              it("initializes the vault", async () => {
                const tx = await program.methods
                  .initialize()
                  .accountsStrict({
                    vault: vaultPda,
                    mint: mint,
                    authority: authority.publicKey,
                    systemProgram: SystemProgram.programId,
                  })
                  .rpc();

                // Fetch and verify account state
                const vault = await program.account.vault.fetch(vaultPda);
                expect(vault.authority.toBase58()).to.equal(
                  authority.publicKey.toBase58()
                );
                expect(vault.totalDeposits.toNumber()).to.equal(0);
              });

              it("deposits tokens", async () => {
                const userAta = await createAssociatedTokenAccount(
                  provider.connection,
                  authority.payer,
                  mint,
                  authority.publicKey
                );

                // Mint test tokens
                await mintTo(
                  provider.connection,
                  authority.payer,
                  mint,
                  userAta,
                  authority.publicKey,
                  1_000_000_000
                );

                await program.methods
                  .deposit(new anchor.BN(500_000_000))
                  .accountsStrict({
                    vault: vaultPda,
                    userTokenAccount: userAta,
                    vaultTokenAccount: vaultTokenAccount,
                    user: authority.publicKey,
                    tokenProgram: anchor.utils.token.TOKEN_PROGRAM_ID,
                  })
                  .rpc();

                const vault = await program.account.vault.fetch(vaultPda);
                expect(vault.totalDeposits.toNumber()).to.equal(500_000_000);
              });

              it("rejects unauthorized withdraw", async () => {
                const attacker = Keypair.generate();

                // Airdrop SOL for fees
                const sig = await provider.connection.requestAirdrop(
                  attacker.publicKey,
                  LAMPORTS_PER_SOL
                );
                await provider.connection.confirmTransaction(sig);

                try {
                  await program.methods
                    .withdraw(new anchor.BN(100))
                    .accountsStrict({
                      vault: vaultPda,
                      authority: attacker.publicKey,
                      // ... other accounts
                    })
                    .signers([attacker])
                    .rpc();

                  expect.fail("Should have thrown");
                } catch (err) {
                  expect(err.error.errorCode.code).to.equal("ConstraintHasOne");
                }
              });
            });
            ```

            Run tests with:
            ```bash
            anchor test                    # starts validator, deploys, runs tests
            anchor test --skip-local-validator  # use existing validator
            ```

            Tips:
            - Use `accountsStrict()` instead of `accounts()` to catch missing accounts at compile time.
            - Use `program.account.<name>.fetch()` to verify state changes.
            - Test error cases with try/catch — check `err.error.errorCode.code` for Anchor errors.
            - Use `provider.connection.requestAirdrop()` to fund test accounts."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to use bankrun for fast Solana program testing?",
            "What is Bankrun and how to set it up?",
            "How to test Solana programs without solana-test-validator?",
        ],
        answer=textwrap.dedent("""\
            Bankrun (solana-bankrun) runs a lightweight BanksServer in-process, making tests 10-100x faster than solana-test-validator. It skips network overhead and gives you direct control over time, slots, and account state.

            ```typescript
            import { start, BanksClient, ProgramTestContext } from "solana-bankrun";
            import { PublicKey, Transaction, SystemProgram, Keypair } from "@solana/web3.js";
            import { Program, AnchorProvider, BN } from "@coral-xyz/anchor";
            import { expect } from "chai";

            // For Anchor programs, use anchor-bankrun:
            import { startAnchor, BankrunProvider } from "anchor-bankrun";
            import { MyProgram } from "../target/types/my_program";

            describe("bankrun tests", () => {
              let context: ProgramTestContext;
              let provider: BankrunProvider;
              let program: Program<MyProgram>;

              before(async () => {
                // Start bankrun with your program deployed
                context = await startAnchor(
                  "", // workspace root (uses Anchor.toml)
                  [], // extra programs to deploy
                  []  // initial accounts to set
                );

                provider = new BankrunProvider(context);
                program = new Program<MyProgram>(
                  require("../target/idl/my_program.json"),
                  provider
                );
              });

              it("creates an account", async () => {
                const [pda] = PublicKey.findProgramAddressSync(
                  [Buffer.from("counter")],
                  program.programId
                );

                await program.methods
                  .initialize()
                  .accounts({
                    counter: pda,
                    authority: provider.wallet.publicKey,
                    systemProgram: SystemProgram.programId,
                  })
                  .rpc();

                const counter = await program.account.counter.fetch(pda);
                expect(counter.count.toNumber()).to.equal(0);
              });

              it("can warp time forward", async () => {
                const currentClock = await context.banksClient.getClock();
                // Advance time by 1 hour
                context.setClock({
                  ...currentClock,
                  unixTimestamp: currentClock.unixTimestamp + BigInt(3600),
                });

                // Now any Clock::get() in your program will see the new time
              });

              it("can set arbitrary account state", async () => {
                const fakeAccount = {
                  lamports: 1_000_000_000,
                  data: Buffer.alloc(100),
                  owner: program.programId,
                  executable: false,
                };

                const address = Keypair.generate().publicKey;
                context.setAccount(address, fakeAccount);

                const account = await context.banksClient.getAccount(address);
                expect(account).to.not.be.null;
                expect(account!.lamports).to.equal(BigInt(1_000_000_000));
              });
            });
            ```

            Install:
            ```bash
            npm install solana-bankrun anchor-bankrun
            ```

            Bankrun advantages:
            - **Speed**: tests run in ~100ms instead of ~5s per test.
            - **Time control**: warp time forward for testing time-dependent logic.
            - **State injection**: set arbitrary account data for edge case testing.
            - **Deterministic**: no network randomness or timing issues.
            - **No validator process**: everything runs in-process.

            When to still use solana-test-validator:
            - Testing CPI to deployed programs (e.g., Metaplex).
            - Testing WebSocket subscriptions.
            - Full integration tests with off-chain components."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to debug a failed transaction on Solana?",
            "How to troubleshoot Solana transaction errors?",
            "What tools help debug Solana programs?",
        ],
        answer=textwrap.dedent("""\
            Debugging failed transactions requires reading logs, decoding error codes, and using the right tools. Here's a systematic approach.

            **Step 1: Get the transaction logs**
            ```typescript
            import { Connection } from "@solana/web3.js";

            async function debugTransaction(connection: Connection, signature: string) {
              const tx = await connection.getTransaction(signature, {
                commitment: "confirmed",
                maxSupportedTransactionVersion: 0,
              });

              if (!tx) {
                console.log("Transaction not found — it may have been dropped");
                return;
              }

              // Print all program logs
              console.log("=== Transaction Logs ===");
              if (tx.meta?.logMessages) {
                for (const log of tx.meta.logMessages) {
                  console.log(log);
                }
              }

              // Check for errors
              if (tx.meta?.err) {
                console.log("\\n=== Error ===");
                console.log(JSON.stringify(tx.meta.err, null, 2));

                // Decode instruction error
                const err = tx.meta.err as any;
                if (err?.InstructionError) {
                  const [instructionIndex, errorDetail] = err.InstructionError;
                  console.log(`Failed at instruction index: ${instructionIndex}`);

                  if (errorDetail?.Custom !== undefined) {
                    const code = errorDetail.Custom;
                    console.log(`Custom error code: ${code} (0x${code.toString(16)})`);

                    // Anchor errors
                    if (code >= 6000) {
                      console.log(`Anchor custom error index: ${code - 6000}`);
                      console.log("Check your #[error_code] enum at this index");
                    } else if (code >= 3000 && code < 4000) {
                      console.log("Anchor constraint error — check account constraints");
                    } else if (code >= 2000 && code < 3000) {
                      console.log("Anchor account error — check account types/ownership");
                    }
                  }
                }
              }

              // Print compute units consumed
              if (tx.meta?.computeUnitsConsumed) {
                console.log(`\\nCompute units consumed: ${tx.meta.computeUnitsConsumed}`);
              }
            }
            ```

            **Step 2: Decode Anchor error codes**
            ```typescript
            // Common Anchor errors:
            const ANCHOR_ERRORS: Record<number, string> = {
              2000: "AccountDiscriminatorAlreadySet",
              2001: "AccountDiscriminatorNotFound",
              2002: "AccountDiscriminatorMismatch",
              2003: "AccountDidNotDeserialize",
              2006: "AccountNotEnoughKeys",
              2009: "AccountNotSystemOwned",
              2011: "AccountNotProgramData",
              2012: "AccountNotAssociatedTokenAccount",
              3000: "ConstraintMut",
              3001: "ConstraintHasOne",
              3002: "ConstraintSigner",
              3003: "ConstraintRaw",
              3004: "ConstraintOwner",
              3006: "ConstraintSeeds",
              3007: "ConstraintExecutable",
              3010: "ConstraintClose",
              3011: "ConstraintAddress",
              3012: "ConstraintZero",
              3016: "ConstraintAssociated",
            };
            ```

            **Step 3: Simulate before sending**
            ```typescript
            const simulation = await connection.simulateTransaction(tx);
            if (simulation.value.err) {
              console.log("Simulation logs:", simulation.value.logs);
            }
            ```

            **Tools for debugging:**
            - **Solana Explorer** (explorer.solana.com): paste the signature to see logs and accounts.
            - **SolanaFM** (solana.fm): better error decoding and account diffing.
            - **Anchor's `Program.addEventListener`**: listen for events in real-time during development.
            - **`solana logs`** CLI: stream program logs from a running validator.
            - **`anchor test --detach`**: keep the validator running after tests for manual inspection."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to mock the Clock sysvar in Anchor tests?",
            "How to test time-dependent logic in Solana programs?",
            "How to advance time in Solana tests?",
        ],
        answer=textwrap.dedent("""\
            Testing time-dependent logic (vesting, lockups, cooldowns) requires controlling the `Clock` sysvar. Bankrun makes this trivial; with solana-test-validator you can use the `warp` command.

            **Method 1: Bankrun (recommended)**
            ```typescript
            import { startAnchor, BankrunProvider } from "anchor-bankrun";

            describe("time tests", () => {
              let context;
              let provider;

              before(async () => {
                context = await startAnchor("", [], []);
                provider = new BankrunProvider(context);
              });

              it("tests vesting after 30 days", async () => {
                // Create the vesting account...

                // Warp time forward by 30 days
                const currentClock = await context.banksClient.getClock();
                const thirtyDays = BigInt(30 * 24 * 60 * 60);
                context.setClock({
                  slot: currentClock.slot,
                  epochStartTimestamp: currentClock.epochStartTimestamp,
                  epoch: currentClock.epoch,
                  leaderScheduleEpoch: currentClock.leaderScheduleEpoch,
                  unixTimestamp: currentClock.unixTimestamp + thirtyDays,
                });

                // Now the vesting claim should succeed
                await program.methods.claim().accounts({...}).rpc();
              });
            });
            ```

            **Method 2: solana-test-validator with warp**
            ```typescript
            import { Connection } from "@solana/web3.js";

            // In Anchor Rust tests, you can use set_sysvar:
            // This example is for the Rust test framework
            ```

            ```rust
            // In Rust program tests using solana-program-test:
            use solana_program_test::*;
            use solana_sdk::clock::Clock;

            #[tokio::test]
            async fn test_with_custom_time() {
                let mut program_test = ProgramTest::new(
                    "my_program",
                    my_program::ID,
                    processor!(my_program::process_instruction),
                );

                let mut context = program_test.start_with_context().await;

                // Set custom clock
                let mut clock = context.banks_client
                    .get_sysvar::<Clock>()
                    .await
                    .unwrap();

                // Advance 7 days
                clock.unix_timestamp += 7 * 24 * 60 * 60;

                context.set_sysvar(&clock);

                // Now execute your instruction — it will see the advanced time
                // ...
            }
            ```

            **In the program itself**, always read clock via `Clock::get()`:
            ```rust
            pub fn claim(ctx: Context<Claim>) -> Result<()> {
                let clock = Clock::get()?;
                let vesting = &ctx.accounts.vesting;

                require!(
                    clock.unix_timestamp >= vesting.unlock_time,
                    ErrorCode::NotYetUnlocked
                );

                // Process claim...
                Ok(())
            }
            ```

            Tips:
            - Always use `Clock::get()?` — never `SystemTime::now()` or other system calls.
            - Bankrun's `setClock` is instant and doesn't require processing empty slots.
            - Test edge cases: exactly at unlock time, 1 second before, and well after."""),
        language="rust",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY 8: NFT & METAPLEX
# ═══════════════════════════════════════════════════════════════════════════

NFT_TEMPLATES: list[QATemplate] = [
    QATemplate(
        questions=[
            "How to mint a compressed NFT using Bubblegum?",
            "How do compressed NFTs work on Solana?",
            "How to create a cNFT with Metaplex Bubblegum?",
        ],
        answer=textwrap.dedent("""\
            Compressed NFTs (cNFTs) use state compression with Merkle trees to store NFT data off-chain while keeping a hash on-chain. This reduces minting cost from ~$2 to ~$0.0005 per NFT.

            ```typescript
            import { Connection, Keypair, PublicKey, Transaction } from "@solana/web3.js";
            import {
              createCreateTreeInstruction,
              createMintV1Instruction,
              PROGRAM_ID as BUBBLEGUM_PROGRAM_ID,
              MetadataArgs,
              TokenProgramVersion,
              TokenStandard,
            } from "@metaplex-foundation/mpl-bubblegum";
            import {
              SPL_ACCOUNT_COMPRESSION_PROGRAM_ID,
              SPL_NOOP_PROGRAM_ID,
              getConcurrentMerkleTreeAccountSize,
              createAllocTreeIx,
            } from "@solana/spl-account-compression";

            async function createMerkleTree(
              connection: Connection,
              payer: Keypair,
              maxDepth: number = 14,  // 2^14 = 16,384 NFTs
              maxBufferSize: number = 64
            ) {
              const treeKeypair = Keypair.generate();

              // Calculate tree space
              const space = getConcurrentMerkleTreeAccountSize(maxDepth, maxBufferSize);
              const allocIx = await createAllocTreeIx(
                connection,
                treeKeypair.publicKey,
                payer.publicKey,
                { maxDepth, maxBufferSize },
                maxDepth // canopy depth (for cheaper proofs)
              );

              // Derive tree authority PDA
              const [treeAuthority] = PublicKey.findProgramAddressSync(
                [treeKeypair.publicKey.toBuffer()],
                BUBBLEGUM_PROGRAM_ID
              );

              const createTreeIx = createCreateTreeInstruction(
                {
                  treeAuthority,
                  merkleTree: treeKeypair.publicKey,
                  payer: payer.publicKey,
                  treeCreator: payer.publicKey,
                  logWrapper: SPL_NOOP_PROGRAM_ID,
                  compressionProgram: SPL_ACCOUNT_COMPRESSION_PROGRAM_ID,
                },
                { maxDepth, maxBufferSize, public: false }
              );

              const tx = new Transaction().add(allocIx, createTreeIx);
              await connection.sendTransaction(tx, [payer, treeKeypair]);

              console.log("Merkle tree created:", treeKeypair.publicKey.toBase58());
              return treeKeypair.publicKey;
            }

            async function mintCompressedNFT(
              connection: Connection,
              payer: Keypair,
              merkleTree: PublicKey,
              collectionMint: PublicKey
            ) {
              const [treeAuthority] = PublicKey.findProgramAddressSync(
                [merkleTree.toBuffer()],
                BUBBLEGUM_PROGRAM_ID
              );

              const [bgumSigner] = PublicKey.findProgramAddressSync(
                [Buffer.from("collection_cpi")],
                BUBBLEGUM_PROGRAM_ID
              );

              const metadata: MetadataArgs = {
                name: "My Compressed NFT",
                symbol: "CNFT",
                uri: "https://arweave.net/your-metadata-uri",
                sellerFeeBasisPoints: 500, // 5% royalty
                creators: [
                  {
                    address: payer.publicKey,
                    verified: false,
                    share: 100,
                  },
                ],
                collection: {
                  key: collectionMint,
                  verified: false,
                },
                uses: null,
                primarySaleHappened: false,
                isMutable: true,
                editionNonce: null,
                tokenStandard: TokenStandard.NonFungible,
                tokenProgramVersion: TokenProgramVersion.Original,
              };

              const mintIx = createMintV1Instruction(
                {
                  treeAuthority,
                  leafOwner: payer.publicKey,
                  leafDelegate: payer.publicKey,
                  merkleTree,
                  payer: payer.publicKey,
                  treeDelegate: payer.publicKey,
                  logWrapper: SPL_NOOP_PROGRAM_ID,
                  compressionProgram: SPL_ACCOUNT_COMPRESSION_PROGRAM_ID,
                },
                { message: metadata }
              );

              const tx = new Transaction().add(mintIx);
              const sig = await connection.sendTransaction(tx, [payer]);
              console.log("Minted cNFT:", sig);
              return sig;
            }
            ```

            Cost comparison (approximate):
            - Regular NFT: ~0.015 SOL per mint ($2+)
            - Compressed NFT: ~0.000005 SOL per mint ($0.0005)
            - A tree with depth 20 can hold 1,048,576 NFTs for ~1.5 SOL total

            Trade-offs:
            - cNFTs require Merkle proofs for transfers (fetched from indexers like Helius DAS API).
            - Not all wallets/marketplaces support cNFTs (but support is growing).
            - Great for airdrops, gaming items, loyalty rewards, and any high-volume NFT use case."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to create an NFT collection with Candy Machine?",
            "How to set up Candy Machine v3 for minting?",
            "How to launch an NFT collection on Solana?",
        ],
        answer=textwrap.dedent("""\
            Candy Machine (by Metaplex) is the standard tool for launching NFT collections on Solana. It handles sequential minting, payment, guards (allowlists, limits, dates), and collection verification.

            ```typescript
            import { createUmi } from "@metaplex-foundation/umi-bundle-defaults";
            import {
              mplCandyMachine,
              create,
              addConfigLines,
              mintV2,
              fetchCandyMachine,
            } from "@metaplex-foundation/mpl-candy-machine";
            import {
              createNft,
              mplTokenMetadata,
            } from "@metaplex-foundation/mpl-token-metadata";
            import {
              generateSigner,
              keypairIdentity,
              percentAmount,
              some,
              sol,
            } from "@metaplex-foundation/umi";

            async function setupCandyMachine() {
              // Initialize Umi
              const umi = createUmi("https://api.devnet.solana.com")
                .use(mplCandyMachine())
                .use(mplTokenMetadata());

              // Set up wallet identity
              const wallet = generateSigner(umi);
              umi.use(keypairIdentity(wallet));

              // Step 1: Create Collection NFT
              const collectionMint = generateSigner(umi);
              await createNft(umi, {
                mint: collectionMint,
                name: "My Collection",
                symbol: "MYCOL",
                uri: "https://arweave.net/collection-metadata.json",
                sellerFeeBasisPoints: percentAmount(5), // 5% royalty
                isCollection: true,
              }).sendAndConfirm(umi);

              // Step 2: Create Candy Machine
              const candyMachine = generateSigner(umi);
              await create(umi, {
                candyMachine,
                collectionMint: collectionMint.publicKey,
                collectionUpdateAuthority: wallet,
                itemsAvailable: 1000,
                sellerFeeBasisPoints: percentAmount(5),
                creators: [
                  {
                    address: wallet.publicKey,
                    verified: true,
                    percentageShare: 100,
                  },
                ],
                configLineSettings: some({
                  prefixName: "NFT #",
                  nameLength: 4,
                  prefixUri: "https://arweave.net/",
                  uriLength: 43,
                  isSequential: false,
                }),
                guards: {
                  solPayment: some({
                    lamports: sol(0.5),
                    destination: wallet.publicKey,
                  }),
                  startDate: some({
                    date: new Date("2025-01-01T00:00:00Z"),
                  }),
                  mintLimit: some({
                    id: 1,
                    limit: 3, // max 3 per wallet
                  }),
                },
              }).sendAndConfirm(umi);

              // Step 3: Add items (config lines)
              const items = [];
              for (let i = 0; i < 100; i++) {
                items.push({
                  name: `${i}`,
                  uri: `item-${i}-metadata.json`,
                });
              }

              await addConfigLines(umi, {
                candyMachine: candyMachine.publicKey,
                index: 0,
                configLines: items,
              }).sendAndConfirm(umi);

              console.log("Candy Machine:", candyMachine.publicKey);
              return candyMachine.publicKey;
            }

            // Minting
            async function mintFromCandyMachine(
              umi: any,
              candyMachineAddress: PublicKey
            ) {
              const candyMachine = await fetchCandyMachine(umi, candyMachineAddress);
              const nftMint = generateSigner(umi);

              await mintV2(umi, {
                candyMachine: candyMachineAddress,
                nftMint,
                collectionMint: candyMachine.collectionMint,
                collectionUpdateAuthority: candyMachine.authority,
                mintArgs: {
                  solPayment: some({
                    destination: candyMachine.authority,
                  }),
                },
              }).sendAndConfirm(umi);

              console.log("Minted NFT:", nftMint.publicKey);
            }
            ```

            Guards available:
            - `solPayment` / `tokenPayment`: payment in SOL or SPL tokens
            - `startDate` / `endDate`: time-based minting window
            - `mintLimit`: per-wallet mint limit
            - `allowList`: Merkle tree-based allowlist (whitelist)
            - `nftGate` / `tokenGate`: require holding specific NFTs/tokens
            - `freezeSolPayment`: freeze minted NFTs until conditions are met"""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to create metadata for a Solana token using Metaplex?",
            "How to add a name, symbol, and image to an SPL token?",
            "How to use Token Metadata program for fungible tokens?",
        ],
        answer=textwrap.dedent("""\
            The Metaplex Token Metadata program lets you attach metadata (name, symbol, URI/image) to any SPL token — both fungible tokens and NFTs. The metadata lives in a PDA derived from the mint address.

            ```typescript
            import {
              Connection,
              Keypair,
              PublicKey,
              Transaction,
              sendAndConfirmTransaction,
            } from "@solana/web3.js";
            import { createMint, mintTo, getAssociatedTokenAddress } from "@solana/spl-token";
            import {
              createCreateMetadataAccountV3Instruction,
              PROGRAM_ID as TOKEN_METADATA_PROGRAM_ID,
              DataV2,
            } from "@metaplex-foundation/mpl-token-metadata";

            async function createTokenWithMetadata(
              connection: Connection,
              payer: Keypair
            ) {
              // Step 1: Create the mint
              const mint = await createMint(
                connection,
                payer,
                payer.publicKey,     // mint authority
                payer.publicKey,     // freeze authority
                9                    // decimals
              );

              // Step 2: Derive the metadata PDA
              const [metadataPDA] = PublicKey.findProgramAddressSync(
                [
                  Buffer.from("metadata"),
                  TOKEN_METADATA_PROGRAM_ID.toBuffer(),
                  mint.toBuffer(),
                ],
                TOKEN_METADATA_PROGRAM_ID
              );

              // Step 3: Define metadata
              const tokenMetadata: DataV2 = {
                name: "My Token",
                symbol: "MYT",
                uri: "https://arweave.net/your-token-metadata.json",
                sellerFeeBasisPoints: 0,
                creators: null,
                collection: null,
                uses: null,
              };

              // Step 4: Create the metadata account
              const createMetadataIx = createCreateMetadataAccountV3Instruction(
                {
                  metadata: metadataPDA,
                  mint: mint,
                  mintAuthority: payer.publicKey,
                  payer: payer.publicKey,
                  updateAuthority: payer.publicKey,
                },
                {
                  createMetadataAccountArgsV3: {
                    data: tokenMetadata,
                    isMutable: true,
                    collectionDetails: null,
                  },
                }
              );

              const tx = new Transaction().add(createMetadataIx);
              await sendAndConfirmTransaction(connection, tx, [payer]);

              console.log("Token mint:", mint.toBase58());
              console.log("Metadata PDA:", metadataPDA.toBase58());
              return { mint, metadataPDA };
            }

            // The off-chain metadata JSON (hosted at the URI) should look like:
            // {
            //   "name": "My Token",
            //   "symbol": "MYT",
            //   "description": "A sample fungible token",
            //   "image": "https://arweave.net/token-image.png",
            //   "attributes": [],
            //   "properties": {
            //     "files": [
            //       {
            //         "uri": "https://arweave.net/token-image.png",
            //         "type": "image/png"
            //       }
            //     ]
            //   }
            // }
            ```

            Key points:
            - The metadata PDA seeds are always: `["metadata", TOKEN_METADATA_PROGRAM_ID, mint]`.
            - The `uri` field should point to a JSON file following the Metaplex JSON standard.
            - For fungible tokens, set `sellerFeeBasisPoints: 0` and `creators: null`.
            - Use `createUpdateMetadataAccountV2Instruction` to update metadata later.
            - Token-2022's built-in metadata extension is an alternative that doesn't require Metaplex."""),
        language="ts",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY 9: SOLANA CONCEPTS & INTERNALS
# ═══════════════════════════════════════════════════════════════════════════

CONCEPTS_TEMPLATES: list[QATemplate] = [
    QATemplate(
        questions=[
            "What is the account model in Solana?",
            "How does Solana store data on-chain?",
            "Explain the Solana account model.",
        ],
        answer=textwrap.dedent("""\
            Solana uses an account-based model where all state is stored in accounts. Unlike Ethereum's contract storage model, Solana separates code (programs) from data (accounts).

            **Account structure:**
            ```
            Account {
                lamports: u64,         // Balance in lamports (1 SOL = 1e9 lamports)
                data: Vec<u8>,         // Arbitrary binary data (up to 10MB)
                owner: Pubkey,         // Program that owns/can modify this account
                executable: bool,      // Is this account a program?
                rent_epoch: u64,       // Epoch when rent was last collected
            }
            ```

            **Key rules:**
            1. **Only the owner program can modify account data** — other programs can only read it.
            2. **Only the System Program can transfer lamports** between accounts (or the program that owns the account can decrease its lamports).
            3. **Programs are stateless** — they're stored in executable accounts but don't have their own storage. All data lives in separate accounts passed to instructions.
            4. **Accounts must be rent-exempt** — they must hold enough SOL to cover their size. The formula is roughly: `(account_size + 128) * 6.96e-6 SOL/byte/year * 2 years`.

            ```typescript
            import { Connection, PublicKey, LAMPORTS_PER_SOL } from "@solana/web3.js";

            async function inspectAccount(connection: Connection, address: PublicKey) {
              const info = await connection.getAccountInfo(address);
              if (!info) {
                console.log("Account does not exist (zero lamports, no data)");
                return;
              }

              console.log("Balance:", info.lamports / LAMPORTS_PER_SOL, "SOL");
              console.log("Data size:", info.data.length, "bytes");
              console.log("Owner:", info.owner.toBase58());
              console.log("Executable:", info.executable);
              console.log("Rent epoch:", info.rentEpoch);

              // Common owners:
              // 11111111111111111111111111111111 = System Program (SOL wallets)
              // TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA = SPL Token
              // BPFLoaderUpgradeab1e11111111111111111111111 = BPF Loader (programs)
            }
            ```

            **Account types in practice:**
            - **Wallet accounts**: owned by System Program, no data, just lamports.
            - **Token accounts**: owned by Token Program, hold token balance + metadata (165 bytes).
            - **Program accounts**: executable, owned by BPF Loader, contain deployed bytecode.
            - **PDA accounts**: owned by a program, used to store program state.
            - **Mint accounts**: owned by Token Program, define a token's supply and properties (82 bytes)."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How do PDAs work under the hood?",
            "What is the math behind Program Derived Addresses?",
            "How are PDAs generated on Solana?",
        ],
        answer=textwrap.dedent("""\
            Program Derived Addresses (PDAs) are deterministic addresses that are guaranteed to NOT be valid Ed25519 public keys — meaning no one holds a private key for them. Only the deriving program can "sign" for them during CPI.

            **How the derivation works:**
            ```
            hash = SHA-256(seeds || program_id || "ProgramDerivedAddress")
            ```
            The runtime tries bump values from 255 down to 0, appending each to the seeds, until the resulting hash is NOT on the Ed25519 curve. This bump value is called the "canonical bump."

            ```rust
            // Under the hood, find_program_address does this:
            pub fn find_program_address(
                seeds: &[&[u8]],
                program_id: &Pubkey,
            ) -> (Pubkey, u8) {
                // Try bumps from 255 down to 0
                for bump in (0..=255).rev() {
                    let mut seeds_with_bump = seeds.to_vec();
                    seeds_with_bump.push(&[bump]);

                    match create_program_address(&seeds_with_bump, program_id) {
                        Ok(address) => return (address, bump),
                        Err(_) => continue, // address was on the curve, try next bump
                    }
                }
                panic!("Could not find program address");
            }

            // create_program_address hashes and checks if result is on curve
            pub fn create_program_address(
                seeds: &[&[u8]],
                program_id: &Pubkey,
            ) -> Result<Pubkey, ProgramError> {
                let mut hasher = Sha256::new();
                for seed in seeds {
                    hasher.update(seed);
                }
                hasher.update(program_id.as_ref());
                hasher.update(b"ProgramDerivedAddress");
                let hash = hasher.finalize();

                let bytes: [u8; 32] = hash.into();

                // Check if the result is on the Ed25519 curve
                if is_on_curve(&bytes) {
                    return Err(ProgramError::InvalidSeeds);
                }
                Ok(Pubkey::new_from_array(bytes))
            }
            ```

            **In Anchor programs, use PDAs like this:**
            ```rust
            #[derive(Accounts)]
            #[instruction(user_id: u64)]
            pub struct CreateUser<'info> {
                #[account(
                    init,
                    payer = payer,
                    space = 8 + UserAccount::INIT_SPACE,
                    seeds = [
                        b"user",
                        payer.key().as_ref(),
                        &user_id.to_le_bytes(),
                    ],
                    bump, // Anchor finds the canonical bump automatically
                )]
                pub user_account: Account<'info, UserAccount>,

                #[account(mut)]
                pub payer: Signer<'info>,
                pub system_program: Program<'info, System>,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct UserAccount {
                pub owner: Pubkey,
                pub user_id: u64,
                pub bump: u8, // store the bump for later use
            }
            ```

            **Why PDAs matter:**
            1. **Deterministic**: given the same seeds and program ID, you always get the same address. No need to store the address separately.
            2. **Program-controlled**: only the program can sign for the PDA via `invoke_signed`, enabling autonomous token transfers, account creation, etc.
            3. **No private key**: impossible for anyone to forge a signature for a PDA externally.
            4. **Canonical bump**: always store and use `ctx.bumps.field_name` — using a non-canonical bump can lead to PDA collision vulnerabilities."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "What is rent and how does rent exemption work?",
            "How much SOL does an account need on Solana?",
            "How to calculate rent for a Solana account?",
        ],
        answer=textwrap.dedent("""\
            Every Solana account must hold enough lamports to cover its storage cost, known as "rent." Since epoch 0, all accounts are required to be **rent-exempt** — meaning they hold at least 2 years' worth of rent. Accounts that aren't rent-exempt are purged.

            **Rent formula:**
            ```
            rent = (account_size + 128) * 3.48 * 10^-6 SOL/byte/epoch * epochs_per_year * 2
            ```
            The 128 bytes is overhead for the account metadata (owner, lamports, etc.).

            ```typescript
            import {
              Connection,
              SystemProgram,
              LAMPORTS_PER_SOL,
            } from "@solana/web3.js";

            async function calculateRent(connection: Connection) {
              // Method 1: Use the RPC method
              const rent0 = await connection.getMinimumBalanceForRentExemption(0);
              console.log("Empty account:", rent0 / LAMPORTS_PER_SOL, "SOL");
              // ~0.00089 SOL

              const rent165 = await connection.getMinimumBalanceForRentExemption(165);
              console.log("Token account (165B):", rent165 / LAMPORTS_PER_SOL, "SOL");
              // ~0.00204 SOL

              const rent10000 = await connection.getMinimumBalanceForRentExemption(10000);
              console.log("10KB account:", rent10000 / LAMPORTS_PER_SOL, "SOL");
              // ~0.0727 SOL

              // Common sizes:
              const sizes = {
                "System account (0 data)": 0,
                "SPL Token mint": 82,
                "SPL Token account": 165,
                "Anchor account (small)": 200,
                "Anchor account (medium)": 1000,
                "Anchor account (large)": 10000,
              };

              for (const [name, size] of Object.entries(sizes)) {
                const lamports = await connection.getMinimumBalanceForRentExemption(size);
                console.log(
                  `${name} (${size}B): ${(lamports / LAMPORTS_PER_SOL).toFixed(6)} SOL`
                );
              }
            }
            ```

            ```rust
            // In an Anchor program, rent is handled automatically with `init`:
            #[derive(Accounts)]
            pub struct CreateAccount<'info> {
                #[account(
                    init,
                    payer = user,  // who pays the rent
                    space = 8 + MyAccount::INIT_SPACE,  // 8 for discriminator + data
                )]
                pub my_account: Account<'info, MyAccount>,
                #[account(mut)]
                pub user: Signer<'info>,
                pub system_program: Program<'info, System>,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct MyAccount {
                pub authority: Pubkey,  // 32 bytes
                pub value: u64,        // 8 bytes
                #[max_len(100)]
                pub name: String,      // 4 + 100 bytes
                pub bump: u8,          // 1 byte
            }
            // Total space: 8 (discriminator) + 32 + 8 + 4 + 100 + 1 = 153 bytes
            // Rent: ~0.00166 SOL
            ```

            Important:
            - Rent is paid once at account creation and refunded when the account is closed.
            - The payer can be any signer — it doesn't have to be the account owner.
            - Maximum account size is 10MB (10,485,760 bytes).
            - The `8 + INIT_SPACE` pattern is standard: 8 bytes for Anchor's account discriminator."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How does Solana handle parallel transaction execution?",
            "What is Sealevel and how does it work?",
            "Why does Solana require specifying accounts upfront?",
        ],
        answer=textwrap.dedent("""\
            Solana's runtime (called Sealevel) can execute transactions in parallel by analyzing their account access patterns. This is why every transaction must declare ALL accounts it will read or write — the runtime uses this information to build a dependency graph.

            **How parallel execution works:**
            ```
            Transaction A: reads [1, 2], writes [3]
            Transaction B: reads [4, 5], writes [6]
            Transaction C: reads [1], writes [2]

            A and B can run in parallel (no shared writable accounts)
            A and C CANNOT run in parallel (both access account 2, and C writes to it)
            B and C can run in parallel (no shared accounts)

            Execution schedule:
            Thread 1: [A] → [C]  (sequential because they share account 2)
            Thread 2: [B]        (parallel with A)
            ```

            **Rules for parallel execution:**
            1. Two transactions can run in parallel if they don't write to any shared accounts.
            2. Two transactions that both READ the same account CAN run in parallel.
            3. If one writes and another reads/writes the same account, they must be sequential.

            **Why this matters for developers:**
            ```rust
            use anchor_lang::prelude::*;

            // DESIGN FOR PARALLELISM:
            // Use per-user accounts instead of global state

            // BAD: Single global counter — all transactions serialize
            #[account]
            pub struct GlobalCounter {
                pub count: u64, // every user writes to the same account
            }

            // GOOD: Per-user counters — transactions for different users parallelize
            #[account]
            pub struct UserCounter {
                pub user: Pubkey,
                pub count: u64,
            }

            // GOOD: Use PDAs derived from user keys
            #[derive(Accounts)]
            pub struct IncrementUser<'info> {
                #[account(
                    mut,
                    seeds = [b"counter", user.key().as_ref()],
                    bump,
                )]
                pub counter: Account<'info, UserCounter>, // unique per user
                pub user: Signer<'info>,
            }
            ```

            **Practical implications:**
            - Popular programs with shared state (AMM pools, order books) become serialization bottlenecks — all transactions touching the same pool execute sequentially.
            - Design your program to minimize shared writable accounts.
            - Use per-user PDAs instead of global state where possible.
            - Read-only accounts (e.g., oracle prices) don't block parallelism — only writes do.
            - The theoretical max is ~50,000 TPS with full parallelism; a single-threaded bottleneck limits a hot account to ~400 TPS."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "What are the compute budget limits in Solana?",
            "How much compute can a Solana transaction use?",
            "What are the resource limits for Solana programs?",
        ],
        answer=textwrap.dedent("""\
            Solana imposes several resource limits on transactions and programs to ensure network performance. Understanding these limits is essential for building programs that work within constraints.

            **Transaction limits:**
            ```
            Max transaction size:        1,232 bytes (serialized)
            Max compute units (per tx):  1,400,000 CU
            Max accounts per tx:         64 (legacy) / 256 (versioned with ALTs)
            Max instructions per tx:     No hard limit (constrained by size + CU)
            Max signers per tx:          No hard limit (constrained by size)
            ```

            **Per-instruction defaults:**
            ```
            Default CU per instruction:  200,000 CU
            Max CU per instruction:      1,400,000 CU (with ComputeBudgetProgram)
            ```

            **Program limits:**
            ```
            Max program binary size:     10 MB (BPF ELF)
            Max account data size:       10 MB (10,485,760 bytes)
            Max CPI depth:               4 levels
            Max CPI instruction size:    1,280 bytes
            Max stack frame size:        4 KB
            Max call depth (BPF):        64
            Max log message:             No hard limit (but consumes CU)
            ```

            **Memory limits:**
            ```
            Heap size:                   32 KB (default), 256 KB (with request_heap_frame)
            Stack size:                  4 KB per frame
            ```

            ```rust
            // Request more heap memory (if default 32KB is not enough)
            // Add this to your program entrypoint:
            #[cfg(not(feature = "no-entrypoint"))]
            solana_program::entrypoint!(process_instruction);

            // Or in Anchor, use the heap_size feature:
            // [features]
            // heap-size-32768 = []    # 32 KB (default)
            // heap-size-131072 = []   # 128 KB
            // heap-size-262144 = []   # 256 KB
            ```

            ```typescript
            import { ComputeBudgetProgram, Transaction } from "@solana/web3.js";

            // Set compute units for a transaction
            const tx = new Transaction().add(
              ComputeBudgetProgram.setComputeUnitLimit({
                units: 400_000, // request 400K CU
              }),
              ComputeBudgetProgram.setComputeUnitPrice({
                microLamports: 10_000, // priority fee
              }),
              // ... your instructions
            );
            ```

            **CU cost reference:**
            - SHA-256 (64 bytes): ~90 CU
            - Ed25519 verify: ~1,800 CU
            - System transfer: ~300 CU
            - SPL Token transfer (CPI): ~4,500 CU
            - Account creation: ~10,000 CU
            - Anchor deserialization: ~2,000-5,000 CU per account
            - `msg!()`: ~100-200 CU
            - PDA derivation: ~1,500 CU"""),
        language="rust",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY 10: ERROR HANDLING & COMMON ISSUES
# ═══════════════════════════════════════════════════════════════════════════

ERROR_HANDLING_TEMPLATES: list[QATemplate] = [
    QATemplate(
        questions=[
            "What does error 0x1 mean in an Anchor program?",
            "How to decode Anchor error codes?",
            "What are the common Anchor error codes?",
        ],
        answer=textwrap.dedent("""\
            Anchor uses specific error code ranges. Error `0x1` (decimal 1) is `InsufficientFunds` from the System Program, not an Anchor error. Here's how to decode errors:

            **Error code ranges:**
            ```
            0 - 99:       System Program / built-in errors
            100 - 1999:   SPL Program errors
            2000 - 2999:  Anchor internal errors (account validation)
            3000 - 3999:  Anchor constraint errors
            4000 - 4999:  Anchor account resolution errors
            6000+:        Your custom #[error_code] errors (6000 + enum index)
            ```

            **Common System/Runtime errors:**
            ```typescript
            const SYSTEM_ERRORS: Record<number, string> = {
              0: "Success",
              1: "InsufficientFunds — not enough SOL/lamports",
              2: "InvalidArgument",
              3: "InvalidInstructionData",
              4: "InvalidAccountData",
              5: "AccountDataTooSmall",
              6: "InsufficientFunds (for rent)",
              7: "IncorrectProgramId — account not owned by expected program",
            };
            ```

            **Common Anchor errors:**
            ```typescript
            const ANCHOR_ERRORS: Record<number, string> = {
              // Account errors (2000-2999)
              2000: "AccountDiscriminatorAlreadySet — account already initialized",
              2001: "AccountDiscriminatorNotFound — missing 8-byte discriminator",
              2002: "AccountDiscriminatorMismatch — wrong account type",
              2003: "AccountDidNotDeserialize — corrupt/wrong data",
              2006: "AccountNotEnoughKeys — missing accounts in instruction",
              // Constraint errors (3000-3999)
              3000: "ConstraintMut — account should be mutable",
              3001: "ConstraintHasOne — has_one check failed",
              3002: "ConstraintSigner — account must be a signer",
              3003: "ConstraintRaw — custom constraint returned false",
              3004: "ConstraintOwner — wrong account owner",
              3006: "ConstraintSeeds — PDA seeds don't match",
              3010: "ConstraintClose — close constraint failed",
              3012: "ConstraintZero — account not zeroed",
              3016: "ConstraintAssociated — not the correct ATA",
            };

            // Decode your custom errors:
            // #[error_code]
            // pub enum MyError {
            //     #[msg("Insufficient balance")]   // 6000
            //     InsufficientBalance,
            //     #[msg("Invalid amount")]          // 6001
            //     InvalidAmount,
            //     #[msg("Unauthorized")]            // 6002
            //     Unauthorized,
            // }

            function decodeAnchorError(code: number): string {
              if (code < 2000) return `System/SPL error: ${code}`;
              if (code < 3000) return `Anchor account error: ${code}`;
              if (code < 4000) return `Anchor constraint error: ${code}`;
              if (code < 6000) return `Anchor error: ${code}`;
              return `Custom program error at index: ${code - 6000}`;
            }
            ```

            **Extracting error codes from transaction results:**
            ```typescript
            try {
              await program.methods.myInstruction().rpc();
            } catch (err: any) {
              if (err.error?.errorCode) {
                console.log("Error code:", err.error.errorCode.code);
                console.log("Error number:", err.error.errorCode.number);
                console.log("Error message:", err.error.errorMessage);
              }
            }
            ```"""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to fix blockhash expiration errors?",
            "What causes 'Blockhash not found' error?",
            "How to handle expired blockhash in Solana transactions?",
        ],
        answer=textwrap.dedent("""\
            Blockhash expiration means your transaction's `recentBlockhash` is too old. Solana blockhashes are valid for about 60-90 seconds (~150 slots). After that, the transaction is permanently rejected.

            **Common causes:**
            1. Slow signing process (hardware wallet, multi-party signing)
            2. Network congestion delaying transaction landing
            3. Reusing a blockhash across multiple transactions that take time

            **Solutions:**

            ```typescript
            import {
              Connection,
              Transaction,
              Keypair,
              BlockhashWithExpiryBlockHeight,
            } from "@solana/web3.js";

            // Solution 1: Get fresh blockhash just before sending
            async function sendFreshBlockhash(
              connection: Connection,
              payer: Keypair,
              buildTransaction: () => Transaction
            ) {
              const tx = buildTransaction();
              // Get blockhash as late as possible
              const { blockhash, lastValidBlockHeight } =
                await connection.getLatestBlockhash("confirmed");
              tx.recentBlockhash = blockhash;
              tx.feePayer = payer.publicKey;
              tx.sign(payer);

              const sig = await connection.sendRawTransaction(tx.serialize());

              // Confirm with blockhash-based strategy
              await connection.confirmTransaction({
                signature: sig,
                blockhash,
                lastValidBlockHeight,
              });

              return sig;
            }

            // Solution 2: Retry with new blockhash
            async function sendWithBlockhashRetry(
              connection: Connection,
              payer: Keypair,
              buildTransaction: () => Transaction,
              maxAttempts = 3
            ) {
              for (let attempt = 0; attempt < maxAttempts; attempt++) {
                const tx = buildTransaction();
                const { blockhash, lastValidBlockHeight } =
                  await connection.getLatestBlockhash("confirmed");
                tx.recentBlockhash = blockhash;
                tx.feePayer = payer.publicKey;
                tx.sign(payer);

                try {
                  const sig = await connection.sendRawTransaction(tx.serialize());
                  const result = await connection.confirmTransaction(
                    { signature: sig, blockhash, lastValidBlockHeight },
                    "confirmed"
                  );

                  if (!result.value.err) return sig;
                } catch (err: any) {
                  const msg = err.message || "";
                  if (
                    msg.includes("Blockhash not found") ||
                    msg.includes("block height exceeded")
                  ) {
                    console.log(`Attempt ${attempt + 1}: blockhash expired, retrying...`);
                    continue;
                  }
                  throw err; // Different error — don't retry
                }
              }
              throw new Error("Transaction failed: blockhash expired after all retries");
            }

            // Solution 3: Use durable nonces for offline/slow signing
            // See the durable nonce example for transactions that need to
            // survive longer than 60 seconds.
            ```

            Best practices:
            - Call `getLatestBlockhash()` immediately before signing — not minutes before.
            - Use `"confirmed"` commitment for blockhash to get a recent one.
            - For retry logic, REBUILD the transaction with a new blockhash — don't re-send the same one.
            - Monitor `lastValidBlockHeight` to know when to give up.
            - For multisig/offline signing workflows, use **durable nonces** instead of recent blockhashes."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "What causes 'Program failed to complete' error?",
            "Why did my Solana program run out of compute?",
            "How to fix compute budget exceeded error?",
        ],
        answer=textwrap.dedent("""\
            "Program failed to complete" means your program exceeded its compute unit budget. The default is 200,000 CU per instruction, or 1,400,000 CU per transaction. This is Solana's equivalent of "out of gas."

            **Common causes and fixes:**

            1. **Not requesting enough CU:**
            ```typescript
            import { ComputeBudgetProgram, Transaction } from "@solana/web3.js";

            const tx = new Transaction().add(
              // Request more compute units
              ComputeBudgetProgram.setComputeUnitLimit({
                units: 1_000_000, // up to 1.4M
              }),
              // ... your instruction
            );
            ```

            2. **Large account deserialization (Anchor):**
            ```rust
            // Use zero-copy for large accounts
            #[account(zero_copy)]
            #[repr(C)]
            pub struct BigAccount {
                pub data: [u8; 10000],
            }

            // In accounts struct:
            pub big: AccountLoader<'info, BigAccount>,
            // Instead of: pub big: Account<'info, BigAccount>,
            ```

            3. **Excessive logging:**
            ```rust
            // BAD: String formatting in loops
            for item in items.iter() {
                msg!("Processing item: {:?}", item); // expensive!
            }

            // GOOD: Log only summary
            msg!("Processed {} items", items.len());
            ```

            4. **Complex math in loops:**
            ```rust
            // BAD: PDA derivation in a loop
            for i in 0..100 {
                let (pda, _) = Pubkey::find_program_address(
                    &[b"item", &i.to_le_bytes()],
                    &program_id,
                ); // ~1500 CU each = 150,000 CU total!
            }

            // GOOD: Pre-compute or pass PDAs as accounts
            ```

            5. **Stack overflow (4KB limit per frame):**
            ```rust
            // BAD: Large arrays on stack
            let buffer = [0u8; 10000]; // stack overflow!

            // GOOD: Use heap allocation
            let buffer = vec![0u8; 10000];

            // Or use Box for large structs in Anchor accounts:
            pub big_account: Box<Account<'info, BigState>>,
            ```

            **Debugging CU usage:**
            ```typescript
            // Simulate to check CU consumption
            const simulation = await connection.simulateTransaction(tx);
            console.log("CU consumed:", simulation.value.unitsConsumed);

            // In program logs, look for:
            // "Program consumed XXXXX of YYYYY compute units"
            ```

            If you're consistently hitting limits, consider:
            - Splitting work across multiple transactions/instructions.
            - Using Pinocchio instead of Anchor for CU-critical paths.
            - Reducing the number of accounts (fewer deserializations).
            - Using `AccountInfo` for accounts you only need the key from."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "What does 'Attempt to debit an account but found no record of a prior credit' mean?",
            "How to fix 'account not found' when sending a transaction?",
            "Why does my Solana transaction fail with AccountNotFound?",
        ],
        answer=textwrap.dedent("""\
            This error means you're trying to use (read/write/debit) an account that doesn't exist on-chain. On Solana, accounts only exist if they hold lamports — an account with 0 lamports is effectively deleted.

            **Common causes:**

            1. **Using the wrong network:**
            ```typescript
            // You deployed to devnet but are connecting to mainnet
            const connection = new Connection("https://api.mainnet-beta.solana.com");
            // Should be:
            const connection = new Connection("https://api.devnet.solana.com");
            ```

            2. **Token account doesn't exist yet:**
            ```typescript
            import {
              getAssociatedTokenAddress,
              getOrCreateAssociatedTokenAccount,
            } from "@solana/spl-token";

            // BAD: Assumes the ATA exists
            const ata = await getAssociatedTokenAddress(mint, owner);
            // If it doesn't exist, any transfer TO it will fail

            // GOOD: Create if it doesn't exist
            const ata = await getOrCreateAssociatedTokenAccount(
              connection,
              payer,
              mint,
              owner
            );

            // Or use createAssociatedTokenAccountIdempotent for atomic creation:
            import { createAssociatedTokenAccountIdempotentInstruction } from "@solana/spl-token";
            tx.add(
              createAssociatedTokenAccountIdempotentInstruction(
                payer.publicKey,
                ata,
                owner,
                mint
              )
            );
            ```

            3. **PDA account not initialized:**
            ```typescript
            // The PDA address is deterministic but the account may not exist
            const [pda] = PublicKey.findProgramAddressSync(
              [Buffer.from("config")],
              programId
            );

            // Check if it exists before using it
            const accountInfo = await connection.getAccountInfo(pda);
            if (!accountInfo) {
              console.log("Account doesn't exist — call initialize first");
            }
            ```

            4. **Account was closed/garbage-collected:**
            ```rust
            // In Anchor, use init_if_needed for accounts that may or may not exist:
            #[account(
                init_if_needed,
                payer = user,
                space = 8 + MyAccount::INIT_SPACE,
                seeds = [b"user", user.key().as_ref()],
                bump,
            )]
            pub my_account: Account<'info, MyAccount>,
            ```

            5. **Wallet has 0 SOL:**
            ```typescript
            // Fund the wallet first
            // On devnet:
            const sig = await connection.requestAirdrop(
              wallet.publicKey,
              2 * LAMPORTS_PER_SOL
            );
            await connection.confirmTransaction(sig);
            ```

            Prevention:
            - Always check if accounts exist before building transactions.
            - Use `getOrCreateAssociatedTokenAccount` for token accounts.
            - Use `init_if_needed` in Anchor when appropriate (with `feature = "init-if-needed"`).
            - Add proper error messages so users know which account is missing."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to fix 'Transaction simulation failed: Error processing Instruction 0'?",
            "How to decode transaction simulation errors?",
            "What does 'Error processing Instruction' mean in Solana?",
        ],
        answer=textwrap.dedent("""\
            "Error processing Instruction N" means instruction at index N in the transaction failed. The number tells you which instruction failed, and the subsequent error detail tells you why.

            **Systematic debugging approach:**

            ```typescript
            import { Connection, Transaction, SendTransactionError } from "@solana/web3.js";

            async function debugFailedTransaction(
              connection: Connection,
              transaction: Transaction,
              signers: Keypair[]
            ) {
              try {
                const sig = await connection.sendTransaction(transaction, signers);
                await connection.confirmTransaction(sig);
              } catch (err) {
                if (err instanceof SendTransactionError) {
                  console.log("=== Transaction Error ===");
                  console.log("Message:", err.message);

                  // Get simulation logs
                  const logs = err.logs;
                  if (logs) {
                    console.log("\\n=== Program Logs ===");
                    for (const log of logs) {
                      // Look for the failure point
                      if (log.includes("failed")) {
                        console.log(">>> FAILURE:", log);
                      } else {
                        console.log(log);
                      }
                    }
                  }
                }
              }
            }

            // Better: simulate first for detailed diagnostics
            async function simulateAndDiagnose(
              connection: Connection,
              transaction: Transaction
            ) {
              const simulation = await connection.simulateTransaction(transaction);

              if (simulation.value.err) {
                console.log("Error:", JSON.stringify(simulation.value.err, null, 2));

                // Parse the error structure
                const err = simulation.value.err as any;
                if (err.InstructionError) {
                  const [index, detail] = err.InstructionError;
                  console.log(`\\nFailed instruction index: ${index}`);
                  console.log("Instructions in transaction:");
                  transaction.instructions.forEach((ix, i) => {
                    const marker = i === index ? ">>> " : "    ";
                    console.log(`${marker}[${i}] Program: ${ix.programId.toBase58()}`);
                  });

                  if (typeof detail === "object" && detail.Custom !== undefined) {
                    console.log(`\\nCustom error code: ${detail.Custom}`);
                  } else if (typeof detail === "string") {
                    console.log(`\\nError type: ${detail}`);
                  }
                }

                // Print logs around the failure
                if (simulation.value.logs) {
                  console.log("\\n=== Logs ===");
                  for (const log of simulation.value.logs) {
                    console.log(log);
                  }
                }
              }
            }
            ```

            **Common "Error processing Instruction" causes:**

            | Error Detail | Meaning |
            |---|---|
            | `Custom(0)` | Generic program error |
            | `Custom(1)` | Insufficient funds |
            | `InvalidAccountData` | Account data doesn't match expected format |
            | `AccountNotFound` | An account in the instruction doesn't exist |
            | `IncorrectProgramId` | Account not owned by expected program |
            | `MissingRequiredSignature` | A required signer didn't sign |
            | `Custom(3012)` | Anchor: ConstraintZero — account not zeroed |
            | `Custom(3006)` | Anchor: ConstraintSeeds — PDA mismatch |
            | `Custom(3001)` | Anchor: ConstraintHasOne — has_one check failed |

            Tips:
            - The instruction index (0, 1, 2...) tells you exactly which instruction failed.
            - Always simulate before sending during development.
            - Read the logs from bottom to top — the last log before "failed" usually has the most useful info.
            - Use Anchor's `Program.addEventListener("error", ...)` for real-time error monitoring."""),
        language="ts",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# ADDITIONAL TEMPLATES — BULK EXPANSION
# Each template generates ~8 records via augmentation.
# ═══════════════════════════════════════════════════════════════════════════

# --- Additional Transaction Templates ---
TRANSACTION_TEMPLATES += [
    QATemplate(
        questions=[
            "How to transfer SOL from one wallet to another?",
            "How to send SOL using TypeScript?",
            "What is the basic SOL transfer code?",
        ],
        answer=textwrap.dedent("""\
            Transferring SOL is the most basic Solana operation. You create a SystemProgram transfer instruction, add it to a transaction, sign, and send.

            ```typescript
            import {
              Connection,
              Keypair,
              PublicKey,
              SystemProgram,
              Transaction,
              sendAndConfirmTransaction,
              LAMPORTS_PER_SOL,
            } from "@solana/web3.js";

            async function transferSol(
              connection: Connection,
              sender: Keypair,
              recipientAddress: string,
              amountSol: number
            ): Promise<string> {
              const recipient = new PublicKey(recipientAddress);
              const lamports = Math.round(amountSol * LAMPORTS_PER_SOL);

              const transaction = new Transaction().add(
                SystemProgram.transfer({
                  fromPubkey: sender.publicKey,
                  toPubkey: recipient,
                  lamports,
                })
              );

              const signature = await sendAndConfirmTransaction(
                connection,
                transaction,
                [sender]
              );

              console.log(`Transferred ${amountSol} SOL. Signature: ${signature}`);
              return signature;
            }
            ```

            Notes:
            - 1 SOL = 1,000,000,000 lamports (1e9).
            - The sender must have enough balance for the transfer amount plus transaction fee (~5000 lamports).
            - Use `sendAndConfirmTransaction` for convenience — it handles signing and confirmation."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to transfer SPL tokens between wallets?",
            "How to send an SPL token using TypeScript?",
            "How to do a token transfer on Solana?",
        ],
        answer=textwrap.dedent("""\
            SPL token transfers require the sender's token account, recipient's token account (Associated Token Account), and the token program. If the recipient doesn't have a token account, you need to create one first.

            ```typescript
            import { Connection, Keypair, PublicKey } from "@solana/web3.js";
            import {
              getOrCreateAssociatedTokenAccount,
              transfer,
              getAssociatedTokenAddress,
            } from "@solana/spl-token";

            async function transferToken(
              connection: Connection,
              sender: Keypair,
              mintAddress: PublicKey,
              recipientAddress: PublicKey,
              amount: number, // in token's smallest unit
            ): Promise<string> {
              // Get or create sender's ATA
              const senderATA = await getAssociatedTokenAddress(
                mintAddress,
                sender.publicKey
              );

              // Get or create recipient's ATA (payer creates if needed)
              const recipientATA = await getOrCreateAssociatedTokenAccount(
                connection,
                sender,      // payer for account creation
                mintAddress,
                recipientAddress
              );

              // Transfer tokens
              const signature = await transfer(
                connection,
                sender,
                senderATA,
                recipientATA.address,
                sender.publicKey,
                amount
              );

              console.log("Transfer signature:", signature);
              return signature;
            }
            ```

            Key points:
            - Each wallet needs a separate token account (ATA) for each token type.
            - `getOrCreateAssociatedTokenAccount` handles ATA creation automatically.
            - The `amount` is in the token's smallest unit (e.g., for 9 decimals, 1 token = 1_000_000_000).
            - The sender must sign as the authority of the source token account."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to create an SPL token on Solana?",
            "How to mint a new fungible token?",
            "How to create a token mint in TypeScript?",
        ],
        answer=textwrap.dedent("""\
            Creating an SPL token involves creating a mint account, then optionally minting tokens to a wallet. The mint authority controls who can create new tokens.

            ```typescript
            import { Connection, Keypair, LAMPORTS_PER_SOL } from "@solana/web3.js";
            import {
              createMint,
              getOrCreateAssociatedTokenAccount,
              mintTo,
            } from "@solana/spl-token";

            async function createToken(
              connection: Connection,
              payer: Keypair,
              decimals: number = 9
            ) {
              // Create the mint
              const mint = await createMint(
                connection,
                payer,             // payer for transaction fees
                payer.publicKey,   // mint authority
                payer.publicKey,   // freeze authority (null for no freeze)
                decimals           // decimal places
              );
              console.log("Mint address:", mint.toBase58());

              // Create an associated token account for the payer
              const tokenAccount = await getOrCreateAssociatedTokenAccount(
                connection,
                payer,
                mint,
                payer.publicKey
              );
              console.log("Token account:", tokenAccount.address.toBase58());

              // Mint 1000 tokens (with 9 decimals: 1000 * 10^9)
              const amount = 1000n * BigInt(10 ** decimals);
              await mintTo(
                connection,
                payer,
                mint,
                tokenAccount.address,
                payer.publicKey, // mint authority
                amount
              );
              console.log(`Minted ${1000} tokens`);

              return { mint, tokenAccount: tokenAccount.address };
            }
            ```

            Key concepts:
            - **Mint account**: defines the token (decimals, supply, authorities).
            - **Mint authority**: can create new tokens. Set to null to make supply fixed.
            - **Freeze authority**: can freeze/thaw token accounts. Set to null to make tokens unfreezable.
            - Standard decimals: 9 for most tokens, 6 for stablecoins, 0 for NFTs."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to close a token account and reclaim rent?",
            "How to reclaim SOL from empty token accounts?",
            "How to clean up unused token accounts on Solana?",
        ],
        answer=textwrap.dedent("""\
            Closing empty token accounts returns the rent (~0.002 SOL per account) to the owner. This is useful for cleaning up dust accounts.

            ```typescript
            import { Connection, Keypair, PublicKey } from "@solana/web3.js";
            import {
              closeAccount,
              TOKEN_PROGRAM_ID,
              getTokenAccountsByOwner,
            } from "@solana/spl-token";

            async function closeEmptyTokenAccounts(
              connection: Connection,
              owner: Keypair
            ): Promise<number> {
              // Find all token accounts
              const tokenAccounts = await connection.getTokenAccountsByOwner(
                owner.publicKey,
                { programId: TOKEN_PROGRAM_ID }
              );

              let closedCount = 0;
              for (const { pubkey, account } of tokenAccounts.value) {
                // Parse balance (offset 64, 8 bytes little-endian u64)
                const balance = account.data.readBigUInt64LE(64);

                if (balance === 0n) {
                  try {
                    await closeAccount(
                      connection,
                      owner,           // payer
                      pubkey,          // token account to close
                      owner.publicKey, // destination for rent lamports
                      owner            // owner/authority of the token account
                    );
                    closedCount++;
                    console.log(`Closed: ${pubkey.toBase58()}`);
                  } catch (err) {
                    console.error(`Failed to close ${pubkey.toBase58()}:`, err);
                  }
                }
              }

              console.log(`Closed ${closedCount} empty accounts, reclaimed ~${(closedCount * 0.00203928).toFixed(4)} SOL`);
              return closedCount;
            }
            ```

            Notes:
            - Only accounts with zero balance can be closed.
            - The rent (~0.00203928 SOL per token account) is returned to the destination.
            - Native SOL (wrapped SOL) accounts can also be closed after unwrapping.
            - Some wallets (Phantom, Solflare) have a "close empty accounts" feature built in."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to create a Solana transaction with memo?",
            "How to add a memo to a Solana transaction?",
            "How to attach a message/note to a Solana transfer?",
        ],
        answer=textwrap.dedent("""\
            The Memo program lets you attach arbitrary text to transactions. Memos are recorded in transaction logs and indexed by explorers.

            ```typescript
            import {
              Connection,
              Keypair,
              PublicKey,
              Transaction,
              TransactionInstruction,
              SystemProgram,
              sendAndConfirmTransaction,
            } from "@solana/web3.js";

            const MEMO_PROGRAM_ID = new PublicKey(
              "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
            );

            async function transferWithMemo(
              connection: Connection,
              sender: Keypair,
              recipient: PublicKey,
              lamports: number,
              memo: string
            ) {
              const tx = new Transaction();

              // Add transfer instruction
              tx.add(
                SystemProgram.transfer({
                  fromPubkey: sender.publicKey,
                  toPubkey: recipient,
                  lamports,
                })
              );

              // Add memo instruction
              tx.add(
                new TransactionInstruction({
                  keys: [{ pubkey: sender.publicKey, isSigner: true, isWritable: false }],
                  programId: MEMO_PROGRAM_ID,
                  data: Buffer.from(memo, "utf-8"),
                })
              );

              const sig = await sendAndConfirmTransaction(connection, tx, [sender]);
              console.log(`Transfer with memo "${memo}": ${sig}`);
              return sig;
            }
            ```

            Use cases:
            - Payment references (invoice IDs, order numbers)
            - On-chain messaging
            - Transaction categorization for accounting
            - Proof of existence (timestamp a document hash)
            - The memo appears in transaction logs and on Solana Explorer."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to send a transaction on Solana devnet?",
            "How to airdrop SOL and test on devnet?",
            "How to get started with Solana development on devnet?",
        ],
        answer=textwrap.dedent("""\
            Devnet is Solana's testing network where you can get free SOL via airdrops. It's the standard environment for development and testing.

            ```typescript
            import {
              Connection,
              Keypair,
              LAMPORTS_PER_SOL,
              SystemProgram,
              Transaction,
              clusterApiUrl,
              sendAndConfirmTransaction,
            } from "@solana/web3.js";

            async function devnetQuickstart() {
              // 1. Connect to devnet
              const connection = new Connection(clusterApiUrl("devnet"), "confirmed");

              // 2. Create a new keypair
              const wallet = Keypair.generate();
              console.log("Public key:", wallet.publicKey.toBase58());

              // 3. Airdrop 2 SOL
              console.log("Requesting airdrop...");
              const airdropSig = await connection.requestAirdrop(
                wallet.publicKey,
                2 * LAMPORTS_PER_SOL
              );
              await connection.confirmTransaction(airdropSig);

              // 4. Check balance
              const balance = await connection.getBalance(wallet.publicKey);
              console.log("Balance:", balance / LAMPORTS_PER_SOL, "SOL");

              // 5. Send a test transaction
              const recipient = Keypair.generate();
              const tx = new Transaction().add(
                SystemProgram.transfer({
                  fromPubkey: wallet.publicKey,
                  toPubkey: recipient.publicKey,
                  lamports: 0.1 * LAMPORTS_PER_SOL,
                })
              );

              const sig = await sendAndConfirmTransaction(connection, tx, [wallet]);
              console.log("Transaction:", sig);
              console.log(`View on explorer: https://explorer.solana.com/tx/${sig}?cluster=devnet`);
            }
            ```

            Devnet tips:
            - Airdrop limit: 2 SOL per request, may be rate-limited.
            - Devnet resets periodically — don't store important data there.
            - Use `clusterApiUrl("devnet")` for the public endpoint.
            - For faster/reliable testing, use a local validator: `solana-test-validator`."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to decode a Solana transaction?",
            "How to parse raw transaction data from Solana?",
            "How to read all instructions from a Solana transaction?",
        ],
        answer=textwrap.dedent("""\
            You can fetch and decode confirmed transactions to inspect their instructions, accounts, and results.

            ```typescript
            import {
              Connection,
              PublicKey,
              ParsedTransactionWithMeta,
            } from "@solana/web3.js";

            async function decodeTransaction(
              connection: Connection,
              signature: string
            ) {
              // Fetch parsed transaction (auto-decodes known programs)
              const tx = await connection.getParsedTransaction(signature, {
                commitment: "confirmed",
                maxSupportedTransactionVersion: 0,
              });

              if (!tx) {
                console.log("Transaction not found");
                return;
              }

              console.log("=== Transaction Details ===");
              console.log("Slot:", tx.slot);
              console.log("Block Time:", new Date((tx.blockTime ?? 0) * 1000).toISOString());
              console.log("Fee:", tx.meta?.fee, "lamports");
              console.log("Status:", tx.meta?.err ? "Failed" : "Success");

              // Iterate instructions
              const instructions = tx.transaction.message.instructions;
              for (let i = 0; i < instructions.length; i++) {
                const ix = instructions[i];
                console.log(`\\n--- Instruction ${i} ---`);
                console.log("Program:", ix.programId.toBase58());

                // Parsed instructions have human-readable info
                if ("parsed" in ix) {
                  console.log("Type:", ix.parsed.type);
                  console.log("Info:", JSON.stringify(ix.parsed.info, null, 2));
                } else {
                  console.log("Data:", ix.data);
                  console.log("Accounts:", ix.accounts.map(a => a.toBase58()));
                }
              }

              // Inner instructions (from CPIs)
              if (tx.meta?.innerInstructions) {
                for (const inner of tx.meta.innerInstructions) {
                  console.log(`\\n--- Inner Instructions (from ix ${inner.index}) ---`);
                  for (const ix of inner.instructions) {
                    console.log("Program:", ix.programId.toBase58());
                    if ("parsed" in ix) {
                      console.log("Type:", ix.parsed.type);
                    }
                  }
                }
              }

              // Balance changes
              if (tx.meta?.preBalances && tx.meta?.postBalances) {
                console.log("\\n--- Balance Changes ---");
                const accounts = tx.transaction.message.accountKeys;
                for (let i = 0; i < accounts.length; i++) {
                  const pre = tx.meta.preBalances[i];
                  const post = tx.meta.postBalances[i];
                  if (pre !== post) {
                    const diff = (post - pre) / 1e9;
                    console.log(`${accounts[i].pubkey.toBase58()}: ${diff > 0 ? "+" : ""}${diff.toFixed(9)} SOL`);
                  }
                }
              }
            }
            ```

            Tips:
            - `getParsedTransaction` auto-decodes System Program, Token Program, and other known programs.
            - Use `maxSupportedTransactionVersion: 0` to support versioned transactions.
            - Inner instructions show CPI calls made by your program."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to get recent transactions for a wallet?",
            "How to fetch transaction history for a Solana address?",
            "How to list past transactions on Solana?",
        ],
        answer=textwrap.dedent("""\
            Use `getSignaturesForAddress` to get recent transaction signatures for any account, then fetch each transaction for details.

            ```typescript
            import { Connection, PublicKey, LAMPORTS_PER_SOL } from "@solana/web3.js";

            async function getTransactionHistory(
              connection: Connection,
              address: PublicKey,
              limit: number = 20
            ) {
              // Get recent signatures
              const signatures = await connection.getSignaturesForAddress(
                address,
                { limit },
                "confirmed"
              );

              console.log(`Found ${signatures.length} recent transactions:\\n`);

              for (const sigInfo of signatures) {
                console.log(`Signature: ${sigInfo.signature}`);
                console.log(`  Slot: ${sigInfo.slot}`);
                console.log(`  Time: ${sigInfo.blockTime ? new Date(sigInfo.blockTime * 1000).toISOString() : "unknown"}`);
                console.log(`  Status: ${sigInfo.err ? "Failed" : "Success"}`);
                if (sigInfo.memo) {
                  console.log(`  Memo: ${sigInfo.memo}`);
                }
                console.log();
              }

              // For pagination, use the last signature as "before" cursor:
              // const olderSigs = await connection.getSignaturesForAddress(
              //   address,
              //   { limit, before: signatures[signatures.length - 1].signature }
              // );

              return signatures;
            }
            ```

            Notes:
            - `getSignaturesForAddress` returns up to 1000 signatures per call.
            - Use `before` parameter for pagination (pass the last signature).
            - For full history on high-activity accounts, use a dedicated indexer (Helius, Triton, Bitquery).
            - The `memo` field is populated if the transaction included a Memo instruction."""),
        language="ts",
    ),
]

# --- Additional Client-TS Templates ---
CLIENT_TS_TEMPLATES += [
    QATemplate(
        questions=[
            "How to load a Solana keypair from a file?",
            "How to read a Solana CLI keypair file?",
            "How to use a keypair JSON file in TypeScript?",
        ],
        answer=textwrap.dedent("""\
            The Solana CLI stores keypairs as JSON files containing an array of 64 bytes (32 secret + 32 public). You can load them in TypeScript.

            ```typescript
            import { Keypair } from "@solana/web3.js";
            import fs from "fs";
            import os from "os";
            import path from "path";

            // Load the default Solana CLI keypair
            function loadDefaultKeypair(): Keypair {
              const keypairPath = path.join(
                os.homedir(),
                ".config",
                "solana",
                "id.json"
              );
              return loadKeypairFromFile(keypairPath);
            }

            // Load from any JSON keypair file
            function loadKeypairFromFile(filePath: string): Keypair {
              const fileContent = fs.readFileSync(filePath, "utf-8");
              const secretKey = Uint8Array.from(JSON.parse(fileContent));
              return Keypair.fromSecretKey(secretKey);
            }

            // Load from base58 private key (Phantom export format)
            import bs58 from "bs58";
            function loadFromBase58(base58PrivateKey: string): Keypair {
              const secretKey = bs58.decode(base58PrivateKey);
              return Keypair.fromSecretKey(secretKey);
            }

            // Load from environment variable
            function loadFromEnv(): Keypair {
              const key = process.env.SOLANA_PRIVATE_KEY;
              if (!key) throw new Error("SOLANA_PRIVATE_KEY not set");

              // Support both JSON array and base58 formats
              if (key.startsWith("[")) {
                return Keypair.fromSecretKey(
                  Uint8Array.from(JSON.parse(key))
                );
              }
              return Keypair.fromSecretKey(bs58.decode(key));
            }
            ```

            Security:
            - Never commit keypair files to version control.
            - Use environment variables or secret managers in production.
            - The 64-byte format is: first 32 bytes = secret key, last 32 bytes = public key."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to create a PDA in TypeScript?",
            "How to derive a Program Derived Address client-side?",
            "How to find a PDA in JavaScript?",
        ],
        answer=textwrap.dedent("""\
            PDAs are derived deterministically from seeds and a program ID. Use `PublicKey.findProgramAddressSync` to compute them client-side (same address as on-chain).

            ```typescript
            import { PublicKey } from "@solana/web3.js";

            const PROGRAM_ID = new PublicKey("YourProgramId...");

            // Simple PDA with string seed
            function findConfigPDA(): [PublicKey, number] {
              return PublicKey.findProgramAddressSync(
                [Buffer.from("config")],
                PROGRAM_ID
              );
            }

            // PDA with user's public key as seed
            function findUserAccountPDA(
              userPubkey: PublicKey
            ): [PublicKey, number] {
              return PublicKey.findProgramAddressSync(
                [
                  Buffer.from("user_account"),
                  userPubkey.toBuffer(),
                ],
                PROGRAM_ID
              );
            }

            // PDA with multiple seeds including a number
            function findOrderPDA(
              market: PublicKey,
              orderId: number
            ): [PublicKey, number] {
              const orderIdBuffer = Buffer.alloc(8);
              orderIdBuffer.writeBigUInt64LE(BigInt(orderId));

              return PublicKey.findProgramAddressSync(
                [
                  Buffer.from("order"),
                  market.toBuffer(),
                  orderIdBuffer,
                ],
                PROGRAM_ID
              );
            }

            // PDA with string seed (e.g., token symbol)
            function findTokenVaultPDA(symbol: string): [PublicKey, number] {
              return PublicKey.findProgramAddressSync(
                [
                  Buffer.from("vault"),
                  Buffer.from(symbol),
                ],
                PROGRAM_ID
              );
            }

            // Usage
            const [configPda, configBump] = findConfigPDA();
            console.log("Config PDA:", configPda.toBase58(), "bump:", configBump);
            ```

            Key points:
            - `findProgramAddressSync` returns `[PublicKey, bump]`. The bump is the canonical bump (highest valid bump).
            - Seeds must match EXACTLY between client and on-chain derivation (same bytes, same order).
            - The sync version is preferred over the async `findProgramAddress` — they return the same result.
            - Numbers must be serialized to bytes explicitly (usually little-endian)."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to call an Anchor program instruction from TypeScript?",
            "How to invoke an Anchor instruction from the client?",
            "How to use the Anchor TypeScript client?",
        ],
        answer=textwrap.dedent("""\
            Anchor generates a TypeScript client from your IDL that provides type-safe instruction calls with a builder pattern.

            ```typescript
            import * as anchor from "@coral-xyz/anchor";
            import { Program, AnchorProvider, BN } from "@coral-xyz/anchor";
            import { Connection, Keypair, PublicKey, SystemProgram } from "@solana/web3.js";
            import { MyProgram } from "../target/types/my_program";
            import idl from "../target/idl/my_program.json";

            async function callAnchorProgram() {
              // Setup provider
              const connection = new Connection("https://api.devnet.solana.com");
              const wallet = new anchor.Wallet(Keypair.generate());
              const provider = new AnchorProvider(connection, wallet, {
                commitment: "confirmed",
              });

              // Create program instance
              const programId = new PublicKey("YourProgramId...");
              const program = new Program<MyProgram>(idl as any, provider);

              // Derive PDA
              const [vaultPda] = PublicKey.findProgramAddressSync(
                [Buffer.from("vault"), wallet.publicKey.toBuffer()],
                programId
              );

              // Call an instruction
              const tx = await program.methods
                .initialize(new BN(1000)) // pass instruction arguments
                .accountsStrict({
                  vault: vaultPda,
                  authority: wallet.publicKey,
                  systemProgram: SystemProgram.programId,
                })
                .rpc(); // sends and confirms transaction

              console.log("Transaction:", tx);

              // Or build without sending (for inspection / multi-ix)
              const instruction = await program.methods
                .deposit(new BN(500))
                .accountsStrict({
                  vault: vaultPda,
                  userTokenAccount: userAta,
                  authority: wallet.publicKey,
                  tokenProgram: TOKEN_PROGRAM_ID,
                })
                .instruction(); // returns TransactionInstruction

              // Fetch account data
              const vaultData = await program.account.vault.fetch(vaultPda);
              console.log("Vault authority:", vaultData.authority.toBase58());
              console.log("Vault balance:", vaultData.balance.toString());
            }
            ```

            Tips:
            - Use `accountsStrict` (not `accounts`) for compile-time type checking.
            - `.rpc()` sends and confirms; `.instruction()` returns the raw instruction.
            - `.transaction()` returns a Transaction object you can customize before sending.
            - Use `new BN(value)` for u64/i64 arguments (BN = big number).
            - Anchor converts camelCase in TypeScript to snake_case in Rust automatically."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to use Solana wallet adapter in a React app?",
            "How to connect Phantom wallet in a React application?",
            "How to integrate Solana wallets in frontend?",
        ],
        answer=textwrap.dedent("""\
            The `@solana/wallet-adapter` library provides React components and hooks for connecting to Solana wallets (Phantom, Solflare, Backpack, etc.).

            ```typescript
            // 1. Install dependencies:
            // npm install @solana/wallet-adapter-react @solana/wallet-adapter-react-ui
            //   @solana/wallet-adapter-wallets @solana/wallet-adapter-base @solana/web3.js

            // App.tsx — Wrap your app with providers
            import {
              ConnectionProvider,
              WalletProvider,
            } from "@solana/wallet-adapter-react";
            import {
              WalletModalProvider,
              WalletMultiButton,
            } from "@solana/wallet-adapter-react-ui";
            import { PhantomWalletAdapter } from "@solana/wallet-adapter-wallets";
            import { clusterApiUrl } from "@solana/web3.js";
            import "@solana/wallet-adapter-react-ui/styles.css";

            function App() {
              const endpoint = clusterApiUrl("devnet");
              const wallets = [new PhantomWalletAdapter()];

              return (
                <ConnectionProvider endpoint={endpoint}>
                  <WalletProvider wallets={wallets} autoConnect>
                    <WalletModalProvider>
                      <WalletMultiButton />
                      <MyComponent />
                    </WalletModalProvider>
                  </WalletProvider>
                </ConnectionProvider>
              );
            }

            // MyComponent.tsx — Use wallet hooks
            import { useConnection, useWallet } from "@solana/wallet-adapter-react";
            import { LAMPORTS_PER_SOL, SystemProgram, Transaction } from "@solana/web3.js";

            function MyComponent() {
              const { connection } = useConnection();
              const { publicKey, sendTransaction, connected } = useWallet();

              async function handleSend() {
                if (!publicKey) return;

                const transaction = new Transaction().add(
                  SystemProgram.transfer({
                    fromPubkey: publicKey,
                    toPubkey: publicKey, // sending to self as example
                    lamports: 0.01 * LAMPORTS_PER_SOL,
                  })
                );

                const { blockhash } = await connection.getLatestBlockhash();
                transaction.recentBlockhash = blockhash;
                transaction.feePayer = publicKey;

                const signature = await sendTransaction(transaction, connection);
                await connection.confirmTransaction(signature, "confirmed");
                console.log("Sent:", signature);
              }

              return (
                <div>
                  {connected ? (
                    <>
                      <p>Connected: {publicKey?.toBase58()}</p>
                      <button onClick={handleSend}>Send 0.01 SOL</button>
                    </>
                  ) : (
                    <p>Connect your wallet to continue</p>
                  )}
                </div>
              );
            }
            ```

            Key hooks:
            - `useWallet()` — provides `publicKey`, `sendTransaction`, `signMessage`, `connected`
            - `useConnection()` — provides the `Connection` object
            - `useAnchorWallet()` — returns wallet compatible with Anchor's `AnchorProvider`"""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to use getAccountInfo to read raw account data?",
            "How to fetch and read a Solana account's data?",
            "How to inspect a Solana account's raw bytes?",
        ],
        answer=textwrap.dedent("""\
            `getAccountInfo` returns the raw account data as a Buffer, which you can manually parse. This is useful for non-Anchor programs or custom deserialization.

            ```typescript
            import { Connection, PublicKey, AccountInfo } from "@solana/web3.js";

            async function readAccountData(
              connection: Connection,
              accountAddress: PublicKey
            ) {
              const accountInfo = await connection.getAccountInfo(accountAddress);
              if (!accountInfo) {
                console.log("Account not found");
                return null;
              }

              console.log("Owner:", accountInfo.owner.toBase58());
              console.log("Lamports:", accountInfo.lamports);
              console.log("Data length:", accountInfo.data.length);
              console.log("Executable:", accountInfo.executable);

              // Parse data manually
              const data = accountInfo.data;

              // For Anchor accounts, first 8 bytes are discriminator
              const discriminator = data.subarray(0, 8);
              console.log("Discriminator:", Buffer.from(discriminator).toString("hex"));

              // Read fields at known offsets
              // Example: Pubkey at offset 8 (32 bytes)
              const pubkeyField = new PublicKey(data.subarray(8, 40));
              console.log("Pubkey field:", pubkeyField.toBase58());

              // Example: u64 at offset 40 (8 bytes, little-endian)
              const u64Field = data.readBigUInt64LE(40);
              console.log("u64 field:", u64Field.toString());

              // Example: u8 at offset 48
              const u8Field = data[48];
              console.log("u8 field:", u8Field);

              // Example: bool at offset 49
              const boolField = data[49] === 1;
              console.log("bool field:", boolField);

              return accountInfo;
            }

            // Fetch multiple accounts in one RPC call
            async function readMultipleAccounts(
              connection: Connection,
              addresses: PublicKey[]
            ) {
              const accounts = await connection.getMultipleAccountsInfo(addresses);
              for (let i = 0; i < addresses.length; i++) {
                const info = accounts[i];
                console.log(
                  addresses[i].toBase58(),
                  info ? `${info.data.length} bytes` : "not found"
                );
              }
              return accounts;
            }
            ```

            Tips:
            - Use `getMultipleAccountsInfo` to batch-fetch accounts in a single RPC call (up to 100).
            - Anchor discriminator = first 8 bytes of SHA-256("account:StructName").
            - Numbers are always little-endian on Solana.
            - For complex deserialization, use Borsh: `import { deserialize } from "borsh"`;"""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to listen for Anchor events in TypeScript?",
            "How to subscribe to program events from Anchor?",
            "How to use addEventListener with Anchor?",
        ],
        answer=textwrap.dedent("""\
            Anchor programs can emit events using `emit!()`. Clients can listen for these events in real-time via WebSocket subscriptions or parse them from transaction logs.

            ```typescript
            import * as anchor from "@coral-xyz/anchor";
            import { Program } from "@coral-xyz/anchor";
            import { MyProgram } from "../target/types/my_program";

            // The Rust event definition:
            // #[event]
            // pub struct SwapEvent {
            //     pub user: Pubkey,
            //     pub amount_in: u64,
            //     pub amount_out: u64,
            //     pub timestamp: i64,
            // }

            async function listenForEvents(program: Program<MyProgram>) {
              // Real-time listener via WebSocket
              const listener = program.addEventListener(
                "swapEvent", // event name in camelCase
                (event, slot, signature) => {
                  console.log("=== Swap Event ===");
                  console.log("User:", event.user.toBase58());
                  console.log("Amount In:", event.amountIn.toString());
                  console.log("Amount Out:", event.amountOut.toString());
                  console.log("Timestamp:", event.timestamp.toString());
                  console.log("Slot:", slot);
                  console.log("Tx:", signature);
                }
              );

              console.log("Listening for swap events... (listener ID:", listener, ")");

              // Later, remove the listener
              // await program.removeEventListener(listener);
            }

            // Parse events from a specific transaction
            async function parseEventsFromTx(
              program: Program<MyProgram>,
              connection: anchor.web3.Connection,
              signature: string
            ) {
              const tx = await connection.getTransaction(signature, {
                commitment: "confirmed",
                maxSupportedTransactionVersion: 0,
              });

              if (!tx?.meta?.logMessages) return;

              const coder = new anchor.BorshCoder(program.idl);
              const eventParser = new anchor.EventParser(
                program.programId,
                coder
              );

              const events = eventParser.parseLogs(tx.meta.logMessages);
              for (const event of events) {
                console.log("Event:", event.name, event.data);
              }
            }
            ```

            Rust side:
            ```rust
            #[event]
            pub struct SwapEvent {
                pub user: Pubkey,
                pub amount_in: u64,
                pub amount_out: u64,
                pub timestamp: i64,
            }

            // In your instruction handler:
            emit!(SwapEvent {
                user: ctx.accounts.user.key(),
                amount_in,
                amount_out,
                timestamp: Clock::get()?.unix_timestamp,
            });
            ```

            Notes:
            - Events are encoded as base64 in program logs (prefixed with "Program data:").
            - Event names are automatically converted between snake_case (Rust) and camelCase (TypeScript).
            - `addEventListener` requires a WebSocket connection to the RPC.
            - Events are NOT stored on-chain — they exist only in transaction logs."""),
        language="ts",
    ),
]

# --- Additional Security Templates ---
SECURITY_TEMPLATES += [
    QATemplate(
        questions=[
            "How to implement access control in an Anchor program?",
            "How to restrict instructions to admin only?",
            "How to create role-based permissions in Solana?",
        ],
        answer=textwrap.dedent("""\
            Access control is essential for protecting sensitive operations. In Anchor, use a combination of signer checks, `has_one` constraints, and custom authorization logic.

            ```rust
            use anchor_lang::prelude::*;

            declare_id!("Access11111111111111111111111111111111111111");

            #[program]
            pub mod access_control {
                use super::*;

                pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
                    let config = &mut ctx.accounts.config;
                    config.admin = ctx.accounts.admin.key();
                    config.operator = ctx.accounts.admin.key(); // admin is initial operator
                    config.paused = false;
                    config.bump = ctx.bumps.config;
                    Ok(())
                }

                // Only admin can call this
                pub fn set_operator(
                    ctx: Context<AdminOnly>,
                    new_operator: Pubkey,
                ) -> Result<()> {
                    ctx.accounts.config.operator = new_operator;
                    Ok(())
                }

                // Only admin or operator can call this
                pub fn update_settings(
                    ctx: Context<OperatorOrAdmin>,
                    new_value: u64,
                ) -> Result<()> {
                    require!(!ctx.accounts.config.paused, ErrorCode::Paused);
                    // ... update logic
                    Ok(())
                }

                // Emergency pause — admin only
                pub fn pause(ctx: Context<AdminOnly>) -> Result<()> {
                    ctx.accounts.config.paused = true;
                    Ok(())
                }
            }

            #[derive(Accounts)]
            pub struct Initialize<'info> {
                #[account(
                    init,
                    payer = admin,
                    space = 8 + Config::INIT_SPACE,
                    seeds = [b"config"],
                    bump,
                )]
                pub config: Account<'info, Config>,
                #[account(mut)]
                pub admin: Signer<'info>,
                pub system_program: Program<'info, System>,
            }

            #[derive(Accounts)]
            pub struct AdminOnly<'info> {
                #[account(
                    mut,
                    seeds = [b"config"],
                    bump = config.bump,
                    has_one = admin, // enforces config.admin == admin.key()
                )]
                pub config: Account<'info, Config>,
                pub admin: Signer<'info>,
            }

            #[derive(Accounts)]
            pub struct OperatorOrAdmin<'info> {
                #[account(
                    mut,
                    seeds = [b"config"],
                    bump = config.bump,
                    // Custom constraint: caller must be admin OR operator
                    constraint = (
                        config.admin == caller.key() ||
                        config.operator == caller.key()
                    ) @ ErrorCode::Unauthorized,
                )]
                pub config: Account<'info, Config>,
                pub caller: Signer<'info>,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct Config {
                pub admin: Pubkey,
                pub operator: Pubkey,
                pub paused: bool,
                pub bump: u8,
            }

            #[error_code]
            pub enum ErrorCode {
                #[msg("Unauthorized: caller is not admin or operator")]
                Unauthorized,
                #[msg("Program is paused")]
                Paused,
            }
            ```

            Patterns:
            - **Single admin**: use `has_one = admin` with a `Signer` check.
            - **Multi-role**: store multiple authority pubkeys, use `constraint` with OR logic.
            - **Timelock**: store a pending admin change with a delay before it takes effect.
            - **Multisig**: integrate with Squads Protocol for multi-party approval.
            - **Pausable**: add a `paused` flag and check it in every sensitive instruction."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How to validate PDA seeds in Anchor?",
            "How do seed constraints work in Anchor?",
            "How to ensure a PDA is derived from the correct seeds?",
        ],
        answer=textwrap.dedent("""\
            Anchor's `seeds` constraint verifies that a PDA is derived from the expected seeds and program ID. This is critical for preventing PDA substitution attacks.

            ```rust
            use anchor_lang::prelude::*;

            #[derive(Accounts)]
            #[instruction(pool_id: u64)]
            pub struct VerifiedPDA<'info> {
                // Basic PDA verification
                #[account(
                    seeds = [b"config"],
                    bump = config.bump,
                )]
                pub config: Account<'info, Config>,

                // PDA with dynamic seeds from instruction args
                #[account(
                    seeds = [
                        b"pool",
                        &pool_id.to_le_bytes(),
                    ],
                    bump = pool.bump,
                )]
                pub pool: Account<'info, Pool>,

                // PDA with seeds from other accounts
                #[account(
                    seeds = [
                        b"user_position",
                        pool.key().as_ref(),
                        user.key().as_ref(),
                    ],
                    bump = user_position.bump,
                )]
                pub user_position: Account<'info, UserPosition>,

                // PDA for a token vault (cross-program)
                #[account(
                    seeds = [b"vault", pool.key().as_ref()],
                    bump,
                    token::mint = pool_mint,
                    token::authority = pool,
                )]
                pub pool_vault: Account<'info, TokenAccount>,

                pub pool_mint: Account<'info, Mint>,
                pub user: Signer<'info>,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct Config { pub bump: u8 }

            #[account]
            #[derive(InitSpace)]
            pub struct Pool {
                pub id: u64,
                pub bump: u8,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct UserPosition {
                pub pool: Pubkey,
                pub user: Pubkey,
                pub bump: u8,
            }

            use anchor_spl::token::{TokenAccount, Mint};
            ```

            Rules:
            - Always store the bump in the account and reference it with `bump = account.bump`.
            - Using `bump` without `= value` recomputes it (costs ~1500 CU). Storing it saves compute.
            - Seeds in `#[instruction()]` must match the instruction argument order.
            - The `seeds` constraint automatically verifies `Pubkey::create_program_address` matches."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How to implement a secure initialization pattern in Anchor?",
            "How to prevent double initialization attacks?",
            "What's the safe way to initialize accounts in Anchor?",
        ],
        answer=textwrap.dedent("""\
            Double initialization is a vulnerability where an attacker re-initializes an account to reset its state. Anchor's `init` constraint prevents this by checking the account discriminator.

            ```rust
            use anchor_lang::prelude::*;

            #[program]
            pub mod secure_init {
                use super::*;

                // SAFE: Anchor's `init` checks discriminator is zero (uninitialized)
                pub fn initialize(ctx: Context<Initialize>, value: u64) -> Result<()> {
                    let state = &mut ctx.accounts.state;
                    state.authority = ctx.accounts.authority.key();
                    state.value = value;
                    state.is_initialized = true;
                    state.bump = ctx.bumps.state;
                    Ok(())
                }

                // For cases where re-initialization should be allowed:
                pub fn initialize_or_update(
                    ctx: Context<InitOrUpdate>,
                    value: u64,
                ) -> Result<()> {
                    let state = &mut ctx.accounts.state;
                    // init_if_needed creates on first call, loads on subsequent calls
                    if state.is_initialized {
                        // Update path — verify authority
                        require!(
                            state.authority == ctx.accounts.authority.key(),
                            ErrorCode::Unauthorized
                        );
                    } else {
                        // First init path
                        state.authority = ctx.accounts.authority.key();
                        state.is_initialized = true;
                        state.bump = ctx.bumps.state;
                    }
                    state.value = value;
                    Ok(())
                }
            }

            #[derive(Accounts)]
            pub struct Initialize<'info> {
                #[account(
                    init,  // FAILS if account already exists (discriminator set)
                    payer = authority,
                    space = 8 + State::INIT_SPACE,
                    seeds = [b"state"],
                    bump,
                )]
                pub state: Account<'info, State>,
                #[account(mut)]
                pub authority: Signer<'info>,
                pub system_program: Program<'info, System>,
            }

            #[derive(Accounts)]
            pub struct InitOrUpdate<'info> {
                #[account(
                    init_if_needed,  // Creates if not exists, loads if exists
                    payer = authority,
                    space = 8 + State::INIT_SPACE,
                    seeds = [b"state"],
                    bump,
                )]
                pub state: Account<'info, State>,
                #[account(mut)]
                pub authority: Signer<'info>,
                pub system_program: Program<'info, System>,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct State {
                pub authority: Pubkey,
                pub value: u64,
                pub is_initialized: bool,
                pub bump: u8,
            }

            #[error_code]
            pub enum ErrorCode {
                #[msg("Unauthorized")]
                Unauthorized,
            }
            ```

            Security notes:
            - `init` + PDA seeds is the safest pattern — the account can only be created once.
            - `init_if_needed` requires `feature = "init-if-needed"` in Anchor.toml and MUST include authority checks for the update path.
            - Never use raw `SystemProgram::create_account` without checking if the account already has data.
            - The Anchor discriminator (8 bytes) acts as an initialization flag — `init` fails if it's already set."""),
        language="rust",
    ),
]

# --- Additional DeFi Templates ---
DEFI_TEMPLATES += [
    QATemplate(
        questions=[
            "How to implement flash loans on Solana?",
            "How do flash loans work on Solana?",
            "How to build a flash loan program?",
        ],
        answer=textwrap.dedent("""\
            Flash loans let users borrow tokens within a single transaction and repay them before the transaction ends. On Solana, this is enforced by checking the loan is repaid at the end of the instruction.

            ```rust
            use anchor_lang::prelude::*;
            use anchor_spl::token::{self, Token, TokenAccount, Transfer};

            declare_id!("Flash11111111111111111111111111111111111111");

            #[program]
            pub mod flash_loan {
                use super::*;

                pub fn flash_borrow(
                    ctx: Context<FlashBorrow>,
                    amount: u64,
                ) -> Result<()> {
                    let pool = &mut ctx.accounts.pool;
                    require!(amount <= pool.available_liquidity, ErrorCode::InsufficientLiquidity);

                    // Record the expected repayment
                    let fee = amount
                        .checked_mul(pool.fee_bps as u64)
                        .ok_or(ErrorCode::MathOverflow)?
                        .checked_div(10_000)
                        .ok_or(ErrorCode::MathOverflow)?
                        .max(1); // minimum 1 lamport fee

                    pool.flash_loan_outstanding = amount;
                    pool.flash_loan_fee = fee;

                    // Transfer tokens to borrower
                    let pool_key = pool.key();
                    let seeds = &[b"pool".as_ref(), pool_key.as_ref(), &[pool.bump]];
                    let signer = &[&seeds[..]];

                    token::transfer(
                        CpiContext::new_with_signer(
                            ctx.accounts.token_program.to_account_info(),
                            Transfer {
                                from: ctx.accounts.pool_vault.to_account_info(),
                                to: ctx.accounts.borrower_token.to_account_info(),
                                authority: pool.to_account_info(),
                            },
                            signer,
                        ),
                        amount,
                    )?;

                    msg!("Flash loan: {} tokens, fee: {}", amount, fee);
                    Ok(())
                }

                pub fn flash_repay(ctx: Context<FlashRepay>) -> Result<()> {
                    let pool = &mut ctx.accounts.pool;
                    require!(pool.flash_loan_outstanding > 0, ErrorCode::NoOutstandingLoan);

                    let repay_amount = pool.flash_loan_outstanding
                        .checked_add(pool.flash_loan_fee)
                        .ok_or(ErrorCode::MathOverflow)?;

                    // Transfer repayment from borrower to pool
                    token::transfer(
                        CpiContext::new(
                            ctx.accounts.token_program.to_account_info(),
                            Transfer {
                                from: ctx.accounts.borrower_token.to_account_info(),
                                to: ctx.accounts.pool_vault.to_account_info(),
                                authority: ctx.accounts.borrower.to_account_info(),
                            },
                        ),
                        repay_amount,
                    )?;

                    // Verify repayment
                    ctx.accounts.pool_vault.reload()?;
                    let expected_balance = pool.available_liquidity
                        .checked_add(pool.flash_loan_fee)
                        .ok_or(ErrorCode::MathOverflow)?;

                    require!(
                        ctx.accounts.pool_vault.amount >= expected_balance,
                        ErrorCode::InsufficientRepayment
                    );

                    // Clear flash loan state
                    pool.available_liquidity = ctx.accounts.pool_vault.amount;
                    pool.flash_loan_outstanding = 0;
                    pool.flash_loan_fee = 0;

                    msg!("Flash loan repaid: {}", repay_amount);
                    Ok(())
                }
            }

            #[derive(Accounts)]
            pub struct FlashBorrow<'info> {
                #[account(mut, seeds = [b"pool", pool.mint.as_ref()], bump = pool.bump)]
                pub pool: Account<'info, Pool>,
                #[account(mut, constraint = pool_vault.key() == pool.vault)]
                pub pool_vault: Account<'info, TokenAccount>,
                #[account(mut)]
                pub borrower_token: Account<'info, TokenAccount>,
                pub borrower: Signer<'info>,
                pub token_program: Program<'info, Token>,
            }

            #[derive(Accounts)]
            pub struct FlashRepay<'info> {
                #[account(mut, seeds = [b"pool", pool.mint.as_ref()], bump = pool.bump)]
                pub pool: Account<'info, Pool>,
                #[account(mut, constraint = pool_vault.key() == pool.vault)]
                pub pool_vault: Account<'info, TokenAccount>,
                #[account(mut)]
                pub borrower_token: Account<'info, TokenAccount>,
                pub borrower: Signer<'info>,
                pub token_program: Program<'info, Token>,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct Pool {
                pub mint: Pubkey,
                pub vault: Pubkey,
                pub available_liquidity: u64,
                pub fee_bps: u16,
                pub flash_loan_outstanding: u64,
                pub flash_loan_fee: u64,
                pub bump: u8,
            }

            #[error_code]
            pub enum ErrorCode {
                #[msg("Insufficient liquidity")]
                InsufficientLiquidity,
                #[msg("No outstanding loan")]
                NoOutstandingLoan,
                #[msg("Insufficient repayment")]
                InsufficientRepayment,
                #[msg("Math overflow")]
                MathOverflow,
            }
            ```

            Important:
            - Both `flash_borrow` and `flash_repay` must be in the SAME transaction.
            - The borrower can perform arbitrary operations between borrow and repay (arbitrage, liquidations, etc.).
            - Always reload the vault account after CPI to check the actual balance.
            - Flash loan fees are typically 0.05-0.3% (5-30 basis points)."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How to implement a lending pool with variable interest rates?",
            "How to calculate variable interest rates for a lending protocol?",
            "How to build a Solana lending program?",
        ],
        answer=textwrap.dedent("""\
            A lending pool uses a utilization-based interest rate model. As more of the pool is borrowed, interest rates increase to incentivize deposits and discourage borrowing.

            ```rust
            use anchor_lang::prelude::*;

            // Interest rate model: utilization-based (like Aave/Compound)
            // Rate = base_rate + utilization * slope1       (if utilization < optimal)
            // Rate = base_rate + optimal * slope1 + (util - optimal) * slope2  (if above)

            pub struct InterestRateModel {
                pub base_rate_bps: u64,      // e.g., 200 = 2%
                pub slope1_bps: u64,         // e.g., 400 = 4% (below optimal)
                pub slope2_bps: u64,         // e.g., 7500 = 75% (above optimal)
                pub optimal_utilization: u64, // e.g., 8000 = 80%
            }

            impl InterestRateModel {
                pub fn calculate_borrow_rate(&self, utilization_bps: u64) -> Result<u64> {
                    if utilization_bps <= self.optimal_utilization {
                        // Below optimal: gentle slope
                        let variable = utilization_bps
                            .checked_mul(self.slope1_bps)
                            .ok_or(error!(ErrorCode::MathOverflow))?
                            .checked_div(self.optimal_utilization)
                            .ok_or(error!(ErrorCode::MathOverflow))?;
                        self.base_rate_bps
                            .checked_add(variable)
                            .ok_or(error!(ErrorCode::MathOverflow))
                    } else {
                        // Above optimal: steep slope to discourage borrowing
                        let excess = utilization_bps
                            .checked_sub(self.optimal_utilization)
                            .ok_or(error!(ErrorCode::MathOverflow))?;
                        let remaining = 10_000u64
                            .checked_sub(self.optimal_utilization)
                            .ok_or(error!(ErrorCode::MathOverflow))?;
                        let steep_part = excess
                            .checked_mul(self.slope2_bps)
                            .ok_or(error!(ErrorCode::MathOverflow))?
                            .checked_div(remaining)
                            .ok_or(error!(ErrorCode::MathOverflow))?;
                        self.base_rate_bps
                            .checked_add(self.slope1_bps)
                            .ok_or(error!(ErrorCode::MathOverflow))?
                            .checked_add(steep_part)
                            .ok_or(error!(ErrorCode::MathOverflow))
                    }
                }

                pub fn calculate_supply_rate(
                    &self,
                    utilization_bps: u64,
                    reserve_factor_bps: u64,
                ) -> Result<u64> {
                    let borrow_rate = self.calculate_borrow_rate(utilization_bps)?;
                    // Supply rate = borrow_rate * utilization * (1 - reserve_factor)
                    let rate = (borrow_rate as u128)
                        .checked_mul(utilization_bps as u128)
                        .ok_or(error!(ErrorCode::MathOverflow))?
                        .checked_mul((10_000 - reserve_factor_bps) as u128)
                        .ok_or(error!(ErrorCode::MathOverflow))?
                        .checked_div(10_000 * 10_000)
                        .ok_or(error!(ErrorCode::MathOverflow))?;
                    Ok(rate as u64)
                }
            }

            // Calculate utilization
            pub fn calculate_utilization(
                total_deposits: u64,
                total_borrows: u64,
            ) -> Result<u64> {
                if total_deposits == 0 {
                    return Ok(0);
                }
                let util = (total_borrows as u128)
                    .checked_mul(10_000)
                    .ok_or(error!(ErrorCode::MathOverflow))?
                    .checked_div(total_deposits as u128)
                    .ok_or(error!(ErrorCode::MathOverflow))?;
                Ok(util.min(10_000) as u64) // cap at 100%
            }

            #[error_code]
            pub enum ErrorCode {
                #[msg("Math overflow")]
                MathOverflow,
            }
            ```

            Example rates with typical parameters (base=2%, slope1=4%, slope2=75%, optimal=80%):
            - 0% utilization → 2% borrow rate
            - 50% utilization → 4.5% borrow rate
            - 80% utilization → 6% borrow rate (optimal point)
            - 90% utilization → 43.5% borrow rate (steep!)
            - 100% utilization → 81% borrow rate

            This model incentivizes:
            - Below optimal: reasonable borrowing costs to attract borrowers
            - Above optimal: rapidly increasing rates to attract depositors and discourage borrowing"""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How to build an order book on Solana?",
            "How to implement a CLOB (central limit order book) on Solana?",
            "How to create a decentralized order book program?",
        ],
        answer=textwrap.dedent("""\
            Order books on Solana typically use a slab data structure (like Serum/Openbook) for efficient O(log n) insertions and O(1) best-price lookups. Here's a simplified design:

            ```rust
            use anchor_lang::prelude::*;

            declare_id!("Order11111111111111111111111111111111111111");

            #[account(zero_copy)]
            #[repr(C)]
            pub struct OrderBook {
                pub market: Pubkey,          // 32
                pub base_mint: Pubkey,       // 32
                pub quote_mint: Pubkey,      // 32
                pub bid_count: u32,          // 4
                pub ask_count: u32,          // 4
                pub next_order_id: u64,      // 8
                pub bids: [Order; 256],      // 256 * 56 = 14,336
                pub asks: [Order; 256],      // 256 * 56 = 14,336
            }

            #[zero_copy]
            #[repr(C)]
            pub struct Order {
                pub owner: Pubkey,    // 32
                pub order_id: u64,    // 8
                pub price: u64,       // 8 (in quote token smallest units per base token)
                pub quantity: u64,    // 8 (in base token smallest units)
            }

            #[program]
            pub mod orderbook {
                use super::*;

                pub fn place_order(
                    ctx: Context<PlaceOrder>,
                    side: Side,
                    price: u64,
                    quantity: u64,
                ) -> Result<()> {
                    let book = &mut ctx.accounts.order_book.load_mut()?;
                    let order_id = book.next_order_id;
                    book.next_order_id += 1;

                    let order = Order {
                        owner: ctx.accounts.user.key(),
                        order_id,
                        price,
                        quantity,
                    };

                    match side {
                        Side::Bid => {
                            require!((book.bid_count as usize) < 256, ErrorCode::BookFull);
                            // Insert sorted by price (highest first for bids)
                            let pos = find_bid_position(&book.bids, book.bid_count, price);
                            shift_right(&mut book.bids, pos as usize, book.bid_count as usize);
                            book.bids[pos as usize] = order;
                            book.bid_count += 1;
                        }
                        Side::Ask => {
                            require!((book.ask_count as usize) < 256, ErrorCode::BookFull);
                            // Insert sorted by price (lowest first for asks)
                            let pos = find_ask_position(&book.asks, book.ask_count, price);
                            shift_right(&mut book.asks, pos as usize, book.ask_count as usize);
                            book.asks[pos as usize] = order;
                            book.ask_count += 1;
                        }
                    }

                    msg!("Placed {} order: price={}, qty={}, id={}",
                        if matches!(side, Side::Bid) { "bid" } else { "ask" },
                        price, quantity, order_id);
                    Ok(())
                }
            }

            fn find_bid_position(bids: &[Order; 256], count: u32, price: u64) -> u32 {
                for i in 0..count {
                    if price > bids[i as usize].price {
                        return i;
                    }
                }
                count
            }

            fn find_ask_position(asks: &[Order; 256], count: u32, price: u64) -> u32 {
                for i in 0..count {
                    if price < asks[i as usize].price {
                        return i;
                    }
                }
                count
            }

            fn shift_right(orders: &mut [Order; 256], pos: usize, count: usize) {
                if count > 0 {
                    for i in (pos..count).rev() {
                        orders[i + 1] = orders[i];
                    }
                }
            }

            #[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy)]
            pub enum Side {
                Bid,
                Ask,
            }

            #[derive(Accounts)]
            pub struct PlaceOrder<'info> {
                #[account(mut)]
                pub order_book: AccountLoader<'info, OrderBook>,
                pub user: Signer<'info>,
            }

            #[error_code]
            pub enum ErrorCode {
                #[msg("Order book is full")]
                BookFull,
            }
            ```

            Production considerations:
            - Use a proper slab/red-black tree (like OpenBook) for O(log n) operations.
            - Implement matching engine that crosses orders on placement.
            - Use `zero_copy` for the order book — it can be hundreds of KB.
            - Consider cranking (off-chain matching) for high throughput.
            - OpenBook v2 is the standard reference implementation for Solana order books."""),
        language="rust",
    ),
]

# --- Additional Architecture Templates ---
ARCHITECTURE_TEMPLATES += [
    QATemplate(
        questions=[
            "How to handle cross-program invocation (CPI) in Anchor?",
            "How to call another Solana program from Anchor?",
            "How to do CPI in an Anchor program?",
        ],
        answer=textwrap.dedent("""\
            Cross-Program Invocation (CPI) lets your program call instructions on other programs (e.g., Token Program, System Program, or your own programs).

            ```rust
            use anchor_lang::prelude::*;
            use anchor_spl::token::{self, Token, TokenAccount, Mint, MintTo, Transfer};

            declare_id!("CPI111111111111111111111111111111111111111");

            #[program]
            pub mod cpi_example {
                use super::*;

                // CPI to SPL Token Program — mint tokens
                pub fn mint_tokens(ctx: Context<MintTokens>, amount: u64) -> Result<()> {
                    // PDA signs the CPI call
                    let authority_key = ctx.accounts.authority.key();
                    let seeds = &[
                        b"mint_auth".as_ref(),
                        authority_key.as_ref(),
                        &[ctx.bumps.mint_authority],
                    ];
                    let signer = &[&seeds[..]];

                    token::mint_to(
                        CpiContext::new_with_signer(
                            ctx.accounts.token_program.to_account_info(),
                            MintTo {
                                mint: ctx.accounts.mint.to_account_info(),
                                to: ctx.accounts.destination.to_account_info(),
                                authority: ctx.accounts.mint_authority.to_account_info(),
                            },
                            signer,
                        ),
                        amount,
                    )?;

                    msg!("Minted {} tokens via CPI", amount);
                    Ok(())
                }

                // CPI to another Anchor program
                pub fn call_other_program(ctx: Context<CallOther>) -> Result<()> {
                    // Using CPI to call another Anchor program
                    let cpi_program = ctx.accounts.other_program.to_account_info();
                    let cpi_accounts = other_program::cpi::accounts::DoSomething {
                        state: ctx.accounts.other_state.to_account_info(),
                        user: ctx.accounts.user.to_account_info(),
                    };
                    let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
                    other_program::cpi::do_something(cpi_ctx, 42)?;

                    Ok(())
                }
            }

            #[derive(Accounts)]
            pub struct MintTokens<'info> {
                #[account(mut)]
                pub mint: Account<'info, Mint>,
                #[account(mut)]
                pub destination: Account<'info, TokenAccount>,
                /// The PDA that has mint authority
                #[account(
                    seeds = [b"mint_auth", authority.key().as_ref()],
                    bump,
                )]
                /// CHECK: PDA used as mint authority
                pub mint_authority: AccountInfo<'info>,
                pub authority: Signer<'info>,
                pub token_program: Program<'info, Token>,
            }

            #[derive(Accounts)]
            pub struct CallOther<'info> {
                /// CHECK: validated by the other program
                #[account(mut)]
                pub other_state: AccountInfo<'info>,
                pub user: Signer<'info>,
                /// CHECK: validated as program
                pub other_program: AccountInfo<'info>,
            }
            ```

            CPI rules:
            - Max CPI depth: 4 levels (A → B → C → D → E would fail).
            - Instruction data size limit: 1,280 bytes for CPI calls.
            - PDA signing: use `CpiContext::new_with_signer` with the PDA seeds.
            - For Anchor-to-Anchor CPI, use the generated `cpi` module from the target program.
            - After a CPI that modifies an account, call `.reload()?` before reading updated data."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How to design accounts that scale to millions of users?",
            "How to handle state management for large-scale Solana programs?",
            "What are the patterns for scalable Solana program design?",
        ],
        answer=textwrap.dedent("""\
            Scalable Solana programs use per-user PDAs, avoid global mutable state, and leverage account compression when possible.

            ```rust
            use anchor_lang::prelude::*;

            // PATTERN 1: Per-user PDAs (most common, infinitely scalable)
            // Each user gets their own account derived from their pubkey
            #[account]
            #[derive(InitSpace)]
            pub struct UserAccount {
                pub user: Pubkey,
                pub balance: u64,
                pub last_action: i64,
                pub bump: u8,
            }

            #[derive(Accounts)]
            pub struct CreateUser<'info> {
                #[account(
                    init,
                    payer = user,
                    space = 8 + UserAccount::INIT_SPACE,
                    seeds = [b"user", user.key().as_ref()],
                    bump,
                )]
                pub user_account: Account<'info, UserAccount>,
                #[account(mut)]
                pub user: Signer<'info>,
                pub system_program: Program<'info, System>,
            }

            // PATTERN 2: Paginated lists using linked accounts
            // For enumerable collections (e.g., all positions in a pool)
            #[account]
            #[derive(InitSpace)]
            pub struct PositionPage {
                pub pool: Pubkey,
                pub page_index: u32,
                pub count: u32,
                pub positions: [PositionEntry; 32], // 32 entries per page
                pub next_page: Option<Pubkey>,
                pub bump: u8,
            }

            #[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, Default, InitSpace)]
            pub struct PositionEntry {
                pub owner: Pubkey,
                pub amount: u64,
                pub active: bool,
            }

            // PATTERN 3: Append-only logs using zero-copy large accounts
            #[account(zero_copy)]
            #[repr(C)]
            pub struct EventLog {
                pub authority: Pubkey,
                pub head: u32,         // next write position
                pub count: u32,        // total events
                pub events: [LogEntry; 1024],
            }

            #[zero_copy]
            #[repr(C)]
            pub struct LogEntry {
                pub timestamp: i64,
                pub event_type: u8,
                pub data: [u8; 31],
            }

            // PATTERN 4: Global state with minimal writes
            // Only store aggregates that are truly global
            #[account]
            #[derive(InitSpace)]
            pub struct GlobalStats {
                pub total_users: u64,      // increment on user creation
                pub total_volume: u128,    // updated asynchronously via crank
                pub last_updated: i64,
                pub bump: u8,
            }
            ```

            Design principles:
            1. **Per-user PDAs are cheap**: creating 1M PDAs costs ~2000 SOL in rent, but each user pays their own.
            2. **Avoid hot accounts**: if every transaction writes the same account, you get ~400 TPS max. Split state per user.
            3. **Use events instead of storage**: emit events for historical data, use indexers (Helius, Yellowstone) to query.
            4. **Lazy computation**: don't update global stats on every transaction — use a crank or periodic update.
            5. **Account compression**: for read-mostly data (e.g., NFTs), use Merkle trees to store millions of entries for pennies."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "How to handle account size limits and reallocation in Anchor?",
            "How to resize an account in Anchor?",
            "How to increase the size of an existing Solana account?",
        ],
        answer=textwrap.dedent("""\
            Anchor's `realloc` constraint lets you increase or decrease account size dynamically. This is useful for variable-length data like vectors or strings.

            ```rust
            use anchor_lang::prelude::*;

            #[program]
            pub mod resizable {
                use super::*;

                pub fn initialize(ctx: Context<Initialize>, name: String) -> Result<()> {
                    let profile = &mut ctx.accounts.profile;
                    profile.authority = ctx.accounts.authority.key();
                    profile.name = name;
                    profile.items = vec![];
                    profile.bump = ctx.bumps.profile;
                    Ok(())
                }

                pub fn add_item(ctx: Context<AddItem>, item: String) -> Result<()> {
                    let profile = &mut ctx.accounts.profile;
                    require!(
                        profile.authority == ctx.accounts.authority.key(),
                        ErrorCode::Unauthorized
                    );
                    profile.items.push(item);
                    Ok(())
                }
            }

            #[derive(Accounts)]
            #[instruction(name: String)]
            pub struct Initialize<'info> {
                #[account(
                    init,
                    payer = authority,
                    space = Profile::space(&name, 0),
                    seeds = [b"profile", authority.key().as_ref()],
                    bump,
                )]
                pub profile: Account<'info, Profile>,
                #[account(mut)]
                pub authority: Signer<'info>,
                pub system_program: Program<'info, System>,
            }

            #[derive(Accounts)]
            #[instruction(item: String)]
            pub struct AddItem<'info> {
                #[account(
                    mut,
                    // Realloc to fit the new item
                    realloc = Profile::space(
                        &profile.name,
                        profile.items.len() + 1,
                    ) + 4 + item.len(), // extra space for the new string
                    realloc::payer = authority,
                    realloc::zero = false, // don't zero new bytes
                    seeds = [b"profile", authority.key().as_ref()],
                    bump = profile.bump,
                    has_one = authority,
                )]
                pub profile: Account<'info, Profile>,
                #[account(mut)]
                pub authority: Signer<'info>,
                pub system_program: Program<'info, System>,
            }

            #[account]
            pub struct Profile {
                pub authority: Pubkey,   // 32
                pub name: String,        // 4 + len
                pub items: Vec<String>,  // 4 + sum(4 + len for each item)
                pub bump: u8,            // 1
            }

            impl Profile {
                pub fn space(name: &str, item_count: usize) -> usize {
                    8                        // discriminator
                    + 32                     // authority
                    + 4 + name.len()         // name (String = 4-byte len + data)
                    + 4 + (item_count * 50)  // items (estimate 50 bytes per item)
                    + 1                      // bump
                }
            }

            #[error_code]
            pub enum ErrorCode {
                #[msg("Unauthorized")]
                Unauthorized,
            }
            ```

            Key points:
            - `realloc` transfers SOL to/from the payer automatically for rent changes.
            - `realloc::zero = false` is faster (skips zeroing new bytes). Use `true` for security-sensitive data.
            - Maximum account size is 10MB.
            - Reallocation costs ~10,000 CU.
            - For frequently resized accounts, allocate extra space upfront to minimize reallocations."""),
        language="rust",
    ),
]

# --- Additional Testing Templates ---
TESTING_TEMPLATES += [
    QATemplate(
        questions=[
            "How to test CPI calls in Anchor?",
            "How to test cross-program invocations?",
            "How to verify CPI behavior in Anchor tests?",
        ],
        answer=textwrap.dedent("""\
            Testing CPIs requires deploying both programs and verifying the state changes from the called program. Here's how to test SPL Token CPIs and custom program CPIs.

            ```typescript
            import * as anchor from "@coral-xyz/anchor";
            import { Program, BN } from "@coral-xyz/anchor";
            import { MyProgram } from "../target/types/my_program";
            import {
              Keypair,
              PublicKey,
              SystemProgram,
              LAMPORTS_PER_SOL,
            } from "@solana/web3.js";
            import {
              createMint,
              getAssociatedTokenAddress,
              createAssociatedTokenAccount,
              mintTo,
              getAccount,
            } from "@solana/spl-token";
            import { expect } from "chai";

            describe("CPI tests", () => {
              const provider = anchor.AnchorProvider.env();
              anchor.setProvider(provider);
              const program = anchor.workspace.MyProgram as Program<MyProgram>;
              const authority = provider.wallet as anchor.Wallet;

              let mint: PublicKey;
              let userAta: PublicKey;
              let vaultAta: PublicKey;
              let vaultPda: PublicKey;

              before(async () => {
                // Create test mint
                mint = await createMint(
                  provider.connection, authority.payer,
                  authority.publicKey, null, 9
                );

                // Derive vault PDA
                [vaultPda] = PublicKey.findProgramAddressSync(
                  [Buffer.from("vault"), mint.toBuffer()],
                  program.programId
                );

                // Create token accounts
                userAta = await createAssociatedTokenAccount(
                  provider.connection, authority.payer, mint, authority.publicKey
                );
                vaultAta = await createAssociatedTokenAccount(
                  provider.connection, authority.payer, mint, vaultPda, true
                );

                // Mint test tokens
                await mintTo(
                  provider.connection, authority.payer, mint,
                  userAta, authority.publicKey, 10_000_000_000
                );
              });

              it("deposits tokens via CPI to Token Program", async () => {
                const depositAmount = new BN(1_000_000_000);

                // Check balances before
                const userBefore = await getAccount(provider.connection, userAta);
                const vaultBefore = await getAccount(provider.connection, vaultAta);

                await program.methods
                  .deposit(depositAmount)
                  .accountsStrict({
                    vault: vaultPda,
                    userTokenAccount: userAta,
                    vaultTokenAccount: vaultAta,
                    user: authority.publicKey,
                    tokenProgram: anchor.utils.token.TOKEN_PROGRAM_ID,
                  })
                  .rpc();

                // Verify CPI effects
                const userAfter = await getAccount(provider.connection, userAta);
                const vaultAfter = await getAccount(provider.connection, vaultAta);

                expect(Number(userAfter.amount)).to.equal(
                  Number(userBefore.amount) - depositAmount.toNumber()
                );
                expect(Number(vaultAfter.amount)).to.equal(
                  Number(vaultBefore.amount) + depositAmount.toNumber()
                );
              });

              it("PDA signs withdrawal CPI correctly", async () => {
                const withdrawAmount = new BN(500_000_000);

                await program.methods
                  .withdraw(withdrawAmount)
                  .accountsStrict({
                    vault: vaultPda,
                    userTokenAccount: userAta,
                    vaultTokenAccount: vaultAta,
                    authority: authority.publicKey,
                    tokenProgram: anchor.utils.token.TOKEN_PROGRAM_ID,
                  })
                  .rpc();

                const vaultAfter = await getAccount(provider.connection, vaultAta);
                expect(Number(vaultAfter.amount)).to.equal(500_000_000);
              });
            });
            ```

            Testing tips:
            - Always check both source and destination balances to verify transfers.
            - Use `getAccount` from `@solana/spl-token` for typed token account data.
            - For PDA-signed CPIs, the test doesn't need to pass the PDA as a signer — the program handles it.
            - To test CPI failures, wrap in try/catch and verify the error code."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to test with different signers in Anchor?",
            "How to test authorization checks with multiple users?",
            "How to simulate different wallets in Anchor tests?",
        ],
        answer=textwrap.dedent("""\
            Testing with multiple signers is essential for verifying access control. Create different keypairs for each role and test both authorized and unauthorized access.

            ```typescript
            import * as anchor from "@coral-xyz/anchor";
            import { Program, BN } from "@coral-xyz/anchor";
            import { MyProgram } from "../target/types/my_program";
            import { Keypair, PublicKey, SystemProgram, LAMPORTS_PER_SOL } from "@solana/web3.js";
            import { expect } from "chai";

            describe("authorization tests", () => {
              const provider = anchor.AnchorProvider.env();
              anchor.setProvider(provider);
              const program = anchor.workspace.MyProgram as Program<MyProgram>;

              const admin = (provider.wallet as anchor.Wallet).payer;
              const operator = Keypair.generate();
              const user = Keypair.generate();
              const attacker = Keypair.generate();

              before(async () => {
                // Fund all test accounts
                for (const kp of [operator, user, attacker]) {
                  const sig = await provider.connection.requestAirdrop(
                    kp.publicKey,
                    2 * LAMPORTS_PER_SOL
                  );
                  await provider.connection.confirmTransaction(sig);
                }
              });

              it("admin can initialize", async () => {
                const [configPda] = PublicKey.findProgramAddressSync(
                  [Buffer.from("config")],
                  program.programId
                );

                await program.methods
                  .initialize()
                  .accountsStrict({
                    config: configPda,
                    admin: admin.publicKey,
                    systemProgram: SystemProgram.programId,
                  })
                  .signers([admin])
                  .rpc();

                const config = await program.account.config.fetch(configPda);
                expect(config.admin.toBase58()).to.equal(admin.publicKey.toBase58());
              });

              it("attacker cannot call admin-only function", async () => {
                const [configPda] = PublicKey.findProgramAddressSync(
                  [Buffer.from("config")],
                  program.programId
                );

                try {
                  await program.methods
                    .adminOnlyAction(new BN(999))
                    .accountsStrict({
                      config: configPda,
                      admin: attacker.publicKey, // wrong signer!
                    })
                    .signers([attacker])
                    .rpc();
                  expect.fail("Should have thrown ConstraintHasOne");
                } catch (err: any) {
                  // Anchor error 2003 = ConstraintHasOne
                  expect(err.error.errorCode.code).to.equal("ConstraintHasOne");
                }
              });

              it("operator can perform operator actions", async () => {
                // First set operator (as admin)
                const [configPda] = PublicKey.findProgramAddressSync(
                  [Buffer.from("config")],
                  program.programId
                );

                await program.methods
                  .setOperator(operator.publicKey)
                  .accountsStrict({
                    config: configPda,
                    admin: admin.publicKey,
                  })
                  .signers([admin])
                  .rpc();

                // Now operator can call operator-level functions
                await program.methods
                  .operatorAction()
                  .accountsStrict({
                    config: configPda,
                    caller: operator.publicKey,
                  })
                  .signers([operator])
                  .rpc();
              });
            });
            ```

            Patterns:
            - Create a new `Keypair` for each role (admin, operator, user, attacker).
            - Fund them with `requestAirdrop` before tests.
            - Pass the keypair in `.signers([...])` when they need to sign.
            - Test both the happy path (authorized) and error path (unauthorized).
            - Check specific error codes to ensure the right check failed."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to write Rust unit tests for Solana programs?",
            "How to test Solana program logic with solana-program-test?",
            "How to use ProgramTest for Solana program testing?",
        ],
        answer=textwrap.dedent("""\
            `solana-program-test` provides a lightweight BPF runtime for testing programs in Rust. It's faster than TypeScript tests and runs directly in `cargo test`.

            ```rust
            #[cfg(test)]
            mod tests {
                use super::*;
                use solana_program_test::*;
                use solana_sdk::{
                    signature::{Keypair, Signer},
                    transaction::Transaction,
                    system_instruction,
                };

                fn program_test() -> ProgramTest {
                    ProgramTest::new(
                        "my_program",        // program name (matches Cargo.toml)
                        crate::ID,           // program ID
                        processor!(crate::entry), // entrypoint
                    )
                }

                #[tokio::test]
                async fn test_initialize() {
                    let mut context = program_test().start_with_context().await;

                    // Create the account to initialize
                    let account = Keypair::new();
                    let rent = context.banks_client
                        .get_rent()
                        .await
                        .unwrap();
                    let space = 8 + 32 + 8 + 1; // discriminator + pubkey + u64 + u8

                    // Build and send transaction
                    let tx = Transaction::new_signed_with_payer(
                        &[
                            system_instruction::create_account(
                                &context.payer.pubkey(),
                                &account.pubkey(),
                                rent.minimum_balance(space),
                                space as u64,
                                &crate::ID,
                            ),
                            // Your program's initialize instruction
                            crate::instruction::initialize(
                                &crate::ID,
                                &account.pubkey(),
                                &context.payer.pubkey(),
                            ),
                        ],
                        Some(&context.payer.pubkey()),
                        &[&context.payer, &account],
                        context.last_blockhash,
                    );

                    context.banks_client
                        .process_transaction(tx)
                        .await
                        .unwrap();

                    // Verify account state
                    let account_data = context.banks_client
                        .get_account(account.pubkey())
                        .await
                        .unwrap()
                        .unwrap();

                    assert_eq!(account_data.owner, crate::ID);
                    assert_eq!(account_data.data.len(), space);
                }

                #[tokio::test]
                async fn test_unauthorized_access() {
                    let mut context = program_test().start_with_context().await;
                    let attacker = Keypair::new();

                    // ... setup ...

                    let tx = Transaction::new_signed_with_payer(
                        &[/* instruction with attacker as signer */],
                        Some(&attacker.pubkey()),
                        &[&attacker],
                        context.last_blockhash,
                    );

                    let result = context.banks_client
                        .process_transaction(tx)
                        .await;

                    // Should fail
                    assert!(result.is_err());
                }

                #[tokio::test]
                async fn test_with_time_warp() {
                    let mut context = program_test().start_with_context().await;

                    // Warp time forward
                    let mut clock: Clock = context.banks_client
                        .get_sysvar()
                        .await
                        .unwrap();
                    clock.unix_timestamp += 86400; // +1 day
                    context.set_sysvar(&clock);

                    // Now instructions will see the advanced time
                }
            }
            ```

            Advantages of Rust tests:
            - Run with `cargo test` — no Node.js or TypeScript needed.
            - Faster than TypeScript tests (no serialization overhead).
            - Direct access to program state for assertions.
            - Can test internal functions, not just instructions.
            - Integrates with standard Rust test tooling (coverage, etc.)."""),
        language="rust",
    ),
]

# --- Additional Concepts Templates ---
CONCEPTS_TEMPLATES += [
    QATemplate(
        questions=[
            "How does the Solana runtime execute transactions?",
            "What happens when a Solana transaction is submitted?",
            "What is the lifecycle of a Solana transaction?",
        ],
        answer=textwrap.dedent("""\
            When you submit a transaction to Solana, it goes through several stages before being committed to the ledger. Understanding this pipeline helps debug issues and optimize performance.

            **Transaction lifecycle:**

            1. **Client submits** → RPC node receives the transaction
            2. **RPC forwards** → Transaction is sent to the current leader validator via QUIC/UDP
            3. **Leader receives** → Transaction enters the leader's transaction processing unit (TPU)
            4. **Signature verification** → Ed25519 signatures are verified in parallel on GPU
            5. **Banking stage** → Transactions are sorted by priority fee and executed:
               a. Lock accounts (read/write sets from the transaction)
               b. Load all referenced accounts from memory
               c. Execute each instruction sequentially
               d. Record results and unlock accounts
            6. **Proof of History** → Transaction is stamped with PoH sequence number
            7. **Propagation** → Block is sent to other validators
            8. **Voting** → Validators vote to confirm the block
            9. **Finalization** → After 31+ confirmations, block is finalized

            **Commitment levels:**
            ```
            processed  → Transaction executed by leader (may be rolled back)
                         Latency: ~400ms
            confirmed  → Voted on by 2/3+ of stake (very unlikely to roll back)
                         Latency: ~2-3 seconds
            finalized  → 31+ blocks deep (irreversible)
                         Latency: ~12-15 seconds
            ```

            **Key properties:**
            - Instructions within a transaction execute sequentially (not parallel).
            - Transactions across different account sets execute in parallel (Sealevel).
            - If any instruction fails, the entire transaction rolls back atomically.
            - The base fee is 5000 lamports per signature (0.000005 SOL).
            - Priority fee = compute units consumed × micro-lamport price.
            - Slot time is ~400ms; epoch is ~2-3 days.

            **Why transactions fail:**
            - Blockhash expired (>150 slots old)
            - Insufficient funds for fee/rent
            - Program error (custom error, constraint violation)
            - Account locked by another transaction (retry usually fixes this)
            - Compute budget exceeded"""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How does the BPF loader work in Solana?",
            "How are Solana programs deployed?",
            "What is the BPF virtual machine in Solana?",
        ],
        answer=textwrap.dedent("""\
            Solana programs run on a modified Berkeley Packet Filter (BPF) virtual machine called SBF (Solana BPF). Programs are compiled to BPF bytecode and deployed to the chain via the BPF Loader.

            **Deployment process:**
            ```bash
            # 1. Build the program (produces .so file)
            anchor build
            # or: cargo build-sbf

            # 2. Deploy to the chain
            solana program deploy target/deploy/my_program.so

            # 3. The BPF Loader:
            #    a. Splits the .so into 1KB chunks
            #    b. Writes chunks to a buffer account (multiple txs)
            #    c. Finalizes the deployment
            #    d. Creates a program account pointing to the buffer
            ```

            **Program account structure:**
            ```
            Program Account (executable = true)
            ├── owner: BPFLoaderUpgradeable (BPFLoaderUpgradeab1e...)
            ├── data: [pointer to ProgramData account]
            └── executable: true

            ProgramData Account
            ├── owner: BPFLoaderUpgradeable
            ├── data: [upgrade_authority (32B) | slot_deployed (8B) | ELF bytecode...]
            └── executable: false
            ```

            **Upgradeable vs Immutable:**
            ```bash
            # Deploy as upgradeable (default)
            solana program deploy my_program.so

            # Make immutable (no more upgrades)
            solana program set-upgrade-authority <PROGRAM_ID> --final

            # Upgrade an existing program
            solana program deploy my_program.so --program-id <EXISTING_PROGRAM_ID>
            ```

            **BPF/SBF details:**
            - Register-based VM with 11 registers (r0-r10)
            - 64-bit architecture
            - Stack: 4KB per frame, 64 frames max
            - Heap: 32KB default, 256KB max
            - No floating point — integer arithmetic only
            - Syscalls: SHA-256, Ed25519 verify, logging, CPI, etc.
            - Programs are position-independent ELF binaries

            **Key points:**
            - Programs are stateless — they don't have storage, only code.
            - The upgrade authority can upgrade program code at any time (unless set to immutable).
            - The same program binary can be deployed to multiple addresses.
            - Programs can be closed to reclaim rent (~0.5-5 SOL depending on binary size)."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "What are the different types of accounts on Solana?",
            "What is the difference between system accounts and program accounts?",
            "What account types exist on Solana?",
        ],
        answer=textwrap.dedent("""\
            Solana has several types of accounts, distinguished by their owner program, data content, and executable flag.

            **Account taxonomy:**

            ```
            ┌─────────────────────────────────────────────────────┐
            │ Wallet / System Accounts                            │
            │ Owner: System Program (1111...1111)                 │
            │ Data: empty (0 bytes)                               │
            │ Purpose: hold SOL balance                           │
            ├─────────────────────────────────────────────────────┤
            │ Program Accounts                                    │
            │ Owner: BPF Loader Upgradeable                       │
            │ Data: pointer to ProgramData                        │
            │ Executable: true                                    │
            │ Purpose: deployed program code                      │
            ├─────────────────────────────────────────────────────┤
            │ Token Mint Accounts                                 │
            │ Owner: Token Program (TokenkegQ...VQ5DA)            │
            │ Data: 82 bytes (mint authority, supply, decimals)   │
            │ Purpose: define a token type                        │
            ├─────────────────────────────────────────────────────┤
            │ Token Accounts (ATA)                                │
            │ Owner: Token Program                                │
            │ Data: 165 bytes (mint, owner, balance, etc.)        │
            │ Purpose: hold token balance for one mint + one owner│
            ├─────────────────────────────────────────────────────┤
            │ Program Data Accounts (PDA)                         │
            │ Owner: Your Program                                 │
            │ Data: discriminator + custom fields                 │
            │ Purpose: store program state                        │
            ├─────────────────────────────────────────────────────┤
            │ Metadata Accounts                                   │
            │ Owner: Metaplex Token Metadata Program              │
            │ Data: name, symbol, URI, creators, etc.             │
            │ Purpose: NFT/token metadata                         │
            └─────────────────────────────────────────────────────┘
            ```

            ```typescript
            import { Connection, PublicKey, LAMPORTS_PER_SOL } from "@solana/web3.js";
            import { TOKEN_PROGRAM_ID } from "@solana/spl-token";

            async function identifyAccountType(
              connection: Connection,
              address: PublicKey
            ): Promise<string> {
              const info = await connection.getAccountInfo(address);
              if (!info) return "does not exist";
              if (info.executable) return "program";

              const owner = info.owner.toBase58();
              switch (owner) {
                case "11111111111111111111111111111111":
                  return "system account (wallet)";
                case TOKEN_PROGRAM_ID.toBase58():
                  return info.data.length === 82 ? "token mint" : "token account";
                case "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb":
                  return "token-2022 account";
                case "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s":
                  return "metaplex metadata";
                case "BPFLoaderUpgradeab1e11111111111111111111111":
                  return "program data";
                default:
                  return `program-owned (${owner})`;
              }
            }
            ```

            Key insight: the **owner** field determines which program can modify the account's data. This is the foundation of Solana's security model — programs can only read (not write) accounts they don't own."""),
        language="ts",
    ),
]

# --- Additional Error Handling Templates ---
ERROR_HANDLING_TEMPLATES += [
    QATemplate(
        questions=[
            "How to handle errors gracefully in Anchor programs?",
            "What is the best pattern for error handling in Solana?",
            "How to create custom errors in Anchor?",
        ],
        answer=textwrap.dedent("""\
            Anchor provides a structured error system with custom error codes, constraint-based validation, and the `require!` macro family for clean error handling.

            ```rust
            use anchor_lang::prelude::*;

            // Define custom errors with the #[error_code] attribute
            #[error_code]
            pub enum ErrorCode {
                #[msg("Amount must be greater than zero")]
                ZeroAmount,                    // 6000

                #[msg("Insufficient balance for withdrawal")]
                InsufficientBalance,           // 6001

                #[msg("Caller is not authorized")]
                Unauthorized,                  // 6002

                #[msg("Operation is temporarily paused")]
                Paused,                        // 6003

                #[msg("Arithmetic overflow")]
                MathOverflow,                  // 6004

                #[msg("Invalid parameter: value out of range")]
                InvalidParameter,              // 6005

                #[msg("Deadline has expired")]
                DeadlineExpired,               // 6006

                #[msg("Slippage tolerance exceeded")]
                SlippageExceeded,              // 6007
            }

            #[program]
            pub mod error_handling {
                use super::*;

                pub fn withdraw(
                    ctx: Context<Withdraw>,
                    amount: u64,
                    min_output: u64,
                    deadline: i64,
                ) -> Result<()> {
                    // require! — simplest validation
                    require!(amount > 0, ErrorCode::ZeroAmount);

                    // require_keys_eq! — compare public keys with readable error
                    require_keys_eq!(
                        ctx.accounts.vault.authority,
                        ctx.accounts.authority.key(),
                        ErrorCode::Unauthorized
                    );

                    // require_gt! / require_gte! — numeric comparisons
                    require_gte!(
                        ctx.accounts.vault.balance,
                        amount,
                        ErrorCode::InsufficientBalance
                    );

                    // Custom validation with constraint
                    let clock = Clock::get()?;
                    require!(
                        clock.unix_timestamp <= deadline,
                        ErrorCode::DeadlineExpired
                    );

                    // Checked arithmetic with custom errors
                    let new_balance = ctx.accounts.vault.balance
                        .checked_sub(amount)
                        .ok_or(error!(ErrorCode::MathOverflow))?;

                    let output = calculate_output(amount)?;
                    require!(output >= min_output, ErrorCode::SlippageExceeded);

                    ctx.accounts.vault.balance = new_balance;
                    Ok(())
                }
            }

            fn calculate_output(amount: u64) -> Result<u64> {
                // Use ? operator with checked math
                let fee = amount
                    .checked_mul(30) // 0.3% fee
                    .ok_or(error!(ErrorCode::MathOverflow))?
                    .checked_div(10_000)
                    .ok_or(error!(ErrorCode::MathOverflow))?;

                amount
                    .checked_sub(fee)
                    .ok_or(error!(ErrorCode::MathOverflow))
            }

            #[derive(Accounts)]
            pub struct Withdraw<'info> {
                #[account(
                    mut,
                    // Constraint-based errors
                    has_one = authority @ ErrorCode::Unauthorized,
                    constraint = !vault.paused @ ErrorCode::Paused,
                )]
                pub vault: Account<'info, Vault>,
                pub authority: Signer<'info>,
            }

            #[account]
            #[derive(InitSpace)]
            pub struct Vault {
                pub authority: Pubkey,
                pub balance: u64,
                pub paused: bool,
            }
            ```

            Error handling best practices:
            - Use `require!()` for simple boolean checks.
            - Use `require_keys_eq!()` / `require_gt!()` / `require_gte!()` for type-specific checks.
            - Attach custom error codes to constraints with `@ ErrorCode::Variant`.
            - Use `checked_*` arithmetic and convert with `.ok_or(error!(...))?`.
            - Custom error codes start at 6000 — the index is the enum variant position."""),
        language="rust",
    ),
    QATemplate(
        questions=[
            "What does 'Transaction too large' error mean?",
            "How to fix transaction size limit errors on Solana?",
            "How to reduce transaction size when hitting the 1232 byte limit?",
        ],
        answer=textwrap.dedent("""\
            Solana transactions have a strict 1232-byte serialized size limit (1 MTU packet). When you exceed this, you need to split the transaction or reduce its size.

            **Why 1232 bytes?**
            - Solana uses UDP/QUIC for transaction forwarding.
            - Each transaction must fit in a single network packet.
            - IPv6 minimum MTU (1280) - UDP header (48) = 1232 bytes.

            **What takes up space:**
            ```
            Signatures:    64 bytes each (1 per signer)
            Header:        3 bytes (num signers, read-only, etc.)
            Account keys:  32 bytes each
            Blockhash:     32 bytes
            Instructions:  variable (program ID index + accounts + data)
            ```

            **Solutions:**

            ```typescript
            import {
              Connection,
              PublicKey,
              Transaction,
              VersionedTransaction,
              TransactionMessage,
              AddressLookupTableAccount,
            } from "@solana/web3.js";

            // Solution 1: Use Versioned Transactions with Address Lookup Tables
            // ALTs replace 32-byte addresses with 1-byte indexes
            async function useALT(
              connection: Connection,
              payer: Keypair,
              instructions: TransactionInstruction[],
              lookupTable: AddressLookupTableAccount
            ) {
              const { blockhash } = await connection.getLatestBlockhash();
              const message = new TransactionMessage({
                payerKey: payer.publicKey,
                recentBlockhash: blockhash,
                instructions,
              }).compileToV0Message([lookupTable]);

              const tx = new VersionedTransaction(message);
              tx.sign([payer]);
              return tx;
            }

            // Solution 2: Split into multiple transactions
            function splitInstructions(
              instructions: TransactionInstruction[],
              maxPerTx: number = 5
            ): TransactionInstruction[][] {
              const batches: TransactionInstruction[][] = [];
              for (let i = 0; i < instructions.length; i += maxPerTx) {
                batches.push(instructions.slice(i, i + maxPerTx));
              }
              return batches;
            }

            // Solution 3: Reduce instruction data size
            // Use compact encoding, bit flags, etc.
            // Example: instead of passing 3 booleans as 3 bytes, pack into 1 byte
            function packFlags(flag1: boolean, flag2: boolean, flag3: boolean): number {
              return (flag1 ? 1 : 0) | (flag2 ? 2 : 0) | (flag3 ? 4 : 0);
            }
            ```

            Strategies to reduce transaction size:
            1. **Address Lookup Tables**: reduce account key size from 32 bytes to 1 byte each (saves ~31 bytes per account).
            2. **Fewer accounts**: redesign to use fewer accounts per instruction.
            3. **Compact instruction data**: use efficient serialization (Borsh is already compact).
            4. **Split transactions**: break into multiple transactions (loses atomicity).
            5. **Fewer signers**: each signature adds 64 bytes."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to handle 'insufficient funds for rent' error?",
            "Why does my account creation fail with rent errors?",
            "How to ensure enough SOL for rent exemption?",
        ],
        answer=textwrap.dedent("""\
            Every Solana account must be rent-exempt, meaning it holds enough lamports to cover ~2 years of storage rent. If you don't provide enough, account creation fails.

            ```typescript
            import {
              Connection,
              Keypair,
              PublicKey,
              SystemProgram,
              Transaction,
              sendAndConfirmTransaction,
            } from "@solana/web3.js";

            async function createAccountWithRent(
              connection: Connection,
              payer: Keypair,
              newAccount: Keypair,
              space: number, // how many bytes of data
              programId: PublicKey
            ) {
              // Calculate rent-exempt balance
              const rentExemptBalance =
                await connection.getMinimumBalanceForRentExemption(space);

              console.log(`Space: ${space} bytes`);
              console.log(`Rent-exempt: ${rentExemptBalance / 1e9} SOL`);

              // Check payer has enough
              const payerBalance = await connection.getBalance(payer.publicKey);
              const txFee = 5000; // base fee
              const totalNeeded = rentExemptBalance + txFee;

              if (payerBalance < totalNeeded) {
                throw new Error(
                  `Insufficient funds: have ${payerBalance / 1e9} SOL, ` +
                  `need ${totalNeeded / 1e9} SOL (${rentExemptBalance / 1e9} rent + ${txFee / 1e9} fee)`
                );
              }

              const tx = new Transaction().add(
                SystemProgram.createAccount({
                  fromPubkey: payer.publicKey,
                  newAccountPubkey: newAccount.publicKey,
                  lamports: rentExemptBalance,
                  space,
                  programId,
                })
              );

              await sendAndConfirmTransaction(connection, tx, [payer, newAccount]);
              console.log("Account created:", newAccount.publicKey.toBase58());
            }

            // Common account sizes and their rent costs:
            async function showRentTable(connection: Connection) {
              const sizes = [
                { name: "Empty (wallet)", bytes: 0 },
                { name: "SPL Token mint", bytes: 82 },
                { name: "SPL Token account", bytes: 165 },
                { name: "Small Anchor account", bytes: 200 },
                { name: "Medium account (1KB)", bytes: 1024 },
                { name: "Large account (10KB)", bytes: 10240 },
                { name: "Very large (100KB)", bytes: 102400 },
              ];

              for (const { name, bytes } of sizes) {
                const rent = await connection.getMinimumBalanceForRentExemption(bytes);
                console.log(`${name} (${bytes}B): ${(rent / 1e9).toFixed(6)} SOL`);
              }
            }
            ```

            Common fixes:
            - **Anchor `init`**: automatically calculates and charges rent from the `payer`.
            - **Manual creation**: always call `getMinimumBalanceForRentExemption(space)` first.
            - **After realloc**: Anchor's `realloc` constraint handles rent changes automatically.
            - **Close accounts**: when closing, all lamports are returned to the destination.
            - If the payer doesn't have enough SOL, fund them first via airdrop (devnet) or transfer."""),
        language="ts",
    ),
]

# --- Additional NFT Templates ---
NFT_TEMPLATES += [
    QATemplate(
        questions=[
            "How to verify a collection on-chain in Metaplex?",
            "How to set and verify NFT collections?",
            "How does collection verification work for Solana NFTs?",
        ],
        answer=textwrap.dedent("""\
            Collection verification proves that an NFT belongs to a specific collection. Only the collection's update authority can verify membership, preventing unauthorized NFTs from claiming collection membership.

            ```typescript
            import { createUmi } from "@metaplex-foundation/umi-bundle-defaults";
            import {
              mplTokenMetadata,
              verifyCollectionV1,
              findMetadataPda,
              unverifyCollectionV1,
            } from "@metaplex-foundation/mpl-token-metadata";
            import {
              keypairIdentity,
              publicKey,
            } from "@metaplex-foundation/umi";

            async function verifyCollection(
              collectionMintAddress: string,
              nftMintAddress: string
            ) {
              const umi = createUmi("https://api.devnet.solana.com")
                .use(mplTokenMetadata());

              // The update authority of the collection must sign
              const collectionAuthority = umi.identity;
              umi.use(keypairIdentity(collectionAuthority));

              const collectionMint = publicKey(collectionMintAddress);
              const nftMint = publicKey(nftMintAddress);

              // Find metadata PDAs
              const collectionMetadata = findMetadataPda(umi, {
                mint: collectionMint,
              });
              const nftMetadata = findMetadataPda(umi, {
                mint: nftMint,
              });

              // Verify the NFT as part of the collection
              await verifyCollectionV1(umi, {
                metadata: nftMetadata,
                collectionMint,
                authority: collectionAuthority,
              }).sendAndConfirm(umi);

              console.log("Collection verified for NFT:", nftMintAddress);
            }

            // To unverify (remove from collection):
            async function unverifyFromCollection(
              umi: any,
              collectionMint: string,
              nftMint: string
            ) {
              await unverifyCollectionV1(umi, {
                metadata: findMetadataPda(umi, { mint: publicKey(nftMint) }),
                collectionMint: publicKey(collectionMint),
                authority: umi.identity,
              }).sendAndConfirm(umi);
            }
            ```

            How collection verification works:
            1. The NFT's metadata has a `collection` field with `{ key: collectionMint, verified: false }`.
            2. The collection's update authority calls `verifyCollectionV1` to set `verified: true`.
            3. Marketplaces and wallets check the `verified` flag to display collection membership.
            4. Only verified collections show up in marketplace collection pages.

            Important:
            - Candy Machine automatically verifies collection during minting.
            - For manual minting, you must call verify separately.
            - Unverified collection NFTs won't show in marketplace collection views.
            - The collection NFT itself must have `collectionDetails` set during creation."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to implement royalty enforcement for Solana NFTs?",
            "How do programmable NFTs enforce royalties?",
            "What is the pNFT standard for royalty enforcement?",
        ],
        answer=textwrap.dedent("""\
            Metaplex's Programmable NFTs (pNFTs) enforce royalties at the protocol level by requiring all transfers to go through the Token Metadata program, which validates royalty rules.

            ```typescript
            import { createUmi } from "@metaplex-foundation/umi-bundle-defaults";
            import {
              mplTokenMetadata,
              createProgrammableNft,
              transferV1,
              TokenStandard,
              findMetadataPda,
              findMasterEditionPda,
              findTokenRecordPda,
            } from "@metaplex-foundation/mpl-token-metadata";
            import {
              generateSigner,
              keypairIdentity,
              percentAmount,
              publicKey,
            } from "@metaplex-foundation/umi";

            async function createPNFT() {
              const umi = createUmi("https://api.devnet.solana.com")
                .use(mplTokenMetadata());
              const creator = generateSigner(umi);
              umi.use(keypairIdentity(creator));

              const mint = generateSigner(umi);

              // Create a Programmable NFT with enforced royalties
              await createProgrammableNft(umi, {
                mint,
                name: "Royalty-Enforced NFT",
                symbol: "PNFT",
                uri: "https://arweave.net/metadata.json",
                sellerFeeBasisPoints: percentAmount(5), // 5% royalty
                creators: [
                  {
                    address: creator.publicKey,
                    verified: true,
                    share: 100,
                  },
                ],
                // Rule set controls transfer behavior
                ruleSet: null, // use default (allow all with royalties)
              }).sendAndConfirm(umi);

              console.log("pNFT created:", mint.publicKey);
              return mint.publicKey;
            }

            // Transferring a pNFT (royalties are enforced automatically)
            async function transferPNFT(
              umi: any,
              mint: string,
              currentOwner: any,
              newOwner: string
            ) {
              const mintPk = publicKey(mint);
              const metadata = findMetadataPda(umi, { mint: mintPk });
              const edition = findMasterEditionPda(umi, { mint: mintPk });

              await transferV1(umi, {
                mint: mintPk,
                authority: currentOwner,
                tokenOwner: currentOwner.publicKey,
                destinationOwner: publicKey(newOwner),
                tokenStandard: TokenStandard.ProgrammableNonFungible,
              }).sendAndConfirm(umi);

              console.log("pNFT transferred to:", newOwner);
            }
            ```

            How pNFT royalty enforcement works:
            - Regular NFTs can be transferred via raw SPL Token `transfer` — bypassing royalties.
            - pNFTs are frozen by default in the Token Program.
            - The ONLY way to transfer a pNFT is through the Token Metadata program's `transferV1`.
            - `transferV1` checks and enforces the `sellerFeeBasisPoints` (royalty percentage).
            - Marketplaces must use `transferV1` — direct token transfers are blocked.

            Token Standards:
            - `NonFungible` — classic NFT (no royalty enforcement)
            - `ProgrammableNonFungible` — pNFT (royalties enforced)
            - `FungibleAsset` — semi-fungible (like game items)
            - `Fungible` — standard fungible token"""),
        language="ts",
    ),
]

# --- Additional Token Extensions Templates ---
TOKEN_EXTENSIONS_TEMPLATES += [
    QATemplate(
        questions=[
            "How to use confidential transfers with Token-2022?",
            "What are confidential transfers in Token Extensions?",
            "How to enable privacy for token transfers on Solana?",
        ],
        answer=textwrap.dedent("""\
            Confidential transfers in Token-2022 use zero-knowledge proofs to hide transfer amounts while keeping the token balances verifiable. The amounts are encrypted using ElGamal encryption.

            ```typescript
            import {
              Connection,
              Keypair,
              SystemProgram,
              Transaction,
              sendAndConfirmTransaction,
            } from "@solana/web3.js";
            import {
              ExtensionType,
              TOKEN_2022_PROGRAM_ID,
              createInitializeMintInstruction,
              createInitializeConfidentialTransferMintInstruction,
              getMintLen,
              ConfidentialTransferMint,
            } from "@solana/spl-token";

            async function createConfidentialMint(
              connection: Connection,
              payer: Keypair
            ) {
              const mintKeypair = Keypair.generate();
              const decimals = 9;

              const mintLen = getMintLen([
                ExtensionType.ConfidentialTransferMint,
              ]);
              const lamports = await connection.getMinimumBalanceForRentExemption(mintLen);

              const tx = new Transaction().add(
                SystemProgram.createAccount({
                  fromPubkey: payer.publicKey,
                  newAccountPubkey: mintKeypair.publicKey,
                  space: mintLen,
                  lamports,
                  programId: TOKEN_2022_PROGRAM_ID,
                }),
                // Initialize confidential transfer extension
                createInitializeConfidentialTransferMintInstruction(
                  mintKeypair.publicKey,
                  payer.publicKey,   // authority
                  true,              // auto-approve new accounts
                  undefined,         // auditor ElGamal pubkey (optional)
                  TOKEN_2022_PROGRAM_ID
                ),
                createInitializeMintInstruction(
                  mintKeypair.publicKey,
                  decimals,
                  payer.publicKey,
                  null,
                  TOKEN_2022_PROGRAM_ID
                )
              );

              await sendAndConfirmTransaction(connection, tx, [payer, mintKeypair]);
              console.log("Confidential mint:", mintKeypair.publicKey.toBase58());
              return mintKeypair.publicKey;
            }
            ```

            How confidential transfers work:
            1. Each token account has both a **public balance** and a **confidential balance**.
            2. Users deposit from public to confidential balance (encrypted).
            3. Confidential transfers move encrypted amounts between accounts.
            4. Users withdraw from confidential to public balance.
            5. Zero-knowledge proofs ensure balances are non-negative and transfers are valid.

            Limitations:
            - ZK proof generation is computationally expensive (client-side).
            - An optional **auditor** can decrypt all amounts (for compliance).
            - Not all wallets support confidential transfers yet.
            - The extension adds significant account size overhead."""),
        language="ts",
    ),
    QATemplate(
        questions=[
            "How to create a token with a permanent delegate using Token-2022?",
            "What is the permanent delegate extension in Token Extensions?",
            "How to use permanent delegate for token clawback?",
        ],
        answer=textwrap.dedent("""\
            The permanent delegate extension gives a designated authority the ability to transfer or burn tokens from ANY token account for that mint. This enables compliance features like clawback and forced transfers.

            ```typescript
            import {
              Connection,
              Keypair,
              SystemProgram,
              Transaction,
              sendAndConfirmTransaction,
            } from "@solana/web3.js";
            import {
              ExtensionType,
              TOKEN_2022_PROGRAM_ID,
              createInitializeMintInstruction,
              createInitializePermanentDelegateInstruction,
              getMintLen,
              createTransferCheckedInstruction,
              getAssociatedTokenAddressSync,
            } from "@solana/spl-token";

            async function createClawbackToken(
              connection: Connection,
              payer: Keypair,
              permanentDelegate: PublicKey // the authority that can clawback
            ) {
              const mintKeypair = Keypair.generate();
              const decimals = 6;

              const mintLen = getMintLen([ExtensionType.PermanentDelegate]);
              const lamports = await connection.getMinimumBalanceForRentExemption(mintLen);

              const tx = new Transaction().add(
                SystemProgram.createAccount({
                  fromPubkey: payer.publicKey,
                  newAccountPubkey: mintKeypair.publicKey,
                  space: mintLen,
                  lamports,
                  programId: TOKEN_2022_PROGRAM_ID,
                }),
                createInitializePermanentDelegateInstruction(
                  mintKeypair.publicKey,
                  permanentDelegate, // can transfer/burn from ANY account
                  TOKEN_2022_PROGRAM_ID
                ),
                createInitializeMintInstruction(
                  mintKeypair.publicKey,
                  decimals,
                  payer.publicKey,
                  null,
                  TOKEN_2022_PROGRAM_ID
                )
              );

              await sendAndConfirmTransaction(connection, tx, [payer, mintKeypair]);
              console.log("Clawback token:", mintKeypair.publicKey.toBase58());
              return mintKeypair.publicKey;
            }

            // The permanent delegate can transfer tokens from anyone:
            async function clawbackTokens(
              connection: Connection,
              permanentDelegate: Keypair,
              mint: PublicKey,
              fromOwner: PublicKey,
              toAddress: PublicKey,
              amount: bigint,
              decimals: number
            ) {
              const sourceAta = getAssociatedTokenAddressSync(
                mint, fromOwner, false, TOKEN_2022_PROGRAM_ID
              );
              const destAta = getAssociatedTokenAddressSync(
                mint, toAddress, false, TOKEN_2022_PROGRAM_ID
              );

              const tx = new Transaction().add(
                createTransferCheckedInstruction(
                  sourceAta,
                  mint,
                  destAta,
                  permanentDelegate.publicKey, // delegate signs instead of owner
                  amount,
                  decimals,
                  [],
                  TOKEN_2022_PROGRAM_ID
                )
              );

              await sendAndConfirmTransaction(connection, tx, [permanentDelegate]);
              console.log(`Clawed back ${amount} tokens from ${fromOwner.toBase58()}`);
            }
            ```

            Use cases:
            - **Regulatory compliance**: freeze/clawback tokens for sanctioned addresses.
            - **Stablecoins**: issuer can freeze/seize tokens (similar to USDC).
            - **Corporate tokens**: company can recover tokens from lost wallets.
            - **Subscription tokens**: revoke access tokens when subscription expires.

            Warning: This is a powerful (and potentially controversial) feature. Users should be clearly informed that the token has a permanent delegate before accepting it."""),
        language="ts",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# CATEGORY REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

CATEGORIES: dict[str, list[QATemplate]] = {
    "transaction": TRANSACTION_TEMPLATES,
    "client-ts": CLIENT_TS_TEMPLATES,
    "security": SECURITY_TEMPLATES,
    "token-extensions": TOKEN_EXTENSIONS_TEMPLATES,
    "defi": DEFI_TEMPLATES,
    "architecture": ARCHITECTURE_TEMPLATES,
    "testing": TESTING_TEMPLATES,
    "nft": NFT_TEMPLATES,
    "concepts": CONCEPTS_TEMPLATES,
    "errors": ERROR_HANDLING_TEMPLATES,
}


# ---------------------------------------------------------------------------
# Record generation
# ---------------------------------------------------------------------------

def build_messages(question: str, answer: str) -> list[dict]:
    """Build a ChatML messages list."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ]


def generate_records(
    categories: dict[str, list[QATemplate]],
    seed: int = 42,
) -> tuple[list[Record], dict[str, int]]:
    """Generate all records from templates. Returns (records, category_counts)."""
    rng = random.Random(seed)
    records: list[Record] = []
    seen_ids: set[str] = set()
    category_counts: dict[str, int] = {}

    for cat_name, templates in categories.items():
        cat_count = 0
        for tmpl in templates:
            tmpl.category = cat_name

            # Augment questions to get more phrasings per template
            aug_questions = augment_questions(tmpl.questions, rng, target=25)
            aug_tmpl = QATemplate(
                questions=aug_questions,
                answer=tmpl.answer,
                language=tmpl.language,
                category=cat_name,
                variations=tmpl.variations,
            )

            pairs = aug_tmpl.expand(rng)
            for pair in pairs:
                messages = build_messages(pair["question"], pair["answer"])
                content = json.dumps(messages, ensure_ascii=False)
                rid = Record.make_id(content)
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)

                record = Record(
                    id=rid,
                    source="synthetic/expert-qa",
                    source_type="qa",
                    content=content,
                    language=tmpl.language,
                    license="synthetic",
                    metadata={
                        "method": "expert-qa",
                        "category": cat_name,
                        "collected_at": today_str(),
                        "anchor_style": "modern",
                        "training_permitted": True,
                    },
                )
                records.append(record)
                cat_count += 1

        category_counts[cat_name] = cat_count

    # Shuffle for training
    rng.shuffle(records)
    return records, category_counts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@app.callback(invoke_without_command=True)
def main(
    dry_run: bool = typer.Option(False, "--dry-run", help="Count records without writing"),
    seed: int = typer.Option(42, "--seed", help="Random seed for deterministic output"),
    categories_filter: Optional[str] = typer.Option(
        None, "--categories", help="Comma-separated category names to include"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Generate expert-level Solana Q&A SFT records."""
    console.print("[bold blue]Sealevel Expert Q&A Generator[/bold blue]")
    console.print()

    # Filter categories if requested
    cats = CATEGORIES
    if categories_filter:
        names = [n.strip() for n in categories_filter.split(",")]
        invalid = [n for n in names if n not in CATEGORIES]
        if invalid:
            console.print(f"[red]Unknown categories: {invalid}[/red]")
            console.print(f"Available: {list(CATEGORIES.keys())}")
            raise typer.Exit(1)
        cats = {k: v for k, v in CATEGORIES.items() if k in names}

    # Generate
    records, counts = generate_records(cats, seed=seed)

    # Stats table
    table = Table(title="Expert Q&A Generation Stats")
    table.add_column("Category", style="cyan")
    table.add_column("Templates", justify="right", style="green")
    table.add_column("Records", justify="right", style="bold green")

    for cat_name in sorted(counts.keys()):
        template_count = len(cats[cat_name])
        table.add_row(cat_name, str(template_count), str(counts[cat_name]))

    table.add_section()
    table.add_row(
        "[bold]TOTAL[/bold]",
        str(sum(len(v) for v in cats.values())),
        f"[bold]{len(records)}[/bold]",
    )
    console.print(table)

    if dry_run:
        console.print("\n[yellow]Dry run — no files written.[/yellow]")
        return

    # Write output
    out_path = Path(output) if output else OUTPUT_FILE
    written = write_jsonl(records, out_path)
    console.print(f"\n[green]Wrote {written} records to {out_path}[/green]")


if __name__ == "__main__":
    app()
