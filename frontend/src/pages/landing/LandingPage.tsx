import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { HeroSection } from './sections/HeroSection'
import { PlatformMetrics } from './sections/PlatformMetrics'
import { ProductShowcase } from './sections/ProductShowcase'
import { WhyRaguard } from './sections/WhyRaguard'
import { CoreFeatures } from './sections/CoreFeatures'
import { SecurityCompliance } from './sections/SecurityCompliance'
import { ArchitectureOverview } from './sections/ArchitectureOverview'
import { UseCases } from './sections/UseCases'
import { FAQ } from './sections/FAQ'
import { FinalCTA } from './sections/FinalCTA'

const SCROLL_STORAGE_KEY = 'veritas-rag:landing-scroll'

export function LandingPage() {
  const location = useLocation()
  const hasRestoredRef = useRef(false)
  const userInteractedRef = useRef(false)

  // 1. Restore scroll position on initial load if no explicit anchor is present
  useEffect(() => {
    const hash = location.hash || window.location.hash
    // If an explicit anchor hash is present, let anchor navigation take precedence
    if (hash) {
      hasRestoredRef.current = true
      const targetId = hash.replace(/^#/, '')
      const scrollToHash = () => {
        const targetEl = document.getElementById(targetId)
        if (targetEl) {
          const navOffset = 80
          const elementPosition = targetEl.getBoundingClientRect().top
          const offsetPosition = elementPosition + window.scrollY - navOffset
          window.scrollTo({
            top: Math.max(0, offsetPosition),
            behavior: 'instant' as ScrollBehavior,
          })
        }
      }
      requestAnimationFrame(scrollToHash)
      const t1 = setTimeout(scrollToHash, 80)
      const t2 = setTimeout(scrollToHash, 250)
      return () => {
        clearTimeout(t1)
        clearTimeout(t2)
      }
    }

    let savedY = 0
    try {
      const raw = sessionStorage.getItem(SCROLL_STORAGE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw)
        savedY = typeof parsed?.y === 'number' ? parsed.y : 0
      }
    } catch {
      // Storage read error — fallback silently
    }

    if (savedY <= 0) {
      hasRestoredRef.current = true
      return
    }

    // Cancel restoration if the user immediately interacts/scrolls
    const markUserInteracted = () => {
      userInteractedRef.current = true
    }

    window.addEventListener('wheel', markUserInteracted, { passive: true, capture: true })
    window.addEventListener('touchmove', markUserInteracted, { passive: true, capture: true })
    window.addEventListener('keydown', markUserInteracted, { passive: true, capture: true })
    window.addEventListener('pointerdown', markUserInteracted, { passive: true, capture: true })

    let rafId: number
    let timeoutId: ReturnType<typeof setTimeout>

    const attemptRestore = () => {
      if (userInteractedRef.current || hasRestoredRef.current) return

      const scrollHeight = document.documentElement.scrollHeight
      const clientHeight = window.innerHeight
      const maxScroll = Math.max(0, scrollHeight - clientHeight)

      if (maxScroll >= savedY || document.readyState === 'complete') {
        window.scrollTo({
          top: Math.min(savedY, maxScroll),
          behavior: 'instant' as ScrollBehavior,
        })
        hasRestoredRef.current = true
      }
    }

    // Execute on animation frame and fallback timeout once DOM is rendered
    rafId = requestAnimationFrame(() => {
      attemptRestore()
      if (!hasRestoredRef.current && !userInteractedRef.current) {
        timeoutId = setTimeout(attemptRestore, 80)
      }
    })

    return () => {
      cancelAnimationFrame(rafId)
      clearTimeout(timeoutId)
      window.removeEventListener('wheel', markUserInteracted)
      window.removeEventListener('touchmove', markUserInteracted)
      window.removeEventListener('keydown', markUserInteracted)
      window.removeEventListener('pointerdown', markUserInteracted)
    }
  }, [location.hash])

  // 2. Persist scroll position during scrolling and before page unload
  useEffect(() => {
    let ticking = false

    const saveScroll = () => {
      // Only persist once initialized or when user has engaged with the page
      if (!hasRestoredRef.current && !userInteractedRef.current) return

      try {
        sessionStorage.setItem(
          SCROLL_STORAGE_KEY,
          JSON.stringify({ y: Math.max(0, window.scrollY), timestamp: Date.now() })
        )
      } catch {
        // Storage quota exceeded or disabled — fail silently
      }
    }

    const onScroll = () => {
      userInteractedRef.current = true
      if (!ticking) {
        window.requestAnimationFrame(() => {
          saveScroll()
          ticking = false
        })
        ticking = true
      }
    }

    const onBeforeUnload = () => {
      saveScroll()
    }

    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('beforeunload', onBeforeUnload)

    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('beforeunload', onBeforeUnload)
    }
  }, [])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex flex-col w-full"
    >
      <HeroSection />
      <PlatformMetrics />
      <ProductShowcase />
      <WhyRaguard />
      <CoreFeatures />
      <SecurityCompliance />
      <ArchitectureOverview />
      <UseCases />
      <FAQ />
      <FinalCTA />
    </motion.div>
  )
}
