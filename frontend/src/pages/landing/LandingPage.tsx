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

export function LandingPage() {
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
