#!/usr/bin/env python3
"""Bulk synthetic data generator — Part 6: Account Validation patterns.

Target: 150 records covering 13 account validation topics.
Uses parameterized entity templates to multiply output.
"""
import hashlib
import json
from pathlib import Path

PROCESSED = Path(__file__).parent.parent / "data" / "processed"
OUT_FILE = PROCESSED / "synthetic-bulk6.jsonl"

# ---------------------------------------------------------------------------
# Entities for parameterized templates
# ---------------------------------------------------------------------------
ENTITIES = [
    ("game", "Game", [("authority", "Pubkey"), ("score", "u64"), ("level", "u8")]),
    ("marketplace", "Marketplace", [("authority", "Pubkey"), ("fee_bps", "u16"), ("total_listings", "u64")]),
    ("pool", "Pool", [("authority", "Pubkey"), ("token_a_reserve", "u64"), ("token_b_reserve", "u64")]),
    ("vault", "Vault", [("authority", "Pubkey"), ("balance", "u64"), ("locked", "bool")]),
    ("auction", "Auction", [("authority", "Pubkey"), ("highest_bid", "u64"), ("end_time", "i64")]),
    ("dao", "Dao", [("authority", "Pubkey"), ("proposal_count", "u32"), ("treasury_balance", "u64")]),
    ("staking", "StakePool", [("authority", "Pubkey"), ("total_staked", "u64"), ("reward_rate", "u64")]),
    ("escrow", "Escrow", [("authority", "Pubkey"), ("amount", "u64"), ("deadline", "i64")]),
    ("lottery", "Lottery", [("authority", "Pubkey"), ("ticket_price", "u64"), ("total_tickets", "u32")]),
    ("lending", "LendingPool", [("authority", "Pubkey"), ("total_deposits", "u64"), ("total_borrows", "u64")]),
    ("registry", "Registry", [("authority", "Pubkey"), ("entry_count", "u32"), ("is_frozen", "bool")]),
    ("campaign", "Campaign", [("authority", "Pubkey"), ("goal", "u64"), ("raised", "u64")]),
    ("raffle", "Raffle", [("authority", "Pubkey"), ("ticket_count", "u32"), ("prize_amount", "u64")]),
    ("guild", "Guild", [("authority", "Pubkey"), ("member_count", "u16"), ("level", "u8")]),
    ("bridge", "Bridge", [("authority", "Pubkey"), ("nonce", "u64"), ("is_paused", "bool")]),
]

SUB_ENTITIES = [
    ("player", "Player", [("owner", "Pubkey"), ("name_hash", "[u8; 32]"), ("xp", "u64")]),
    ("config", "Config", [("admin", "Pubkey"), ("fee_bps", "u16"), ("bump", "u8")]),
    ("token_vault", "TokenVault", [("mint", "Pubkey"), ("amount", "u64"), ("bump", "u8")]),
    ("listing", "Listing", [("seller", "Pubkey"), ("price", "u64"), ("is_active", "bool")]),
    ("bid", "Bid", [("bidder", "Pubkey"), ("amount", "u64"), ("timestamp", "i64")]),
    ("proposal", "Proposal", [("proposer", "Pubkey"), ("vote_count", "u64"), ("status", "u8")]),
    ("stake_entry", "StakeEntry", [("staker", "Pubkey"), ("amount", "u64"), ("start_time", "i64")]),
    ("receipt", "Receipt", [("payer", "Pubkey"), ("amount", "u64"), ("bump", "u8")]),
    ("ticket", "Ticket", [("buyer", "Pubkey"), ("number", "u32"), ("bump", "u8")]),
    ("position", "Position", [("owner", "Pubkey"), ("collateral", "u64"), ("debt", "u64")]),
]


def make_id(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def make_record(content: str, category: str) -> dict:
    return {
        "id": make_id(content),
        "source": "synthetic/glan",
        "source_type": "synthetic",
        "content": content,
        "language": "rust",
        "license": "synthetic-original",
        "metadata": {
            "method": "glan",
            "category": category,
            "anchor_version_class": "modern",
        },
    }


def fields_to_struct(name: str, fields: list[tuple[str, str]]) -> str:
    lines = [f"    pub {f}: {t}," for f, t in fields]
    return f"pub struct {name} {{\n" + "\n".join(lines) + "\n}"


def fields_to_init_space(name: str, fields: list[tuple[str, str]]) -> str:
    lines = [f"    pub {f}: {t}," for f, t in fields]
    return (
        "#[account]\n#[derive(InitSpace)]\n"
        f"pub struct {name} {{\n" + "\n".join(lines) + "\n}"
    )


records: list[dict] = []

# ═══════════════════════════════════════════════════════════════════════════════
# 1. has_one / has_many constraints (10 records)
# ═══════════════════════════════════════════════════════════════════════════════

HAS_ONE_PAIRS = [
    (ENTITIES[0], SUB_ENTITIES[0]),  # Game has_one Player
    (ENTITIES[1], SUB_ENTITIES[1]),  # Marketplace has_one Config
    (ENTITIES[2], SUB_ENTITIES[2]),  # Pool has_one TokenVault
    (ENTITIES[3], SUB_ENTITIES[1]),  # Vault has_one Config
    (ENTITIES[4], SUB_ENTITIES[4]),  # Auction has_one Bid
    (ENTITIES[5], SUB_ENTITIES[5]),  # Dao has_one Proposal
    (ENTITIES[6], SUB_ENTITIES[6]),  # StakePool has_one StakeEntry
    (ENTITIES[7], SUB_ENTITIES[7]),  # Escrow has_one Receipt
    (ENTITIES[8], SUB_ENTITIES[8]),  # Lottery has_one Ticket
    (ENTITIES[9], SUB_ENTITIES[9]),  # LendingPool has_one Position
]

for (p_snake, p_name, p_fields), (c_snake, c_name, c_fields) in HAS_ONE_PAIRS:
    q = (
        f"How do I use Anchor's `has_one` constraint to validate that a "
        f"`{p_name}` account owns a `{c_name}` account?"
    )
    a = f"""In modern Anchor (0.30+), use the `has_one` constraint in your `#[derive(Accounts)]` struct. The parent account must store the child's `Pubkey`, and `has_one` verifies they match.

```rust
use anchor_lang::prelude::*;

#[account]
#[derive(InitSpace)]
{fields_to_init_space(p_name, p_fields + [(c_snake, "Pubkey"), ("bump", "u8")])}

#[account]
#[derive(InitSpace)]
{fields_to_init_space(c_name, c_fields + [("bump", "u8")])}

#[derive(Accounts)]
pub struct Validate{p_name}<'info> {{
    #[account(mut)]
    pub authority: Signer<'info>,

    #[account(
        mut,
        has_one = authority,
        has_one = {c_snake},
        seeds = [b"{p_snake}", authority.key().as_ref()],
        bump = {p_snake}.bump,
    )]
    pub {p_snake}: Account<'info, {p_name}>,

    #[account(
        seeds = [b"{c_snake}", {p_snake}.key().as_ref()],
        bump = {c_snake}.bump,
    )]
    pub {c_snake}: Account<'info, {c_name}>,
}}
```

The `has_one = {c_snake}` constraint checks that `{p_snake}.{c_snake} == {c_snake}.key()`. If the keys don't match, the transaction fails with a `ConstraintHasOne` error. This prevents an attacker from passing in a `{c_name}` belonging to a different `{p_name}`."""
    content = f"### Question\n{q}\n\n### Answer\n{a}"
    records.append(make_record(content, "has_one_constraints"))

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Custom constraint expressions (10 records)
# ═══════════════════════════════════════════════════════════════════════════════

CONSTRAINT_SCENARIOS = [
    ("authority check", "vault.authority == authority.key()", "Vault", "vault",
     "Verifies the signer is the vault's recorded authority. This is equivalent to `has_one = authority` but written explicitly."),
    ("timestamp check", "auction.end_time > Clock::get()?.unix_timestamp", "Auction", "auction",
     "Ensures the auction has not ended yet. The Clock sysvar provides the current on-chain timestamp."),
    ("balance minimum", "pool.total_staked >= 1_000_000", "StakePool", "pool",
     "Requires a minimum staked balance before allowing the operation. Useful for governance thresholds."),
    ("state enum check", "escrow.status == EscrowStatus::Active", "Escrow", "escrow",
     "Only allows the instruction when the escrow is in an Active state. Prevents operations on settled or cancelled escrows."),
    ("combined constraints", "dao.proposal_count < 100 && dao.authority == authority.key()", "Dao", "dao",
     "Multiple conditions can be combined with `&&`. Both must be true or the transaction fails."),
    ("fee range", "marketplace.fee_bps <= 10_000", "Marketplace", "marketplace",
     "Validates fee basis points are within a valid range (0-100%). Prevents misconfiguration."),
    ("not frozen", "!registry.is_frozen @ RegistryError::Frozen", "Registry", "registry",
     "Uses the `@` syntax to provide a custom error code when the constraint fails."),
    ("goal not reached", "campaign.raised < campaign.goal", "Campaign", "campaign",
     "Only allows contributions while the campaign goal has not been reached."),
    ("non-zero amount", "raffle.ticket_count > 0 @ RaffleError::NoTickets", "Raffle", "raffle",
     "Ensures there is at least one ticket before drawing a winner. Custom error via `@`."),
    ("paused check", "!bridge.is_paused @ BridgeError::Paused", "Bridge", "bridge",
     "Prevents all operations when the bridge is paused. Important safety mechanism for cross-chain programs."),
]

for desc, expr, struct_name, acc_name, explanation in CONSTRAINT_SCENARIOS:
    q = f"How do I write a custom `#[account(constraint = ...)]` in Anchor for a {desc}?"
    a = f"""Use the `constraint` attribute in your Accounts struct. The expression must evaluate to `bool`, and you can optionally attach a custom error with `@`.

```rust
use anchor_lang::prelude::*;

#[derive(Accounts)]
pub struct Check{struct_name}<'info> {{
    #[account(mut)]
    pub authority: Signer<'info>,

    #[account(
        mut,
        constraint = {expr},
    )]
    pub {acc_name}: Account<'info, {struct_name}>,
}}
```

{explanation}

You can also combine `constraint` with other attributes like `seeds`, `has_one`, and `mut`:

```rust
#[account(
    mut,
    seeds = [b"{acc_name}", authority.key().as_ref()],
    bump = {acc_name}.bump,
    constraint = {expr},
)]
pub {acc_name}: Account<'info, {struct_name}>,
```

If the constraint expression evaluates to `false`, Anchor returns `ConstraintRaw` (or your custom error if using `@`)."""
    content = f"### Question\n{q}\n\n### Answer\n{a}"
    records.append(make_record(content, "custom_constraints"))

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Account close patterns (10 records)
# ═══════════════════════════════════════════════════════════════════════════════

CLOSE_TARGETS = [
    ("authority", "The rent-exempt lamports are returned to the original authority who created the account."),
    ("treasury", "Lamports go to a program-controlled treasury PDA, useful for collecting fees."),
    ("fee_receiver", "A designated fee receiver gets the reclaimed rent, common in marketplace programs."),
    ("dao_treasury", "The DAO treasury receives the lamports, keeping funds within governance control."),
    ("protocol_vault", "Protocol vault accumulates reclaimed rent as additional protocol revenue."),
]

for i, (e_snake, e_name, e_fields) in enumerate(ENTITIES[:10]):
    close_target, close_explanation = CLOSE_TARGETS[i % len(CLOSE_TARGETS)]
    q = f"How do I close a `{e_name}` account in Anchor and reclaim its rent to `{close_target}`?"
    a = f"""Use the `close` constraint in modern Anchor (0.30+). This zeroes the account data, transfers all lamports to the target, and sets the owner to the System Program.

```rust
use anchor_lang::prelude::*;

#[derive(Accounts)]
pub struct Close{e_name}<'info> {{
    #[account(mut)]
    pub {close_target}: Signer<'info>,

    #[account(
        mut,
        close = {close_target},
        has_one = authority,
        seeds = [b"{e_snake}", authority.key().as_ref()],
        bump = {e_snake}.bump,
    )]
    pub {e_snake}: Account<'info, {e_name}>,

    pub authority: Signer<'info>,
}}
```

{close_explanation}

Important security considerations:
1. **Data is zeroed** — the discriminator is set to a special `CLOSED_ACCOUNT_DISCRIMINATOR`, preventing resurrection attacks where someone re-initializes the account in the same transaction.
2. **All lamports are transferred** — the account becomes rent-ineligible and will be garbage-collected.
3. **Always verify authority** — use `has_one = authority` to ensure only the rightful owner can close.
4. **Close in the correct order** — if other accounts reference this one via `has_one`, close dependents first.

```rust
// If you need to close and verify state before closing:
pub fn close_{e_snake}(ctx: Context<Close{e_name}>) -> Result<()> {{
    let {e_snake} = &ctx.accounts.{e_snake};
    // Verify any preconditions before close
    require!(!{e_snake}.locked, {e_name}Error::AccountLocked);
    // The close happens automatically via the constraint
    Ok(())
}}
```"""
    content = f"### Question\n{q}\n\n### Answer\n{a}"
    records.append(make_record(content, "account_close"))

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Realloc patterns (10 records)
# ═══════════════════════════════════════════════════════════════════════════════

REALLOC_SCENARIOS = [
    ("adding a new field to", "Profile", "profile",
     [("authority", "Pubkey"), ("name", "String"), ("bio", "String"), ("bump", "u8")],
     [("authority", "Pubkey"), ("name", "String"), ("bio", "String"), ("avatar_uri", "String"), ("bump", "u8")],
     "avatar_uri: String", "#[max_len(200)]\n    pub avatar_uri: String,"),
    ("extending a vector in", "Whitelist", "whitelist",
     [("authority", "Pubkey"), ("addresses", "Vec<Pubkey>"), ("bump", "u8")],
     [("authority", "Pubkey"), ("addresses", "Vec<Pubkey>"), ("bump", "u8")],
     "addresses: Vec<Pubkey>", "/// Grows from max_len(50) to max_len(100)"),
    ("resizing a string in", "Metadata", "metadata",
     [("authority", "Pubkey"), ("name", "String"), ("uri", "String"), ("bump", "u8")],
     [("authority", "Pubkey"), ("name", "String"), ("uri", "String"), ("bump", "u8")],
     "uri: String", "/// URI grows from max_len(100) to max_len(256)"),
    ("upgrading schema of", "GameState", "game_state",
     [("authority", "Pubkey"), ("score", "u64"), ("bump", "u8")],
     [("authority", "Pubkey"), ("score", "u64"), ("achievements", "Vec<u8>"), ("last_played", "i64"), ("bump", "u8")],
     "achievements + last_played", "pub achievements: Vec<u8>,\n    pub last_played: i64,"),
    ("growing a log buffer in", "EventLog", "event_log",
     [("authority", "Pubkey"), ("events", "Vec<u8>"), ("bump", "u8")],
     [("authority", "Pubkey"), ("events", "Vec<u8>"), ("bump", "u8")],
     "events: Vec<u8>", "/// Event buffer grows from max_len(1024) to max_len(4096)"),
]

for i in range(10):
    scenario = REALLOC_SCENARIOS[i % len(REALLOC_SCENARIOS)]
    desc, struct_name, acc_name, old_fields, new_fields, change_desc, _ = scenario
    ent = ENTITIES[i]
    e_snake, e_name = ent[0], ent[1]

    q = f"How do I use `realloc` in Anchor to resize a `{struct_name}` account when {desc} it?"
    new_space_expr = f"8 + {struct_name}V2::INIT_SPACE"
    a = f"""Use the `realloc` constraint in modern Anchor (0.30+). This allows you to grow (or shrink) an existing account without closing and re-creating it.

```rust
use anchor_lang::prelude::*;

// Original struct
#[account]
#[derive(InitSpace)]
pub struct {struct_name} {{
{chr(10).join(f"    pub {f}: {t}," for f, t in old_fields)}
}}

// Updated struct with new fields
#[account]
#[derive(InitSpace)]
pub struct {struct_name}V2 {{
{chr(10).join(f"    pub {f}: {t}," for f, t in new_fields)}
}}

#[derive(Accounts)]
pub struct Resize{struct_name}<'info> {{
    #[account(mut)]
    pub authority: Signer<'info>,

    #[account(
        mut,
        realloc = {new_space_expr},
        realloc::payer = authority,
        realloc::zero = false,
        has_one = authority,
        seeds = [b"{acc_name}", authority.key().as_ref()],
        bump = {acc_name}.bump,
    )]
    pub {acc_name}: Account<'info, {struct_name}V2>,

    pub system_program: Program<'info, System>,
}}
```

Key points about `realloc`:
- **`realloc::payer`** — the account that pays for additional space (must be `mut` and a `Signer`).
- **`realloc::zero = false`** — set to `true` if you want new bytes zeroed. Usually `false` for performance.
- **Growing** — the payer provides additional lamports for rent-exemption.
- **Shrinking** — excess lamports are refunded to the payer.
- **Max 10KB increase** per realloc call per instruction.
- The account discriminator (first 8 bytes) is preserved automatically.

For adding `{change_desc}`, calculate new space: `8` (discriminator) + `{struct_name}V2::INIT_SPACE`."""
    content = f"### Question\n{q}\n\n### Answer\n{a}"
    records.append(make_record(content, "realloc_patterns"))

# ═══════════════════════════════════════════════════════════════════════════════
# 5. Init_if_needed patterns (10 records)
# ═══════════════════════════════════════════════════════════════════════════════

INIT_IF_NEEDED_CASES = [
    ("UserProfile", "user_profile", "user", True,
     "User profiles where the PDA is derived from the user's pubkey — only that user can initialize it, so it's safe.",
     [("user", "Pubkey"), ("points", "u64"), ("bump", "u8")],
     'seeds = [b"profile", user.key().as_ref()]'),
    ("AssociatedTokenAccount", "user_ata", "user", True,
     "ATAs are deterministic — the address uniquely identifies the (wallet, mint) pair, so front-running can't inject wrong data.",
     [], "associated_token::mint = mint, associated_token::authority = user"),
    ("VaultAccount", "vault", "admin", False,
     "Vault accounts without user-specific seeds are DANGEROUS with init_if_needed. An attacker could initialize the vault first with their own authority.",
     [("authority", "Pubkey"), ("balance", "u64"), ("bump", "u8")],
     'seeds = [b"vault", mint.key().as_ref()]'),
    ("GameSession", "session", "player", True,
     "Game sessions with player-specific seeds are safe — only that player can init their session PDA.",
     [("player", "Pubkey"), ("score", "u64"), ("started_at", "i64"), ("bump", "u8")],
     'seeds = [b"session", player.key().as_ref(), game.key().as_ref()]'),
    ("StakeRecord", "stake_record", "staker", True,
     "Stake records keyed to staker pubkey — safe because only the staker pays and inits their own record.",
     [("staker", "Pubkey"), ("amount", "u64"), ("start_time", "i64"), ("bump", "u8")],
     'seeds = [b"stake", staker.key().as_ref(), pool.key().as_ref()]'),
    ("GlobalConfig", "config", "admin", False,
     "Global config without payer-specific seeds is DANGEROUS. Anyone could front-run initialization and set themselves as admin.",
     [("admin", "Pubkey"), ("fee_bps", "u16"), ("bump", "u8")],
     'seeds = [b"config"]'),
    ("RewardTracker", "tracker", "user", True,
     "Per-user reward trackers are safe since seeds include the user's pubkey.",
     [("user", "Pubkey"), ("claimed", "u64"), ("last_claim", "i64"), ("bump", "u8")],
     'seeds = [b"rewards", user.key().as_ref(), pool.key().as_ref()]'),
    ("OrderBook", "order_book", "market_admin", False,
     "Shared order book accounts should use explicit `init` with admin verification, not `init_if_needed`.",
     [("authority", "Pubkey"), ("bid_count", "u32"), ("ask_count", "u32"), ("bump", "u8")],
     'seeds = [b"orderbook", market.key().as_ref()]'),
    ("DepositReceipt", "receipt", "depositor", True,
     "Per-depositor receipts with depositor in seeds are safe — deterministic and user-scoped.",
     [("depositor", "Pubkey"), ("amount", "u64"), ("timestamp", "i64"), ("bump", "u8")],
     'seeds = [b"receipt", depositor.key().as_ref(), vault.key().as_ref()]'),
    ("ProtocolFeeAccount", "fee_account", "protocol_admin", False,
     "Protocol-wide fee accounts should NEVER use init_if_needed. Use a dedicated `initialize` instruction with admin checks.",
     [("authority", "Pubkey"), ("accumulated_fees", "u64"), ("bump", "u8")],
     'seeds = [b"fees"]'),
]

for struct_name, acc_name, payer, is_safe, explanation, fields, seeds_expr in INIT_IF_NEEDED_CASES:
    safe_label = "safe" if is_safe else "dangerous"
    q = (
        f"Is it safe to use `init_if_needed` for a `{struct_name}` account in Anchor? "
        f"Show the pattern and explain the security implications."
    )
    if is_safe:
        a = f"""Yes, `init_if_needed` is **safe** for `{struct_name}` in this case because the PDA seeds include the payer's pubkey, making front-running impossible.

```rust
use anchor_lang::prelude::*;

#[account]
#[derive(InitSpace)]
pub struct {struct_name} {{
{chr(10).join(f"    pub {f}: {t}," for f, t in fields) if fields else "    // Uses SPL token account layout"}
}}

#[derive(Accounts)]
pub struct Create{struct_name}<'info> {{
    #[account(mut)]
    pub {payer}: Signer<'info>,

    #[account(
        init_if_needed,
        payer = {payer},
        space = 8 + {struct_name}::INIT_SPACE,
        {seeds_expr},
        bump,
    )]
    pub {acc_name}: Account<'info, {struct_name}>,

    pub system_program: Program<'info, System>,
}}
```

{explanation}

To enable `init_if_needed`, add to your `Cargo.toml`:
```toml
anchor-lang = {{ version = "0.30.1", features = ["init-if-needed"] }}
```

The instruction handler should set fields only if the account is newly created:
```rust
pub fn create_or_use(ctx: Context<Create{struct_name}>) -> Result<()> {{
    let acc = &mut ctx.accounts.{acc_name};
    if acc.{fields[0][0] if fields else "authority"} == Pubkey::default() {{
        // First time — initialize fields
        acc.{fields[0][0] if fields else "authority"} = ctx.accounts.{payer}.key();
        acc.bump = ctx.bumps.{acc_name};
    }}
    // Proceed with logic...
    Ok(())
}}
```"""
    else:
        a = f"""**No, `init_if_needed` is DANGEROUS** for `{struct_name}` in this case. The PDA seeds do NOT include the payer's pubkey, so an attacker can front-run initialization.

```rust
// ❌ DANGEROUS — do NOT do this:
#[derive(Accounts)]
pub struct Create{struct_name}<'info> {{
    #[account(mut)]
    pub {payer}: Signer<'info>,

    #[account(
        init_if_needed,
        payer = {payer},
        space = 8 + {struct_name}::INIT_SPACE,
        {seeds_expr},
        bump,
    )]
    pub {acc_name}: Account<'info, {struct_name}>,

    pub system_program: Program<'info, System>,
}}
// An attacker can call this first and set authority to their own key!
```

{explanation}

**Instead, use explicit `init` with proper authorization:**

```rust
// ✅ SAFE — separate init instruction with admin check
#[derive(Accounts)]
pub struct Initialize{struct_name}<'info> {{
    #[account(mut)]
    pub {payer}: Signer<'info>,

    #[account(
        init,
        payer = {payer},
        space = 8 + {struct_name}::INIT_SPACE,
        {seeds_expr},
        bump,
    )]
    pub {acc_name}: Account<'info, {struct_name}>,

    // Additional auth check — e.g., multisig or known admin
    #[account(
        constraint = admin_config.admin == {payer}.key() @ MyError::Unauthorized,
    )]
    pub admin_config: Account<'info, AdminConfig>,

    pub system_program: Program<'info, System>,
}}
```

Rule of thumb: only use `init_if_needed` when the PDA seeds include the payer's pubkey, making the account user-scoped and deterministic."""
    content = f"### Question\n{q}\n\n### Answer\n{a}"
    records.append(make_record(content, "init_if_needed"))

# ═══════════════════════════════════════════════════════════════════════════════
# 6. Seeds and PDA derivation (15 records)
# ═══════════════════════════════════════════════════════════════════════════════

SEED_PATTERNS = [
    ("single string seed", 'seeds = [b"config"]', "config", "Config",
     "A single static seed. Only one account can exist for this PDA — used for global singletons like program config."),
    ("user pubkey seed", 'seeds = [b"profile", user.key().as_ref()]', "profile", "UserProfile",
     "Includes the user's pubkey in seeds. Creates a unique PDA per user — the most common pattern."),
    ("two pubkey seeds", 'seeds = [b"relationship", user_a.key().as_ref(), user_b.key().as_ref()]', "relationship", "Relationship",
     "Two pubkeys create a unique pair. Used for friendships, trade pairs, LP positions. Order matters!"),
    ("string seed", 'seeds = [b"market", market_name.as_bytes()]', "market", "Market",
     "A dynamic string seed. The market_name parameter must be passed in the instruction args and validated for length."),
    ("u64 seed", 'seeds = [b"order", &order_id.to_le_bytes()]', "order", "Order",
     "Numeric seed using little-endian byte encoding. Creates one PDA per order ID."),
    ("u16 seed", 'seeds = [b"tier", &tier_level.to_le_bytes()]', "tier", "Tier",
     "Small integer seeds also use to_le_bytes(). Useful for fixed sets like tier levels."),
    ("enum discriminator seed", 'seeds = [b"vault", &[vault_type as u8]]', "vault", "TypedVault",
     "Encode enum variants as a single byte seed. One PDA per enum variant."),
    ("multi-seed with pubkey and u64", 'seeds = [b"stake", pool.key().as_ref(), &epoch.to_le_bytes()]', "stake", "EpochStake",
     "Combines a pubkey (which pool) with an integer (which epoch). Creates per-pool per-epoch accounts."),
    ("three seeds: pubkey + string + u64", 'seeds = [b"listing", seller.key().as_ref(), collection.as_bytes(), &item_id.to_le_bytes()]', "listing", "Listing",
     "Three-part seed for marketplace listings. Unique per seller, collection name, and item."),
    ("bump stored in account", 'seeds = [b"data", authority.key().as_ref()], bump = data.bump', "data", "DataAccount",
     "After init, store the bump in the account and reference it with `bump = data.bump`. This saves compute units vs re-deriving."),
    ("canonical bump derivation", 'seeds = [b"treasury"], bump', "treasury", "Treasury",
     "Using `bump` without a value makes Anchor find the canonical bump. Used during `init` when the account doesn't exist yet."),
    ("PDA signer in CPI", 'seeds = [b"vault_auth", mint.key().as_ref()], bump = vault_auth.bump', "vault_auth", "VaultAuthority",
     "The PDA acts as a signer for CPIs. Pass `&[seeds, &[bump]]` to `CpiContext::new_with_signer`."),
    ("user + mint seed", 'seeds = [b"deposit", user.key().as_ref(), mint.key().as_ref()]', "deposit", "DepositRecord",
     "Per-user per-mint deposit tracking. Common in lending protocols and DEXs."),
    ("counter-based seed", 'seeds = [b"item", collection.key().as_ref(), &collection.item_count.to_le_bytes()]', "item", "CollectionItem",
     "Uses a counter from a parent account as seed. Creates sequential PDAs — but requires the parent account to track the count."),
    ("hash-based seed", 'seeds = [b"commitment", &commitment_hash]', "commitment", "Commitment",
     "Uses a hash as a seed for commit-reveal schemes. The hash is computed off-chain and verified on-chain after reveal."),
]

for desc, seeds_code, acc_name, struct_name, explanation in SEED_PATTERNS:
    q = f"How do I derive a PDA in Anchor using a {desc}? Show the seeds and bump usage."
    a = f"""Here's how to use a {desc} for PDA derivation in modern Anchor (0.30+):

```rust
use anchor_lang::prelude::*;

#[derive(Accounts)]
pub struct Create{struct_name}<'info> {{
    #[account(mut)]
    pub authority: Signer<'info>,

    #[account(
        init,
        payer = authority,
        space = 8 + {struct_name}::INIT_SPACE,
        {seeds_code},
        bump,
    )]
    pub {acc_name}: Account<'info, {struct_name}>,

    pub system_program: Program<'info, System>,
}}

#[derive(Accounts)]
pub struct Read{struct_name}<'info> {{
    #[account(
        {seeds_code.replace(", bump = " + acc_name + ".bump", ", bump = " + acc_name + ".bump") if "bump = " in seeds_code else seeds_code + ", bump = " + acc_name + ".bump"},
    )]
    pub {acc_name}: Account<'info, {struct_name}>,
}}
```

{explanation}

When creating the account, use `bump` (no value) to let Anchor find the canonical bump. After init, store the bump:

```rust
pub fn create(ctx: Context<Create{struct_name}>) -> Result<()> {{
    let {acc_name} = &mut ctx.accounts.{acc_name};
    {acc_name}.bump = ctx.bumps.{acc_name};
    Ok(())
}}
```

When reading/modifying, reference the stored bump with `bump = {acc_name}.bump` to save ~2000 compute units vs re-deriving."""
    content = f"### Question\n{q}\n\n### Answer\n{a}"
    records.append(make_record(content, "seeds_pda"))

# ═══════════════════════════════════════════════════════════════════════════════
# 7. Account serialization / space (15 records)
# ═══════════════════════════════════════════════════════════════════════════════

SPACE_EXAMPLES = [
    ("SimpleCounter", [("authority", "Pubkey", 32), ("count", "u64", 8), ("bump", "u8", 1)],
     None, "8 + 32 + 8 + 1 = 49"),
    ("UserProfile", [("authority", "Pubkey", 32), ("name", "String", "4 + 32"), ("bio", "String", "4 + 256"), ("level", "u8", 1), ("bump", "u8", 1)],
     [("#[max_len(32)]", "name"), ("#[max_len(256)]", "bio")], "8 + 32 + 36 + 260 + 1 + 1 = 338"),
    ("TokenLedger", [("owner", "Pubkey", 32), ("entries", "Vec<Pubkey>", "4 + 10 * 32"), ("total", "u64", 8), ("bump", "u8", 1)],
     [("#[max_len(10)]", "entries")], "8 + 32 + 324 + 8 + 1 = 373"),
    ("OptionalData", [("authority", "Pubkey", 32), ("nickname", "Option<String>", "1 + 4 + 20"), ("referrer", "Option<Pubkey>", "1 + 32"), ("bump", "u8", 1)],
     [("#[max_len(20)]", "nickname")], "8 + 32 + 25 + 33 + 1 = 99"),
    ("GameState", [("authority", "Pubkey", 32), ("board", "[u8; 64]", 64), ("turn", "u8", 1), ("status", "u8", 1), ("bump", "u8", 1)],
     None, "8 + 32 + 64 + 1 + 1 + 1 = 107"),
    ("MarketOrder", [("trader", "Pubkey", 32), ("mint", "Pubkey", 32), ("price", "u64", 8), ("quantity", "u64", 8), ("side", "u8", 1), ("timestamp", "i64", 8), ("bump", "u8", 1)],
     None, "8 + 32 + 32 + 8 + 8 + 1 + 8 + 1 = 98"),
    ("VotingRecord", [("voter", "Pubkey", 32), ("votes", "Vec<u64>", "4 + 50 * 8"), ("total_weight", "u64", 8), ("bump", "u8", 1)],
     [("#[max_len(50)]", "votes")], "8 + 32 + 404 + 8 + 1 = 453"),
    ("NestedConfig", [("admin", "Pubkey", 32), ("fee_config", "FeeConfig", "2 + 2 + 2"), ("limits", "Limits", "8 + 8 + 8"), ("bump", "u8", 1)],
     None, "8 + 32 + 6 + 24 + 1 = 71"),
    ("EventLog", [("authority", "Pubkey", 32), ("events", "Vec<u8>", "4 + 2048"), ("event_count", "u32", 4), ("bump", "u8", 1)],
     [("#[max_len(2048)]", "events")], "8 + 32 + 2052 + 4 + 1 = 2097"),
    ("MultiVec", [("owner", "Pubkey", 32), ("names", "Vec<String>", "4 + 5 * (4 + 32)"), ("scores", "Vec<u64>", "4 + 20 * 8"), ("bump", "u8", 1)],
     [("#[max_len(5, 32)]", "names"), ("#[max_len(20)]", "scores")], "8 + 32 + 184 + 164 + 1 = 389"),
    ("EnumField", [("owner", "Pubkey", 32), ("status", "Status", "1 + 8"), ("bump", "u8", 1)],
     None, "8 + 32 + 9 + 1 = 50 (enum uses 1 byte discriminant + largest variant)"),
    ("BoolHeavy", [("authority", "Pubkey", 32), ("is_active", "bool", 1), ("is_frozen", "bool", 1), ("is_verified", "bool", 1), ("count", "u32", 4), ("bump", "u8", 1)],
     None, "8 + 32 + 1 + 1 + 1 + 4 + 1 = 48"),
    ("LargeString", [("authority", "Pubkey", 32), ("content", "String", "4 + 1024"), ("version", "u16", 2), ("bump", "u8", 1)],
     [("#[max_len(1024)]", "content")], "8 + 32 + 1028 + 2 + 1 = 1071"),
    ("MixedTypes", [("authority", "Pubkey", 32), ("amount", "u128", 16), ("price", "u64", 8), ("flags", "u8", 1), ("label", "String", "4 + 16"), ("bump", "u8", 1)],
     [("#[max_len(16)]", "label")], "8 + 32 + 16 + 8 + 1 + 20 + 1 = 86"),
    ("TwoOptions", [("authority", "Pubkey", 32), ("delegate", "Option<Pubkey>", "1 + 32"), ("expiry", "Option<i64>", "1 + 8"), ("active", "bool", 1), ("bump", "u8", 1)],
     None, "8 + 32 + 33 + 9 + 1 + 1 = 84"),
]

for struct_name, fields, annotations, space_calc in SPACE_EXAMPLES:
    field_lines = []
    for f in fields:
        fname, ftype = f[0], f[1]
        ann = None
        if annotations:
            for ann_str, ann_field in annotations:
                if ann_field == fname:
                    ann = ann_str
                    break
        if ann:
            field_lines.append(f"    {ann}\n    pub {fname}: {ftype},")
        else:
            field_lines.append(f"    pub {fname}: {ftype},")

    q = f"How do I calculate the account space for a `{struct_name}` struct in Anchor? Show both `InitSpace` derive and manual calculation."
    a = f"""Use `#[derive(InitSpace)]` for automatic calculation, and understand the manual math for debugging.

```rust
use anchor_lang::prelude::*;

#[account]
#[derive(InitSpace)]
pub struct {struct_name} {{
{chr(10).join(field_lines)}
}}

// Manual space calculation:
// Discriminator:  8 bytes (always)
// {chr(10).join(f"// {f[0]:15s}: {f[2]} bytes" for f in fields)}
// Total: {space_calc}

#[derive(Accounts)]
pub struct Create{struct_name}<'info> {{
    #[account(mut)]
    pub authority: Signer<'info>,

    #[account(
        init,
        payer = authority,
        space = 8 + {struct_name}::INIT_SPACE,
    )]
    pub account: Account<'info, {struct_name}>,

    pub system_program: Program<'info, System>,
}}
```

Space rules:
- **Discriminator**: Always 8 bytes (Anchor's account type identifier)
- **Pubkey**: 32 bytes
- **u8/bool**: 1, **u16**: 2, **u32**: 4, **u64/i64**: 8, **u128/i128**: 16
- **String**: 4 (length prefix) + max_len
- **Vec<T>**: 4 (length prefix) + max_len * size_of(T)
- **Option<T>**: 1 (discriminant) + size_of(T)
- **Enum**: 1 (variant discriminant) + size of largest variant
- **[T; N]**: N * size_of(T)

Always use `8 + {struct_name}::INIT_SPACE` in the `space` attribute — the `8 +` accounts for the discriminator that `InitSpace` does NOT include."""
    content = f"### Question\n{q}\n\n### Answer\n{a}"
    records.append(make_record(content, "account_space"))

# ═══════════════════════════════════════════════════════════════════════════════
# 8. Token account constraints (15 records)
# ═══════════════════════════════════════════════════════════════════════════════

TOKEN_SCENARIOS = [
    ("token::mint constraint", "Verify a token account belongs to a specific mint",
     """#[account(
        mut,
        token::mint = expected_mint,
        token::authority = user,
    )]
    pub user_tokens: Account<'info, TokenAccount>,
    pub expected_mint: Account<'info, Mint>,""",
     "The `token::mint` constraint verifies `user_tokens.mint == expected_mint.key()`. Prevents passing a token account for the wrong mint."),
    ("token::authority constraint", "Verify a token account's authority matches the signer",
     """#[account(
        mut,
        token::authority = authority,
    )]
    pub source: Account<'info, TokenAccount>,
    pub authority: Signer<'info>,""",
     "Ensures only the rightful owner can use this token account in the instruction."),
    ("associated_token::mint + authority", "Use an Associated Token Account (ATA)",
     """#[account(
        init_if_needed,
        payer = user,
        associated_token::mint = mint,
        associated_token::authority = user,
    )]
    pub user_ata: Account<'info, TokenAccount>,
    pub mint: Account<'info, Mint>,
    #[account(mut)]
    pub user: Signer<'info>,
    pub associated_token_program: Program<'info, AssociatedToken>,""",
     "ATAs are deterministic — derived from (wallet, mint). `init_if_needed` is safe here because the address is unique."),
    ("checking token balance", "Require minimum token balance before an action",
     """#[account(
        constraint = user_tokens.amount >= required_amount @ MyError::InsufficientBalance,
        token::mint = mint,
        token::authority = user,
    )]
    pub user_tokens: Account<'info, TokenAccount>,""",
     "Combine `constraint` with token constraints. The balance check happens at instruction validation time."),
    ("checking delegate", "Verify a token account has a specific delegate approved",
     """#[account(
        mut,
        constraint = delegated_tokens.delegate.contains(&delegate.key()) @ MyError::NotDelegated,
        constraint = delegated_tokens.delegated_amount >= amount @ MyError::InsufficientDelegation,
    )]
    pub delegated_tokens: Account<'info, TokenAccount>,
    pub delegate: Signer<'info>,""",
     "Check both that a delegate is set and that the delegated amount is sufficient."),
    ("PDA token authority", "Token account owned by a PDA",
     """#[account(
        mut,
        token::mint = mint,
        token::authority = vault_authority,
    )]
    pub vault_tokens: Account<'info, TokenAccount>,

    /// CHECK: PDA used as token authority
    #[account(
        seeds = [b"vault_auth", mint.key().as_ref()],
        bump = vault_state.auth_bump,
    )]
    pub vault_authority: UncheckedAccount<'info>,""",
     "A PDA acts as the authority for program-controlled token accounts. The PDA signs via CPI with `CpiContext::new_with_signer`."),
    ("init token account with seeds", "Create a PDA-owned token account",
     """#[account(
        init,
        payer = authority,
        token::mint = mint,
        token::authority = vault_auth,
        seeds = [b"vault_tokens", mint.key().as_ref()],
        bump,
    )]
    pub vault_tokens: Account<'info, TokenAccount>,""",
     "Combine `init` with `token::mint` and `token::authority` to create a new token account at a PDA address."),
    ("mint::authority + decimals", "Create a new mint with specific decimals",
     """#[account(
        init,
        payer = authority,
        mint::decimals = 6,
        mint::authority = authority,
    )]
    pub new_mint: Account<'info, Mint>,
    #[account(mut)]
    pub authority: Signer<'info>,""",
     "The `mint::decimals` and `mint::authority` constraints configure a new mint during initialization."),
    ("mint::freeze_authority", "Create a mint with a freeze authority",
     """#[account(
        init,
        payer = authority,
        mint::decimals = 9,
        mint::authority = authority,
        mint::freeze_authority = freeze_auth,
    )]
    pub new_mint: Account<'info, Mint>,
    pub freeze_auth: Signer<'info>,""",
     "Set a separate freeze authority for compliance tokens. The freeze authority can freeze/thaw individual token accounts."),
    ("two token accounts same mint", "Transfer between two accounts of the same mint",
     """#[account(
        mut,
        token::mint = mint,
        token::authority = sender,
    )]
    pub from: Account<'info, TokenAccount>,

    #[account(
        mut,
        token::mint = mint,
    )]
    pub to: Account<'info, TokenAccount>,
    pub mint: Account<'info, Mint>,
    pub sender: Signer<'info>,""",
     "Both token accounts must share the same mint. Only the `from` account needs an authority check since the sender is transferring out."),
    ("ATA for recipient", "Create ATA for someone else (airdrop pattern)",
     """#[account(
        init_if_needed,
        payer = sender,
        associated_token::mint = mint,
        associated_token::authority = recipient,
    )]
    pub recipient_ata: Account<'info, TokenAccount>,
    /// CHECK: Any valid pubkey can receive tokens
    pub recipient: UncheckedAccount<'info>,""",
     "The sender pays for ATA creation, but the ATA is owned by the recipient. Common for airdrops and reward distributions."),
    ("token account close authority", "Close a token account and reclaim rent",
     """#[account(
        mut,
        token::mint = mint,
        token::authority = authority,
        constraint = closing_account.amount == 0 @ MyError::NonZeroBalance,
    )]
    pub closing_account: Account<'info, TokenAccount>,""",
     "Before closing a token account, verify the balance is zero. Use SPL Token's `close_account` instruction to reclaim rent."),
    ("multiple mints validation", "Verify token accounts for a swap pair",
     """#[account(mut, token::mint = mint_a, token::authority = user)]
    pub user_a: Account<'info, TokenAccount>,
    #[account(mut, token::mint = mint_b, token::authority = user)]
    pub user_b: Account<'info, TokenAccount>,
    #[account(mut, token::mint = mint_a, token::authority = pool_auth)]
    pub pool_a: Account<'info, TokenAccount>,
    #[account(mut, token::mint = mint_b, token::authority = pool_auth)]
    pub pool_b: Account<'info, TokenAccount>,
    pub mint_a: Account<'info, Mint>,
    pub mint_b: Account<'info, Mint>,""",
     "For swaps, validate all four token accounts (user A, user B, pool A, pool B) against their respective mints and authorities."),
    ("token account with constraint expression", "Check mint supply before minting more",
     """#[account(
        mut,
        constraint = mint.supply < MAX_SUPPLY @ MyError::MaxSupplyReached,
    )]
    pub mint: Account<'info, Mint>,""",
     "Access mint fields like `supply`, `decimals`, and `mint_authority` in constraint expressions."),
    ("Interface token accounts", "Token-2022 compatible token constraints",
     """use anchor_spl::token_interface::{Mint, TokenAccount, TokenInterface};

    #[account(
        mut,
        token::mint = mint,
        token::authority = user,
        token::token_program = token_program,
    )]
    pub user_tokens: InterfaceAccount<'info, TokenAccount>,
    pub mint: InterfaceAccount<'info, Mint>,
    pub token_program: Interface<'info, TokenInterface>,""",
     "Use `InterfaceAccount` and `Interface` types for Token-2022 compatibility. Add `token::token_program` to validate the correct program."),
]

for title, desc, code_snippet, explanation in TOKEN_SCENARIOS:
    q = f"How do I use `{title}` in Anchor to {desc.lower()}?"
    a = f"""Here's the pattern for {desc.lower()} using modern Anchor (0.30+):

```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{{Token, TokenAccount, Mint}};
use anchor_spl::associated_token::AssociatedToken;

#[derive(Accounts)]
pub struct MyInstruction<'info> {{
    {code_snippet}
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}}
```

{explanation}

These constraints are checked during account deserialization — before your instruction handler runs. If any check fails, the transaction is rejected with a descriptive error."""
    content = f"### Question\n{q}\n\n### Answer\n{a}"
    records.append(make_record(content, "token_constraints"))

# ═══════════════════════════════════════════════════════════════════════════════
# 9. System program interactions (10 records)
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_SCENARIOS = [
    ("create a new account", "CreateAccount",
     """Use `system_program::create_account` to allocate a new account with specific space and owner.

```rust
use anchor_lang::prelude::*;
use anchor_lang::system_program;

pub fn create_raw_account(ctx: Context<CreateRawAccount>, space: u64) -> Result<()> {
    let rent = Rent::get()?;
    let lamports = rent.minimum_balance(space as usize);

    system_program::create_account(
        CpiContext::new(
            ctx.accounts.system_program.to_account_info(),
            system_program::CreateAccount {
                from: ctx.accounts.payer.to_account_info(),
                to: ctx.accounts.new_account.to_account_info(),
            },
        ),
        lamports,
        space,
        ctx.program_id,
    )?;
    Ok(())
}

#[derive(Accounts)]
pub struct CreateRawAccount<'info> {
    #[account(mut)]
    pub payer: Signer<'info>,
    #[account(mut)]
    pub new_account: Signer<'info>,
    pub system_program: Program<'info, System>,
}
```

Note: In most cases, Anchor's `#[account(init)]` handles this automatically. Use raw `create_account` only when you need custom owner assignment or non-Anchor accounts."""),
    ("transfer SOL", "TransferSOL",
     """Transfer SOL between accounts using the System Program.

```rust
use anchor_lang::prelude::*;
use anchor_lang::system_program;

pub fn send_sol(ctx: Context<SendSol>, amount: u64) -> Result<()> {
    system_program::transfer(
        CpiContext::new(
            ctx.accounts.system_program.to_account_info(),
            system_program::Transfer {
                from: ctx.accounts.sender.to_account_info(),
                to: ctx.accounts.recipient.to_account_info(),
            },
        ),
        amount,
    )?;
    Ok(())
}

#[derive(Accounts)]
pub struct SendSol<'info> {
    #[account(mut)]
    pub sender: Signer<'info>,
    /// CHECK: Any account can receive SOL
    #[account(mut)]
    pub recipient: UncheckedAccount<'info>,
    pub system_program: Program<'info, System>,
}
```

For PDA-to-user transfers, you can also directly modify lamports:
```rust
**ctx.accounts.pda_vault.to_account_info().try_borrow_mut_lamports()? -= amount;
**ctx.accounts.recipient.to_account_info().try_borrow_mut_lamports()? += amount;
```"""),
    ("transfer SOL from PDA", "TransferFromPDA",
     """Transfer SOL from a PDA using signer seeds.

```rust
use anchor_lang::prelude::*;
use anchor_lang::system_program;

pub fn withdraw_from_pda(ctx: Context<WithdrawPDA>, amount: u64) -> Result<()> {
    let seeds = &[
        b"treasury".as_ref(),
        &[ctx.accounts.treasury.bump],
    ];

    system_program::transfer(
        CpiContext::new_with_signer(
            ctx.accounts.system_program.to_account_info(),
            system_program::Transfer {
                from: ctx.accounts.treasury.to_account_info(),
                to: ctx.accounts.authority.to_account_info(),
            },
            &[seeds],
        ),
        amount,
    )?;
    Ok(())
}

#[derive(Accounts)]
pub struct WithdrawPDA<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(
        mut,
        seeds = [b"treasury"],
        bump = treasury.bump,
        has_one = authority,
    )]
    pub treasury: Account<'info, Treasury>,
    pub system_program: Program<'info, System>,
}
```"""),
    ("allocate space for an account", "AllocateSpace",
     """Allocate additional space for an existing account.

```rust
use anchor_lang::prelude::*;
use anchor_lang::solana_program::system_instruction;

pub fn allocate_more_space(ctx: Context<AllocateMore>, new_space: u64) -> Result<()> {
    let account = &ctx.accounts.target_account;
    let current_space = account.to_account_info().data_len();

    require!(new_space as usize > current_space, MyError::ShrinkNotAllowed);

    // Calculate additional rent needed
    let rent = Rent::get()?;
    let current_lamports = account.to_account_info().lamports();
    let required_lamports = rent.minimum_balance(new_space as usize);

    if required_lamports > current_lamports {
        let diff = required_lamports - current_lamports;
        let ix = system_instruction::transfer(
            &ctx.accounts.payer.key(),
            &account.key(),
            diff,
        );
        anchor_lang::solana_program::program::invoke(&ix, &[
            ctx.accounts.payer.to_account_info(),
            account.to_account_info(),
        ])?;
    }

    account.to_account_info().realloc(new_space as usize, false)?;
    Ok(())
}
```

In most Anchor programs, prefer `#[account(realloc = ...)]` which handles this automatically."""),
    ("assign program ownership", "AssignOwner",
     """Assign a new owner program to an account.

```rust
use anchor_lang::prelude::*;
use anchor_lang::solana_program::system_instruction;

pub fn assign_to_program(ctx: Context<AssignOwner>) -> Result<()> {
    let ix = system_instruction::assign(
        &ctx.accounts.target.key(),
        ctx.program_id,
    );
    anchor_lang::solana_program::program::invoke(&ix, &[
        ctx.accounts.target.to_account_info(),
    ])?;
    Ok(())
}

#[derive(Accounts)]
pub struct AssignOwner<'info> {
    #[account(mut)]
    pub target: Signer<'info>,
    pub system_program: Program<'info, System>,
}
```

Ownership assignment is rarely needed directly — `create_account` and Anchor's `init` handle this. It's useful for advanced patterns like migrating accounts between programs."""),
    ("fund a PDA with SOL", "FundPDA",
     """Fund a PDA to hold SOL (e.g., for a treasury or vault).

```rust
use anchor_lang::prelude::*;
use anchor_lang::system_program;

pub fn fund_treasury(ctx: Context<FundTreasury>, amount: u64) -> Result<()> {
    system_program::transfer(
        CpiContext::new(
            ctx.accounts.system_program.to_account_info(),
            system_program::Transfer {
                from: ctx.accounts.funder.to_account_info(),
                to: ctx.accounts.treasury.to_account_info(),
            },
        ),
        amount,
    )?;
    Ok(())
}

#[derive(Accounts)]
pub struct FundTreasury<'info> {
    #[account(mut)]
    pub funder: Signer<'info>,
    #[account(
        mut,
        seeds = [b"treasury"],
        bump = treasury.bump,
    )]
    pub treasury: Account<'info, Treasury>,
    pub system_program: Program<'info, System>,
}
```

The treasury PDA can hold arbitrary lamports beyond rent-exemption. Use `SystemAccount<'info>` if the PDA doesn't need Anchor serialization."""),
    ("check rent exemption", "CheckRent",
     """Verify an account is rent-exempt before performing operations.

```rust
use anchor_lang::prelude::*;

pub fn verify_rent_exempt(ctx: Context<VerifyRent>) -> Result<()> {
    let rent = Rent::get()?;
    let account = &ctx.accounts.target;
    let lamports = account.to_account_info().lamports();
    let data_len = account.to_account_info().data_len();

    require!(
        rent.is_exempt(lamports, data_len),
        MyError::NotRentExempt,
    );
    msg!("Account is rent-exempt with {} lamports for {} bytes", lamports, data_len);
    Ok(())
}
```

Anchor's `init` automatically funds accounts to be rent-exempt. This check is useful for accounts created outside Anchor or for verifying accounts haven't been drained."""),
    ("create account with PDA signer", "CreateWithPDA",
     """Create a new account where a PDA pays the rent.

```rust
use anchor_lang::prelude::*;
use anchor_lang::system_program;

pub fn pda_creates_account(ctx: Context<PDACreates>, space: u64) -> Result<()> {
    let rent = Rent::get()?;
    let lamports = rent.minimum_balance(space as usize);
    let seeds = &[b"treasury".as_ref(), &[ctx.accounts.treasury.bump]];

    system_program::create_account(
        CpiContext::new_with_signer(
            ctx.accounts.system_program.to_account_info(),
            system_program::CreateAccount {
                from: ctx.accounts.treasury.to_account_info(),
                to: ctx.accounts.new_account.to_account_info(),
            },
            &[seeds],
        ),
        lamports,
        space,
        ctx.program_id,
    )?;
    Ok(())
}

#[derive(Accounts)]
pub struct PDACreates<'info> {
    pub authority: Signer<'info>,
    #[account(
        mut,
        seeds = [b"treasury"],
        bump = treasury.bump,
        has_one = authority,
    )]
    pub treasury: Account<'info, Treasury>,
    #[account(mut)]
    pub new_account: Signer<'info>,
    pub system_program: Program<'info, System>,
}
```"""),
    ("close and reclaim SOL", "CloseAndReclaim",
     """Manually close an account and reclaim all lamports.

```rust
use anchor_lang::prelude::*;

pub fn close_manual(ctx: Context<CloseManual>) -> Result<()> {
    let dest = &ctx.accounts.destination;
    let source = &ctx.accounts.closeable;

    // Transfer all lamports
    let source_lamports = source.to_account_info().lamports();
    **source.to_account_info().try_borrow_mut_lamports()? = 0;
    **dest.to_account_info().try_borrow_mut_lamports()? = dest
        .to_account_info()
        .lamports()
        .checked_add(source_lamports)
        .ok_or(ProgramError::ArithmeticOverflow)?;

    // Zero the data to prevent resurrection
    let mut data = source.to_account_info().try_borrow_mut_data()?;
    for byte in data.iter_mut() {
        *byte = 0;
    }

    Ok(())
}
```

Prefer Anchor's `#[account(close = destination)]` constraint which handles all of this automatically and securely."""),
    ("transfer SOL with checked math", "SafeTransfer",
     """Transfer SOL with overflow-safe arithmetic.

```rust
use anchor_lang::prelude::*;
use anchor_lang::system_program;

pub fn safe_transfer(ctx: Context<SafeTransfer>, amount: u64) -> Result<()> {
    // Verify sender has enough lamports
    let sender_balance = ctx.accounts.sender.to_account_info().lamports();
    let rent = Rent::get()?;
    let min_balance = rent.minimum_balance(0); // Minimum for wallet

    require!(
        sender_balance.checked_sub(amount).ok_or(MyError::Underflow)? >= min_balance,
        MyError::WouldBecomeInsolvent,
    );

    system_program::transfer(
        CpiContext::new(
            ctx.accounts.system_program.to_account_info(),
            system_program::Transfer {
                from: ctx.accounts.sender.to_account_info(),
                to: ctx.accounts.recipient.to_account_info(),
            },
        ),
        amount,
    )?;
    Ok(())
}
```

Always verify the sender retains enough lamports for rent-exemption after the transfer."""),
]

for desc, struct_name, answer_body in SYSTEM_SCENARIOS:
    q = f"How do I {desc} using the System Program in an Anchor program?"
    a = answer_body
    content = f"### Question\n{q}\n\n### Answer\n{a}"
    records.append(make_record(content, "system_program"))

# ═══════════════════════════════════════════════════════════════════════════════
# 10. Signer and authority patterns (10 records)
# ═══════════════════════════════════════════════════════════════════════════════

SIGNER_PATTERNS = [
    ("single authority signer",
     """Verify a single authority signs the transaction.

```rust
use anchor_lang::prelude::*;

#[derive(Accounts)]
pub struct AdminAction<'info> {
    pub admin: Signer<'info>,

    #[account(
        mut,
        has_one = admin @ MyError::Unauthorized,
        seeds = [b"config"],
        bump = config.bump,
    )]
    pub config: Account<'info, Config>,
}
```

The `Signer<'info>` type verifies `is_signer == true` on the account. Combined with `has_one = admin`, this ensures the signing wallet matches the stored admin key."""),
    ("admin and authority separation",
     """Separate admin (upgrades/config) from authority (day-to-day operations).

```rust
use anchor_lang::prelude::*;

#[account]
#[derive(InitSpace)]
pub struct Protocol {
    pub admin: Pubkey,       // Can change config, pause, upgrade
    pub authority: Pubkey,   // Can execute operations
    pub is_paused: bool,
    pub bump: u8,
}

#[derive(Accounts)]
pub struct AdminOnly<'info> {
    pub admin: Signer<'info>,
    #[account(mut, has_one = admin)]
    pub protocol: Account<'info, Protocol>,
}

#[derive(Accounts)]
pub struct AuthorityOnly<'info> {
    pub authority: Signer<'info>,
    #[account(
        mut,
        has_one = authority,
        constraint = !protocol.is_paused @ MyError::Paused,
    )]
    pub protocol: Account<'info, Protocol>,
}

// Transfer admin to a new wallet (admin-only)
pub fn transfer_admin(ctx: Context<AdminOnly>, new_admin: Pubkey) -> Result<()> {
    ctx.accounts.protocol.admin = new_admin;
    Ok(())
}
```

This pattern lets you use a cold wallet for admin and a hot wallet for authority."""),
    ("multi-sig pattern with two signers",
     """Require two signers for high-value operations.

```rust
use anchor_lang::prelude::*;

#[derive(Accounts)]
pub struct DualSign<'info> {
    pub signer_a: Signer<'info>,
    pub signer_b: Signer<'info>,

    #[account(
        mut,
        constraint = vault.signer_a == signer_a.key() @ MyError::WrongSignerA,
        constraint = vault.signer_b == signer_b.key() @ MyError::WrongSignerB,
    )]
    pub vault: Account<'info, MultiSigVault>,
}

#[account]
#[derive(InitSpace)]
pub struct MultiSigVault {
    pub signer_a: Pubkey,
    pub signer_b: Pubkey,
    pub balance: u64,
    pub bump: u8,
}
```

Both signers must be included in the transaction's signers array. This provides basic 2-of-2 multisig."""),
    ("M-of-N multisig approval",
     """Implement M-of-N approval where M signers out of N must approve.

```rust
use anchor_lang::prelude::*;

#[account]
#[derive(InitSpace)]
pub struct Multisig {
    pub threshold: u8,           // M: required approvals
    #[max_len(10)]
    pub signers: Vec<Pubkey>,    // N: authorized signers
    pub bump: u8,
}

#[account]
#[derive(InitSpace)]
pub struct Transaction {
    pub multisig: Pubkey,
    pub instruction_data: [u8; 256],
    #[max_len(10)]
    pub approvals: Vec<bool>,    // Tracks who approved
    pub executed: bool,
    pub bump: u8,
}

pub fn approve(ctx: Context<Approve>) -> Result<()> {
    let multisig = &ctx.accounts.multisig;
    let tx = &mut ctx.accounts.transaction;
    let signer = ctx.accounts.signer.key();

    // Find signer index
    let idx = multisig.signers.iter()
        .position(|s| s == &signer)
        .ok_or(MyError::NotASigner)?;

    require!(!tx.approvals[idx], MyError::AlreadyApproved);
    tx.approvals[idx] = true;

    // Check if threshold met
    let approval_count = tx.approvals.iter().filter(|&&a| a).count();
    if approval_count >= multisig.threshold as usize {
        // Execute the transaction...
        tx.executed = true;
    }
    Ok(())
}
```"""),
    ("program-as-signer via PDA",
     """Use a PDA as a program-controlled signer for CPIs.

```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

pub fn vault_withdraw(ctx: Context<VaultWithdraw>, amount: u64) -> Result<()> {
    let seeds = &[
        b"vault_authority".as_ref(),
        ctx.accounts.vault.mint.as_ref(),
        &[ctx.accounts.vault.auth_bump],
    ];
    let signer_seeds = &[&seeds[..]];

    token::transfer(
        CpiContext::new_with_signer(
            ctx.accounts.token_program.to_account_info(),
            Transfer {
                from: ctx.accounts.vault_tokens.to_account_info(),
                to: ctx.accounts.user_tokens.to_account_info(),
                authority: ctx.accounts.vault_authority.to_account_info(),
            },
            signer_seeds,
        ),
        amount,
    )?;
    Ok(())
}

#[derive(Accounts)]
pub struct VaultWithdraw<'info> {
    #[account(mut)]
    pub user: Signer<'info>,
    #[account(has_one = user, seeds = [b"vault", user.key().as_ref()], bump = vault.bump)]
    pub vault: Account<'info, VaultState>,
    /// CHECK: PDA authority for token account
    #[account(seeds = [b"vault_authority", vault.mint.as_ref()], bump = vault.auth_bump)]
    pub vault_authority: UncheckedAccount<'info>,
    #[account(mut, token::authority = vault_authority)]
    pub vault_tokens: Account<'info, TokenAccount>,
    #[account(mut, token::authority = user)]
    pub user_tokens: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}
```

The PDA `vault_authority` cannot sign client-side transactions. It signs only through `CpiContext::new_with_signer` with the correct seeds."""),
    ("PDA signer seeds construction",
     """Properly construct signer seeds for PDA signing.

```rust
use anchor_lang::prelude::*;

pub fn pda_action(ctx: Context<PDAAction>) -> Result<()> {
    // Method 1: Seeds from account fields
    let pool_key = ctx.accounts.pool.key();
    let seeds = &[
        b"pool_auth".as_ref(),
        pool_key.as_ref(),
        &[ctx.accounts.pool.auth_bump],
    ];
    let signer_seeds = &[&seeds[..]];

    // Method 2: Multiple PDA signers (rare but possible)
    let seeds_a = &[b"auth_a".as_ref(), &[bump_a]];
    let seeds_b = &[b"auth_b".as_ref(), &[bump_b]];
    let multi_signers = &[&seeds_a[..], &seeds_b[..]];

    // Use in CPI:
    some_cpi(CpiContext::new_with_signer(program, accounts, signer_seeds))?;
    Ok(())
}
```

Key rules:
- Seeds must exactly match what was used to derive the PDA
- The bump byte is always the last element
- Store bumps in account state to avoid re-derivation
- Use `ctx.bumps.field_name` during `init` to get the canonical bump"""),
    ("optional signer pattern",
     """Handle optional signers for instructions that may or may not need authorization.

```rust
use anchor_lang::prelude::*;

#[derive(Accounts)]
pub struct MaybeAuth<'info> {
    pub user: Signer<'info>,

    #[account(
        mut,
        seeds = [b"item", item.key().as_ref()],
        bump = item.bump,
    )]
    pub item: Account<'info, Item>,

    /// CHECK: Admin for privileged actions, otherwise can be any account
    pub admin: UncheckedAccount<'info>,

    #[account(seeds = [b"config"], bump = config.bump)]
    pub config: Account<'info, Config>,
}

pub fn update_item(ctx: Context<MaybeAuth>, new_value: u64) -> Result<()> {
    let item = &mut ctx.accounts.item;

    if item.owner == ctx.accounts.user.key() {
        // Owner can always update
        item.value = new_value;
    } else if ctx.accounts.admin.is_signer
        && ctx.accounts.admin.key() == ctx.accounts.config.admin
    {
        // Admin can override
        item.value = new_value;
    } else {
        return err!(MyError::Unauthorized);
    }
    Ok(())
}
```

Check `is_signer` manually on `UncheckedAccount` for conditional signer verification."""),
    ("delegated authority pattern",
     """Allow an authority to delegate signing rights to another wallet.

```rust
use anchor_lang::prelude::*;

#[account]
#[derive(InitSpace)]
pub struct Delegation {
    pub owner: Pubkey,
    pub delegate: Pubkey,
    pub expires_at: i64,
    pub permissions: u8,   // Bitfield: 1=read, 2=write, 4=close
    pub bump: u8,
}

#[derive(Accounts)]
pub struct DelegatedAction<'info> {
    pub actor: Signer<'info>,

    #[account(
        seeds = [b"delegation", delegation.owner.as_ref(), actor.key().as_ref()],
        bump = delegation.bump,
        constraint = delegation.delegate == actor.key() @ MyError::NotDelegate,
        constraint = delegation.expires_at > Clock::get()?.unix_timestamp @ MyError::DelegationExpired,
        constraint = delegation.permissions & 2 != 0 @ MyError::NoWritePermission,
    )]
    pub delegation: Account<'info, Delegation>,

    #[account(mut, has_one = owner)]
    pub resource: Account<'info, Resource>,

    /// CHECK: Resource owner, verified by has_one
    pub owner: UncheckedAccount<'info>,
}
```

The delegation PDA is derived from (owner, delegate) and stores time-limited, permission-scoped access."""),
    ("role-based access control",
     """Implement role-based access with an on-chain role registry.

```rust
use anchor_lang::prelude::*;

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, PartialEq, Eq, InitSpace)]
pub enum Role {
    Admin,
    Operator,
    Minter,
    Pauser,
}

#[account]
#[derive(InitSpace)]
pub struct RoleAssignment {
    pub user: Pubkey,
    pub role: Role,
    pub granted_by: Pubkey,
    pub granted_at: i64,
    pub bump: u8,
}

#[derive(Accounts)]
#[instruction(required_role: Role)]
pub struct RequireRole<'info> {
    pub actor: Signer<'info>,

    #[account(
        seeds = [b"role", actor.key().as_ref(), &[required_role as u8]],
        bump = role_assignment.bump,
        constraint = role_assignment.user == actor.key() @ MyError::WrongUser,
        constraint = role_assignment.role == required_role @ MyError::WrongRole,
    )]
    pub role_assignment: Account<'info, RoleAssignment>,
}
```

Each (user, role) pair is a separate PDA. To check if a user has a role, the PDA must exist and pass validation."""),
    ("upgrade authority pattern",
     """Implement a two-step authority transfer (propose + accept) to prevent accidental lockout.

```rust
use anchor_lang::prelude::*;

#[account]
#[derive(InitSpace)]
pub struct Governed {
    pub authority: Pubkey,
    pub pending_authority: Option<Pubkey>,
    pub bump: u8,
}

pub fn propose_authority(ctx: Context<ProposeAuth>, new_authority: Pubkey) -> Result<()> {
    let gov = &mut ctx.accounts.governed;
    gov.pending_authority = Some(new_authority);
    msg!("Proposed new authority: {}", new_authority);
    Ok(())
}

pub fn accept_authority(ctx: Context<AcceptAuth>) -> Result<()> {
    let gov = &mut ctx.accounts.governed;
    gov.authority = ctx.accounts.new_authority.key();
    gov.pending_authority = None;
    msg!("Authority transferred to: {}", gov.authority);
    Ok(())
}

#[derive(Accounts)]
pub struct ProposeAuth<'info> {
    pub authority: Signer<'info>,
    #[account(mut, has_one = authority)]
    pub governed: Account<'info, Governed>,
}

#[derive(Accounts)]
pub struct AcceptAuth<'info> {
    pub new_authority: Signer<'info>,
    #[account(
        mut,
        constraint = governed.pending_authority == Some(new_authority.key()) @ MyError::NotPendingAuth,
    )]
    pub governed: Account<'info, Governed>,
}
```

Two-step transfer prevents accidentally setting authority to a wrong or inaccessible address."""),
]

for title, answer_body in SIGNER_PATTERNS:
    q = f"How do I implement a {title} in an Anchor program?"
    a = answer_body
    content = f"### Question\n{q}\n\n### Answer\n{a}"
    records.append(make_record(content, "signer_authority"))

# ═══════════════════════════════════════════════════════════════════════════════
# 11. Account lifecycle (15 records)
# ═══════════════════════════════════════════════════════════════════════════════

LIFECYCLE_ENTITIES = [
    ("subscription", "Subscription", "SubscriptionStatus",
     ["Pending", "Active", "Paused", "Cancelled", "Expired"],
     [("user", "Pubkey"), ("plan", "u8"), ("started_at", "i64"), ("expires_at", "i64")]),
    ("order", "Order", "OrderStatus",
     ["Created", "Funded", "Filled", "Settled", "Cancelled"],
     [("maker", "Pubkey"), ("price", "u64"), ("amount", "u64"), ("filled_amount", "u64")]),
    ("proposal", "Proposal", "ProposalStatus",
     ["Draft", "Active", "Passed", "Rejected", "Executed"],
     [("proposer", "Pubkey"), ("votes_for", "u64"), ("votes_against", "u64"), ("execute_after", "i64")]),
    ("loan", "Loan", "LoanStatus",
     ["Requested", "Approved", "Active", "Repaid", "Defaulted"],
     [("borrower", "Pubkey"), ("principal", "u64"), ("interest_rate", "u16"), ("due_date", "i64")]),
    ("escrow", "Escrow", "EscrowStatus",
     ["Initialized", "Funded", "Released", "Disputed", "Resolved"],
     [("buyer", "Pubkey"), ("seller", "Pubkey"), ("amount", "u64"), ("deadline", "i64")]),
]

for e_snake, e_name, status_enum, statuses, fields in LIFECYCLE_ENTITIES:
    # Init record
    q = f"How do I initialize a `{e_name}` account with a state machine pattern in Anchor?"
    a = f"""Use an enum to represent the lifecycle status of a `{e_name}`:

```rust
use anchor_lang::prelude::*;

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, PartialEq, Eq, InitSpace)]
pub enum {status_enum} {{
{chr(10).join(f"    {s}," for s in statuses)}
}}

#[account]
#[derive(InitSpace)]
pub struct {e_name} {{
{chr(10).join(f"    pub {f}: {t}," for f, t in fields)}
    pub status: {status_enum},
    pub bump: u8,
}}

pub fn initialize_{e_snake}(ctx: Context<Init{e_name}>) -> Result<()> {{
    let {e_snake} = &mut ctx.accounts.{e_snake};
    {e_snake}.{fields[0][0]} = ctx.accounts.authority.key();
    {e_snake}.status = {status_enum}::{statuses[0]};
    {e_snake}.bump = ctx.bumps.{e_snake};
    Ok(())
}}

#[derive(Accounts)]
pub struct Init{e_name}<'info> {{
    #[account(mut)]
    pub authority: Signer<'info>,

    #[account(
        init,
        payer = authority,
        space = 8 + {e_name}::INIT_SPACE,
        seeds = [b"{e_snake}", authority.key().as_ref()],
        bump,
    )]
    pub {e_snake}: Account<'info, {e_name}>,

    pub system_program: Program<'info, System>,
}}
```

The account starts in `{statuses[0]}` status. Each subsequent instruction validates the current status before transitioning."""
    content = f"### Question\n{q}\n\n### Answer\n{a}"
    records.append(make_record(content, "account_lifecycle"))

    # Transition record
    q2 = f"How do I implement state transitions for a `{e_name}` (from `{statuses[0]}` to `{statuses[1]}` to `{statuses[2]}`) in Anchor?"
    a2 = f"""Validate the current status before each transition using constraints:

```rust
use anchor_lang::prelude::*;

pub fn activate_{e_snake}(ctx: Context<Transition{e_name}>) -> Result<()> {{
    let {e_snake} = &mut ctx.accounts.{e_snake};

    // Validate transition: {statuses[0]} -> {statuses[1]}
    require!(
        {e_snake}.status == {status_enum}::{statuses[0]},
        {e_name}Error::Invalid{status_enum}Transition,
    );

    {e_snake}.status = {status_enum}::{statuses[1]};
    msg!("{e_name} transitioned to {statuses[1]}");
    Ok(())
}}

pub fn advance_{e_snake}(ctx: Context<Transition{e_name}>) -> Result<()> {{
    let {e_snake} = &mut ctx.accounts.{e_snake};

    // Validate transition: {statuses[1]} -> {statuses[2]}
    require!(
        {e_snake}.status == {status_enum}::{statuses[1]},
        {e_name}Error::Invalid{status_enum}Transition,
    );

    {e_snake}.status = {status_enum}::{statuses[2]};
    Ok(())
}}

#[derive(Accounts)]
pub struct Transition{e_name}<'info> {{
    pub authority: Signer<'info>,

    #[account(
        mut,
        has_one = {fields[0][0]} @ {e_name}Error::Unauthorized,
        seeds = [b"{e_snake}", {fields[0][0]}.key().as_ref()],
        bump = {e_snake}.bump,
    )]
    pub {e_snake}: Account<'info, {e_name}>,

    /// CHECK: Referenced by has_one
    pub {fields[0][0]}: UncheckedAccount<'info>,
}}

#[error_code]
pub enum {e_name}Error {{
    #[msg("Invalid status transition")]
    Invalid{status_enum}Transition,
    #[msg("Unauthorized")]
    Unauthorized,
}}
```

Each instruction enforces a specific valid transition. Invalid transitions (e.g., `{statuses[2]}` -> `{statuses[0]}`) are rejected."""
    content2 = f"### Question\n{q2}\n\n### Answer\n{a2}"
    records.append(make_record(content2, "account_lifecycle"))

    # Close record
    q3 = f"How do I close a `{e_name}` account after it reaches a terminal state (`{statuses[-1]}` or `{statuses[-2]}`) in Anchor?"
    a3 = f"""Only allow closing when the account is in a terminal state:

```rust
use anchor_lang::prelude::*;

pub fn close_{e_snake}(ctx: Context<Close{e_name}>) -> Result<()> {{
    let {e_snake} = &ctx.accounts.{e_snake};

    // Only terminal states can be closed
    require!(
        {e_snake}.status == {status_enum}::{statuses[-1]}
            || {e_snake}.status == {status_enum}::{statuses[-2]},
        {e_name}Error::CannotCloseActiveAccount,
    );

    // The close constraint handles lamport transfer and data zeroing
    Ok(())
}}

#[derive(Accounts)]
pub struct Close{e_name}<'info> {{
    #[account(mut)]
    pub authority: Signer<'info>,

    #[account(
        mut,
        close = authority,
        has_one = {fields[0][0]} @ {e_name}Error::Unauthorized,
        seeds = [b"{e_snake}", {fields[0][0]}.key().as_ref()],
        bump = {e_snake}.bump,
        constraint = {e_snake}.status == {status_enum}::{statuses[-1]}
            || {e_snake}.status == {status_enum}::{statuses[-2]}
            @ {e_name}Error::CannotCloseActiveAccount,
    )]
    pub {e_snake}: Account<'info, {e_name}>,

    /// CHECK: Referenced by has_one
    pub {fields[0][0]}: UncheckedAccount<'info>,
}}
```

The `close` constraint:
1. Transfers all lamports to `authority`
2. Zeros the account data (sets discriminator to `CLOSED_ACCOUNT_DISCRIMINATOR`)
3. Assigns the account to the System Program

This prevents account resurrection attacks and reclaims rent for the user."""
    content3 = f"### Question\n{q3}\n\n### Answer\n{a3}"
    records.append(make_record(content3, "account_lifecycle"))

# ═══════════════════════════════════════════════════════════════════════════════
# 12. Zero-copy accounts (10 records)
# ═══════════════════════════════════════════════════════════════════════════════

ZERO_COPY_EXAMPLES = [
    ("OrderBook", [("bids", "[Order; 256]"), ("asks", "[Order; 256]"), ("bid_count", "u32"), ("ask_count", "u32"), ("authority", "Pubkey")],
     "An order book with 512 orders (256 bids + 256 asks). At ~50 bytes per order, this is ~25 KB — too large for standard borsh deserialization."),
    ("PriceHistory", [("prices", "[PriceEntry; 1024]"), ("head", "u32"), ("count", "u32"), ("authority", "Pubkey")],
     "A circular buffer of 1024 price entries. Stores historical oracle prices on-chain for TWAP calculations."),
    ("Bitmap", [("bits", "[u8; 8192]"), ("authority", "Pubkey"), ("total_set", "u32")],
     "An 8 KB bitmap for tracking 65,536 boolean flags. Used for airdrop claim tracking or ticket validation."),
    ("LargeWhitelist", [("addresses", "[Pubkey; 256]"), ("count", "u16"), ("authority", "Pubkey")],
     "A whitelist of 256 addresses (8 KB). Zero-copy avoids deserializing all 256 pubkeys on every access."),
    ("GameBoard", [("cells", "[u8; 4096]"), ("width", "u16"), ("height", "u16"), ("turn_count", "u32"), ("authority", "Pubkey")],
     "A 64x64 game board stored as a flat array. Each cell is a u8 representing the tile state."),
    ("VotingMatrix", [("votes", "[u64; 1024]"), ("proposal_count", "u16"), ("authority", "Pubkey")],
     "Vote tallies for up to 1024 proposals. Each u64 stores the vote count for one proposal."),
    ("TokenBalanceSheet", [("balances", "[Balance; 512]"), ("token_count", "u16"), ("authority", "Pubkey")],
     "Tracks balances for up to 512 tokens. Used in portfolio tracking or multi-token vaults."),
    ("EventBuffer", [("events", "[EventEntry; 500]"), ("head", "u32"), ("tail", "u32"), ("authority", "Pubkey")],
     "A ring buffer of 500 events. New events overwrite the oldest when full. Zero-copy allows appending without full deserialization."),
    ("LeaderboardData", [("entries", "[LeaderEntry; 100]"), ("entry_count", "u8"), ("last_updated", "i64"), ("authority", "Pubkey")],
     "Top 100 leaderboard entries. Zero-copy allows updating a single entry without deserializing all 100."),
    ("CollateralRegistry", [("positions", "[CollateralPosition; 200]"), ("position_count", "u16"), ("total_collateral", "u64"), ("authority", "Pubkey")],
     "Tracks 200 collateral positions for a lending protocol. Zero-copy is critical for efficient position lookups."),
]

for struct_name, fields, description in ZERO_COPY_EXAMPLES:
    q = f"When and how should I use `#[account(zero_copy)]` for a `{struct_name}` in Anchor?"
    a = f"""Use `#[account(zero_copy)]` when your account exceeds ~10 KB or when you want to avoid full deserialization overhead.

{description}

```rust
use anchor_lang::prelude::*;

#[account(zero_copy)]
#[repr(C)]
pub struct {struct_name} {{
{chr(10).join(f"    pub {f}: {t}," for f, t in fields)}
}}

// Initialize a zero-copy account
#[derive(Accounts)]
pub struct Initialize{struct_name}<'info> {{
    #[account(mut)]
    pub authority: Signer<'info>,

    #[account(
        init,
        payer = authority,
        space = 8 + std::mem::size_of::<{struct_name}>(),
    )]
    pub {struct_name.lower()}: AccountLoader<'info, {struct_name}>,

    pub system_program: Program<'info, System>,
}}

// Access a zero-copy account
pub fn read_{struct_name.lower()}(ctx: Context<Read{struct_name}>) -> Result<()> {{
    let data = ctx.accounts.{struct_name.lower()}.load()?;
    msg!("Authority: {{}}", data.authority);
    Ok(())
}}

pub fn write_{struct_name.lower()}(ctx: Context<Write{struct_name}>) -> Result<()> {{
    let mut data = ctx.accounts.{struct_name.lower()}.load_mut()?;
    // Modify specific fields without full deserialization
    data.authority = ctx.accounts.new_authority.key();
    Ok(())
}}
```

Key rules for `zero_copy`:
1. **`#[repr(C)]`** is required — ensures predictable memory layout
2. Use **`AccountLoader<'info, T>`** instead of `Account<'info, T>`
3. Call **`.load()`** for read access, **`.load_mut()`** for write access
4. **No `String` or `Vec`** — only fixed-size types (arrays, primitives, fixed structs)
5. All inner types must also be `#[repr(C)]` and implement `bytemuck::Pod + Zeroable`
6. Space is `8 + std::mem::size_of::<T>()` (discriminator + struct size)
7. **Alignment**: fields must be naturally aligned (u64 on 8-byte boundary, u32 on 4-byte, etc.)"""
    content = f"### Question\n{q}\n\n### Answer\n{a}"
    records.append(make_record(content, "zero_copy"))

# ═══════════════════════════════════════════════════════════════════════════════
# 13. Remaining accounts (10 records)
# ═══════════════════════════════════════════════════════════════════════════════

REMAINING_SCENARIOS = [
    ("batch airdrop to multiple recipients",
     """Iterate `ctx.remaining_accounts` to send tokens to a dynamic list of recipients.

```rust
use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};

pub fn batch_airdrop(ctx: Context<BatchAirdrop>, amount_per_recipient: u64) -> Result<()> {
    let remaining = &ctx.remaining_accounts;

    // Remaining accounts are (recipient_ata, recipient_ata, ...)
    require!(remaining.len() > 0, MyError::NoRecipients);
    require!(remaining.len() <= 20, MyError::TooManyRecipients);

    let seeds = &[b"airdrop_vault".as_ref(), &[ctx.accounts.vault.bump]];

    for recipient_ata_info in remaining.iter() {
        // Validate each account is a token account with correct mint
        let recipient_ata = Account::<TokenAccount>::try_from(recipient_ata_info)?;
        require!(recipient_ata.mint == ctx.accounts.mint.key(), MyError::WrongMint);

        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from: ctx.accounts.source.to_account_info(),
                    to: recipient_ata_info.clone(),
                    authority: ctx.accounts.vault.to_account_info(),
                },
                &[seeds],
            ),
            amount_per_recipient,
        )?;
    }

    Ok(())
}
```

Always validate each remaining account — never trust them blindly."""),
    ("dynamic account resolution for a swap router",
     """Route a swap through dynamic intermediate pools passed as remaining accounts.

```rust
use anchor_lang::prelude::*;

pub fn route_swap(ctx: Context<RouteSwap>, amount_in: u64, min_out: u64) -> Result<()> {
    let remaining = &ctx.remaining_accounts;

    // Remaining accounts come in groups of 3: [pool, token_a, token_b]
    require!(remaining.len() % 3 == 0, MyError::InvalidAccountCount);

    let mut current_amount = amount_in;

    for chunk in remaining.chunks(3) {
        let pool_info = &chunk[0];
        let token_from_info = &chunk[1];
        let token_to_info = &chunk[2];

        // Validate pool account is owned by the DEX program
        require!(
            pool_info.owner == &ctx.accounts.dex_program.key(),
            MyError::InvalidPool,
        );

        // Execute swap via CPI (simplified)
        // current_amount = swap_cpi(pool, token_from, token_to, current_amount)?;
        msg!("Swapped {} through pool {}", current_amount, pool_info.key());
    }

    require!(current_amount >= min_out, MyError::SlippageExceeded);
    Ok(())
}
```"""),
    ("validating remaining accounts against a whitelist",
     """Check that all remaining accounts are in an on-chain whitelist.

```rust
use anchor_lang::prelude::*;

pub fn process_whitelisted(ctx: Context<ProcessWhitelisted>) -> Result<()> {
    let whitelist = &ctx.accounts.whitelist;
    let remaining = &ctx.remaining_accounts;

    for account_info in remaining.iter() {
        // Verify each account's key is in the whitelist
        let is_whitelisted = whitelist.addresses.iter()
            .any(|addr| addr == &account_info.key());

        require!(is_whitelisted, MyError::NotWhitelisted);

        // Process the whitelisted account...
        msg!("Processing whitelisted account: {}", account_info.key());
    }

    Ok(())
}

#[derive(Accounts)]
pub struct ProcessWhitelisted<'info> {
    pub authority: Signer<'info>,
    #[account(has_one = authority)]
    pub whitelist: Account<'info, Whitelist>,
}
```"""),
    ("collecting signatures from remaining accounts",
     """Verify multiple signers passed as remaining accounts for multi-party approval.

```rust
use anchor_lang::prelude::*;

pub fn multi_approve(ctx: Context<MultiApprove>) -> Result<()> {
    let config = &ctx.accounts.config;
    let remaining = &ctx.remaining_accounts;

    let mut valid_signers = 0u8;

    for account_info in remaining.iter() {
        // Check if this remaining account is a signer
        if !account_info.is_signer {
            continue;
        }

        // Check if this signer is in our authorized list
        if config.authorized_signers.contains(&account_info.key()) {
            valid_signers += 1;
        }
    }

    require!(
        valid_signers >= config.required_signatures,
        MyError::InsufficientSignatures,
    );

    msg!("Approved with {}/{} signatures", valid_signers, config.required_signatures);
    Ok(())
}
```"""),
    ("iterating remaining accounts with index tracking",
     """Process remaining accounts with explicit index tracking for structured data.

```rust
use anchor_lang::prelude::*;

pub fn process_pairs(ctx: Context<ProcessPairs>) -> Result<()> {
    let remaining = &ctx.remaining_accounts;

    require!(remaining.len() % 2 == 0, MyError::OddAccountCount);

    let mut index = 0usize;
    while index < remaining.len() {
        let account_a = &remaining[index];
        let account_b = &remaining[index + 1];

        // Validate pair relationship
        require!(account_a.is_writable, MyError::AccountNotWritable);
        require!(account_b.is_writable, MyError::AccountNotWritable);

        // Process the pair
        msg!("Processing pair: {} and {}", account_a.key(), account_b.key());

        index += 2;
    }

    Ok(())
}
```

Using index-based iteration gives you precise control over which accounts form logical groups."""),
    ("deserializing remaining accounts as typed Anchor accounts",
     """Deserialize remaining accounts into typed Anchor account structs for validation.

```rust
use anchor_lang::prelude::*;

pub fn process_typed_remaining(ctx: Context<TypedRemaining>) -> Result<()> {
    let remaining = &ctx.remaining_accounts;

    for account_info in remaining.iter() {
        // Try to deserialize as our program's account type
        let typed: Account<UserProfile> = Account::try_from(account_info)?;

        // Now we have full type-safe access
        require!(typed.is_active, MyError::InactiveProfile);
        msg!("Profile owner: {}, level: {}", typed.owner, typed.level);

        // Note: This checks:
        // 1. Account owner == our program ID
        // 2. Discriminator matches UserProfile
        // 3. Data deserializes correctly
    }

    Ok(())
}

#[account]
#[derive(InitSpace)]
pub struct UserProfile {
    pub owner: Pubkey,
    pub level: u8,
    pub is_active: bool,
    pub bump: u8,
}
```"""),
    ("passing remaining accounts through CPI",
     """Forward remaining accounts to a CPI call for composability.

```rust
use anchor_lang::prelude::*;

pub fn forward_to_program(ctx: Context<ForwardAccounts>) -> Result<()> {
    let remaining = &ctx.remaining_accounts;

    // Build account metas from remaining accounts
    let mut account_metas: Vec<AccountMeta> = Vec::new();
    let mut account_infos: Vec<AccountInfo> = Vec::new();

    for account_info in remaining.iter() {
        let meta = if account_info.is_writable {
            if account_info.is_signer {
                AccountMeta::new(account_info.key(), true)
            } else {
                AccountMeta::new(account_info.key(), false)
            }
        } else {
            AccountMeta::new_readonly(account_info.key(), account_info.is_signer)
        };
        account_metas.push(meta);
        account_infos.push(account_info.clone());
    }

    // Invoke target program with forwarded accounts
    let ix = anchor_lang::solana_program::instruction::Instruction {
        program_id: ctx.accounts.target_program.key(),
        accounts: account_metas,
        data: vec![], // Build your instruction data
    };

    anchor_lang::solana_program::program::invoke(&ix, &account_infos)?;
    Ok(())
}
```"""),
    ("counting and validating remaining account types",
     """Count different account types in remaining accounts for validation.

```rust
use anchor_lang::prelude::*;

pub fn validate_remaining(ctx: Context<ValidateRemaining>) -> Result<()> {
    let remaining = &ctx.remaining_accounts;

    let mut signer_count = 0u32;
    let mut writable_count = 0u32;
    let mut program_owned = 0u32;

    for info in remaining.iter() {
        if info.is_signer {
            signer_count += 1;
        }
        if info.is_writable {
            writable_count += 1;
        }
        if info.owner == ctx.program_id {
            program_owned += 1;
        }
    }

    msg!("Remaining: {} total, {} signers, {} writable, {} program-owned",
        remaining.len(), signer_count, writable_count, program_owned);

    require!(signer_count >= 1, MyError::NoSignerInRemaining);
    Ok(())
}
```"""),
    ("optional accounts via remaining_accounts",
     """Use remaining accounts for truly optional accounts (not just Option<Account>).

```rust
use anchor_lang::prelude::*;

pub fn with_optional_referrer(ctx: Context<WithOptional>, amount: u64) -> Result<()> {
    let remaining = &ctx.remaining_accounts;

    // Process the main action
    let vault = &mut ctx.accounts.vault;
    vault.total_deposits += amount;

    // Optional: if a referrer account is passed, credit them
    if let Some(referrer_info) = remaining.first() {
        // Validate it's a program-owned account
        require!(
            referrer_info.owner == ctx.program_id,
            MyError::InvalidReferrer,
        );

        let mut referrer: Account<ReferralProfile> =
            Account::try_from(referrer_info)?;

        let referral_bonus = amount / 100; // 1% referral
        referrer.total_earnings += referral_bonus;

        // Serialize back manually since it's not in the Accounts struct
        let mut data = referrer_info.try_borrow_mut_data()?;
        let dst: &mut [u8] = &mut data;
        referrer.try_serialize(&mut &mut dst[8..])?;
    }

    Ok(())
}
```

Use remaining accounts when the number of optional accounts varies per call."""),
    ("remaining accounts with Anchor access control macro",
     """Combine remaining_accounts with custom validation logic.

```rust
use anchor_lang::prelude::*;

pub fn batch_update(ctx: Context<BatchUpdate>, values: Vec<u64>) -> Result<()> {
    let remaining = &ctx.remaining_accounts;

    require!(
        remaining.len() == values.len(),
        MyError::LengthMismatch,
    );

    for (i, account_info) in remaining.iter().enumerate() {
        // Verify owner
        require!(
            account_info.owner == ctx.program_id,
            MyError::WrongOwner,
        );

        // Verify writable
        require!(
            account_info.is_writable,
            MyError::AccountNotWritable,
        );

        // Deserialize, update, re-serialize
        let mut account: Account<DataEntry> =
            Account::try_from(account_info)?;

        // Verify this entry belongs to the signer
        require!(
            account.authority == ctx.accounts.authority.key(),
            MyError::Unauthorized,
        );

        account.value = values[i];

        let mut data = account_info.try_borrow_mut_data()?;
        account.try_serialize(&mut &mut data[8..])?;
    }

    msg!("Updated {} accounts", remaining.len());
    Ok(())
}

#[derive(Accounts)]
pub struct BatchUpdate<'info> {
    pub authority: Signer<'info>,
}
```

This pattern is useful for batch operations where the number of accounts varies per transaction."""),
]

for title, answer_body in REMAINING_SCENARIOS:
    q = f"How do I use `ctx.remaining_accounts` for {title} in Anchor?"
    a = answer_body
    content = f"### Question\n{q}\n\n### Answer\n{a}"
    records.append(make_record(content, "remaining_accounts"))


# ═══════════════════════════════════════════════════════════════════════════════
# Write output
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote {len(records)} records to {OUT_FILE}")

    # Category breakdown
    from collections import Counter
    cats = Counter(r["metadata"]["category"] for r in records)
    for cat, count in sorted(cats.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
