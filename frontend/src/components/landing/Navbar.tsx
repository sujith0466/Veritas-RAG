import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Shield, Menu, X, LogOut } from 'lucide-react'
import { cn } from '@/utils/cn'
import { Button } from '@/components/common/Button'
import { MagneticButton } from '@/components/motion/MagneticButton'
import { useAuthStore } from '@/stores/authStore'
import { UserMenu } from '@/components/navigation/UserMenu'

export function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [hoveredLink, setHoveredLink] = useState<string | null>(null)
  const [activeSection, setActiveSection] = useState<string>('')

  const isAuthenticated = useAuthStore((s) => s.status === 'AUTHENTICATED')
  const logout = useAuthStore((s) => s.clearAuth)

  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 70)

      // Update active section
      const sections = ['platform', 'security', 'features', 'architecture']
      for (const section of sections.reverse()) {
        const el = document.getElementById(section)
        if (el && window.scrollY >= (el.offsetTop - 100)) {
          setActiveSection(section)
          return
        }
      }
      if (window.scrollY < 200) setActiveSection('')
    }
    window.addEventListener('scroll', handleScroll)
    handleScroll()
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  const handleLaunch = () => {
    if (isAuthenticated) {
      navigate('/dashboard')
    } else {
      navigate('/auth/login')
    }
  }

  const handleScrollTo = (e: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    e.preventDefault()
    setMobileMenuOpen(false)
    if (location.pathname !== '/') {
      navigate('/')
      setTimeout(() => {
        const el = document.getElementById(id)
        if (el) el.scrollIntoView({ behavior: 'smooth' })
      }, 100)
    } else {
      const el = document.getElementById(id)
      if (el) el.scrollIntoView({ behavior: 'smooth' })
      else if (id === '') window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const navLinks = [
    { label: 'Platform', href: 'platform' },
    { label: 'Security', href: 'security' },
    { label: 'Features', href: 'features' },
    { label: 'Architecture', href: 'architecture' },
  ]

  return (
    <header
      className={cn(
        "fixed top-0 inset-x-0 z-50 transition-all duration-500",
        scrolled
          ? "bg-background/80 backdrop-blur-xl border-b border-white/10 shadow-[0_4px_40px_rgba(0,0,0,0.15)] py-3"
          : "bg-transparent py-6 border-b border-transparent"
      )}
    >
      <div className="container mx-auto px-4 md:px-8 max-w-7xl flex items-center justify-between">
        {/* Logo */}
        <a
          href="#"
          onClick={(e) => handleScrollTo(e, '')}
          className="flex items-center space-x-2.5 group outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-md p-1"
        >
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-primary to-primary/60 text-primary-foreground shadow-[0_0_15px_hsl(var(--primary)/0.5)] flex items-center justify-center group-hover:scale-105 transition-transform">
            <Shield className="w-5 h-5" />
          </div>
          <span className="font-bold text-xl tracking-tight text-foreground group-hover:text-primary transition-colors">
            RAGuard <span className="font-light text-muted-foreground">AI</span>
          </span>
        </a>

        {/* Desktop Nav */}
        <nav
          className="hidden md:flex items-center space-x-1 bg-surface/50 border border-border/40 px-2 py-1.5 rounded-full backdrop-blur-md"
          onMouseLeave={() => setHoveredLink(null)}
        >
          {navLinks.map((link) => {
            const isActive = activeSection === link.href
            return (
              <a
                key={link.label}
                href={`#${link.href}`}
                onClick={(e) => handleScrollTo(e, link.href)}
                onMouseEnter={() => setHoveredLink(link.label)}
                className={cn(
                  "relative px-4 py-2 text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-full",
                  isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                )}
              >
                <span className="relative z-10">{link.label}</span>
                {hoveredLink === link.label && (
                  <motion.div
                    layoutId="navbar-hover"
                    className="absolute inset-0 bg-surface-elevated shadow-sm border border-border/50 rounded-full -z-0"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />
                )}
                {isActive && hoveredLink !== link.label && (
                  <motion.div
                    layoutId="navbar-active"
                    className="absolute inset-0 bg-surface-elevated/50 shadow-sm border border-border/30 rounded-full -z-0"
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />
                )}
              </a>
            )
          })}
        </nav>

        {/* Actions */}
        <div className="hidden md:flex items-center space-x-4">
          {!isAuthenticated ? (
            <>
              <Button variant="ghost" size="sm" onClick={() => navigate('/auth/login')} className="hover:bg-surface-elevated rounded-full px-5">
                Sign In
              </Button>
              <MagneticButton variant="primary" onClick={handleLaunch} className="text-sm font-semibold h-10 px-6 rounded-full shadow-[0_0_20px_hsl(var(--primary)/0.3)]">
                Launch Workspace
              </MagneticButton>
            </>
          ) : (
            <UserMenu />
          )}
        </div>

        {/* Mobile Toggle */}
        <div className="md:hidden flex items-center space-x-4">
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 text-foreground outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-md"
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden bg-background/95 backdrop-blur-xl border-b border-border/40 overflow-hidden"
          >
            <div className="px-4 py-6 flex flex-col space-y-4">
              {navLinks.map((link, i) => (
                <motion.a
                  key={link.label}
                  href={`#${link.href}`}
                  onClick={(e) => handleScrollTo(e, link.href)}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className={cn(
                    "text-lg font-medium",
                    activeSection === link.href ? "text-primary" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {link.label}
                </motion.a>
              ))}
              <div className="h-px bg-border/50 my-2" />

              {!isAuthenticated ? (
                <Button variant="ghost" onClick={() => { setMobileMenuOpen(false); navigate('/auth/login'); }} className="justify-start">
                  Sign In
                </Button>
              ) : (
                <Button variant="ghost" onClick={() => { setMobileMenuOpen(false); logout(); }} className="justify-start text-danger hover:text-danger hover:bg-danger/10">
                  <LogOut className="w-4 h-4 mr-2" />
                  Log out
                </Button>
              )}

              {!isAuthenticated && (
                <Button onClick={() => { setMobileMenuOpen(false); handleLaunch(); }} className="justify-start bg-primary text-primary-foreground">
                  Launch Workspace
                </Button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  )
}
