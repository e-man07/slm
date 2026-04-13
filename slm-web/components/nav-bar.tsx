"use client"

import * as React from "react"
import Link from "next/link"
import Image from "next/image"
import { usePathname } from "next/navigation"
import { useTheme } from "next-themes"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  BubbleChatIcon,
  InspectCodeIcon,
  BookOpen01Icon,
  ChartEvaluationIcon,
  Sun01Icon,
  Moon01Icon,
  GithubIcon,
  Menu01Icon,
} from "@hugeicons/core-free-icons"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"

interface NavBarProps {
  minimal?: boolean
}

const NAV_LINKS = [
  { href: "/chat", label: "Chat", icon: BubbleChatIcon },
  { href: "/explain/tx", label: "Explain", icon: InspectCodeIcon },
  { href: "/docs", label: "Docs", icon: BookOpen01Icon },
  { href: "/eval", label: "Eval", icon: ChartEvaluationIcon },
] as const

function NavLink({
  href,
  icon,
  children,
}: {
  href: string
  icon: typeof BubbleChatIcon
  children: React.ReactNode
}) {
  const pathname = usePathname()
  const isActive = pathname === href || pathname.startsWith(href + "/")

  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-1.5 text-sm transition-colors",
        isActive
          ? "text-foreground"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      <HugeiconsIcon icon={icon} size={16} />
      {children}
    </Link>
  )
}

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => setMounted(true), [])

  if (!mounted) {
    return (
      <Button variant="ghost" size="icon" aria-label="Toggle theme">
        <div className="size-[18px]" />
      </Button>
    )
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      aria-label="Toggle theme"
    >
      <HugeiconsIcon
        icon={resolvedTheme === "dark" ? Sun01Icon : Moon01Icon}
        size={18}
      />
    </Button>
  )
}

function MobileMenu() {
  const pathname = usePathname()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden" aria-label="Menu">
          <HugeiconsIcon icon={Menu01Icon} size={18} />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {NAV_LINKS.map((link) => {
          const isActive =
            pathname === link.href || pathname.startsWith(link.href + "/")
          return (
            <DropdownMenuItem key={link.href} asChild>
              <Link
                href={link.href}
                className={cn(
                  "flex items-center gap-2",
                  isActive && "font-medium",
                )}
              >
                <HugeiconsIcon icon={link.icon} size={16} />
                {link.label}
              </Link>
            </DropdownMenuItem>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function NavBar({ minimal = false }: NavBarProps) {
  return (
    <nav
      data-slot="nav-bar"
      className="sticky top-0 z-50 w-full border-b border-border bg-background/80 backdrop-blur-sm"
    >
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
        <Link href="/" className="flex items-center">
          <Image
            src="/logo.svg"
            alt="SLM"
            width={80}
            height={28}
            className="dark:invert-0 invert"
            priority
          />
        </Link>

        {!minimal && (
          <div className="hidden items-center gap-6 md:flex">
            {NAV_LINKS.map((link) => (
              <NavLink key={link.href} href={link.href} icon={link.icon}>
                {link.label}
              </NavLink>
            ))}
          </div>
        )}

        <div className="flex items-center gap-1">
          <ThemeToggle />
          <Button variant="ghost" size="icon" asChild>
            <a
              href="https://github.com/kshitij-hash/slm"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="GitHub"
            >
              <HugeiconsIcon icon={GithubIcon} size={18} />
            </a>
          </Button>
          {!minimal && <MobileMenu />}
        </div>
      </div>
    </nav>
  )
}
