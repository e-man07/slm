import Link from "next/link"
import { cn } from "@/lib/utils"

interface FooterProps {
  className?: string
}

export function Footer({ className }: FooterProps) {
  return (
    <footer
      data-slot="footer"
      className={cn("py-8 text-xs text-muted-foreground", className)}
    >
      <div className="mx-auto flex max-w-[1120px] flex-wrap items-center justify-between gap-4 px-6">
        <div>
          Built for Solana &middot;{" "}
          <span className="text-foreground">MIT</span>
        </div>
        <div className="inline-flex items-center gap-1">
          <span className="inline-block size-1 bg-current" />
          <span className="inline-block size-1 bg-current" />
          <span className="inline-block size-1 bg-current" />
        </div>
        <div className="flex items-center gap-1">
          <a
            href="https://github.com/kshitij-hash/slm"
            target="_blank"
            rel="noopener noreferrer"
            className="px-1.5 py-2 transition-colors hover:text-foreground"
          >
            github
          </a>
          <span className="opacity-40">/</span>
          <Link href="/docs" className="px-1.5 py-2 transition-colors hover:text-foreground">
            docs
          </Link>
          <span className="opacity-40">/</span>
          <Link href="/eval" className="px-1.5 py-2 transition-colors hover:text-foreground">
            dataset card
          </Link>
          <span className="opacity-40">/</span>
          <Link href="/eval" className="px-1.5 py-2 transition-colors hover:text-foreground">
            model card
          </Link>
        </div>
      </div>
    </footer>
  )
}
