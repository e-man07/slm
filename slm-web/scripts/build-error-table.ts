/**
 * Build script: Generates an expanded error-table.json covering all major
 * Solana programs. Run with: bun scripts/build-error-table.ts
 *
 * Sources:
 * - Anchor Framework: anchor-lang crate error definitions
 * - SPL Token: spl-token program errors
 * - SPL Token-2022: token-2022 extension errors
 * - System Program: system instruction errors
 * - Stake Program: stake instruction errors
 * - Vote Program: vote instruction errors
 * - BPF Loader: loader errors
 * - Associated Token Account: ATA errors
 * - DeFi programs: Jupiter, Orca, Raydium (from public IDLs)
 * - Metaplex Token Metadata: NFT metadata program errors
 */

import { writeFileSync } from "fs"
import { resolve } from "path"

interface ErrorEntry {
  code: number
  hex: string
  name: string
  message: string
}

interface ProgramErrors {
  program_id: string
  program_name: string
  errors: ErrorEntry[]
}

function toHex(code: number): string {
  return `0x${code.toString(16).toUpperCase()}`
}

function makeError(code: number, name: string, message: string): ErrorEntry {
  return { code, hex: toHex(code), name, message }
}

// ---- Anchor Framework ----
const anchorErrors: ErrorEntry[] = [
  // Instruction errors (100-199)
  makeError(100, "InstructionMissing", "8 byte instruction identifier not provided"),
  makeError(101, "InstructionFallbackNotFound", "Fallback functions are not supported"),
  makeError(102, "InstructionDidNotDeserialize", "The program could not deserialize the given instruction"),
  makeError(103, "InstructionDidNotSerialize", "The program could not serialize the given instruction"),
  // IDL errors (1000-1099)
  makeError(1000, "IdlInstructionStub", "The program was compiled without idl instructions"),
  makeError(1001, "IdlInstructionInvalidProgram", "Invalid program given to the IDL instruction"),
  // Constraint errors (2000-2099)
  makeError(2000, "ConstraintMut", "A mut constraint was violated"),
  makeError(2001, "ConstraintHasOne", "A has one constraint was violated"),
  makeError(2002, "ConstraintSigner", "A signer constraint was violated"),
  makeError(2003, "ConstraintSeeds", "A seeds constraint was violated"),
  makeError(2004, "ConstraintExecutable", "An executable constraint was violated"),
  makeError(2005, "ConstraintMint", "A mint constraint was violated"),
  makeError(2006, "ConstraintOwner", "An owner constraint was violated"),
  makeError(2007, "ConstraintRentExempt", "A rent exempt constraint was violated"),
  makeError(2008, "ConstraintZero", "A zero constraint was violated"),
  makeError(2009, "ConstraintTokenMint", "A token mint constraint was violated"),
  makeError(2010, "ConstraintTokenOwner", "A token owner constraint was violated"),
  makeError(2011, "ConstraintMintMintAuthority", "A mint authority constraint was violated"),
  makeError(2012, "ConstraintSpace", "A space constraint was violated"),
  makeError(2013, "ConstraintAccountIsNone", "An account constraint was violated"),
  makeError(2014, "ConstraintClose", "A close constraint was violated"),
  makeError(2015, "ConstraintAddress", "An address constraint was violated"),
  makeError(2016, "ConstraintTokenAuthority", "Expected token account authority"),
  makeError(2017, "ConstraintMintFreezeAuthority", "Expected mint freeze authority"),
  makeError(2018, "ConstraintTokenTokenProgram", "Expected token program in constraints"),
  makeError(2019, "ConstraintMintTokenProgram", "Expected mint token program in constraints"),
  makeError(2020, "ConstraintAssociatedInit", "An associated constraint init was violated"),
  makeError(2021, "ConstraintPayerInit", "A payer init constraint was violated"),
  makeError(2022, "ConstraintGroupMaxSize", "A group max size constraint was violated"),
  // Account errors (3000-3099)
  makeError(3000, "AccountDiscriminatorAlreadySet", "The account discriminator was already set on this account"),
  makeError(3001, "AccountDiscriminatorNotFound", "No 8 byte discriminator was found on the account"),
  makeError(3002, "AccountDiscriminatorMismatch", "8 byte discriminator did not match what was expected"),
  makeError(3003, "AccountDidNotDeserialize", "Failed to deserialize the account"),
  makeError(3004, "AccountDidNotSerialize", "Failed to serialize the account"),
  makeError(3005, "AccountNotEnoughKeys", "Not enough account keys given to the instruction"),
  makeError(3006, "AccountNotMutable", "The given account is not mutable"),
  makeError(3007, "AccountOwnedByWrongProgram", "The given account is owned by a different program than expected"),
  makeError(3008, "InvalidProgramId", "Program ID was not as expected"),
  makeError(3009, "InvalidProgramExecutable", "Program account is not executable"),
  makeError(3010, "AccountNotSigner", "The given account did not sign"),
  makeError(3011, "AccountNotSystemOwned", "The given account is not owned by the system program"),
  makeError(3012, "AccountNotInitialized", "The program expected this account to be already initialized"),
  makeError(3013, "AccountNotProgramData", "The given account is not a program data account"),
  makeError(3014, "AccountNotAssociatedTokenAccount", "The given account is not the associated token account"),
  makeError(3015, "AccountSysvarMismatch", "The given public key does not match the expected sysvar"),
  makeError(3016, "AccountReallocExceedsLimit", "The account reallocation exceeds the MAX_PERMITTED_DATA_INCREASE"),
  makeError(3017, "AccountDuplicateReallocs", "The account was duplicated for more than one reallocation"),
  // State errors (4000-4099)
  makeError(4000, "StateInvalidAddress", "The given state account does not have the correct address"),
  // Miscellaneous errors (4100-4199)
  makeError(4100, "DeclaredProgramIdMismatch", "The declared program id does not match the actual program id"),
  makeError(4101, "TryingToInitPayerAsProgramAccount", "You cannot/should not initialize the payer account as a program account"),
  makeError(4102, "InvalidNumericConversion", "The program could not perform the numeric conversion"),
  // Deprecated
  makeError(5000, "Deprecated", "The API being used is deprecated and should no longer be used"),
]

// ---- SPL Token ----
const splTokenErrors: ErrorEntry[] = [
  makeError(0, "NotRentExempt", "Lamport balance below rent-exempt threshold"),
  makeError(1, "InsufficientFunds", "Insufficient funds"),
  makeError(2, "InvalidMint", "Invalid Mint"),
  makeError(3, "MintMismatch", "Account not associated with this Mint"),
  makeError(4, "OwnerMismatch", "Owner does not match"),
  makeError(5, "FixedSupply", "Fixed supply"),
  makeError(6, "AlreadyInUse", "Already in use"),
  makeError(7, "InvalidNumberOfProvidedSigners", "Invalid number of provided signers"),
  makeError(8, "InvalidNumberOfRequiredSigners", "Invalid number of required signers"),
  makeError(9, "UninitializedState", "State is uninitialized"),
  makeError(10, "NativeNotSupported", "Instruction does not support native tokens"),
  makeError(11, "NonNativeHasBalance", "Non-native account can only be closed if its balance is zero"),
  makeError(12, "InvalidInstruction", "Invalid instruction"),
  makeError(13, "InvalidState", "State is invalid for requested operation"),
  makeError(14, "Overflow", "Operation overflowed"),
  makeError(15, "AuthorityTypeNotSupported", "Account does not support specified authority type"),
  makeError(16, "MintCannotFreeze", "This token mint cannot freeze accounts"),
  makeError(17, "AccountFrozen", "Account is frozen"),
  makeError(18, "MintDecimalsMismatch", "The provided decimals value different from the Mint decimals"),
  makeError(19, "NonNativeNotSupported", "Instruction does not support non-native tokens"),
]

// ---- SPL Token-2022 (extends SPL Token with extension errors) ----
const splToken2022Errors: ErrorEntry[] = [
  ...splTokenErrors,
  makeError(20, "InvalidExtensionType", "Extension type does not match already existing extensions"),
  makeError(21, "InvalidState2022", "State is invalid for requested operation in Token-2022"),
  makeError(22, "ExtensionBaseMismatch", "Extension base account type does not match"),
  makeError(23, "ExtensionAlreadyInitialized", "Extension is already initialized on this account"),
  makeError(24, "ConfidentialTransferAccountHasBalance", "An account can only be closed if its confidential balance is zero"),
  makeError(25, "ConfidentialTransferAccountNotApproved", "Account not approved for confidential transfers"),
  makeError(26, "ConfidentialTransferDepositsAndTransfersDisabled", "Confidential transfer deposits and transfers disabled"),
  makeError(27, "ConfidentialTransferElGamalPubkeyMismatch", "ElGamal public key mismatch"),
  makeError(28, "MintHasSupply", "Mint has non-zero supply. Burn all tokens before closing the mint"),
  makeError(29, "NoMemo", "No memo in previous instruction; required for recipient to receive a transfer"),
  makeError(30, "TransferFeeExceedsMaximum", "Transfer fee exceeds maximum of 10,000 basis points"),
  makeError(31, "MintRequiredForTransfer", "Mint required for this account to transfer tokens, use transfer_checked or transfer_checked_with_fee"),
  makeError(32, "FeeMismatch", "Calculated fee does not match expected fee"),
  makeError(33, "FeeParametersMismatch", "Fee parameters associated with zero-knowledge transfer do not match fee on mint"),
  makeError(34, "ImmutableOwner", "The owner authority cannot be changed"),
  makeError(35, "AccountHasWithheldTransferFees", "An account can only be closed if its withheld fee balance is zero, harvest fees to the mint and try again"),
  makeError(36, "NoDefaultAccountState", "No default account state"),
  makeError(37, "ExtensionNotFound", "Extension not found in account data"),
  makeError(38, "NonTransferable", "Non-transferable tokens can't be moved to another account"),
  makeError(39, "NonTransferableNeedsImmutableOwnership", "Non-transferable tokens must have permanent delegate and immutable owner"),
  makeError(40, "MaximumPendingBalanceCreditCounterExceeded", "Maximum pending balance credit counter exceeded"),
  makeError(41, "MaximumDepositAmountExceeded", "Maximum deposit transfer amount exceeded"),
  makeError(42, "CpiGuardSettingsLocked", "CPI Guard cannot be enabled or disabled in CPI"),
  makeError(43, "CpiGuardTransferBlocked", "CPI Guard is enabled, and a program attempted to transfer user funds via CPI without using a delegate"),
  makeError(44, "CpiGuardBurnBlocked", "CPI Guard is enabled, and a program attempted to burn user funds via CPI without using a delegate"),
  makeError(45, "CpiGuardCloseAccountBlocked", "CPI Guard is enabled, and a program attempted to close user account via CPI without returning lamports to owner"),
  makeError(46, "CpiGuardApproveBlocked", "CPI Guard is enabled, and a program attempted to approve a delegate via CPI"),
  makeError(47, "CpiGuardSetAuthorityBlocked", "CPI Guard is enabled, and a program attempted to change authority via CPI"),
  makeError(48, "CpiGuardSetCloseAuthorityBlocked", "CPI Guard is enabled, and a program attempted to set a close authority via CPI"),
]

// ---- System Program ----
const systemProgramErrors: ErrorEntry[] = [
  makeError(0, "AccountAlreadyInUse", "An account with the same address already exists"),
  makeError(1, "ResultWithNegativeLamports", "Account does not have enough SOL to perform the operation"),
  makeError(2, "InvalidProgramId", "Cannot assign account to this program id"),
  makeError(3, "InvalidAccountDataLength", "Cannot allocate account data of this length"),
  makeError(4, "MaxSeedLengthExceeded", "Length of requested seed is too long"),
  makeError(5, "AddressWithSeedMismatch", "Provided address does not match addressed derived from seed"),
  makeError(6, "NonceNoRecentBlockhashes", "Advancing stored nonce requires a populated RecentBlockhashes sysvar"),
  makeError(7, "NonceBlockhashNotExpired", "Stored nonce is still in recent_blockhashes"),
  makeError(8, "NonceUnexpectedBlockhashValue", "Specified nonce does not match stored nonce"),
]

// ---- Stake Program ----
const stakeProgramErrors: ErrorEntry[] = [
  makeError(0, "NoCreditsToRedeem", "Not enough credits to redeem"),
  makeError(1, "LockupInForce", "Lockup has not yet expired"),
  makeError(2, "AlreadyDeactivated", "Stake already deactivated"),
  makeError(3, "TooSoonToRedelegate", "One re-delegation permitted per epoch"),
  makeError(4, "InsufficientStake", "Split amount is more than is staked"),
  makeError(5, "MergeTransientStake", "Stake account with transient stake cannot be merged"),
  makeError(6, "MergeMismatch", "Stake account merge failed due to different authority, lockups or state"),
  makeError(7, "CustodianMissing", "Custodian address not present"),
  makeError(8, "CustodianSignatureMissing", "Custodian signature not present"),
  makeError(9, "InsufficientReferenceVotes", "Insufficient voting activity in the reference vote account"),
  makeError(10, "VoteAddressMismatch", "Stake account is not delegated to the provided vote account"),
  makeError(11, "MinimumDelinquentEpochsForDeactivation", "Stake account has not been delinquent for the minimum epochs"),
  makeError(12, "InsufficientDelegation", "Delegation amount is less than the minimum"),
  makeError(13, "RedelegateTransientOrInactiveStake", "Stake account with transient or inactive stake cannot be redelegated"),
  makeError(14, "RedelegateToSameVoteAccount", "Stake redelegation to the same vote account is not permitted"),
]

// ---- Vote Program ----
const voteProgramErrors: ErrorEntry[] = [
  makeError(0, "VoteTooOld", "Vote already recorded or not in slot hashes history"),
  makeError(1, "SlotsMismatch", "Vote slots do not match bank history"),
  makeError(2, "SlotHashMismatch", "Vote hash does not match bank hash"),
  makeError(3, "EmptySlots", "Vote has no slots, invalid"),
  makeError(4, "TimestampTooOld", "Vote timestamp not recent"),
  makeError(5, "TooSoonToReauthorize", "Authorized voter has already been changed this epoch"),
  makeError(6, "LockoutConflict", "Old lockout not found in slot hashes"),
  makeError(7, "NewVoteStateLockoutMismatch", "New vote state lockout does not match the old vote state lockout"),
  makeError(8, "SlotsNotOrdered", "Slots in new vote state are not ordered"),
  makeError(9, "ConfirmationsNotOrdered", "Confirmations in new vote state are not ordered"),
  makeError(10, "ZeroConfirmations", "Confirmation of zero in new vote state"),
  makeError(11, "ConfirmationTooLarge", "New state has a confirmation that is too large"),
  makeError(12, "RootRollBack", "New vote state root is not in the old vote state"),
  makeError(13, "ConfirmationRollBack", "Confirmations for new vote were smaller than the old vote state"),
  makeError(14, "SlotSmallerThanRoot", "New vote has a slot smaller than the root"),
  makeError(15, "TooManyVotes", "New vote has too many votes"),
  makeError(16, "VotesTooOldAllFiltered", "Every slot in the vote was older than the SlotHashes history"),
  makeError(17, "CommissionUpdateTooLate", "Commission cannot be changed during an epoch"),
  makeError(18, "ActiveVoteAccountClose", "Cannot close vote account unless it stopped voting at least one full epoch ago"),
]

// ---- BPF Loader ----
const bpfLoaderErrors: ErrorEntry[] = [
  makeError(0, "InvalidInstruction", "Invalid instruction"),
  makeError(1, "InvalidAccountData", "Invalid account data"),
  makeError(2, "AccountDataTooSmall", "Account data too small for instruction"),
  makeError(3, "InsufficientFunds", "Insufficient funds for fee or rent"),
  makeError(4, "IncorrectProgramId", "Incorrect program id for instruction"),
  makeError(5, "MissingRequiredSignature", "Missing required signature"),
  makeError(6, "AccountAlreadyInitialized", "Account already initialized"),
  makeError(7, "UninitializedAccount", "Uninitialized account"),
  makeError(8, "InvalidArgument", "Provided argument is invalid"),
  makeError(9, "ProgramNotExecutable", "Program is not executable"),
  makeError(10, "AccountNotRentExempt", "Account not rent exempt"),
  makeError(11, "UnsupportedSysvar", "Unsupported sysvar"),
  makeError(12, "IllegalOwner", "Provided owner is not allowed"),
]

// ---- Associated Token Account ----
const ataErrors: ErrorEntry[] = [
  makeError(0, "InvalidOwner", "Associated token account owner does not match address derivation"),
  makeError(1, "TokenAccountNotFound", "Token account not found"),
  makeError(2, "InvalidTokenProgramId", "Invalid token program id"),
]

// ---- Jupiter (v6 - JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4) ----
const jupiterErrors: ErrorEntry[] = [
  makeError(6000, "EmptyRoute", "Route must not be empty"),
  makeError(6001, "SlippageToleranceExceeded", "Slippage tolerance exceeded"),
  makeError(6002, "InvalidCalculation", "Invalid calculation"),
  makeError(6003, "MissingPlatformFeeAccount", "Missing platform fee account"),
  makeError(6004, "InvalidSlippage", "Invalid slippage"),
  makeError(6005, "NotEnoughPercent", "Not enough percent to 100"),
  makeError(6006, "InvalidInputIndex", "Token input index is invalid"),
  makeError(6007, "InvalidOutputIndex", "Token output index is invalid"),
  makeError(6008, "NotEnoughAccountKeys", "Not enough account keys given"),
  makeError(6009, "NonZeroMinimumOutAmountNotSupported", "Non zero minimum out amount not supported"),
  makeError(6010, "InvalidRoutePlan", "Invalid route plan"),
  makeError(6011, "InvalidReferralAuthority", "Invalid referral authority"),
  makeError(6012, "LedgerTokenAccountDoesNotMatch", "Token account does not match the ledger"),
  makeError(6013, "InvalidTokenLedger", "Invalid token ledger"),
  makeError(6014, "IncorrectTokenProgramID", "Token program ID is incorrect"),
  makeError(6015, "TokenProgramNotProvided", "Token program not provided"),
  makeError(6016, "SwapNotSupported", "Swap not supported"),
  makeError(6017, "ExactOutAmountNotMatched", "Exact out amount not matched"),
  makeError(6018, "SourceAndDestinationMintCannotBeTheSame", "Source and destination mint cannot be the same"),
]

// ---- Orca Whirlpool (whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc) ----
const orcaErrors: ErrorEntry[] = [
  makeError(6000, "InvalidEnum", "Enum value could not be converted"),
  makeError(6001, "InvalidStartTick", "Invalid start tick index provided"),
  makeError(6002, "TickArrayExistInPool", "Tick-array already exists in this whirlpool"),
  makeError(6003, "TickArrayIndexOutofBounds", "Attempted to access an out of bounds tick array index"),
  makeError(6004, "InvalidTickSpacing", "Tick-spacing is not supported"),
  makeError(6005, "ClosePositionNotEmpty", "Position is not empty, it still has liquidity"),
  makeError(6006, "DivideByZero", "Unable to divide by zero"),
  makeError(6007, "NumberCastError", "Unable to cast number into BigInt"),
  makeError(6008, "NumberDownCastError", "Unable to down cast number"),
  makeError(6009, "TickNotFound", "Tick not found within tick array"),
  makeError(6010, "InvalidTickIndex", "Provided tick index is either out of bounds or uninitializable"),
  makeError(6011, "SqrtPriceOutOfBounds", "Provided sqrt price out of bounds"),
  makeError(6012, "LiquidityZero", "Liquidity amount must be greater than zero"),
  makeError(6013, "LiquidityTooHigh", "Liquidity amount must be less than i64::MAX"),
  makeError(6014, "LiquidityOverflow", "Liquidity overflow"),
  makeError(6015, "LiquidityUnderflow", "Liquidity underflow"),
  makeError(6016, "TokenMaxExceeded", "Token max exceeded"),
  makeError(6017, "TokenMinSubceeded", "Token min subceeded"),
  makeError(6018, "MissingOrInvalidDelegate", "Position token account has a missing or invalid delegate"),
  makeError(6019, "InvalidPositionTokenAmount", "Position token amount must be 1"),
  makeError(6020, "InvalidTimestampConversion", "Timestamp should be convertible from i64 to u64"),
  makeError(6021, "InvalidTimestamp", "Timestamp should be greater than the last updated timestamp"),
  makeError(6022, "InvalidTickArraySequence", "Invalid tick array sequence provided for instruction"),
  makeError(6023, "InvalidTokenMintOrder", "Token Mint in wrong order"),
  makeError(6024, "RewardNotInitialized", "Reward not initialized"),
  makeError(6025, "InvalidRewardIndex", "Invalid reward index"),
  makeError(6026, "RewardVaultAmountInsufficient", "Reward vault requires tokens to support emissions for at least one day"),
  makeError(6027, "FeeRateMaxExceeded", "Exceeded max fee rate"),
  makeError(6028, "ProtocolFeeRateMaxExceeded", "Exceeded max protocol fee rate"),
  makeError(6029, "MultiplicationShiftRightOverflow", "Multiplication with shift right overflow"),
  makeError(6030, "MulDivOverflow", "Mul-div estimated result exceeds u128"),
  makeError(6031, "MulDivInvalidInput", "Mul-div overflow"),
  makeError(6032, "MultiplicationOverflow", "Multiplication overflow"),
  makeError(6033, "InvalidSqrtPriceLimitDirection", "Invalid sqrt price limit direction"),
  makeError(6034, "ZeroTradableAmount", "Zero tradable amount"),
  makeError(6035, "AmountOutBelowMinimum", "Amount out below minimum threshold"),
  makeError(6036, "AmountInAboveMaximum", "Amount in above maximum threshold"),
  makeError(6037, "TickArraySequenceInvalidIndex", "Invalid index for tick array sequence"),
  makeError(6038, "AmountCalcOverflow", "Amount calculated overflows"),
  makeError(6039, "AmountRemainingOverflow", "Amount remaining overflows"),
]

// ---- Raydium AMM V4 (675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8) ----
const raydiumErrors: ErrorEntry[] = [
  makeError(6000, "AlreadyInUse", "Already in use"),
  makeError(6001, "InvalidProgramAddress", "Invalid program address generated from bump seed and key"),
  makeError(6002, "ExpectedMint", "Input account is not a valid SPL Token Mint"),
  makeError(6003, "ExpectedAccount", "Input account is not a valid SPL Token Account"),
  makeError(6004, "InvalidCoinVault", "Input coin vault is invalid"),
  makeError(6005, "InvalidPCVault", "Input pc vault is invalid"),
  makeError(6006, "InvalidTokenLP", "Input lp mint is invalid"),
  makeError(6007, "InvalidDestTokenCoin", "Input dest token coin is invalid"),
  makeError(6008, "InvalidDestTokenPC", "Input dest token pc is invalid"),
  makeError(6009, "InvalidPoolMint", "Input pool mint is invalid"),
  makeError(6010, "InvalidOpenOrders", "Input open orders is invalid"),
  makeError(6011, "InvalidSerumMarket", "Input serum market is invalid"),
  makeError(6012, "InvalidSerumProgram", "Input serum program is invalid"),
  makeError(6013, "InvalidTargetOrders", "Input target orders is invalid"),
  makeError(6014, "InvalidWithdrawQueue", "Input withdraw queue is invalid"),
  makeError(6015, "InvalidTempLP", "Input temp lp token is invalid"),
  makeError(6016, "InvalidCoinMint", "Input coin mint is invalid"),
  makeError(6017, "InvalidPCMint", "Input pc mint is invalid"),
  makeError(6018, "InvalidOwner", "Input owner is invalid"),
  makeError(6019, "InvalidSupply", "Pool supply cannot be zero on the first deposit"),
  makeError(6020, "InvalidDelegate", "Invalid delegate"),
  makeError(6021, "InvalidSignAccount", "Invalid signer account"),
  makeError(6022, "InvalidFreezeAuthority", "Invalid freeze authority"),
  makeError(6023, "ExceededSlippage", "Swap amount exceeds maximum slippage"),
  makeError(6024, "InvalidCloseAuthority", "Invalid close authority"),
  makeError(6025, "InvalidMathCalculation", "Math calculation overflow or underflow"),
]

// ---- Metaplex Token Metadata (metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s) ----
const metaplexErrors: ErrorEntry[] = [
  makeError(0, "InstructionUnpackError", "Failed to unpack instruction data"),
  makeError(1, "InstructionPackError", "Failed to pack instruction data"),
  makeError(2, "NotRentExempt", "Lamport balance below rent-exempt threshold"),
  makeError(3, "AlreadyInitialized", "Already initialized"),
  makeError(4, "Uninitialized", "Uninitialized"),
  makeError(5, "InvalidMetadataKey", "Metadata's key must match seed of ['metadata', program id, mint] provided"),
  makeError(6, "InvalidEditionKey", "Edition's key must match seed of ['metadata', program id, name, 'edition'] provided"),
  makeError(7, "UpdateAuthorityIncorrect", "Update Authority given does not match"),
  makeError(8, "UpdateAuthorityIsNotSigner", "Update Authority is not yet a signer"),
  makeError(9, "NotMintAuthority", "Not the mint authority"),
  makeError(10, "InvalidMintAuthority", "Mint given does not match mint on Metadata"),
  makeError(11, "NameTooLong", "Name too long"),
  makeError(12, "SymbolTooLong", "Symbol too long"),
  makeError(13, "UriTooLong", "URI too long"),
  makeError(14, "UpdateAuthorityMustBeEqualToMetadataAuthorityAndSigner", "Update authority must be equivalent to the metadata's authority and also signer"),
  makeError(15, "MintMismatch", "Mint given does not match metadata mint"),
  makeError(16, "EditionsMustHaveExactlyOneToken", "Editions must have exactly one token"),
  makeError(17, "MaxEditionsMintedAlready", "Maximum editions already minted"),
  makeError(18, "TokenMintToFailed", "Minting failed"),
  makeError(19, "MasterRecordMismatch", "Master record mismatch"),
  makeError(20, "DestinationMintMismatch", "Destination mint mismatch"),
  makeError(21, "EditionAlreadyMinted", "Edition already minted"),
  makeError(22, "PrintingMintDecimalsShouldBeZero", "Printing mint decimals should be zero"),
  makeError(23, "OneTimePrintingAuthorizationMintDecimalsShouldBeZero", "One time printing mint decimals should be zero"),
  makeError(24, "EditionMintDecimalsShouldBeZero", "Edition mint decimals should be zero"),
  makeError(25, "TokenBurnFailed", "Token burn failed"),
  makeError(26, "TokenAccountOneTimeAuthMintMismatch", "The one time authorization mint does not match"),
  makeError(27, "DerivedKeyInvalid", "Derived key invalid"),
  makeError(28, "PrintingMintMismatch", "The printing mint does not match"),
  makeError(29, "OneTimePrintingAuthMintMismatch", "One time printing authorization mint mismatch"),
  makeError(30, "TokenAccountMintMismatch", "Token account does not have correct mint"),
  makeError(31, "TokenAccountMintMismatchV2", "Token account does not have correct mint"),
  makeError(32, "NotEnoughTokens", "Not enough tokens to mint a limited edition"),
  makeError(33, "PrintingMintAuthorizationAccountMismatch", "Printing mint authorization account mismatch"),
  makeError(34, "AuthorizationTokenAccountOwnerMismatch", "Authorization token account owner mismatch"),
  makeError(35, "Disabled", "This feature is currently disabled"),
  makeError(36, "CreatorsTooLong", "Creators list too long"),
  makeError(37, "CreatorsMustBeAtleastOne", "Creators must be at least one if set"),
  makeError(38, "MustBeOneOfCreators", "If using a+creators array, you must be one of the creators"),
  makeError(39, "NoCreatorsPresentOnMetadata", "This metadata does not have creators"),
  makeError(40, "CreatorNotFound", "This creator address was not found"),
  makeError(41, "InvalidBasisPoints", "Basis points cannot be more than 10000"),
  makeError(42, "PrimarySaleCanOnlyBeFlippedToTrue", "Primary sale can only be flipped to true and is immutable"),
  makeError(43, "OwnerMismatch", "Owner does not match that on the account given"),
  makeError(44, "NoBalanceInAccountForAuthorization", "This account has no tokens to be used for authorization"),
  makeError(45, "ShareTotalMustBe100", "Share total must equal 100 for creator array"),
  makeError(46, "ReservationExists", "This reservation list already exists"),
  makeError(47, "ReservationDoesNotExist", "This reservation list does not exist"),
  makeError(48, "ReservationNotSet", "This reservation list has not been set"),
  makeError(49, "ReservationAlreadyMade", "This reservation list has already been set"),
  makeError(50, "BeyondMaxAddressSize", "Provided more addresses than max for reservation list"),
]

// ---- Compute Budget Program ----
const computeBudgetErrors: ErrorEntry[] = [
  makeError(0, "InvalidInstruction", "Invalid instruction"),
  makeError(1, "DuplicateInstruction", "Duplicate instruction, only one of each type permitted"),
]

// ---- Memo Program ----
const memoProgramErrors: ErrorEntry[] = [
  makeError(0, "InvalidAccountData", "Invalid UTF-8 memo data"),
  makeError(1, "MissingSigner", "Missing required signer"),
]

// ---- Name Service ----
const nameServiceErrors: ErrorEntry[] = [
  makeError(0, "OutOfSpace", "Out of space"),
  makeError(1, "InvalidParent", "Invalid parent"),
  makeError(2, "InvalidOwner", "Invalid owner"),
  makeError(3, "InvalidClass", "Invalid class"),
]

// Assemble the final programs array
const programs: ProgramErrors[] = [
  {
    program_id: "anchor_internal",
    program_name: "Anchor Framework",
    errors: anchorErrors,
  },
  {
    program_id: "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    program_name: "SPL Token",
    errors: splTokenErrors,
  },
  {
    program_id: "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    program_name: "SPL Token-2022",
    errors: splToken2022Errors,
  },
  {
    program_id: "11111111111111111111111111111111",
    program_name: "System Program",
    errors: systemProgramErrors,
  },
  {
    program_id: "Stake11111111111111111111111111111111111111",
    program_name: "Stake Program",
    errors: stakeProgramErrors,
  },
  {
    program_id: "Vote111111111111111111111111111111111111111",
    program_name: "Vote Program",
    errors: voteProgramErrors,
  },
  {
    program_id: "BPFLoaderUpgradeab1e11111111111111111111111",
    program_name: "BPF Loader Upgradeable",
    errors: bpfLoaderErrors,
  },
  {
    program_id: "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    program_name: "Associated Token Account",
    errors: ataErrors,
  },
  {
    program_id: "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
    program_name: "Jupiter v6",
    errors: jupiterErrors,
  },
  {
    program_id: "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
    program_name: "Orca Whirlpool",
    errors: orcaErrors,
  },
  {
    program_id: "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
    program_name: "Raydium AMM V4",
    errors: raydiumErrors,
  },
  {
    program_id: "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s",
    program_name: "Metaplex Token Metadata",
    errors: metaplexErrors,
  },
  {
    program_id: "ComputeBudget111111111111111111111111111111",
    program_name: "Compute Budget",
    errors: computeBudgetErrors,
  },
  {
    program_id: "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
    program_name: "Memo Program v2",
    errors: memoProgramErrors,
  },
  {
    program_id: "namesLPneVptA9Z5rqUDD9tMTWEJwofgaYwp8cawRkX",
    program_name: "Name Service",
    errors: nameServiceErrors,
  },
]

const errorTable = { programs }

// Validate and write
const totalErrors = programs.reduce((sum, p) => sum + p.errors.length, 0)
console.log(`Generated error table:`)
console.log(`  Programs: ${programs.length}`)
console.log(`  Total errors: ${totalErrors}`)

for (const program of programs) {
  const codes = program.errors.map((e) => e.code)
  const uniqueCodes = new Set(codes)
  if (uniqueCodes.size !== codes.length) {
    console.error(`ERROR: Duplicate codes in ${program.program_name}`)
    process.exit(1)
  }
}

const outPath = resolve(import.meta.dir, "..", "data", "error-table.json")
writeFileSync(outPath, JSON.stringify(errorTable, null, 2) + "\n")
console.log(`Written to: ${outPath}`)
