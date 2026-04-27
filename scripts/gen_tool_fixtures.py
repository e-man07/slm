"""In-memory project fixtures for tool-calling synthetic data generation.

Each fixture builds a realistic Solana project tree under a tmp_path. Generators
use these fixtures so tool execution (read_file, glob_files, grep_files) returns
real, deterministic output that exactly matches what the production CLI produces.

Usage:
    from gen_tool_fixtures import build_fixture, FIXTURES, list_fixtures

    with build_fixture("anchor_counter") as fx:
        # fx.path is a tmp directory with the full project tree
        # fx.files lists every file under the tree (relative paths)
        # fx.name is "anchor_counter"
        ...
"""
from __future__ import annotations

import contextlib
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator


@dataclass
class Fixture:
    """A materialized project tree on disk."""
    name: str
    path: Path
    files: list[str]  # relative paths
    description: str  # one-line summary, used in user prompts


# ── Fixture content definitions ──
# Each fixture is a dict {relative_path: file_content}. Built fresh each run
# under a tmp directory. Content stays small (≤80 lines per file) so trajectories
# fit within max_seq_length=8192 tokens.


ANCHOR_COUNTER: dict[str, str] = {
    "Anchor.toml": '''[features]
seeds = false
skip-lint = false

[programs.localnet]
counter = "11111111111111111111111111111111"

[provider]
cluster = "Localnet"
wallet = "~/.config/solana/id.json"

[scripts]
test = "yarn run ts-mocha -p ./tsconfig.json -t 1000000 tests/**/*.ts"
''',
    "Cargo.toml": '''[workspace]
members = ["programs/*"]
resolver = "2"
''',
    "programs/counter/Cargo.toml": '''[package]
name = "counter"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib", "lib"]
name = "counter"

[dependencies]
anchor-lang = "0.30.1"
''',
    "programs/counter/src/lib.rs": '''use anchor_lang::prelude::*;

// Program ID is set in Anchor.toml

#[program]
pub mod counter {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        ctx.accounts.counter.count = 0;
        ctx.accounts.counter.authority = ctx.accounts.user.key();
        ctx.accounts.counter.bump = ctx.bumps.counter;
        Ok(())
    }

    pub fn increment(ctx: Context<Increment>) -> Result<()> {
        ctx.accounts.counter.count = ctx.accounts.counter.count
            .checked_add(1)
            .ok_or(ErrorCode::Overflow)?;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = user,
        space = 8 + 8 + 32 + 1,
        seeds = [b"counter", user.key().as_ref()],
        bump
    )]
    pub counter: Account<'info, Counter>,
    #[account(mut)]
    pub user: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct Increment<'info> {
    #[account(
        mut,
        seeds = [b"counter", authority.key().as_ref()],
        bump = counter.bump,
        has_one = authority,
    )]
    pub counter: Account<'info, Counter>,
    pub authority: Signer<'info>,
}

#[account]
pub struct Counter {
    pub count: u64,
    pub authority: Pubkey,
    pub bump: u8,
}

#[error_code]
pub enum ErrorCode {
    #[msg("Counter overflow")]
    Overflow,
}
''',
    "tests/counter.ts": '''import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { Counter } from "../target/types/counter";
import { assert } from "chai";

describe("counter", () => {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);
  const program = anchor.workspace.Counter as Program<Counter>;

  it("Initializes counter", async () => {
    const [counterPda] = anchor.web3.PublicKey.findProgramAddressSync(
      [Buffer.from("counter"), provider.wallet.publicKey.toBuffer()],
      program.programId
    );
    await program.methods.initialize().accounts({ counter: counterPda }).rpc();
    const account = await program.account.counter.fetch(counterPda);
    assert.equal(account.count.toNumber(), 0);
  });
});
''',
    "package.json": '''{
  "name": "counter",
  "version": "0.1.0",
  "scripts": {
    "test": "anchor test"
  },
  "dependencies": {
    "@coral-xyz/anchor": "^0.30.1"
  }
}
''',
    "tsconfig.json": '''{
  "compilerOptions": {
    "types": ["mocha", "chai"],
    "typeRoots": ["./node_modules/@types"],
    "lib": ["es2015"],
    "module": "commonjs",
    "target": "es6",
    "esModuleInterop": true
  }
}
''',
    "README.md": '''# Counter

A simple Anchor counter program with PDA-derived counter accounts.

## Build

    anchor build

## Test

    anchor test
''',
}


ANCHOR_VAULT: dict[str, str] = {
    "Anchor.toml": '''[programs.localnet]
vault = "11111111111111111111111111111111"

[provider]
cluster = "Localnet"
wallet = "~/.config/solana/id.json"
''',
    "programs/vault/Cargo.toml": '''[package]
name = "vault"
version = "0.1.0"
edition = "2021"

[dependencies]
anchor-lang = "0.30.1"
anchor-spl = "0.30.1"
''',
    "programs/vault/src/lib.rs": '''use anchor_lang::prelude::*;
use anchor_spl::token::{Token, TokenAccount, Transfer, transfer};

#[program]
pub mod vault {
    use super::*;

    pub fn deposit(ctx: Context<Deposit>, amount: u64) -> Result<()> {
        let cpi_accounts = Transfer {
            from: ctx.accounts.user_token.to_account_info(),
            to: ctx.accounts.vault_token.to_account_info(),
            authority: ctx.accounts.user.to_account_info(),
        };
        let cpi_ctx = CpiContext::new(ctx.accounts.token_program.to_account_info(), cpi_accounts);
        transfer(cpi_ctx, amount)?;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Deposit<'info> {
    #[account(mut)]
    pub user_token: Account<'info, TokenAccount>,
    #[account(mut)]
    pub vault_token: Account<'info, TokenAccount>,
    pub user: Signer<'info>,
    pub token_program: Program<'info, Token>,
}
''',
    "programs/vault/src/state.rs": '''use anchor_lang::prelude::*;

#[account]
pub struct Vault {
    pub authority: Pubkey,
    pub total_deposited: u64,
    pub bump: u8,
}
''',
    "programs/vault/src/errors.rs": '''use anchor_lang::prelude::*;

#[error_code]
pub enum VaultError {
    #[msg("Insufficient balance")]
    InsufficientBalance,
    #[msg("Vault is paused")]
    Paused,
}
''',
}


# A program with a deliberate PDA bug (uses ctx.bumps.get() — deprecated)
# Used for "find the bug" Group F examples.
ANCHOR_BUGGY: dict[str, str] = {
    "Anchor.toml": '''[programs.localnet]
buggy = "11111111111111111111111111111111"
''',
    "programs/buggy/src/lib.rs": '''use anchor_lang::prelude::*;

#[program]
pub mod buggy {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        // BUG: deprecated bump access pattern
        ctx.accounts.profile.bump = *ctx.bumps.get("profile").unwrap();
        ctx.accounts.profile.owner = ctx.accounts.user.key();
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = user,
        space = 8 + 32 + 1,
        seeds = [b"profile", user.key().as_ref()],
        bump,
    )]
    pub profile: Account<'info, Profile>,
    #[account(mut)]
    pub user: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[account]
pub struct Profile {
    pub owner: Pubkey,
    pub bump: u8,
}
''',
}


# A program that still uses declare_id! — for migration examples
ANCHOR_LEGACY: dict[str, str] = {
    "Anchor.toml": '''[programs.localnet]
legacy = "Fg6PaFpoGXkKXx2KcD684s5rJNHHk3JG462ZiJxkZuFZ"
''',
    "programs/legacy/src/lib.rs": '''use anchor_lang::prelude::*;

declare_id!("Fg6PaFpoGXkKXx2KcD684s5rJNHHk3JG462ZiJxkZuFZ");

#[program]
pub mod legacy {
    use super::*;

    pub fn create(ctx: Context<Create>) -> ProgramResult {
        ctx.accounts.data.value = 42;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Create<'info> {
    #[account(init, payer = user, space = 8 + 8)]
    pub data: Account<'info, Data>,
    #[account(mut)]
    pub user: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[account]
pub struct Data {
    pub value: u64,
}
''',
}


NATIVE_SOLANA: dict[str, str] = {
    "Cargo.toml": '''[package]
name = "native_program"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib", "lib"]

[dependencies]
solana-program = "1.18"
borsh = "1.5"
''',
    "src/lib.rs": '''use borsh::{BorshDeserialize, BorshSerialize};
use solana_program::{
    account_info::{next_account_info, AccountInfo},
    entrypoint,
    entrypoint::ProgramResult,
    msg,
    pubkey::Pubkey,
};

entrypoint!(process_instruction);

#[derive(BorshSerialize, BorshDeserialize, Debug)]
pub struct CounterAccount {
    pub count: u64,
}

pub fn process_instruction(
    _program_id: &Pubkey,
    accounts: &[AccountInfo],
    _instruction_data: &[u8],
) -> ProgramResult {
    let accounts_iter = &mut accounts.iter();
    let counter = next_account_info(accounts_iter)?;
    let mut data = CounterAccount::try_from_slice(&counter.data.borrow())?;
    data.count += 1;
    data.serialize(&mut &mut counter.data.borrow_mut()[..])?;
    msg!("Count: {}", data.count);
    Ok(())
}
''',
}


PINOCCHIO: dict[str, str] = {
    "Cargo.toml": '''[package]
name = "pinocchio_counter"
version = "0.1.0"
edition = "2021"

[lib]
crate-type = ["cdylib", "lib"]

[dependencies]
pinocchio = "0.7"
pinocchio-pubkey = "0.2"
''',
    "src/lib.rs": '''use pinocchio::{
    account_info::AccountInfo,
    entrypoint,
    program_error::ProgramError,
    pubkey::Pubkey,
    ProgramResult,
};

entrypoint!(process_instruction);

pub fn process_instruction(
    _program_id: &Pubkey,
    accounts: &[AccountInfo],
    instruction_data: &[u8],
) -> ProgramResult {
    let [counter_acct, _system_program] = accounts else {
        return Err(ProgramError::NotEnoughAccountKeys);
    };

    let mut data = counter_acct.try_borrow_mut_data()?;
    let value = u64::from_le_bytes(data[..8].try_into().unwrap());
    let new_value = value.wrapping_add(1);
    data[..8].copy_from_slice(&new_value.to_le_bytes());
    Ok(())
}
''',
}


# A multi-program workspace — exercises glob/grep across many files
MULTI_WORKSPACE: dict[str, str] = {
    "Anchor.toml": '''[programs.localnet]
escrow = "11111111111111111111111111111111"
oracle = "22222222222222222222222222222222"
''',
    "Cargo.toml": '''[workspace]
members = ["programs/escrow", "programs/oracle"]
resolver = "2"
''',
    "programs/escrow/Cargo.toml": '''[package]
name = "escrow"
version = "0.1.0"
edition = "2021"

[dependencies]
anchor-lang = "0.30.1"
''',
    "programs/escrow/src/lib.rs": '''use anchor_lang::prelude::*;

#[program]
pub mod escrow {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>, amount: u64) -> Result<()> {
        ctx.accounts.escrow.amount = amount;
        ctx.accounts.escrow.maker = ctx.accounts.maker.key();
        ctx.accounts.escrow.bump = ctx.bumps.escrow;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    #[account(
        init,
        payer = maker,
        space = 8 + 8 + 32 + 1,
        seeds = [b"escrow", maker.key().as_ref()],
        bump
    )]
    pub escrow: Account<'info, Escrow>,
    #[account(mut)]
    pub maker: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[account]
pub struct Escrow {
    pub amount: u64,
    pub maker: Pubkey,
    pub bump: u8,
}
''',
    "programs/oracle/Cargo.toml": '''[package]
name = "oracle"
version = "0.1.0"
edition = "2021"

[dependencies]
anchor-lang = "0.30.1"
''',
    "programs/oracle/src/lib.rs": '''use anchor_lang::prelude::*;

#[program]
pub mod oracle {
    use super::*;

    pub fn update(ctx: Context<Update>, price: u64) -> Result<()> {
        ctx.accounts.feed.price = price;
        ctx.accounts.feed.last_updated = Clock::get()?.unix_timestamp;
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Update<'info> {
    #[account(mut, has_one = authority)]
    pub feed: Account<'info, PriceFeed>,
    pub authority: Signer<'info>,
}

#[account]
pub struct PriceFeed {
    pub authority: Pubkey,
    pub price: u64,
    pub last_updated: i64,
}
''',
}


# An empty / new workspace — for "scaffold this" examples
EMPTY_WORKSPACE: dict[str, str] = {
    ".gitignore": '''target/
node_modules/
.anchor/
test-ledger/
''',
}


# A simple Rust program with a syntax error — for cargo check error scenarios
BROKEN_RUST: dict[str, str] = {
    "Cargo.toml": '''[package]
name = "broken"
version = "0.1.0"
edition = "2021"

[dependencies]
anchor-lang = "0.30.1"
''',
    "src/lib.rs": '''use anchor_lang::prelude::*;

#[program]
pub mod broken {
    use super::*;

    pub fn initialize(ctx: Context<Initialize>) -> Result<()> {
        // Missing semicolon and undefined variable
        let value = unknown_variable
        Ok(())
    }
}

#[derive(Accounts)]
pub struct Initialize<'info> {
    pub user: Signer<'info>,
}
''',
}


# ── Fixture registry ──

FIXTURES: dict[str, dict[str, str]] = {
    "anchor_counter": ANCHOR_COUNTER,
    "anchor_vault": ANCHOR_VAULT,
    "anchor_buggy": ANCHOR_BUGGY,
    "anchor_legacy": ANCHOR_LEGACY,
    "native_solana": NATIVE_SOLANA,
    "pinocchio": PINOCCHIO,
    "multi_workspace": MULTI_WORKSPACE,
    "empty_workspace": EMPTY_WORKSPACE,
    "broken_rust": BROKEN_RUST,
}


FIXTURE_DESCRIPTIONS: dict[str, str] = {
    "anchor_counter": "An Anchor counter program with PDA-derived state",
    "anchor_vault": "An Anchor vault program with SPL token transfers",
    "anchor_buggy": "An Anchor program with a deprecated ctx.bumps.get() pattern",
    "anchor_legacy": "A legacy Anchor program using declare_id! and ProgramResult",
    "native_solana": "A native Solana program (no Anchor)",
    "pinocchio": "A Pinocchio framework program (zero-copy)",
    "multi_workspace": "A multi-program Anchor workspace (escrow + oracle)",
    "empty_workspace": "An empty workspace ready for scaffolding",
    "broken_rust": "An Anchor program with a syntax error (for cargo error testing)",
}


# ── Builder ──


def _materialize(content_map: dict[str, str], target: Path) -> list[str]:
    """Write all files to target directory, return list of relative paths."""
    files: list[str] = []
    for rel_path, content in content_map.items():
        abs_path = target / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")
        files.append(rel_path)
    return sorted(files)


@contextlib.contextmanager
def build_fixture(name: str) -> Iterator[Fixture]:
    """Build a fixture in a temp directory, clean up on exit."""
    if name not in FIXTURES:
        raise KeyError(f"Unknown fixture: {name}. Available: {sorted(FIXTURES)}")

    tmp = Path(tempfile.mkdtemp(prefix=f"slm_fx_{name}_"))
    try:
        files = _materialize(FIXTURES[name], tmp)
        yield Fixture(
            name=name,
            path=tmp,
            files=files,
            description=FIXTURE_DESCRIPTIONS.get(name, ""),
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def list_fixtures() -> list[str]:
    """Return all fixture names."""
    return sorted(FIXTURES.keys())


# ── CLI smoke test ──

if __name__ == "__main__":
    print(f"Available fixtures: {len(FIXTURES)}")
    for name in list_fixtures():
        with build_fixture(name) as fx:
            print(f"  {name}: {len(fx.files)} files — {fx.description}")
            for f in fx.files[:3]:
                print(f"    - {f}")
            if len(fx.files) > 3:
                print(f"    ... and {len(fx.files) - 3} more")
