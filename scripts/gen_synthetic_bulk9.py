#!/usr/bin/env python3
"""Bulk synthetic data generator — Part 9: TypeScript client patterns.
Target: ~150 records.
"""
import hashlib, json
from pathlib import Path

PROCESSED = Path(__file__).parent.parent / "data" / "processed"

def make_rec(content, category, lang="ts"):
    return {
        "id": hashlib.sha256(content.encode()).hexdigest(),
        "source": "synthetic/glan", "source_type": "synthetic",
        "content": content, "language": lang, "license": "synthetic-original",
        "metadata": {"method": "glan", "category": category, "anchor_version_class": "modern"},
    }

records = []

# ── 1. Anchor client basics (15 records) ──
ENTITIES = [
    ("userProfile", "UserProfile", ["authority", "username", "reputation", "createdAt"]),
    ("gameState", "GameState", ["player", "score", "level", "isActive"]),
    ("vault", "Vault", ["authority", "balance", "bump"]),
    ("proposal", "Proposal", ["creator", "title", "votesFor", "votesAgainst", "status"]),
    ("listing", "Listing", ["seller", "price", "mint", "isActive"]),
]

# Setup patterns
records.append(make_rec(
    "### Question\nHow do I set up an Anchor client in TypeScript?\n\n### Answer\n```typescript\nimport * as anchor from '@coral-xyz/anchor';\nimport { Program } from '@coral-xyz/anchor';\nimport { MyProgram } from '../target/types/my_program';\n\n// Option 1: With wallet (browser)\nconst provider = anchor.AnchorProvider.env();\nanchor.setProvider(provider);\nconst program = anchor.workspace.MyProgram as Program<MyProgram>;\n\n// Option 2: With keypair (Node.js)\nimport { Connection, Keypair } from '@solana/web3.js';\nconst connection = new Connection('https://api.devnet.solana.com');\nconst wallet = new anchor.Wallet(Keypair.fromSecretKey(secretKey));\nconst provider = new anchor.AnchorProvider(connection, wallet, {\n  commitment: 'confirmed',\n});\nconst program = new Program(idl, provider);\n```",
    "client_setup"))

records.append(make_rec(
    "### Question\nHow do I connect to different Solana clusters in TypeScript?\n\n### Answer\n```typescript\nimport { Connection, clusterApiUrl } from '@solana/web3.js';\n\n// Devnet\nconst devnet = new Connection(clusterApiUrl('devnet'));\n\n// Mainnet\nconst mainnet = new Connection(clusterApiUrl('mainnet-beta'));\n\n// Local\nconst local = new Connection('http://localhost:8899');\n\n// Custom RPC (Helius, QuickNode, etc.)\nconst custom = new Connection('https://rpc.helius.xyz/?api-key=YOUR_KEY', {\n  commitment: 'confirmed',\n  wsEndpoint: 'wss://rpc.helius.xyz/?api-key=YOUR_KEY',\n});\n```",
    "client_setup"))

# Fetch patterns for each entity
for camel, pascal, fields in ENTITIES:
    field_log = ", ".join(f"account.{f}" for f in fields[:3])
    records.append(make_rec(
        f"### Question\nHow do I fetch a `{pascal}` account in TypeScript with Anchor?\n\n### Answer\n```typescript\n// Fetch single account\nconst account = await program.account.{camel}.fetch(accountPubkey);\nconsole.log({field_log});\n\n// Fetch multiple\nconst accounts = await program.account.{camel}.fetchMultiple([\n  pubkey1, pubkey2, pubkey3,\n]);\n\n// Fetch all with optional filter\nconst all{pascal}s = await program.account.{camel}.all();\nfor (const {{ account, publicKey }} of all{pascal}s) {{\n  console.log(publicKey.toBase58(), {field_log});\n}}\n\n// With memcmp filter (e.g., filter by authority)\nconst filtered = await program.account.{camel}.all([\n  {{ memcmp: {{ offset: 8, bytes: authorityPubkey.toBase58() }} }},\n]);\n```",
        "account_fetching"))

# ── 2. Transaction construction (15 records) ──
for camel, pascal, fields in ENTITIES:
    records.append(make_rec(
        f"### Question\nHow do I send an `initialize` instruction for `{pascal}` in TypeScript?\n\n### Answer\n```typescript\nconst tx = await program.methods\n  .initialize{pascal}()\n  .accounts({{\n    {camel}: {camel}Pda,\n    authority: wallet.publicKey,\n    systemProgram: anchor.web3.SystemProgram.programId,\n  }})\n  .rpc();\n\nconsole.log('Transaction signature:', tx);\n\n// Wait for confirmation\nconst confirmation = await connection.confirmTransaction(tx, 'confirmed');\n```",
        "transaction_construction"))

TX_PATTERNS = [
    ("priority_fees", "How do I add priority fees to a Solana transaction?",
     "```typescript\nimport { ComputeBudgetProgram } from '@solana/web3.js';\n\nconst tx = new Transaction();\n\n// Set compute unit limit\ntx.add(ComputeBudgetProgram.setComputeUnitLimit({ units: 200_000 }));\n\n// Set priority fee (microLamports per CU)\ntx.add(ComputeBudgetProgram.setComputeUnitPrice({ microLamports: 50_000 }));\n\n// Add your instruction\ntx.add(myInstruction);\n\nawait sendAndConfirmTransaction(connection, tx, [payer]);\n```"),
    ("versioned_tx", "How do I create a versioned transaction with address lookup tables?",
     "```typescript\nimport { TransactionMessage, VersionedTransaction, AddressLookupTableAccount } from '@solana/web3.js';\n\n// Fetch lookup table\nconst lookupTableAccount = await connection\n  .getAddressLookupTable(lookupTableAddress)\n  .then(res => res.value);\n\n// Build versioned transaction\nconst messageV0 = new TransactionMessage({\n  payerKey: payer.publicKey,\n  recentBlockhash: (await connection.getLatestBlockhash()).blockhash,\n  instructions: [instruction1, instruction2],\n}).compileToV0Message([lookupTableAccount]);\n\nconst tx = new VersionedTransaction(messageV0);\ntx.sign([payer]);\n\nconst sig = await connection.sendTransaction(tx);\n```"),
    ("simulate", "How do I simulate a transaction before sending?",
     "```typescript\n// Build transaction without sending\nconst tx = await program.methods\n  .myInstruction(args)\n  .accounts({ ... })\n  .transaction();\n\ntx.recentBlockhash = (await connection.getLatestBlockhash()).blockhash;\ntx.feePayer = wallet.publicKey;\n\n// Simulate\nconst simulation = await connection.simulateTransaction(tx);\nconsole.log('Logs:', simulation.value.logs);\nconsole.log('CU used:', simulation.value.unitsConsumed);\nconsole.log('Error:', simulation.value.err);\n\n// Only send if simulation succeeds\nif (!simulation.value.err) {\n  const sig = await sendAndConfirmTransaction(connection, tx, [wallet.payer]);\n}\n```"),
    ("multi_ix", "How do I send multiple instructions in one transaction?",
     "```typescript\n// Method 1: Anchor methods chaining\nconst tx = new Transaction();\n\ntx.add(\n  await program.methods.instructionOne(arg1).accounts({...}).instruction(),\n  await program.methods.instructionTwo(arg2).accounts({...}).instruction(),\n  await program.methods.instructionThree(arg3).accounts({...}).instruction(),\n);\n\nawait sendAndConfirmTransaction(connection, tx, [payer]);\n\n// Method 2: Using preInstructions/postInstructions\nawait program.methods\n  .mainInstruction()\n  .accounts({...})\n  .preInstructions([setupIx])\n  .postInstructions([cleanupIx])\n  .rpc();\n```"),
    ("durable_nonce", "How do I use durable nonces for offline signing?",
     "```typescript\nimport { SystemProgram, NONCE_ACCOUNT_LENGTH, NonceAccount } from '@solana/web3.js';\n\n// Create nonce account\nconst nonceKeypair = Keypair.generate();\nconst tx = new Transaction().add(\n  SystemProgram.createAccount({\n    fromPubkey: payer.publicKey,\n    newAccountPubkey: nonceKeypair.publicKey,\n    lamports: await connection.getMinimumBalanceForRentExemption(NONCE_ACCOUNT_LENGTH),\n    space: NONCE_ACCOUNT_LENGTH,\n    programId: SystemProgram.programId,\n  }),\n  SystemProgram.nonceInitialize({\n    noncePubkey: nonceKeypair.publicKey,\n    authorizedPubkey: payer.publicKey,\n  })\n);\n\n// Use nonce in transaction (replaces recentBlockhash)\nconst nonceInfo = await connection.getNonce(nonceKeypair.publicKey);\nconst offlineTx = new Transaction();\nofflineTx.recentBlockhash = nonceInfo.nonce;\nofflineTx.add(\n  SystemProgram.nonceAdvance({ noncePubkey: nonceKeypair.publicKey, authorizedPubkey: payer.publicKey }),\n  myInstruction\n);\n```"),
    ("retry_logic", "How do I implement retry logic for Solana transactions?",
     "```typescript\nasync function sendWithRetry(\n  connection: Connection,\n  tx: Transaction,\n  signers: Keypair[],\n  maxRetries = 3\n): Promise<string> {\n  for (let attempt = 0; attempt < maxRetries; attempt++) {\n    try {\n      const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash();\n      tx.recentBlockhash = blockhash;\n      tx.sign(...signers);\n      \n      const sig = await connection.sendRawTransaction(tx.serialize(), {\n        skipPreflight: false,\n        maxRetries: 0,\n      });\n      \n      await connection.confirmTransaction({\n        signature: sig,\n        blockhash,\n        lastValidBlockHeight,\n      });\n      \n      return sig;\n    } catch (e) {\n      if (attempt === maxRetries - 1) throw e;\n      console.log(`Retry ${attempt + 1}/${maxRetries}`);\n      await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));\n    }\n  }\n  throw new Error('Max retries exceeded');\n}\n```"),
    ("confirmation", "What are the different commitment levels in Solana?",
     "```typescript\n// 'processed' — Fastest, but may be rolled back\nconst processed = await connection.getBalance(pubkey, 'processed');\n\n// 'confirmed' — Supermajority of validators confirmed (recommended)\nconst confirmed = await connection.getBalance(pubkey, 'confirmed');\n\n// 'finalized' — Absolute certainty, ~30 slots behind\nconst finalized = await connection.getBalance(pubkey, 'finalized');\n\n// For transactions:\nawait connection.confirmTransaction(sig, 'confirmed');\n\n// Guidelines:\n// - UI updates: 'confirmed'\n// - Financial operations: 'confirmed' or 'finalized'\n// - Read-after-write: 'confirmed'\n```"),
]
for name, q, a in TX_PATTERNS:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "transaction_patterns"))

# ── 3. PDA derivation in TypeScript (15 records) ──
PDA_SEEDS = [
    ("simple string", '[Buffer.from("config")]', 'seeds = [b"config"]'),
    ("user-specific", '[Buffer.from("profile"), user.toBuffer()]', 'seeds = [b"profile", user.key().as_ref()]'),
    ("two pubkeys", '[Buffer.from("pair"), mintA.toBuffer(), mintB.toBuffer()]', 'seeds = [b"pair", mint_a.key().as_ref(), mint_b.key().as_ref()]'),
    ("with u64", '[Buffer.from("order"), new BN(orderId).toArrayLike(Buffer, "le", 8)]', 'seeds = [b"order", &order_id.to_le_bytes()]'),
    ("with u8 enum", '[Buffer.from("tier"), Buffer.from([tierLevel])]', 'seeds = [b"tier", &[tier_level]]'),
    ("nested PDA", '[Buffer.from("reward"), poolPda.toBuffer(), user.toBuffer()]', 'seeds = [b"reward", pool.key().as_ref(), user.key().as_ref()]'),
    ("with string", '[Buffer.from("name"), Buffer.from(username)]', 'seeds = [b"name", username.as_bytes()]'),
    ("multi-seed complex", '[Buffer.from("escrow"), seller.toBuffer(), buyer.toBuffer(), new BN(tradeId).toArrayLike(Buffer, "le", 8)]',
     'seeds = [b"escrow", seller.key().as_ref(), buyer.key().as_ref(), &trade_id.to_le_bytes()]'),
]

for desc, ts_seeds, rust_seeds in PDA_SEEDS:
    records.append(make_rec(
        f"### Question\nHow do I derive a PDA with {desc} seeds in TypeScript to match Rust?\n\n### Answer\n```typescript\n// TypeScript\nconst [pda, bump] = PublicKey.findProgramAddressSync(\n  {ts_seeds},\n  programId\n);\n```\n\n```rust\n// Matching Rust Anchor constraint\n#[account({rust_seeds}, bump)]\npub account: Account<'info, MyData>,\n```\n\nKey rules:\n- Seeds must be in the **exact same order** in both client and program\n- Use `toBuffer()` for Pubkeys (32 bytes)\n- Use `BN.toArrayLike(Buffer, 'le', 8)` for u64 (little-endian, 8 bytes)\n- Use `Buffer.from(string)` for string seeds\n- Use `Buffer.from([number])` for u8 values",
        "pda_derivation"))

# Common PDA mistakes
PDA_MISTAKES = [
    ("wrong endianness", "Using big-endian for numbers", "// ❌ Wrong: big-endian\nnew BN(id).toArrayLike(Buffer, 'be', 8)\n\n// ✅ Correct: Solana uses little-endian\nnew BN(id).toArrayLike(Buffer, 'le', 8)"),
    ("wrong seed order", "Seeds in different order than program", "// ❌ Wrong order\n[Buffer.from('vault'), user.toBuffer(), mint.toBuffer()]\n\n// ✅ Must match program exactly:\n// seeds = [b\"vault\", mint.key().as_ref(), user.key().as_ref()]\n[Buffer.from('vault'), mint.toBuffer(), user.toBuffer()]"),
    ("string encoding", "Using wrong string encoding", "// ❌ Wrong: includes null terminator or extra bytes\nBuffer.from(name + '\\0')\n\n// ✅ Correct: plain UTF-8 bytes\nBuffer.from(name)"),
    ("bump confusion", "Confusing bump usage", "// findProgramAddressSync returns the canonical bump\nconst [pda, bump] = PublicKey.findProgramAddressSync(seeds, programId);\n\n// You don't pass the bump to Anchor — it finds it automatically\n// via `bump` in the seeds constraint.\n// Store the bump in the account for CPI signing later."),
    ("pubkey bytes", "Using base58 string instead of bytes", "// ❌ Wrong: base58 string\n[Buffer.from(user.toBase58())]\n\n// ✅ Correct: raw 32-byte key\n[user.toBuffer()]"),
    ("number size", "Using wrong byte size for numbers", "// ❌ Wrong: u64 needs 8 bytes, not 4\nnew BN(amount).toArrayLike(Buffer, 'le', 4)\n\n// ✅ Correct sizes:\n// u8 = 1 byte, u16 = 2 bytes, u32 = 4 bytes, u64 = 8 bytes\nnew BN(amount).toArrayLike(Buffer, 'le', 8)"),
    ("createProgramAddress", "Using createProgramAddress instead of findProgramAddress", "// ❌ Don't use this unless you already know the bump:\nPublicKey.createProgramAddressSync(seeds, programId)\n\n// ✅ Use find — it searches for a valid bump:\nconst [pda, bump] = PublicKey.findProgramAddressSync(seeds, programId);\n// findProgramAddress tries bump=255, 254, 253... until it finds one\n// that produces a valid off-curve point."),
]
for name, desc, code in PDA_MISTAKES:
    records.append(make_rec(
        f"### Question\nCommon PDA mistake in TypeScript: {desc}\n\n### Answer\n```typescript\n{code}\n```",
        "pda_mistakes"))

# ── 4. Token operations in TS (15 records) ──
TOKEN_TS = [
    ("create_mint", "How do I create a new SPL token mint in TypeScript?",
     "```typescript\nimport { createMint } from '@solana/spl-token';\n\nconst mint = await createMint(\n  connection,\n  payer,           // Fee payer\n  mintAuthority,   // Mint authority\n  freezeAuthority, // Freeze authority (null for none)\n  9,               // Decimals\n);\nconsole.log('Mint:', mint.toBase58());\n```"),
    ("create_ata", "How do I create an Associated Token Account?",
     "```typescript\nimport { getOrCreateAssociatedTokenAccount } from '@solana/spl-token';\n\nconst ata = await getOrCreateAssociatedTokenAccount(\n  connection,\n  payer,\n  mint,\n  owner,  // Token account owner\n);\nconsole.log('ATA:', ata.address.toBase58());\nconsole.log('Balance:', ata.amount.toString());\n```"),
    ("mint_tokens", "How do I mint tokens to an account?",
     "```typescript\nimport { mintTo } from '@solana/spl-token';\n\nconst sig = await mintTo(\n  connection,\n  payer,\n  mint,\n  destination, // Token account to mint to\n  mintAuthority,\n  1_000_000_000, // Amount (with decimals: 1 token with 9 decimals)\n);\n```"),
    ("transfer_tokens", "How do I transfer SPL tokens?",
     "```typescript\nimport { transfer } from '@solana/spl-token';\n\nconst sig = await transfer(\n  connection,\n  payer,\n  sourceTokenAccount,\n  destinationTokenAccount,\n  owner,\n  1_000_000, // Amount in base units\n);\n```"),
    ("burn_tokens", "How do I burn SPL tokens?",
     "```typescript\nimport { burn } from '@solana/spl-token';\n\nconst sig = await burn(\n  connection,\n  payer,\n  tokenAccount,\n  mint,\n  owner,\n  500_000, // Amount to burn\n);\n```"),
    ("wrap_sol", "How do I wrap SOL into an SPL token?",
     "```typescript\nimport { NATIVE_MINT, createSyncNativeInstruction, getAssociatedTokenAddress } from '@solana/spl-token';\n\n// 1. Get/create wrapped SOL ATA\nconst ata = await getAssociatedTokenAddress(NATIVE_MINT, wallet.publicKey);\n\n// 2. Transfer SOL to the ATA\nconst tx = new Transaction().add(\n  SystemProgram.transfer({\n    fromPubkey: wallet.publicKey,\n    toPubkey: ata,\n    lamports: amount,\n  }),\n  createSyncNativeInstruction(ata),\n);\n```"),
    ("get_balance", "How do I get a token balance?",
     "```typescript\nimport { getAccount } from '@solana/spl-token';\n\nconst account = await getAccount(connection, tokenAccountAddress);\nconsole.log('Balance:', account.amount.toString());\nconsole.log('Mint:', account.mint.toBase58());\nconsole.log('Owner:', account.owner.toBase58());\n\n// Or get all token accounts for a wallet\nconst accounts = await connection.getTokenAccountsByOwner(\n  walletPubkey,\n  { programId: TOKEN_PROGRAM_ID }\n);\n```"),
    ("close_account", "How do I close a token account to reclaim SOL?",
     "```typescript\nimport { closeAccount } from '@solana/spl-token';\n\n// Token account must have 0 balance first\nconst sig = await closeAccount(\n  connection,\n  payer,\n  tokenAccount,  // Account to close\n  destination,    // SOL destination\n  owner,          // Token account owner\n);\n```"),
    ("get_all_tokens", "How do I get all token balances for a wallet?",
     "```typescript\nconst accounts = await connection.getParsedTokenAccountsByOwner(\n  walletPubkey,\n  { programId: TOKEN_PROGRAM_ID }\n);\n\nfor (const { account, pubkey } of accounts.value) {\n  const data = account.data.parsed.info;\n  console.log(`Mint: ${data.mint}`);\n  console.log(`Balance: ${data.tokenAmount.uiAmount}`);\n  console.log(`Decimals: ${data.tokenAmount.decimals}`);\n}\n```"),
    ("metadata_fetch", "How do I fetch token metadata?",
     "```typescript\nimport { Metaplex } from '@metaplex-foundation/js';\n\nconst metaplex = Metaplex.make(connection);\nconst nft = await metaplex.nfts().findByMint({ mintAddress: mint });\n\nconsole.log('Name:', nft.name);\nconsole.log('Symbol:', nft.symbol);\nconsole.log('URI:', nft.uri);\nconsole.log('Creators:', nft.creators);\n```"),
]
for name, q, a in TOKEN_TS:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "token_operations"))

# Additional token ops
TOKEN_EXTRA = [
    ("freeze", "Freeze a token account", "import { freezeAccount } from '@solana/spl-token';\nawait freezeAccount(connection, payer, tokenAccount, mint, freezeAuthority);"),
    ("thaw", "Thaw a frozen token account", "import { thawAccount } from '@solana/spl-token';\nawait thawAccount(connection, payer, tokenAccount, mint, freezeAuthority);"),
    ("approve_delegate", "Approve a delegate", "import { approve } from '@solana/spl-token';\nawait approve(connection, payer, tokenAccount, delegate, owner, amount);"),
    ("revoke_delegate", "Revoke a delegate", "import { revoke } from '@solana/spl-token';\nawait revoke(connection, payer, tokenAccount, owner);"),
    ("set_authority", "Change mint authority", "import { setAuthority, AuthorityType } from '@solana/spl-token';\nawait setAuthority(connection, payer, mint, currentAuthority, AuthorityType.MintTokens, newAuthority);"),
]
for name, desc, code in TOKEN_EXTRA:
    records.append(make_rec(
        f"### Question\nHow do I {desc.lower()} in TypeScript?\n\n### Answer\n```typescript\n{code}\n```",
        "token_operations"))

# ── 5. Event handling (10 records) ──
for camel, pascal, fields in ENTITIES:
    records.append(make_rec(
        f"### Question\nHow do I listen for events from the `{pascal}` program in TypeScript?\n\n### Answer\n```typescript\n// Subscribe to events\nconst listener = program.addEventListener('{pascal}Event', (event, slot) => {{\n  console.log(`[Slot ${{slot}}] {pascal} event:`, event);\n}});\n\n// Later: remove listener\nawait program.removeEventListener(listener);\n\n// Parse events from transaction logs\nconst tx = await connection.getTransaction(sig, {{ maxSupportedTransactionVersion: 0 }});\nconst events = program.coder.events.decode(tx.meta.logMessages);\n```",
        "event_handling"))

EVENT_PATTERNS = [
    ("websocket", "How do I use WebSocket subscriptions in Solana?",
     "```typescript\n// Account change subscription\nconst subId = connection.onAccountChange(\n  accountPubkey,\n  (accountInfo) => {\n    console.log('Account changed:', accountInfo.data);\n  },\n  'confirmed'\n);\n\n// Program subscription (all accounts)\nconst progSub = connection.onProgramAccountChange(\n  programId,\n  (keyedAccountInfo) => {\n    console.log('Key:', keyedAccountInfo.accountId.toBase58());\n  }\n);\n\n// Log subscription\nconst logSub = connection.onLogs(programId, (logs) => {\n  console.log('Logs:', logs.logs);\n});\n\n// Unsubscribe\nawait connection.removeAccountChangeListener(subId);\n```"),
    ("parse_logs", "How do I parse Anchor events from transaction logs?",
     "```typescript\nimport { BorshCoder, EventParser } from '@coral-xyz/anchor';\n\nconst coder = new BorshCoder(idl);\nconst parser = new EventParser(programId, coder);\n\nconst tx = await connection.getTransaction(signature, {\n  maxSupportedTransactionVersion: 0,\n});\n\nconst events = parser.parseLogs(tx.meta.logMessages);\nfor (const event of events) {\n  console.log('Event name:', event.name);\n  console.log('Event data:', event.data);\n}\n```"),
    ("slot_subscribe", "How do I subscribe to slot updates?",
     "```typescript\nconnection.onSlotChange((slotInfo) => {\n  console.log('Slot:', slotInfo.slot);\n  console.log('Parent:', slotInfo.parent);\n  console.log('Root:', slotInfo.root);\n});\n```"),
    ("signature_subscribe", "How do I wait for a specific transaction?",
     "```typescript\nconst { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash();\n\nawait connection.confirmTransaction({\n  signature: txSignature,\n  blockhash,\n  lastValidBlockHeight,\n}, 'confirmed');\n\n// Or with callback\nconnection.onSignature(txSignature, (result) => {\n  if (result.err) console.error('Failed:', result.err);\n  else console.log('Confirmed!');\n});\n```"),
    ("helius_webhooks", "How do I set up Helius webhooks for program events?",
     "```typescript\n// Helius provides webhooks for real-time program monitoring\nconst response = await fetch('https://api.helius.xyz/v0/webhooks', {\n  method: 'POST',\n  headers: { 'Content-Type': 'application/json' },\n  body: JSON.stringify({\n    webhookURL: 'https://myserver.com/webhook',\n    transactionTypes: ['Any'],\n    accountAddresses: [programId.toBase58()],\n    webhookType: 'enhanced',\n  }),\n});\n```"),
]
for name, q, a in EVENT_PATTERNS:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "event_handling"))

# ── 6. Bankrun testing (15 records) ──
BANKRUN = [
    ("setup", "How do I set up bankrun for Solana testing?",
     "```typescript\nimport { start } from 'solana-bankrun';\nimport { PublicKey } from '@solana/web3.js';\n\nconst programId = new PublicKey('YOUR_PROGRAM_ID');\nconst context = await start(\n  [{ name: 'my_program', programId }],\n  []  // Initial accounts\n);\n\nconst client = context.banksClient;\nconst payer = context.payer;\n```"),
    ("process_tx", "How do I process transactions in bankrun?",
     "```typescript\nconst tx = new Transaction().add(myInstruction);\ntx.recentBlockhash = context.lastBlockhash;\ntx.sign(payer);\n\nawait client.processTransaction(tx);\n\n// Fetch account after\nconst account = await client.getAccount(accountPubkey);\nconsole.log('Data:', account.data);\n```"),
    ("clock", "How do I manipulate time in bankrun tests?",
     "```typescript\n// Get current clock\nconst clock = await client.getClock();\n\n// Fast-forward time\nclock.unixTimestamp = BigInt(Math.floor(Date.now() / 1000) + 86400);\nclock.slot = clock.slot + 100n;\ncontext.setClock(clock);\n\n// Now test time-dependent logic\nawait client.processTransaction(tx);\n```"),
    ("set_account", "How do I set up account state in bankrun?",
     "```typescript\nimport { start, BanksClient } from 'solana-bankrun';\n\n// Pre-populate accounts\nconst context = await start(programs, [\n  {\n    address: myAccountPubkey,\n    info: {\n      lamports: 1_000_000_000,\n      data: Buffer.from(serializedData),\n      owner: programId,\n      executable: false,\n    },\n  },\n]);\n```"),
    ("vs_anchor_test", "What's the difference between bankrun and anchor test?",
     "| Feature | anchor test | bankrun |\n|---|---|---|\n| Speed | Slow (spawns validator) | Fast (in-process) |\n| Clock control | No | Yes |\n| Account injection | No | Yes |\n| CPI support | Full | Full |\n| Program deploy | Automatic | Manual |\n| Logs | solana logs | In-process |\n\nUse **bankrun** for unit tests (fast, deterministic). Use **anchor test** for integration/E2E."),
    ("error_testing", "How do I test for expected errors in bankrun?",
     "```typescript\ntry {\n  await client.processTransaction(badTx);\n  throw new Error('Should have failed');\n} catch (e) {\n  // Check error type\n  expect(e.message).toContain('custom program error: 0x1770');\n}\n\n// Or with chai\nimport { expect } from 'chai';\nawait expect(client.processTransaction(badTx)).to.be.rejected;\n```"),
    ("multiple_signers", "How do I test with multiple signers in bankrun?",
     "```typescript\nconst alice = Keypair.generate();\nconst bob = Keypair.generate();\n\n// Fund accounts\ncontext.setAccount(alice.publicKey, {\n  lamports: 10_000_000_000,\n  data: Buffer.alloc(0),\n  owner: SystemProgram.programId,\n  executable: false,\n});\n\nconst tx = new Transaction().add(multiSigInstruction);\ntx.sign(alice, bob);\nawait client.processTransaction(tx);\n```"),
]
for name, q, a in BANKRUN:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "bankrun_testing"))

# Bankrun with Anchor
BANKRUN_ANCHOR = [
    ("anchor_bankrun", "How do I use bankrun with Anchor?",
     "```typescript\nimport { startAnchor } from 'solana-bankrun';\nimport { BankrunProvider } from 'anchor-bankrun';\nimport { Program } from '@coral-xyz/anchor';\n\nconst context = await startAnchor('.', [], []);\nconst provider = new BankrunProvider(context);\nconst program = new Program(idl, provider);\n\n// Now use program.methods as usual\nawait program.methods\n  .initialize()\n  .accounts({ ... })\n  .rpc();\n```"),
]
for name, q, a in BANKRUN_ANCHOR:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "bankrun_testing"))

# ── 7. Error handling in clients (10 records) ──
CLIENT_ERRORS = [
    ("catch_anchor", "How do I catch Anchor errors in TypeScript?",
     "```typescript\nimport { AnchorError, ProgramError } from '@coral-xyz/anchor';\n\ntry {\n  await program.methods.myInstruction().rpc();\n} catch (e) {\n  if (e instanceof AnchorError) {\n    console.log('Error code:', e.error.errorCode.number);  // e.g., 6000\n    console.log('Error name:', e.error.errorCode.code);    // e.g., 'InsufficientFunds'\n    console.log('Message:', e.error.errorMessage);\n    console.log('Logs:', e.logs);\n  } else if (e instanceof ProgramError) {\n    console.log('Program error:', e.code);\n  } else {\n    console.log('Unknown error:', e);\n  }\n}\n```"),
    ("send_tx_error", "How do I handle SendTransactionError?",
     "```typescript\nimport { SendTransactionError } from '@solana/web3.js';\n\ntry {\n  await sendAndConfirmTransaction(connection, tx, [payer]);\n} catch (e) {\n  if (e instanceof SendTransactionError) {\n    console.log('Logs:', e.logs);\n    console.log('Message:', e.message);\n    // Parse the custom error code from logs\n    const errorMatch = e.logs?.find(l => l.includes('custom program error'));\n  }\n}\n```"),
    ("timeout_handling", "How do I handle transaction timeout?",
     "```typescript\nasync function sendWithTimeout(connection, tx, signers, timeoutMs = 30000) {\n  const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash();\n  tx.recentBlockhash = blockhash;\n  \n  const sig = await connection.sendTransaction(tx, signers);\n  \n  const result = await Promise.race([\n    connection.confirmTransaction({ signature: sig, blockhash, lastValidBlockHeight }),\n    new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout')), timeoutMs))\n  ]);\n  \n  return sig;\n}\n```"),
    ("preflight_error", "What does 'Simulation failed' mean?",
     "Preflight simulation runs your transaction before sending. If it fails:\n\n```typescript\ntry {\n  await program.methods.myInstruction().rpc();\n} catch (e) {\n  // Disable preflight to see on-chain error\n  await program.methods.myInstruction().rpc({\n    skipPreflight: true,  // Send anyway\n  });\n}\n```\n\n**Warning:** `skipPreflight: true` sends the transaction even if simulation fails. Use only for debugging — the transaction will still fail on-chain but you'll get better logs."),
    ("custom_error_map", "How do I create a custom error mapping?",
     "```typescript\nconst ERROR_MAP: Record<number, string> = {\n  6000: 'Insufficient funds for this operation',\n  6001: 'Unauthorized: you are not the owner',\n  6002: 'Pool is currently paused',\n  6003: 'Slippage tolerance exceeded',\n};\n\nfunction getErrorMessage(e: unknown): string {\n  if (e instanceof AnchorError) {\n    return ERROR_MAP[e.error.errorCode.number] || e.error.errorMessage;\n  }\n  return String(e);\n}\n```"),
]
for name, q, a in CLIENT_ERRORS:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "client_errors"))

# ── 8. RPC optimization (10 records) ──
RPC_OPT = [
    ("batch_requests", "How do I batch RPC requests?",
     "```typescript\n// Fetch multiple accounts in one call\nconst accounts = await connection.getMultipleAccountsInfo([\n  pubkey1, pubkey2, pubkey3, pubkey4, pubkey5,\n]);\n\n// With Anchor\nconst results = await program.account.myStruct.fetchMultiple([\n  pda1, pda2, pda3,\n]);\n```"),
    ("data_slice", "How do I fetch only part of an account's data?",
     "```typescript\n// Fetch only specific bytes (e.g., first 40 bytes)\nconst accounts = await connection.getProgramAccounts(programId, {\n  dataSlice: { offset: 0, length: 40 },  // Only fetch 40 bytes\n  filters: [\n    { dataSize: 200 },  // Filter by account size\n  ],\n});\n```\n\nUseful for fetching many accounts when you only need specific fields."),
    ("memcmp_filter", "How do I filter getProgramAccounts efficiently?",
     "```typescript\nconst accounts = await connection.getProgramAccounts(programId, {\n  filters: [\n    { dataSize: 165 },  // TokenAccount size\n    { memcmp: {\n      offset: 32,  // Mint field offset\n      bytes: mintPubkey.toBase58(),\n    }},\n  ],\n});\n```\n\nAlways use `dataSize` + `memcmp` filters to reduce RPC load. Without filters, getProgramAccounts fetches ALL accounts."),
    ("websocket_vs_polling", "Should I use WebSockets or polling?",
     "**WebSockets** (real-time):\n```typescript\nconnection.onAccountChange(pubkey, callback, 'confirmed');\n```\n\n**Polling** (periodic):\n```typescript\nsetInterval(async () => {\n  const info = await connection.getAccountInfo(pubkey);\n}, 5000);\n```\n\nUse WebSockets for real-time UIs. Use polling for background jobs where slight delay is OK."),
    ("rpc_caching", "How do I cache RPC responses?",
     "```typescript\n// Simple in-memory cache\nconst cache = new Map<string, { data: any, expiry: number }>();\n\nasync function cachedFetch(key: string, fetcher: () => Promise<any>, ttlMs = 5000) {\n  const cached = cache.get(key);\n  if (cached && Date.now() < cached.expiry) return cached.data;\n  \n  const data = await fetcher();\n  cache.set(key, { data, expiry: Date.now() + ttlMs });\n  return data;\n}\n\n// Usage\nconst balance = await cachedFetch(\n  `balance:${pubkey}`,\n  () => connection.getBalance(pubkey),\n  3000\n);\n```"),
]
for name, q, a in RPC_OPT:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "rpc_optimization"))

# ── Write output ──
PROCESSED.mkdir(parents=True, exist_ok=True)
out = PROCESSED / "synthetic-bulk9.jsonl"
with open(out, "w") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"Wrote {len(records)} records to {out}")
cats = {}
for r in records:
    c = r["metadata"]["category"]
    cats[c] = cats.get(c, 0) + 1
for c, n in sorted(cats.items()):
    print(f"  {c}: {n}")
