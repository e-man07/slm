#!/usr/bin/env python3
"""Bulk synthetic data generator — Part 8: CPI, composability, Token-2022.
Target: ~150 records.
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

# ── 1. CPI to Token Program (20 records) ──
TOKEN_OPS = [
    ("transfer", "Transfer SPL tokens between accounts",
     "token::transfer", "Transfer", "from, to, authority",
     "pub from: Account<'info, TokenAccount>,\n    pub to: Account<'info, TokenAccount>,\n    pub authority: Signer<'info>,",
     "token::transfer(cpi_ctx, amount)?;"),
    ("transfer_checked", "Transfer with decimal verification",
     "token::transfer_checked", "TransferChecked", "from, to, mint, authority",
     "pub from: Account<'info, TokenAccount>,\n    pub to: Account<'info, TokenAccount>,\n    pub mint: Account<'info, Mint>,\n    pub authority: Signer<'info>,",
     "token::transfer_checked(cpi_ctx, amount, decimals)?;"),
    ("mint_to", "Mint new tokens to an account",
     "token::mint_to", "MintTo", "mint, to, authority",
     "#[account(mut)]\n    pub mint: Account<'info, Mint>,\n    #[account(mut)]\n    pub to: Account<'info, TokenAccount>,\n    pub authority: Signer<'info>,",
     "token::mint_to(cpi_ctx, amount)?;"),
    ("burn", "Burn tokens from an account",
     "token::burn", "Burn", "mint, from, authority",
     "#[account(mut)]\n    pub mint: Account<'info, Mint>,\n    #[account(mut)]\n    pub from: Account<'info, TokenAccount>,\n    pub authority: Signer<'info>,",
     "token::burn(cpi_ctx, amount)?;"),
    ("approve", "Approve a delegate to spend tokens",
     "token::approve", "Approve", "to, delegate, authority",
     "#[account(mut)]\n    pub to: Account<'info, TokenAccount>,\n    /// CHECK: delegate\n    pub delegate: AccountInfo<'info>,\n    pub authority: Signer<'info>,",
     "token::approve(cpi_ctx, amount)?;"),
    ("revoke", "Revoke a delegate's approval",
     "token::revoke", "Revoke", "source, authority",
     "#[account(mut)]\n    pub source: Account<'info, TokenAccount>,\n    pub authority: Signer<'info>,",
     "token::revoke(cpi_ctx)?;"),
    ("freeze_account", "Freeze a token account",
     "token::freeze_account", "FreezeAccount", "account, mint, authority",
     "#[account(mut)]\n    pub account: Account<'info, TokenAccount>,\n    pub mint: Account<'info, Mint>,\n    pub authority: Signer<'info>,",
     "token::freeze_account(cpi_ctx)?;"),
    ("thaw_account", "Unfreeze a token account",
     "token::thaw_account", "ThawAccount", "account, mint, authority",
     "#[account(mut)]\n    pub account: Account<'info, TokenAccount>,\n    pub mint: Account<'info, Mint>,\n    pub authority: Signer<'info>,",
     "token::thaw_account(cpi_ctx)?;"),
    ("close_account", "Close a token account and reclaim SOL",
     "token::close_account", "CloseAccount", "account, destination, authority",
     "#[account(mut)]\n    pub account: Account<'info, TokenAccount>,\n    #[account(mut)]\n    /// CHECK: receives SOL\n    pub destination: AccountInfo<'info>,\n    pub authority: Signer<'info>,",
     "token::close_account(cpi_ctx)?;"),
    ("set_authority", "Change token account or mint authority",
     "token::set_authority", "SetAuthority", "account_or_mint, current_authority",
     "#[account(mut)]\n    pub account_or_mint: AccountInfo<'info>,\n    pub current_authority: Signer<'info>,",
     "token::set_authority(\n        cpi_ctx,\n        AuthorityType::AccountOwner,\n        Some(new_authority),\n    )?;"),
]

for fn_name, desc, cpi_fn, struct_name, _accs, acc_fields, call in TOKEN_OPS:
    records.append(make_rec(
        f"### Question\nHow do I {desc.lower()} using CPI in Anchor?\n\n### Answer\n```rust\nuse anchor_lang::prelude::*;\nuse anchor_spl::token::{{self, Token, TokenAccount, Mint}};\n\n#[derive(Accounts)]\npub struct {struct_name}Ctx<'info> {{\n    {acc_fields}\n    pub token_program: Program<'info, Token>,\n}}\n\npub fn handle_{fn_name}(ctx: Context<{struct_name}Ctx>, amount: u64) -> Result<()> {{\n    let cpi_ctx = CpiContext::new(\n        ctx.accounts.token_program.to_account_info(),\n        {cpi_fn.split('::')[1].title() if '::' in cpi_fn else struct_name} {{\n            // ... accounts\n        }},\n    );\n    {call}\n    Ok(())\n}}\n```",
        "cpi_token"
    ))

# PDA signer variants for each of first 10 ops
for fn_name, desc, cpi_fn, struct_name, _accs, acc_fields, call in TOKEN_OPS[:10]:
    records.append(make_rec(
        f"### Question\nHow do I {desc.lower()} from a PDA-controlled account in Anchor?\n\n### Answer\nUse `CpiContext::new_with_signer` when the authority is a PDA:\n\n```rust\nlet seeds = &[\n    b\"vault\",\n    ctx.accounts.mint.key().as_ref(),\n    &[ctx.accounts.vault_state.bump],\n];\nlet signer = &[&seeds[..]];\n\nlet cpi_ctx = CpiContext::new_with_signer(\n    ctx.accounts.token_program.to_account_info(),\n    {struct_name} {{\n        // ... accounts with PDA as authority\n    }},\n    signer,\n);\n{call}\n```\n\nKey: The PDA must be the authority of the token account, and you pass its seeds to prove ownership.",
        "cpi_pda_signer"
    ))

# ── 2. CPI to System Program (10 records) ──
SYSTEM_OPS = [
    ("create_account", "Create a new account with specific space and owner",
     "system_program::create_account(\n        CpiContext::new(system.to_account_info(), CreateAccount {\n            from: payer.to_account_info(),\n            to: new_account.to_account_info(),\n        }),\n        lamports,\n        space as u64,\n        &program_id,\n    )?;"),
    ("transfer_sol", "Transfer SOL between accounts",
     "system_program::transfer(\n        CpiContext::new(system.to_account_info(), Transfer {\n            from: from.to_account_info(),\n            to: to.to_account_info(),\n        }),\n        amount,\n    )?;"),
    ("transfer_sol_pda", "Transfer SOL from a PDA",
     "let seeds = &[b\"treasury\", &[bump]];\n    let signer = &[&seeds[..]];\n    system_program::transfer(\n        CpiContext::new_with_signer(\n            system.to_account_info(),\n            Transfer {\n                from: treasury_pda.to_account_info(),\n                to: recipient.to_account_info(),\n            },\n            signer,\n        ),\n        amount,\n    )?;"),
    ("allocate", "Allocate space for an account",
     "system_program::allocate(\n        CpiContext::new(system.to_account_info(), Allocate {\n            account_to_allocate: acc.to_account_info(),\n        }),\n        new_space as u64,\n    )?;"),
    ("assign", "Assign account ownership to a program",
     "system_program::assign(\n        CpiContext::new(system.to_account_info(), Assign {\n            account_to_assign: acc.to_account_info(),\n        }),\n        &my_program_id,\n    )?;"),
    ("sol_transfer_lamports", "Direct lamport transfer without CPI (for PDA-owned accounts)",
     "// For accounts owned by your program, you can transfer directly:\n    **ctx.accounts.from.to_account_info().try_borrow_mut_lamports()? -= amount;\n    **ctx.accounts.to.to_account_info().try_borrow_mut_lamports()? += amount;"),
    ("rent_exempt_check", "Check if account is rent-exempt",
     "let rent = Rent::get()?;\n    let balance = ctx.accounts.my_account.to_account_info().lamports();\n    let data_len = ctx.accounts.my_account.to_account_info().data_len();\n    require!(rent.is_exempt(balance, data_len), MyError::NotRentExempt);"),
    ("close_and_reclaim", "Close account and send SOL to receiver",
     "// Anchor's close constraint handles this:\n    #[account(mut, close = receiver)]\n    pub my_account: Account<'info, MyData>,\n    #[account(mut)]\n    /// CHECK: receives rent\n    pub receiver: AccountInfo<'info>,\n\n    // Manual equivalent:\n    let dest_lamports = ctx.accounts.receiver.lamports();\n    **ctx.accounts.receiver.lamports.borrow_mut() = dest_lamports + ctx.accounts.my_account.to_account_info().lamports();\n    **ctx.accounts.my_account.to_account_info().lamports.borrow_mut() = 0;"),
    ("create_pda_account", "Create a PDA account via CPI",
     "let seeds = &[b\"data\", user.key().as_ref(), &[bump]];\n    let signer = &[&seeds[..]];\n    system_program::create_account(\n        CpiContext::new_with_signer(\n            system.to_account_info(),\n            CreateAccount {\n                from: payer.to_account_info(),\n                to: pda.to_account_info(),\n            },\n            signer,\n        ),\n        rent.minimum_balance(space),\n        space as u64,\n        &ctx.program_id,\n    )?;"),
    ("native_sol_wrapping", "Wrap SOL into a token account",
     "// 1. Create wrapped SOL token account\n    // 2. Transfer SOL to it\n    system_program::transfer(cpi_ctx, amount)?;\n    // 3. Sync native balance\n    token::sync_native(CpiContext::new(\n        token_program.to_account_info(),\n        SyncNative { account: wrapped_sol_account.to_account_info() },\n    ))?;"),
]
for name, desc, code in SYSTEM_OPS:
    records.append(make_rec(
        f"### Question\nHow do I {desc.lower()} in Anchor?\n\n### Answer\n```rust\n{code}\n```",
        "cpi_system"
    ))

# ── 3. Token-2022 extensions (20 records) ──
EXTENSIONS = [
    ("transfer_hook", "How do I create a Token-2022 transfer hook?",
     "A transfer hook program is called automatically on every token transfer:\n\n```rust\nuse anchor_lang::prelude::*;\nuse spl_transfer_hook_interface::instruction::TransferHookInstruction;\n\n#[program]\npub mod transfer_hook {\n    use super::*;\n\n    pub fn transfer_hook(ctx: Context<TransferHook>, amount: u64) -> Result<()> {\n        // Custom logic executed on every transfer\n        msg!(\"Transfer hook: {} tokens moved\", amount);\n        \n        // Example: enforce transfer restrictions\n        let clock = Clock::get()?;\n        require!(\n            clock.unix_timestamp > ctx.accounts.config.transfer_start_time,\n            MyError::TransfersNotYetEnabled\n        );\n        Ok(())\n    }\n}\n```\n\nRegister the hook when creating the mint with `spl_token_2022::extension::transfer_hook`."),
    ("transfer_fee", "How do I add transfer fees with Token-2022?",
     "Token-2022's TransferFee extension charges fees on every transfer:\n\n```rust\n// The mint is created with a transfer fee config:\n// - fee_basis_points: e.g., 250 = 2.5%\n// - max_fee: maximum fee in token base units\n\n// Transfers automatically deduct fees:\n// If you transfer 1000 tokens with 2.5% fee:\n// - Recipient gets 975 tokens\n// - 25 tokens held as withheld fees in the recipient's account\n\n// Harvest fees (collect withheld fees to a designated account):\nuse spl_token_2022::instruction::harvest_withheld_tokens_to_mint;\n```"),
    ("confidential_transfer", "What are confidential transfers in Token-2022?",
     "Confidential transfers hide transfer amounts using zero-knowledge proofs:\n\n- Balances are encrypted using ElGamal\n- Transfers include ZK proofs that the sender has sufficient funds\n- Only the sender/recipient can see the actual amounts\n- Auditor keys can optionally decrypt for compliance\n\nNote: This is computationally expensive and adds significant transaction size."),
    ("permanent_delegate", "How does the permanent delegate extension work?",
     "A permanent delegate can transfer or burn tokens from ANY holder:\n\n```rust\n// Created during mint initialization\n// The delegate authority can:\n// 1. Transfer tokens from any account of this mint\n// 2. Burn tokens from any account of this mint\n\n// Use case: regulated assets, clawback mechanisms\n// WARNING: Users should be aware this authority exists\n```"),
    ("non_transferable", "How do I create soulbound/non-transferable tokens?",
     "Use the NonTransferable extension:\n\n```rust\n// Tokens can only be minted and burned, never transferred\n// Perfect for:\n// - Soulbound tokens (SBTs)\n// - Achievement badges\n// - Identity credentials\n// - Voting power that shouldn't be traded\n\n// Created by adding NonTransferable extension during mint init\n// Any transfer attempt will fail at the token program level\n```"),
    ("metadata_pointer", "How do I use the metadata pointer extension?",
     "Token-2022 can store metadata directly on the mint:\n\n```rust\n// Instead of a separate Metaplex metadata account,\n// store token metadata on the mint itself:\n// - name, symbol, uri\n// - Additional custom fields\n\nuse spl_token_2022::extension::metadata_pointer;\nuse spl_token_metadata_interface::state::TokenMetadata;\n\n// Benefits:\n// - One fewer account to manage\n// - Lower cost (no Metaplex fees)\n// - Atomic with mint creation\n```"),
    ("interest_bearing", "How do interest-bearing tokens work?",
     "The InterestBearingConfig extension simulates interest accrual:\n\n```rust\n// The displayed balance grows over time based on an interest rate\n// Actual token count doesn't change — it's a UI/calculation layer\n\n// rate_authority can update the rate\n// Useful for:\n// - Yield-bearing stablecoins\n// - Rebasing tokens\n// - Time-weighted voting power\n\n// Get the \"display\" amount:\n// amount_with_interest = raw_amount * (1 + rate * time_elapsed)\n```"),
    ("default_account_state", "How do I set a default state for new token accounts?",
     "DefaultAccountState extension makes new accounts frozen by default:\n\n```rust\n// When creating the mint with DefaultAccountState::Frozen:\n// - All new token accounts start frozen\n// - Mint authority must explicitly thaw accounts\n// - Useful for KYC/compliance flows\n\n// Flow:\n// 1. User creates token account (starts frozen)\n// 2. User completes KYC\n// 3. Authority thaws the account\n// 4. User can now receive/send tokens\n```"),
    ("group_pointer", "How do I use token groups with Token-2022?",
     "Token groups allow hierarchical token relationships:\n\n```rust\n// Group pointer: designates a mint as a group\n// Member pointer: designates a mint as a member of a group\n\n// Use cases:\n// - NFT collections (group = collection, members = individual NFTs)\n// - Token families (group = protocol token, members = LP tokens)\n// - Organizational tokens (group = DAO, members = sub-DAO tokens)\n```"),
    ("cpi_guard", "What does the CPI guard extension do?",
     "CPI Guard prevents certain actions during cross-program invocations:\n\n```rust\n// When enabled on a token account:\n// - Transfer cannot happen during CPI (only top-level)\n// - Prevents programs from moving tokens without explicit user approval\n\n// User enables: spl-token enable-cpi-guard <ACCOUNT>\n// User disables: spl-token disable-cpi-guard <ACCOUNT>\n\n// This protects users from malicious programs that might\n// try to drain tokens via CPI\n```"),
]

# 10 direct + 10 integration patterns
for name, q, a in EXTENSIONS:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "token_2022"))

# Token-2022 integration with Anchor (10 records)
ANCHOR_T22 = [
    ("interface_setup", "How do I support both Token and Token-2022 in Anchor?",
     "```rust\nuse anchor_spl::token_interface::{\n    TokenInterface, TokenAccount as ITokenAccount,\n    Mint as IMint, transfer_checked, TransferChecked,\n};\n\n#[derive(Accounts)]\npub struct Transfer<'info> {\n    #[account(mut)]\n    pub from: InterfaceAccount<'info, ITokenAccount>,\n    #[account(mut)]\n    pub to: InterfaceAccount<'info, ITokenAccount>,\n    pub mint: InterfaceAccount<'info, IMint>,\n    pub authority: Signer<'info>,\n    pub token_program: Interface<'info, TokenInterface>,\n}\n```\n\nUsing `Interface` and `InterfaceAccount` works with both Token and Token-2022."),
    ("detect_program", "How do I detect which token program an account uses?",
     "```rust\nuse anchor_spl::token::ID as TOKEN_ID;\nuse anchor_spl::token_2022::ID as TOKEN_2022_ID;\n\nlet owner = ctx.accounts.token_account.to_account_info().owner;\nif *owner == TOKEN_ID {\n    msg!(\"Standard SPL Token\");\n} else if *owner == TOKEN_2022_ID {\n    msg!(\"Token-2022\");\n}\n```"),
    ("create_t22_mint", "How do I create a Token-2022 mint with extensions in Anchor?",
     "```rust\n// Token-2022 mints need extra space for extensions.\n// Calculate space dynamically based on enabled extensions.\n// Use anchor_spl::token_2022 for the program reference.\n\nuse anchor_spl::token_2022::Token2022;\n\n#[derive(Accounts)]\npub struct CreateMint<'info> {\n    #[account(mut)]\n    pub payer: Signer<'info>,\n    /// CHECK: Will be initialized as mint\n    #[account(mut)]\n    pub mint: Signer<'info>,\n    pub token_program: Program<'info, Token2022>,\n    pub system_program: Program<'info, System>,\n}\n```"),
    ("transfer_t22", "How do I transfer Token-2022 tokens in Anchor?",
     "```rust\nuse anchor_spl::token_interface::{transfer_checked, TransferChecked, TokenInterface};\n\npub fn transfer_tokens(ctx: Context<Transfer>, amount: u64) -> Result<()> {\n    let decimals = ctx.accounts.mint.decimals;\n    transfer_checked(\n        CpiContext::new(\n            ctx.accounts.token_program.to_account_info(),\n            TransferChecked {\n                from: ctx.accounts.from.to_account_info(),\n                to: ctx.accounts.to.to_account_info(),\n                mint: ctx.accounts.mint.to_account_info(),\n                authority: ctx.accounts.authority.to_account_info(),\n            },\n        ),\n        amount,\n        decimals,\n    )\n}\n```\n\nAlways use `transfer_checked` with Token-2022 — it's required for mints with TransferFee extension."),
    ("get_extensions", "How do I read Token-2022 extension data?",
     "```rust\nuse spl_token_2022::extension::StateWithExtensions;\nuse spl_token_2022::state::Mint as T22Mint;\n\nlet mint_data = ctx.accounts.mint.to_account_info();\nlet mint_info = mint_data.try_borrow_data()?;\nlet mint = StateWithExtensions::<T22Mint>::unpack(&mint_info)?;\n\n// Check for transfer fee\nif let Ok(fee_config) = mint.get_extension::<TransferFeeConfig>() {\n    let fee_bps = fee_config.newer_transfer_fee.transfer_fee_basis_points;\n    msg!(\"Transfer fee: {} bps\", u16::from(fee_bps));\n}\n```"),
    ("close_t22", "How do I close a Token-2022 account with extensions?",
     "Some extensions (like TransferFee) may have withheld tokens. You must harvest them first:\n```rust\n// 1. Harvest withheld fees\n// 2. Then close the account normally\ntoken::close_account(cpi_ctx)?;\n```\n\nNon-transferable tokens can still be closed by burning them first."),
    ("t22_ata", "How do I create ATAs for Token-2022 mints?",
     "```typescript\nimport { getAssociatedTokenAddressSync, TOKEN_2022_PROGRAM_ID } from '@solana/spl-token';\n\nconst ata = getAssociatedTokenAddressSync(\n  mint,\n  owner,\n  false,\n  TOKEN_2022_PROGRAM_ID  // Must specify Token-2022!\n);\n```\n\nIn Anchor:\n```rust\n#[account(\n    init_if_needed,\n    payer = payer,\n    associated_token::mint = mint,\n    associated_token::authority = owner,\n    associated_token::token_program = token_program,  // Pass T22\n)]\npub token_account: InterfaceAccount<'info, ITokenAccount>,\n```"),
    ("t22_metadata", "How do I set metadata on a Token-2022 mint?",
     "```rust\n// After creating mint with metadata_pointer extension:\nuse spl_token_metadata_interface::instruction::initialize as init_metadata;\n\nlet ix = init_metadata(\n    &spl_token_2022::id(),\n    &mint_key,\n    &update_authority,\n    &mint_key,  // metadata address = mint address\n    &update_authority,\n    \"My Token\".to_string(),\n    \"TKN\".to_string(),\n    \"https://example.com/metadata.json\".to_string(),\n);\ninvoke(&ix, &accounts)?;\n```"),
    ("t22_vs_metaplex", "When should I use Token-2022 metadata vs Metaplex?",
     "**Token-2022 metadata:** Simpler, cheaper, built into the token program. Best for fungible tokens, simple NFTs, or when you want minimal dependencies.\n\n**Metaplex metadata:** Richer feature set — collections, creators, royalties, programmable NFTs, rule sets. Best for NFT ecosystems, marketplaces, or when you need advanced NFT features.\n\nRule of thumb:\n- Fungible tokens → Token-2022 metadata\n- NFTs for marketplaces → Metaplex\n- Simple badges/SBTs → Token-2022 (non-transferable + metadata)"),
    ("t22_migration", "How do I migrate from SPL Token to Token-2022?",
     "You can't convert existing mints. Migration requires:\n1. Create new Token-2022 mint with desired extensions\n2. Build a migration program that burns old tokens and mints new ones 1:1\n3. Or use a wrapper: users deposit old tokens, receive new ones\n\n```rust\n// Simplified migration instruction:\npub fn migrate(ctx: Context<Migrate>, amount: u64) -> Result<()> {\n    // Burn old SPL tokens\n    token::burn(old_ctx, amount)?;\n    // Mint new Token-2022 tokens\n    token_2022::mint_to(new_ctx_with_signer, amount)?;\n    Ok(())\n}\n```"),
]
for name, q, a in ANCHOR_T22:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "token_2022_anchor"))

# ── 4. Cross-program patterns (15 records) ──
CPI_PATTERNS = [
    ("return_data", "How do I pass data back from a CPI call?",
     "```rust\n// In the called program:\nuse anchor_lang::solana_program::program::set_return_data;\n\npub fn get_price(ctx: Context<GetPrice>) -> Result<()> {\n    let price: u64 = calculate_price();\n    set_return_data(&price.to_le_bytes());\n    Ok(())\n}\n\n// In the calling program:\nuse anchor_lang::solana_program::program::get_return_data;\n\npub fn use_price(ctx: Context<UsePrice>) -> Result<()> {\n    // CPI call...\n    let (_, data) = get_return_data().ok_or(MyError::NoReturnData)?;\n    let price = u64::from_le_bytes(data[..8].try_into().unwrap());\n    Ok(())\n}\n```"),
    ("emit_events", "How do I emit events in Anchor and subscribe to them?",
     "```rust\n#[event]\npub struct SwapEvent {\n    pub user: Pubkey,\n    pub amount_in: u64,\n    pub amount_out: u64,\n    pub timestamp: i64,\n}\n\npub fn swap(ctx: Context<Swap>, amount: u64) -> Result<()> {\n    // ... swap logic ...\n    emit!(SwapEvent {\n        user: ctx.accounts.user.key(),\n        amount_in: amount,\n        amount_out: output,\n        timestamp: Clock::get()?.unix_timestamp,\n    });\n    Ok(())\n}\n```\n\n```typescript\n// Subscribe in client\nconst listener = program.addEventListener('SwapEvent', (event) => {\n    console.log(`Swap: ${event.amountIn} -> ${event.amountOut}`);\n});\n// Remove listener\nprogram.removeEventListener(listener);\n```"),
    ("remaining_accounts_cpi", "How do I pass remaining accounts through CPI?",
     "```rust\npub fn process(ctx: Context<Process>) -> Result<()> {\n    let remaining = ctx.remaining_accounts;\n    \n    // Build CPI with remaining accounts\n    let mut cpi_accounts = vec![\n        ctx.accounts.main_account.to_account_info(),\n    ];\n    cpi_accounts.extend(remaining.iter().map(|a| a.to_account_info()));\n    \n    let ix = Instruction {\n        program_id: ctx.accounts.target_program.key(),\n        accounts: cpi_accounts.iter().map(|a| AccountMeta {\n            pubkey: a.key(),\n            is_signer: a.is_signer,\n            is_writable: a.is_writable,\n        }).collect(),\n        data: instruction_data,\n    };\n    invoke(&ix, &cpi_accounts)?;\n    Ok(())\n}\n```"),
    ("cpi_depth", "What's the CPI depth limit and how do I work within it?",
     "Solana allows max 4 levels of CPI nesting:\n- Level 0: Your program (called by runtime)\n- Level 1: Your program calls Token Program\n- Level 2: Token Program calls Transfer Hook\n- Level 3: Transfer Hook calls another program\n- Level 4: MAX — any deeper call fails\n\nDesign tips:\n- Keep CPI chains shallow\n- Combine operations into single instructions when possible\n- If hitting depth limits, restructure to use multiple top-level instructions"),
    ("invoke_signed", "When do I use invoke vs invoke_signed?",
     "```rust\nuse anchor_lang::solana_program::program::invoke;\nuse anchor_lang::solana_program::program::invoke_signed;\n\n// invoke: when a regular signer (keypair) authorizes\ninvoke(&instruction, &account_infos)?;\n\n// invoke_signed: when a PDA authorizes (program signs)\nlet seeds = &[b\"authority\", pool_key.as_ref(), &[bump]];\ninvoke_signed(&instruction, &account_infos, &[seeds])?;\n```\n\nIn Anchor, this is abstracted:\n```rust\n// Regular signer\nCpiContext::new(program, accounts)\n// PDA signer\nCpiContext::new_with_signer(program, accounts, signer_seeds)\n```"),
    ("anchor_cpi_module", "How do I use Anchor's CPI module for type-safe cross-program calls?",
     "```rust\n// In the called program's lib.rs, Anchor generates a CPI module.\n// In the calling program:\nuse other_program::cpi::accounts::DoSomething;\nuse other_program::cpi::do_something;\nuse other_program::program::OtherProgram;\n\n#[derive(Accounts)]\npub struct CallOther<'info> {\n    pub other_program: Program<'info, OtherProgram>,\n    // ... accounts needed by do_something\n}\n\npub fn call(ctx: Context<CallOther>) -> Result<()> {\n    let cpi_ctx = CpiContext::new(\n        ctx.accounts.other_program.to_account_info(),\n        DoSomething {\n            // ... accounts\n        },\n    );\n    do_something(cpi_ctx, args)?;\n    Ok(())\n}\n```"),
    ("composable_vault", "How do I build a composable vault that wraps token operations?",
     "```rust\n#[program]\npub mod fee_vault {\n    use super::*;\n    \n    pub fn deposit_with_fee(ctx: Context<Deposit>, amount: u64) -> Result<()> {\n        let fee = amount.checked_mul(ctx.accounts.config.fee_bps as u64)\n            .ok_or(MyError::Overflow)?\n            .checked_div(10_000)\n            .ok_or(MyError::Overflow)?;\n        let deposit = amount.checked_sub(fee).ok_or(MyError::Overflow)?;\n        \n        // Transfer fee to treasury\n        token::transfer(\n            CpiContext::new(ctx.accounts.token_program.to_account_info(),\n                Transfer { from: ctx.accounts.user_token.to_account_info(),\n                    to: ctx.accounts.treasury.to_account_info(),\n                    authority: ctx.accounts.user.to_account_info() }),\n            fee,\n        )?;\n        \n        // Transfer deposit to vault\n        token::transfer(\n            CpiContext::new(ctx.accounts.token_program.to_account_info(),\n                Transfer { from: ctx.accounts.user_token.to_account_info(),\n                    to: ctx.accounts.vault_token.to_account_info(),\n                    authority: ctx.accounts.user.to_account_info() }),\n            deposit,\n        )?;\n        Ok(())\n    }\n}\n```"),
    ("flash_loan_pattern", "How do I implement a flash loan pattern in Anchor?",
     "```rust\n// Flash loans require borrowing and repaying in the same transaction.\n// Use instruction introspection to verify repayment:\n\nuse anchor_lang::solana_program::sysvar::instructions;\n\npub fn flash_borrow(ctx: Context<FlashBorrow>, amount: u64) -> Result<()> {\n    // Verify that a repay instruction exists later in the transaction\n    let ixs = ctx.accounts.instructions.to_account_info();\n    let current_idx = instructions::load_current_index_checked(&ixs)? as usize;\n    \n    // Look ahead for repay instruction\n    let mut found_repay = false;\n    let num_ixs = instructions::get_instruction_relative(0, &ixs);\n    // ... check subsequent instructions for repay\n    \n    require!(found_repay, MyError::MissingRepayment);\n    \n    // Transfer tokens to borrower\n    token::transfer(cpi_ctx_with_signer, amount)?;\n    Ok(())\n}\n```"),
    ("event_cpi", "How do I use Anchor's event CPI feature?",
     "```rust\n// In Anchor 0.30+, events can be emitted via CPI for indexing:\n\n#[event]\npub struct PriceUpdate {\n    pub oracle: Pubkey,\n    pub price: u64,\n    pub slot: u64,\n}\n\npub fn update_price(ctx: Context<UpdatePrice>, price: u64) -> Result<()> {\n    ctx.accounts.oracle_state.price = price;\n    \n    emit!(PriceUpdate {\n        oracle: ctx.accounts.oracle_state.key(),\n        price,\n        slot: Clock::get()?.slot,\n    });\n    Ok(())\n}\n\n// Events are stored in transaction logs and can be:\n// 1. Parsed by indexers (Helius, Yellowstone)\n// 2. Subscribed to via WebSocket\n// 3. Queried from transaction history\n```"),
    ("atomic_operations", "How do I ensure atomicity across multiple CPI calls?",
     "Solana transactions are atomic — all instructions succeed or all fail. Use this:\n\n```rust\npub fn atomic_swap(ctx: Context<AtomicSwap>, amount_a: u64, amount_b: u64) -> Result<()> {\n    // Step 1: Transfer token A from user to pool\n    token::transfer(cpi_ctx_a, amount_a)?;\n    \n    // Step 2: Transfer token B from pool to user\n    token::transfer(cpi_ctx_b_with_signer, amount_b)?;\n    \n    // If step 2 fails, step 1 is also rolled back!\n    // No partial state — fully atomic.\n    Ok(())\n}\n```\n\nFor multi-instruction transactions, all instructions in the transaction are atomic together."),
    ("instruction_introspection", "How do I inspect other instructions in the same transaction?",
     "```rust\nuse anchor_lang::solana_program::sysvar::instructions::{\n    self, get_instruction_relative, load_current_index_checked,\n};\n\npub fn guarded_action(ctx: Context<Guarded>) -> Result<()> {\n    let ix_sysvar = &ctx.accounts.instruction_sysvar;\n    let current_idx = load_current_index_checked(ix_sysvar)? as usize;\n    \n    // Check the previous instruction\n    let prev_ix = get_instruction_relative(-1, ix_sysvar)?;\n    require!(\n        prev_ix.program_id == expected_program_id,\n        MyError::InvalidPrecedingInstruction\n    );\n    \n    Ok(())\n}\n\n#[derive(Accounts)]\npub struct Guarded<'info> {\n    /// CHECK: instruction sysvar\n    #[account(address = instructions::ID)]\n    pub instruction_sysvar: AccountInfo<'info>,\n}\n```"),
    ("program_id_validation", "How does Anchor validate program IDs in CPI?",
     "Anchor automatically validates program IDs:\n```rust\n// This ensures token_program is actually the Token Program:\npub token_program: Program<'info, Token>,\n\n// For custom programs:\npub my_program: Program<'info, MyOtherProgram>,\n\n// For unchecked programs (rare), validate manually:\n/// CHECK: validated in handler\npub external_program: AccountInfo<'info>,\n\n// In handler:\nrequire_keys_eq!(\n    ctx.accounts.external_program.key(),\n    expected_program_id,\n    MyError::InvalidProgram\n);\n```"),
    ("reusable_cpi_helpers", "How do I create reusable CPI helper functions?",
     "```rust\npub fn transfer_tokens<'info>(\n    token_program: &AccountInfo<'info>,\n    from: &AccountInfo<'info>,\n    to: &AccountInfo<'info>,\n    authority: &AccountInfo<'info>,\n    amount: u64,\n    signer_seeds: Option<&[&[&[u8]]]>,\n) -> Result<()> {\n    let cpi_accounts = Transfer {\n        from: from.clone(),\n        to: to.clone(),\n        authority: authority.clone(),\n    };\n    let cpi_ctx = match signer_seeds {\n        Some(seeds) => CpiContext::new_with_signer(token_program.clone(), cpi_accounts, seeds),\n        None => CpiContext::new(token_program.clone(), cpi_accounts),\n    };\n    token::transfer(cpi_ctx, amount)\n}\n```"),
    ("account_ownership_cpi", "How do I verify account ownership across CPI calls?",
     "```rust\n// Anchor does this automatically with typed accounts:\npub vault: Account<'info, TokenAccount>,  // Verifies Token Program owns it\npub data: Account<'info, MyStruct>,        // Verifies your program owns it\n\n// For manual checks:\nrequire!(\n    *ctx.accounts.account.owner == expected_owner,\n    MyError::InvalidOwner\n);\n\n// Important: After CPI, account data may be stale.\n// Reload if needed:\nctx.accounts.vault.reload()?;\nlet updated_balance = ctx.accounts.vault.amount;\n```"),
    ("callback_pattern", "How do I implement a callback pattern in Solana?",
     "Solana doesn't have callbacks, but you can use instruction introspection:\n\n```rust\n// Pattern: Require that your program is called again after the CPI\npub fn pre_action(ctx: Context<PreAction>) -> Result<()> {\n    let ixs = &ctx.accounts.instruction_sysvar;\n    let current = load_current_index_checked(ixs)? as i64;\n    \n    // Verify our program is called again later\n    let next_ix = get_instruction_relative(1, ixs)?;\n    require!(\n        next_ix.program_id == crate::ID,\n        MyError::MissingCallback\n    );\n    \n    // Store state for the \"callback\" to verify\n    ctx.accounts.state.pending = true;\n    Ok(())\n}\n\npub fn post_action(ctx: Context<PostAction>) -> Result<()> {\n    require!(ctx.accounts.state.pending, MyError::NoPending);\n    ctx.accounts.state.pending = false;\n    // Verify conditions met...\n    Ok(())\n}\n```"),
]
for name, q, a in CPI_PATTERNS:
    records.append(make_rec(f"### Question\n{q}\n\n### Answer\n{a}", "cpi_patterns"))

# ── 5. Composability: wrapping protocols (15 records) ──
PROTOCOLS = ["staking", "lending", "governance", "marketplace", "vault"]
WRAP_OPS = [
    ("deposit_with_fee", "deposit into {proto} with an automatic fee deduction"),
    ("withdraw_with_cooldown", "withdraw from {proto} with a cooldown period check"),
    ("admin_pause", "pause/unpause the {proto} for emergency stops"),
]
for proto in PROTOCOLS:
    for op_name, desc in WRAP_OPS:
        records.append(make_rec(
            f"### Question\nHow do I {desc.format(proto=proto)} in an Anchor program?\n\n### Answer\n```rust\nuse anchor_lang::prelude::*;\n\n#[program]\npub mod {proto}_wrapper {{\n    use super::*;\n\n    pub fn {op_name}(ctx: Context<{op_name.title().replace('_', '')}>, amount: u64) -> Result<()> {{\n        let config = &ctx.accounts.config;\n        require!(!config.paused, {proto.title()}Error::Paused);\n\n        // Validate and process\n        let clock = Clock::get()?;\n        msg!(\"{proto} {op_name}: {{}} at slot {{}}\", amount, clock.slot);\n\n        // CPI to underlying protocol...\n        Ok(())\n    }}\n}}\n\n#[error_code]\npub enum {proto.title()}Error {{\n    #[msg(\"Protocol is paused\")]\n    Paused,\n    #[msg(\"Cooldown not elapsed\")]\n    CooldownActive,\n    #[msg(\"Amount too low\")]\n    AmountTooLow,\n}}\n```",
            "composability"
        ))

# ── Write output ──
PROCESSED.mkdir(parents=True, exist_ok=True)
out = PROCESSED / "synthetic-bulk8.jsonl"
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
