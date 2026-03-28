#!/usr/bin/env python3
"""Bulk synthetic data generator — Part 12: Testing, deployment, devops.
Target: ~100 records.
"""
import hashlib, json
from pathlib import Path

PROCESSED = Path(__file__).parent.parent / "data" / "processed"

def make_rec(content, category, lang="rust"):
    return {
        "id": hashlib.sha256(content.encode()).hexdigest(),
        "source": "synthetic/glan", "source_type": "synthetic",
        "content": content, "language": lang, "license": "synthetic-original",
        "metadata": {"method": "glan", "category": category, "anchor_version_class": "modern"},
    }

records = []

# ── 1. Anchor test patterns (20) ──
PROGRAMS = ["marketplace", "staking", "lending", "governance", "vault"]
TEST_PATTERNS = [
    ("init_test", "How do I write a basic initialization test for {prog}?",
     'describe("{prog}", () => {{\n  const provider = anchor.AnchorProvider.env();\n  anchor.setProvider(provider);\n  const program = anchor.workspace.{Prog} as Program<{Prog}>;\n\n  it("initializes {prog}", async () => {{\n    const [pda] = PublicKey.findProgramAddressSync(\n      [Buffer.from("{prog}")],\n      program.programId\n    );\n\n    await program.methods\n      .initialize()\n      .accounts({{\n        {prog}State: pda,\n        authority: provider.wallet.publicKey,\n        systemProgram: SystemProgram.programId,\n      }})\n      .rpc();\n\n    const state = await program.account.{prog}State.fetch(pda);\n    assert.ok(state.authority.equals(provider.wallet.publicKey));\n  }});\n}});'),
    ("error_test", "How do I test that {prog} rejects unauthorized access?",
     'it("rejects unauthorized {prog} access", async () => {{\n  const unauthorized = Keypair.generate();\n  \n  try {{\n    await program.methods\n      .adminAction()\n      .accounts({{\n        {prog}State: pda,\n        authority: unauthorized.publicKey,\n      }})\n      .signers([unauthorized])\n      .rpc();\n    assert.fail("Should have thrown");\n  }} catch (e) {{\n    assert.ok(e instanceof AnchorError);\n    assert.equal(e.error.errorCode.code, "ConstraintHasOne");\n  }}\n}});'),
    ("state_test", "How do I test state changes in {prog}?",
     'it("updates {prog} state correctly", async () => {{\n  const newValue = new BN(1000);\n  \n  await program.methods\n    .update(newValue)\n    .accounts({{\n      {prog}State: pda,\n      authority: provider.wallet.publicKey,\n    }})\n    .rpc();\n\n  const state = await program.account.{prog}State.fetch(pda);\n  assert.ok(state.value.eq(newValue));\n}});'),
    ("multi_ix_test", "How do I test multiple instructions in one {prog} transaction?",
     'it("executes multiple {prog} instructions atomically", async () => {{\n  const tx = new Transaction();\n  \n  tx.add(\n    await program.methods.stepOne(args1).accounts({{...}}).instruction(),\n    await program.methods.stepTwo(args2).accounts({{...}}).instruction(),\n  );\n\n  await provider.sendAndConfirm(tx);\n  \n  const state = await program.account.{prog}State.fetch(pda);\n  assert.ok(state.completed);\n}});'),
]

for prog in PROGRAMS:
    Prog = prog.title()
    for name, q_template, a_template in TEST_PATTERNS:
        q = q_template.format(prog=prog, Prog=Prog)
        a = a_template.format(prog=prog, Prog=Prog)
        records.append(make_rec(
            f"### Question\n{q}\n\n### Answer\n```typescript\n{a}\n```",
            "testing", "ts"
        ))

# ── 2. Deployment (15) ──
DEPLOY = [
    ("deploy_devnet", "How do I deploy an Anchor program to devnet?",
     "```bash\n# Configure for devnet\nsolana config set --url devnet\n\n# Airdrop SOL for deployment\nsolana airdrop 5\n\n# Build and deploy\nanchor build\nanchor deploy --provider.cluster devnet\n\n# Or in one step:\nanchor test --provider.cluster devnet --skip-local-validator\n```\n\nUpdate `Anchor.toml`:\n```toml\n[provider]\ncluster = \"devnet\"\nwallet = \"~/.config/solana/id.json\"\n```"),
    ("deploy_mainnet", "How do I deploy to mainnet safely?",
     "```bash\n# 1. Verify program on devnet first\nanchor verify <PROGRAM_ID> --provider.cluster devnet\n\n# 2. Build with mainnet config\nanchor build -- --features mainnet\n\n# 3. Deploy with explicit wallet\nanchor deploy --provider.cluster mainnet \\\n  --provider.wallet /path/to/deployer-keypair.json\n\n# 4. Verify on-chain\nanchor verify <PROGRAM_ID> --provider.cluster mainnet\n\n# 5. Consider using a multisig as upgrade authority\nsolana program set-upgrade-authority <PROGRAM_ID> \\\n  --new-upgrade-authority <MULTISIG_ADDRESS>\n```"),
    ("upgrade_program", "How do I upgrade a deployed program?",
     "```bash\n# Build new version\nanchor build\n\n# Deploy upgrade\nanchor upgrade <PROGRAM_ID> \\\n  --program-filepath target/deploy/my_program.so \\\n  --provider.cluster devnet\n\n# Or using solana CLI:\nsolana program deploy target/deploy/my_program.so \\\n  --program-id <PROGRAM_ID> \\\n  --upgrade-authority /path/to/authority.json\n```"),
    ("make_immutable", "How do I make a program immutable?",
     "```bash\n# WARNING: This is IRREVERSIBLE\nsolana program set-upgrade-authority <PROGRAM_ID> --final\n\n# After this, the program can NEVER be upgraded.\n# Do this only when you're 100% confident the program is correct.\n# Consider a timelock governance process before making immutable.\n```"),
    ("buffer_deploy", "How do I use buffer accounts for deployment?",
     "```bash\n# Write program to buffer (useful for large programs)\nsolana program write-buffer target/deploy/my_program.so\n# Returns: Buffer: <BUFFER_ADDRESS>\n\n# Deploy from buffer\nsolana program deploy --buffer <BUFFER_ADDRESS> \\\n  --program-id <PROGRAM_ID>\n\n# Close unused buffer to reclaim SOL\nsolana program close --buffers\n```"),
    ("verify_program", "How do I verify a deployed program matches source?",
     "```bash\n# Anchor verify (compares on-chain bytecode with local build)\nanchor verify <PROGRAM_ID> --provider.cluster mainnet\n\n# This rebuilds from source in a Docker container\n# and compares the bytecode hash with what's deployed.\n\n# Check on Solana Explorer:\n# https://explorer.solana.com/address/<PROGRAM_ID>\n# Look for \"Verified\" badge\n```"),
    ("program_info", "How do I check program deployment info?",
     "```bash\n# View program details\nsolana program show <PROGRAM_ID>\n\n# Output includes:\n# - Program Id\n# - Owner (BPF Loader)\n# - ProgramData Address\n# - Authority (upgrade authority)\n# - Last Deployed Slot\n# - Data Length\n```"),
    ("keypair_management", "How do I manage program keypairs?",
     "```bash\n# Generate new program keypair\nsolana-keygen new -o target/deploy/my_program-keypair.json\n\n# Get program ID from keypair\nsolana address -k target/deploy/my_program-keypair.json\n\n# Set in Anchor.toml:\n[programs.devnet]\nmy_program = \"<PROGRAM_ID>\"\n\n# And in lib.rs:\ndeclare_program!(\"<PROGRAM_ID>\");\n```"),
    ("anchor_toml", "What are the important Anchor.toml settings?",
     "```toml\n[features]\nseeds = true             # Verify PDA seeds\nskip-lint = false        # Keep linting\n\n[programs.devnet]\nmy_program = \"Fg6PaFpo...\"\n\n[programs.mainnet]\nmy_program = \"Fg6PaFpo...\"\n\n[registry]\nurl = \"https://api.apr.dev\"\n\n[provider]\ncluster = \"localnet\"\nwallet = \"~/.config/solana/id.json\"\n\n[scripts]\ntest = \"yarn run ts-mocha -p ./tsconfig.json -t 1000000 tests/**/*.ts\"\n\n[test]\nstartup_wait = 10000\n\n[test.validator]\nurl = \"https://api.mainnet-beta.solana.com\"  # Fork mainnet\n\n[[test.validator.clone]]\naddress = \"TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA\"\n```"),
]
for name, q, a in DEPLOY:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "deployment", "md"))

# ── 3. Local development (10) ──
LOCAL_DEV = [
    ("local_validator", "How do I set up a local Solana validator?",
     "```bash\n# Start test validator\nsolana-test-validator\n\n# With specific programs cloned from mainnet\nsolana-test-validator \\\n  --clone TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA \\\n  --clone ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL \\\n  --url https://api.mainnet-beta.solana.com\n\n# With specific accounts cloned\nsolana-test-validator \\\n  --clone <ACCOUNT_ADDRESS> \\\n  --url mainnet-beta\n\n# Reset ledger\nsolana-test-validator --reset\n```"),
    ("airdrop", "How do I get SOL for testing?",
     "```bash\n# Devnet (max 5 SOL per request)\nsolana airdrop 5 --url devnet\n\n# Local validator (unlimited)\nsolana airdrop 100 --url localhost\n\n# In TypeScript:\nawait connection.requestAirdrop(wallet.publicKey, 5 * LAMPORTS_PER_SOL);\nawait connection.confirmTransaction(sig);\n```"),
    ("clone_accounts", "How do I clone mainnet accounts to local validator?",
     "```bash\n# Clone a program\nsolana-test-validator --clone <PROGRAM_ID> --url mainnet-beta\n\n# Clone multiple accounts\nsolana-test-validator \\\n  --clone <ACCOUNT_1> \\\n  --clone <ACCOUNT_2> \\\n  --clone <PROGRAM_ID> \\\n  --url mainnet-beta\n\n# Or dump an account to file and load it:\nsolana account <ADDRESS> --output json > account.json\nsolana-test-validator --account <ADDRESS> account.json\n```"),
    ("anchor_localnet", "How do I use Anchor's localnet?",
     "```bash\n# anchor test automatically:\n# 1. Starts solana-test-validator\n# 2. Builds your program\n# 3. Deploys it\n# 4. Runs tests\n# 5. Stops validator\n\nanchor test\n\n# Keep validator running after tests:\nanchor test --detach\n\n# Then connect to it:\nsolana config set --url localhost\nsolana logs <PROGRAM_ID>\n```"),
    ("idl_generation", "How do I generate and use the IDL?",
     "```bash\n# Build generates IDL automatically\nanchor build\n# Output: target/idl/my_program.json\n\n# Upload IDL to chain (for clients to fetch)\nanchor idl init <PROGRAM_ID> --filepath target/idl/my_program.json\n\n# Update IDL\nanchor idl upgrade <PROGRAM_ID> --filepath target/idl/my_program.json\n\n# Fetch IDL from chain\nanchor idl fetch <PROGRAM_ID>\n```\n\nIn TypeScript:\n```typescript\n// IDL is auto-imported from target/types/\nimport { MyProgram } from '../target/types/my_program';\n```"),
]
for name, q, a in LOCAL_DEV:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "local_development", "md"))

# ── 4. CI/CD (10) ──
CICD = [
    ("github_actions", "How do I set up GitHub Actions for an Anchor project?",
     "```yaml\n# .github/workflows/test.yml\nname: Anchor Tests\n\non:\n  push:\n    branches: [main]\n  pull_request:\n    branches: [main]\n\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      \n      - name: Install Solana\n        run: |\n          sh -c \"$(curl -sSfL https://release.anza.xyz/stable/install)\"\n          echo \"$HOME/.local/share/solana/install/active_release/bin\" >> $GITHUB_PATH\n      \n      - name: Install Anchor\n        run: |\n          cargo install --git https://github.com/coral-xyz/anchor avm --force\n          avm install latest\n          avm use latest\n      \n      - name: Install deps\n        run: yarn install\n      \n      - name: Build\n        run: anchor build\n      \n      - name: Test\n        run: anchor test\n```"),
    ("caching", "How do I cache Solana/Anchor builds in CI?",
     "```yaml\n- name: Cache Solana\n  uses: actions/cache@v4\n  with:\n    path: |\n      ~/.local/share/solana\n      ~/.cache/solana\n    key: solana-${{ runner.os }}-stable\n\n- name: Cache Cargo\n  uses: actions/cache@v4\n  with:\n    path: |\n      ~/.cargo/registry\n      ~/.cargo/git\n      target\n    key: cargo-${{ runner.os }}-${{ hashFiles('**/Cargo.lock') }}\n\n- name: Cache Node\n  uses: actions/cache@v4\n  with:\n    path: node_modules\n    key: node-${{ runner.os }}-${{ hashFiles('yarn.lock') }}\n```"),
    ("auto_deploy", "How do I auto-deploy on merge to main?",
     "```yaml\n# .github/workflows/deploy.yml\nname: Deploy to Devnet\n\non:\n  push:\n    branches: [main]\n\njobs:\n  deploy:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      # ... install steps ...\n      \n      - name: Setup keypair\n        run: echo \"${{ secrets.DEPLOY_KEYPAIR }}\" > keypair.json\n      \n      - name: Deploy\n        run: |\n          solana config set --url devnet\n          anchor build\n          anchor deploy --provider.cluster devnet \\\n            --provider.wallet keypair.json\n      \n      - name: Smoke test\n        run: |\n          # Run a simple test against devnet\n          yarn test:smoke\n      \n      - name: Cleanup\n        if: always()\n        run: rm -f keypair.json\n```"),
    ("security_scan", "How do I add security scanning to CI?",
     "```yaml\n- name: Cargo audit\n  run: |\n    cargo install cargo-audit\n    cargo audit\n\n- name: Clippy lints\n  run: cargo clippy -- -D warnings\n\n- name: Soteria scan (optional)\n  run: |\n    # Soteria is a Solana-specific static analyzer\n    soteria -analyzeAll .\n```"),
]
for name, q, a in CICD:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "cicd", "md"))

# ── 5. Security auditing tools (10) ──
AUDIT = [
    ("trident_fuzz", "How do I use Trident for fuzz testing Anchor programs?",
     "```bash\n# Install Trident\ncargo install trident-cli\n\n# Initialize in your project\ntrident init\n\n# Write fuzz target (trident-tests/fuzz_tests/fuzz_0/fuzz_instructions.rs)\n# Trident generates templates automatically\n\n# Run fuzzer\ntrident fuzz run fuzz_0\n```\n\nTrident generates random instruction sequences and checks for:\n- Panics / crashes\n- Unexpected error codes\n- Invariant violations"),
    ("cargo_audit", "How do I check for known vulnerabilities?",
     "```bash\n# Install\ncargo install cargo-audit\n\n# Run audit\ncargo audit\n\n# Fix vulnerabilities\ncargo audit fix\n\n# In CI:\ncargo audit --deny warnings\n```"),
    ("audit_checklist_code", "What code patterns should I look for in a security review?",
     "```rust\n// 1. Missing signer check\n/// CHECK: ← Red flag if no validation explained\npub authority: AccountInfo<'info>,\n\n// 2. Unchecked arithmetic\nlet total = a + b;  // Should use checked_add\n\n// 3. Missing owner check\nlet data = AccountInfo::try_from(account)?;  // No owner verification\n\n// 4. Hardcoded addresses\nlet admin = Pubkey::from_str(\"...\").unwrap();  // Should be in account state\n\n// 5. No close protection\n#[account(mut)]  // Missing `close = receiver` or close guard\npub old_account: Account<'info, OldData>,\n\n// 6. init_if_needed without user-specific seeds\n#[account(init_if_needed, seeds = [b\"global\"], ...)]  // Dangerous!\n```"),
]
for name, q, a in AUDIT:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "security_audit", "md"))

# ── 6. Monitoring (7) ──
MONITORING = [
    ("helius_webhooks", "How do I monitor program activity with Helius webhooks?",
     "```typescript\n// Set up a webhook to monitor your program\nconst webhook = await fetch('https://api.helius.xyz/v0/webhooks?api-key=YOUR_KEY', {\n  method: 'POST',\n  headers: { 'Content-Type': 'application/json' },\n  body: JSON.stringify({\n    webhookURL: 'https://yourserver.com/webhook',\n    transactionTypes: ['Any'],\n    accountAddresses: [PROGRAM_ID],\n    webhookType: 'enhanced',\n  }),\n});\n\n// Webhook payload includes parsed transaction data\n// Set up an Express handler:\napp.post('/webhook', (req, res) => {\n  const txns = req.body;\n  for (const tx of txns) {\n    console.log('Type:', tx.type);\n    console.log('Fee:', tx.fee);\n    console.log('Accounts:', tx.accountData);\n  }\n  res.sendStatus(200);\n});\n```"),
    ("health_check", "How do I implement a health check for my Solana service?",
     "```typescript\napp.get('/health', async (req, res) => {\n  const checks = {\n    rpc: false,\n    program: false,\n    timestamp: new Date().toISOString(),\n  };\n  \n  try {\n    // Check RPC\n    const slot = await connection.getSlot();\n    checks.rpc = slot > 0;\n    \n    // Check program exists\n    const programInfo = await connection.getAccountInfo(PROGRAM_ID);\n    checks.program = programInfo?.executable === true;\n    \n    const healthy = Object.values(checks).every(v => v === true || typeof v === 'string');\n    res.status(healthy ? 200 : 503).json(checks);\n  } catch (e) {\n    res.status(503).json({ ...checks, error: e.message });\n  }\n});\n```"),
    ("transaction_monitor", "How do I monitor transactions for my program?",
     "```typescript\n// Real-time monitoring via WebSocket\nconst subId = connection.onLogs(\n  new PublicKey(PROGRAM_ID),\n  (logs, ctx) => {\n    console.log(`[Slot ${ctx.slot}] Transaction:`, logs.signature);\n    \n    // Check for errors\n    if (logs.err) {\n      console.error('Error:', logs.err);\n      // Send alert to Discord/Slack\n    }\n    \n    // Parse specific events\n    for (const log of logs.logs) {\n      if (log.includes('Program log:')) {\n        console.log('Log:', log);\n      }\n    }\n  },\n  'confirmed'\n);\n```"),
]
for name, q, a in MONITORING:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "monitoring", "ts"))

# ── Write output ──
PROCESSED.mkdir(parents=True, exist_ok=True)
out = PROCESSED / "synthetic-bulk12.jsonl"
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
