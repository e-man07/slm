import Link from "next/link"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowRight01Icon } from "@hugeicons/core-free-icons"

export interface BreadcrumbItem {
  label: string
  href: string
}

interface BreadcrumbProps {
  items: BreadcrumbItem[]
}

export function Breadcrumb({ items }: BreadcrumbProps) {
  return (
    <nav
      aria-label="Breadcrumb"
      className="flex items-center gap-1.5 font-mono text-xs text-muted-foreground"
    >
      <Link href="/" className="transition-colors hover:text-foreground">
        Home
      </Link>
      {items.map((item, i) => (
        <span key={item.href} className="flex items-center gap-1.5">
          <HugeiconsIcon icon={ArrowRight01Icon} size={12} />
          {i === items.length - 1 ? (
            <span className="text-foreground">{item.label}</span>
          ) : (
            <Link
              href={item.href}
              className="transition-colors hover:text-foreground"
            >
              {item.label}
            </Link>
          )}
        </span>
      ))}
    </nav>
  )
}
