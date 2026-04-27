import type { Metadata } from "next"
import { Geist, JetBrains_Mono } from "next/font/google"

import "./globals.css"
import { ThemeProvider } from "@/components/theme-provider"
import { AuthSessionProvider } from "@/components/auth/session-provider"
import { Toaster } from "@/components/ui/sonner"
import { cn } from "@/lib/utils"
import { auth } from "@/lib/auth-next"

const fontSans = Geist({
  subsets: ["latin"],
  variable: "--font-sans",
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
})

export const metadata: Metadata = {
  title: "Sealevel - Solana Language Model",
  description:
    "The Solana coding AI that actually knows Solana. Chat, explain transactions, decode errors.",
  openGraph: {
    title: "Sealevel - Solana Language Model",
    description:
      "The Solana coding AI that actually knows Solana. Chat, explain transactions, decode errors.",
    siteName: "Sealevel",
    type: "website",
    images: [
      {
        url: "/og-image.svg",
        width: 1200,
        height: 630,
        alt: "Sealevel - Solana Language Model",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Sealevel - Solana Language Model",
    description:
      "The Solana coding AI that actually knows Solana. Chat, explain transactions, decode errors.",
    images: ["/og-image.svg"],
  },
  icons: {
    icon: "/logo.svg",
  },
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  const session = await auth()

  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={cn(
        "antialiased",
        fontSans.variable,
        "font-mono",
        jetbrainsMono.variable,
      )}
    >
      <head>
        <meta name="theme-color" content="oklch(0.153 0.006 107.1)" media="(prefers-color-scheme: dark)" />
        <meta name="theme-color" content="oklch(1 0 0)" media="(prefers-color-scheme: light)" />
        <meta name="color-scheme" content="light dark" />
      </head>
      <body>
        <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:bg-background focus:px-4 focus:py-2 focus:text-sm focus:border focus:border-border">
          Skip to main content
        </a>
        <AuthSessionProvider session={session}>
          <ThemeProvider>
            {children}
            <Toaster />
          </ThemeProvider>
        </AuthSessionProvider>
      </body>
    </html>
  )
}
