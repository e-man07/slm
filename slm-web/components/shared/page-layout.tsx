import { NavBar } from "@/components/nav-bar"
import { Footer } from "@/components/footer"
import { cn } from "@/lib/utils"

interface PageLayoutProps {
  children: React.ReactNode
  hideFooter?: boolean
  navMinimal?: boolean
  className?: string
  fullWidth?: boolean
}

export function PageLayout({
  children,
  hideFooter = false,
  navMinimal = false,
  className,
  fullWidth = false,
}: PageLayoutProps) {
  return (
    <div data-slot="page-layout" className="flex min-h-svh flex-col">
      <NavBar minimal={navMinimal} />
      <main
        id="main-content"
        className={cn(
          "flex-1",
          !fullWidth && "mx-auto w-full max-w-[1120px] px-6",
          className,
        )}
      >
        {children}
      </main>
      {!hideFooter && <Footer />}
    </div>
  )
}
