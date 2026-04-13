/**
 * Mock vscode module for testing VS Code extensions outside the extension host.
 */

export const workspace = {
  getConfiguration: (section?: string) => ({
    get: (key: string, defaultValue?: unknown) => {
      const config: Record<string, unknown> = {
        apiKey: "slm_test_key",
        apiUrl: "https://slm.dev/api",
        mode: "quality",
      }
      return config[key] ?? defaultValue
    },
    has: (key: string) => ["apiKey", "apiUrl", "mode"].includes(key),
    update: async () => {},
  }),
}

export const window = {
  showInformationMessage: async (...args: unknown[]) => undefined,
  showErrorMessage: async (...args: unknown[]) => undefined,
  showInputBox: async (options?: unknown) => "test-input",
  withProgress: async (options: unknown, task: (progress: unknown) => Promise<unknown>) => {
    return task({ report: () => {} })
  },
}

export const commands = {
  registerCommand: (command: string, callback: (...args: unknown[]) => unknown) => ({
    dispose: () => {},
  }),
}

export const chat = {
  createChatParticipant: (id: string, handler: unknown) => ({
    iconPath: undefined,
    dispose: () => {},
  }),
}

export class Uri {
  static parse(value: string) {
    return { scheme: "https", authority: "", path: value }
  }
  static file(path: string) {
    return { scheme: "file", path }
  }
}

export const CancellationTokenSource = class {
  token = { isCancellationRequested: false, onCancellationRequested: () => ({ dispose: () => {} }) }
  cancel() {}
  dispose() {}
}

export enum LanguageModelChatMessageRole {
  User = 1,
  Assistant = 2,
}

export const MarkdownString = class {
  value: string
  constructor(value: string = "") {
    this.value = value
  }
}

export const ExtensionContext = {}

export type Disposable = { dispose: () => void }
