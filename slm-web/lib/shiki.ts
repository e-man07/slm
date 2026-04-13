import { createHighlighter, type Highlighter } from "shiki"

let highlighter: Highlighter | null = null

export async function getHighlighter(): Promise<Highlighter> {
  if (!highlighter) {
    highlighter = await createHighlighter({
      themes: ["vitesse-dark", "vitesse-light"],
      langs: ["rust", "typescript", "toml", "json", "bash", "javascript"],
    })
  }
  return highlighter
}
