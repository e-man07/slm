"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTheme } from "next-themes"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { UserMenu } from "@/components/auth/user-menu"
import { cn } from "@/lib/utils"

interface NavBarProps {
  minimal?: boolean
}

const NAV_LINKS = [
  { href: "/chat", label: "Chat", num: "01" },
  { href: "/explain/tx", label: "Tx Explain", num: "02" },
  { href: "/explain/error", label: "Error Decode", num: "03" },
  { href: "/eval", label: "Eval", num: "04" },
  { href: "/docs", label: "Docs", num: "05" },
] as const

function NavLink({
  href,
  num,
  children,
}: {
  href: string
  num: string
  children: React.ReactNode
}) {
  const pathname = usePathname()
  const isActive = pathname === href || pathname.startsWith(href + "/")

  return (
    <Link
      href={href}
      className={cn(
        "inline-flex items-center gap-2 px-3 py-2 text-xs tracking-[0.04em] border-b-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        isActive
          ? "text-foreground border-b-[var(--slm-accent)]"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      <span
        className={cn(
          "text-[10px]",
          isActive ? "slm-accent" : "text-[var(--slm-border-strong)]",
        )}
      >
        {num}
      </span>
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
      <button className="grid size-11 place-items-center text-muted-foreground sm:size-9" aria-label="Toggle theme">
        <div className="size-4" />
      </button>
    )
  }

  return (
    <button
      className="grid size-11 place-items-center text-muted-foreground transition-colors hover:text-foreground hover:bg-muted sm:size-9 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      aria-label="Toggle theme"
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="square" aria-hidden="true">
        {resolvedTheme === "dark" ? (
          <>
            <path d="M12 3v2M12 19v2M5 12H3M21 12h-2M18.4 5.6l-1.4 1.4M7 17l-1.4 1.4M18.4 18.4L17 17M7 7L5.6 5.6" />
            <circle cx="12" cy="12" r="4" />
          </>
        ) : (
          <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
        )}
      </svg>
    </button>
  )
}

function MobileMenu() {
  const pathname = usePathname()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="grid size-11 place-items-center text-muted-foreground transition-colors hover:text-foreground hover:bg-muted md:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-label="Menu">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
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
                <span className="text-[10px] text-muted-foreground">{link.num}</span>
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
      className="sticky top-0 z-50 w-full border-b border-border"
      style={{
        background: "color-mix(in oklab, var(--background) 80%, transparent)",
        backdropFilter: "blur(12px)",
      }}
    >
      <div className="mx-auto flex h-14 max-w-[1120px] items-center justify-between gap-6 px-6">
        <Link href="/" className="flex items-center gap-2 text-[15px] font-bold tracking-[2px]">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/sealevel.png" alt="Sealevel" width={32} height={28} />
          <span>SEALEVEL</span>
        </Link>

        {!minimal && (
          <div className="hidden items-center gap-0.5 md:flex">
            {NAV_LINKS.map((link) => (
              <NavLink key={link.href} href={link.href} num={link.num}>
                {link.label}
              </NavLink>
            ))}
          </div>
        )}

        <div className="flex items-center gap-1.5">
          <ThemeToggle />
          <a
            href="https://github.com/kshitij-hash/slm"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="GitHub"
            className="grid size-11 place-items-center text-muted-foreground transition-colors hover:text-foreground hover:bg-muted sm:size-9 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 1.27a11 11 0 0 0-3.48 21.46c.55.1.75-.23.75-.52v-1.83c-3.06.67-3.7-1.47-3.7-1.47-.5-1.27-1.22-1.6-1.22-1.6-1-.68.08-.67.08-.67 1.1.08 1.68 1.13 1.68 1.13.98 1.68 2.57 1.2 3.2.92.1-.72.38-1.2.7-1.48-2.44-.28-5-1.22-5-5.44 0-1.2.43-2.18 1.13-2.95-.1-.28-.49-1.4.1-2.9 0 0 .92-.3 3 1.12a10.4 10.4 0 0 1 5.48 0c2.1-1.42 3-1.12 3-1.12.6 1.5.22 2.62.11 2.9.7.77 1.13 1.76 1.13 2.95 0 4.23-2.57 5.15-5.02 5.43.4.34.75 1 .75 2.02v3c0 .3.2.63.76.52A11 11 0 0 0 12 1.27" />
            </svg>
          </a>
          <UserMenu />
          {!minimal && <MobileMenu />}
        </div>
      </div>
    </nav>
  )
}
