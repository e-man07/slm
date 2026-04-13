import { cn } from "@/lib/utils"
import { getHighlighter } from "@/lib/shiki"
import { CopyButton } from "./copy-button"

interface CodeBlockProps {
  code: string
  language?: string
  filename?: string
  showLineNumbers?: boolean
  className?: string
}

const LANGUAGE_LABELS: Record<string, string> = {
  rust: "Rust",
  typescript: "TypeScript",
  ts: "TypeScript",
  javascript: "JavaScript",
  js: "JavaScript",
  toml: "TOML",
  json: "JSON",
  bash: "Bash",
  text: "Text",
}

export async function CodeBlock({
  code,
  language = "text",
  filename,
  showLineNumbers = false,
  className,
}: CodeBlockProps) {
  const highlighter = await getHighlighter()
  const lang = language.toLowerCase()
  const supportedLangs = highlighter.getLoadedLanguages()
  const resolvedLang = supportedLangs.includes(lang) ? lang : "text"

  const html = highlighter.codeToHtml(code.trim(), {
    lang: resolvedLang,
    themes: { dark: "vitesse-dark", light: "vitesse-light" },
  })

  const label = filename ?? LANGUAGE_LABELS[lang] ?? lang

  return (
    <div
      data-slot="code-block"
      className={cn(
        "group relative border border-border bg-card overflow-hidden",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <span className="text-xs text-muted-foreground">{label}</span>
        <CopyButton value={code.trim()} />
      </div>
      <div
        className={cn(
          "overflow-x-auto p-4 text-sm [&_pre]:!bg-transparent [&_code]:!bg-transparent",
          showLineNumbers && "[&_code]:counter-reset-[line] [&_.line]:before:counter-increment-[line] [&_.line]:before:content-[counter(line)] [&_.line]:before:mr-4 [&_.line]:before:inline-block [&_.line]:before:w-4 [&_.line]:before:text-right [&_.line]:before:text-muted-foreground/40",
        )}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  )
}
