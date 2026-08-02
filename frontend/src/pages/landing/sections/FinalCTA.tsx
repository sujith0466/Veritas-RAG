import { ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { FadeUp } from '@/components/motion/FadeUp'
import { MagneticButton } from '@/components/motion/MagneticButton'

export function FinalCTA() {
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((s) => s.status === 'AUTHENTICATED')

  const handleLaunch = () => {
    navigate(isAuthenticated ? '/dashboard' : '/auth/login')
  }

  return (
    <section className="py-32 relative overflow-hidden bg-background">
      {/* Intense but elegant background glow */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-primary/10 via-background to-background pointer-events-none" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-4xl h-[400px] bg-primary/10 blur-[150px] rounded-full pointer-events-none" />

      <div className="container mx-auto px-4 md:px-8 max-w-4xl relative z-10 text-center">
        <FadeUp yOffset={30} duration={0.7}>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-bold text-foreground mb-6 tracking-tight">
            Ready to Build AI You Can <span className="text-primary">Trust?</span>
          </h2>

          <p className="text-lg md:text-xl text-muted-foreground leading-relaxed mb-10 max-w-2xl mx-auto">
            Deploy enterprise-grade RAG systems with grounded responses, explainability, and reliability built in.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 w-full sm:w-auto">
            <MagneticButton
              variant="primary"
              onClick={handleLaunch}
              className="w-full sm:w-auto text-base h-12 px-8 shadow-[0_0_20px_rgb(59,130,246,0.2)] hover:shadow-[0_0_30px_rgb(59,130,246,0.4)] transition-shadow group"
            >
              Launch Workspace
              <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
            </MagneticButton>

            <MagneticButton
              variant="outline"
              className="w-full sm:w-auto text-base h-12 px-8 border-border/60 hover:bg-surface-elevated"
            >
              Request Enterprise Demo
            </MagneticButton>
          </div>
        </FadeUp>
      </div>
    </section>
  )
}
