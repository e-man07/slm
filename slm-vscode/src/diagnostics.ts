import * as vscode from "vscode"

/**
 * Deprecated Solana/Anchor patterns to flag.
 * Mirrors slm-mcp/src/lib/constants.ts DEPRECATED_PATTERNS.
 */
interface DeprecatedPattern {
  regex: RegExp
  name: string
  suggestion: string
  fix?: string
}

const DEPRECATED_PATTERNS: DeprecatedPattern[] = [
  {
    regex: /\bdeclare_id!\s*\([^)]*\)\s*;?/g,
    name: "declare_id! is deprecated",
    suggestion: "Use `declare_program!` instead in modern Anchor (0.30+).",
    fix: "declare_program!(my_program);",
  },
  {
    regex: /coral-xyz\/anchor/g,
    name: "coral-xyz/anchor moved",
    suggestion: "Use `solana-foundation/anchor` — the project moved to the Solana Foundation.",
    fix: "solana-foundation/anchor",
  },
  {
    regex: /\bload_instruction_at\b/g,
    name: "load_instruction_at is deprecated",
    suggestion: "Use `get_instruction_relative` instead.",
    fix: "get_instruction_relative",
  },
  {
    regex: /\breentrancy[_-]?guard\b/gi,
    name: "Reentrancy guards not needed on Solana",
    suggestion: "Solana prevents reentrancy via CPI depth limits — remove this guard.",
  },
  {
    regex: /ctx\.bumps\.get\(\s*["']([^"']+)["']\s*\)/g,
    name: "ctx.bumps.get() deprecated in Anchor 0.30+",
    suggestion: "Use `ctx.bumps.field_name` directly.",
  },
]

const DIAGNOSTIC_SOURCE = "Sealevel"

function checkDocument(
  document: vscode.TextDocument,
): vscode.Diagnostic[] {
  if (document.languageId !== "rust" && document.languageId !== "toml") return []

  const diagnostics: vscode.Diagnostic[] = []
  const text = document.getText()

  for (const pattern of DEPRECATED_PATTERNS) {
    // Reset regex lastIndex (global flag)
    pattern.regex.lastIndex = 0
    let match: RegExpExecArray | null
    while ((match = pattern.regex.exec(text)) !== null) {
      const start = document.positionAt(match.index)
      const end = document.positionAt(match.index + match[0].length)
      const diag = new vscode.Diagnostic(
        new vscode.Range(start, end),
        `${pattern.name}. ${pattern.suggestion}`,
        vscode.DiagnosticSeverity.Warning,
      )
      diag.source = DIAGNOSTIC_SOURCE
      diag.code = pattern.name
      diagnostics.push(diag)
    }
  }

  return diagnostics
}

/**
 * CodeAction provider — offers "Replace with modern pattern" quick-fix.
 */
class SLMCodeActionProvider implements vscode.CodeActionProvider {
  provideCodeActions(
    document: vscode.TextDocument,
    _range: vscode.Range | vscode.Selection,
    context: vscode.CodeActionContext,
  ): vscode.CodeAction[] {
    const actions: vscode.CodeAction[] = []

    for (const diag of context.diagnostics) {
      if (diag.source !== DIAGNOSTIC_SOURCE) continue

      const pattern = DEPRECATED_PATTERNS.find((p) => p.name === diag.code)
      if (!pattern?.fix) continue

      const action = new vscode.CodeAction(
        `Sealevel: ${pattern.name.split(" ")[0]} → ${pattern.fix}`,
        vscode.CodeActionKind.QuickFix,
      )
      action.diagnostics = [diag]
      action.edit = new vscode.WorkspaceEdit()
      action.edit.replace(document.uri, diag.range, pattern.fix)
      action.isPreferred = true
      actions.push(action)
    }

    // Offer "Ask Sealevel to migrate this" action for each warning
    for (const diag of context.diagnostics) {
      if (diag.source !== DIAGNOSTIC_SOURCE) continue

      const askAction = new vscode.CodeAction(
        "Sealevel: Migrate to modern Anchor patterns",
        vscode.CodeActionKind.QuickFix,
      )
      askAction.diagnostics = [diag]
      askAction.command = {
        command: "workbench.action.chat.open",
        title: "Migrate",
        arguments: [
          `@slm migrate this to modern Anchor 0.30+ patterns:\n\n\`\`\`rust\n${document.getText()}\n\`\`\``,
        ],
      }
      actions.push(askAction)
      break // One "ask" action per doc is enough
    }

    return actions
  }
}

export function registerDiagnostics(context: vscode.ExtensionContext): {
  collection: vscode.DiagnosticCollection
} {
  const collection = vscode.languages.createDiagnosticCollection("slm")
  context.subscriptions.push(collection)

  const update = (doc: vscode.TextDocument) => {
    collection.set(doc.uri, checkDocument(doc))
  }

  // Scan open docs at activation
  vscode.workspace.textDocuments.forEach(update)

  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument(update),
    vscode.workspace.onDidChangeTextDocument((e) => update(e.document)),
    vscode.workspace.onDidCloseTextDocument((doc) => collection.delete(doc.uri)),
    vscode.languages.registerCodeActionsProvider(
      [{ language: "rust" }, { language: "toml" }],
      new SLMCodeActionProvider(),
      { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] },
    ),
  )

  return { collection }
}
