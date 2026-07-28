import { Navbar } from '@/components/landing/Navbar'
import { Footer } from '@/components/landing/Footer'
import { Outlet } from 'react-router-dom'
import { MarketingThemeProvider } from '@/providers/MarketingThemeProvider'
import { LandingBackground } from '@/components/landing/background/LandingBackground'

export function LandingLayout() {
  return (
    <MarketingThemeProvider>
      <div className="min-h-screen bg-transparent text-foreground selection:bg-primary/30 selection:text-primary flex flex-col font-sans relative">
        <LandingBackground />
        <Navbar />
        <main className="flex-1 flex flex-col relative z-0">
          <Outlet />
        </main>
        <Footer />
      </div>
    </MarketingThemeProvider>
  )
}
