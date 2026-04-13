import { NavBar } from "@/components/nav-bar"
import { Footer } from "@/components/footer"
import { cn } from "@/lib/utils"

interface PageLayoutProps {
  children: React.ReactNode
  hideFooter?: boolean
  navMinimal?: boolean
  className?: string
}

export function PageLayout({
  children,
  hideFooter = false,
  navMinimal = false,
  className,
}: PageLayoutProps) {
  return (
    <div data-slot="page-layout" className="flex min-h-svh flex-col">
      <NavBar minimal={navMinimal} />
      <main
        className={cn(
          "mx-auto w-full max-w-5xl flex-1 px-4 py-8",
          className,
        )}
      >
        {children}
      </main>
      {!hideFooter && <Footer />}
    </div>
  )
}
