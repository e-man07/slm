import Link from "next/link"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

interface FooterProps {
  className?: string
}

export function Footer({ className }: FooterProps) {
  return (
    <footer
      data-slot="footer"
      className={cn("border-t border-border py-8", className)}
    >
      <div className="mx-auto flex max-w-5xl flex-col items-center gap-4 px-4 text-sm text-muted-foreground md:flex-row md:justify-between">
        <span>Built for Solana</span>
        <span>Powered by Solana Foundation</span>
        <div className="flex items-center gap-4">
          <a
            href="https://github.com/kshitij-hash/slm"
            target="_blank"
            rel="noopener noreferrer"
            className="transition-colors hover:text-foreground"
          >
            GitHub
          </a>
          <Separator orientation="vertical" className="h-4" />
          <Link
            href="/docs"
            className="transition-colors hover:text-foreground"
          >
            Docs
          </Link>
        </div>
      </div>
    </footer>
  )
}
