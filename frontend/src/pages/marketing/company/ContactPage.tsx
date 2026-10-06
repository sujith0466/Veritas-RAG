import { useState } from 'react'
import {
  ShieldCheck,
  Send,
  CheckCircle2,
  Terminal,
  HelpCircle,
} from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'
import { FadeUp } from '@/components/motion/FadeUp'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import { Label } from '@/components/common/Label'

export function ContactPage() {
  const [submitted, setSubmitted] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    organization: '',
    message: '',
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.email || !formData.message) return
    setSubmitted(true)
  }

  const heroVisual = (
    <div className="w-full max-w-lg rounded-2xl border border-border/70 bg-surface/80 backdrop-blur-md p-6 md:p-8 shadow-xl">
      {submitted ? (
        <div className="text-center py-8 space-y-4">
          <div className="w-14 h-14 rounded-full bg-success/10 text-success flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-7 h-7" />
          </div>
          <h3 className="text-xl font-bold text-foreground">Inquiry Received</h3>
          <p className="text-sm text-muted-foreground max-w-xs mx-auto">
            Thank you for reaching out. Our engineering team will review your requirements and respond shortly.
          </p>
          <Button
            variant="outline"
            onClick={() => setSubmitted(false)}
            className="rounded-full mt-4"
          >
            Send Another Message
          </Button>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <h3 className="text-lg font-bold text-foreground mb-2">Technical Inquiry</h3>
          <p className="text-xs text-muted-foreground mb-4">
            Discuss private cloud deployments, multi-tenant requirements, or custom chunking strategies.
          </p>

          <div className="space-y-1.5">
            <Label htmlFor="contact-name">Full Name</Label>
            <Input
              id="contact-name"
              placeholder="Alex Chen"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="contact-email">Work Email</Label>
            <Input
              id="contact-email"
              type="email"
              required
              placeholder="alex@enterprise.com"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="contact-org">Organization</Label>
            <Input
              id="contact-org"
              placeholder="Enterprise Corp"
              value={formData.organization}
              onChange={(e) => setFormData({ ...formData, organization: e.target.value })}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="contact-msg">Message / Deployment Scope</Label>
            <textarea
              id="contact-msg"
              required
              rows={3}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary text-foreground placeholder:text-muted-foreground"
              placeholder="Tell us about your document volume and retrieval requirements..."
              value={formData.message}
              onChange={(e) => setFormData({ ...formData, message: e.target.value })}
            />
          </div>

          <Button type="submit" className="w-full rounded-xl bg-primary text-primary-foreground mt-2">
            <Send className="w-4 h-4 mr-2" />
            <span>Submit Inquiry</span>
          </Button>
        </form>
      )}
    </div>
  )

  const channels = [
    {
      icon: Terminal,
      title: 'Technical Documentation',
      desc: 'Access installation guides, deployment scripts, and API specs anytime in our developer center.',
      linkText: 'Browse Documentation',
      href: '/resources/documentation',
    },
    {
      icon: ShieldCheck,
      title: 'Security Office',
      desc: 'Inquiries regarding vulnerability reporting, data isolation, and cryptographic Join Codes.',
      linkText: 'Review Security',
      href: '/platform/security',
    },
    {
      icon: HelpCircle,
      title: 'Community & Issues',
      desc: 'Explore implementation discussions and report issues on our open repository tracking board.',
      linkText: 'View Guides',
      href: '/resources/api-reference',
    },
  ]

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="Contact & Enterprise Support"
        title={
          <>
            Connect with the{' '}
            <span className="text-primary">Veritas Engineering Team.</span>
          </>
        }
        subtitle="Have questions about self-hosting, hybrid retrieval benchmarks, or multi-tenant workspace architecture? We're here to assist."
        visual={heroVisual}
      />

      {/* Direct Channels */}
      <section className="py-20 lg:py-28 border-t border-border/40">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {channels.map((c) => (
              <FadeUp key={c.title} className="p-8 rounded-2xl border border-border/60 bg-surface/70 shadow-sm flex flex-col justify-between" yOffset={20}>
                <div>
                  <div className="w-12 h-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-6">
                    <c.icon className="w-6 h-6" />
                  </div>
                  <h3 className="text-xl font-bold text-foreground mb-3">{c.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed mb-6">{c.desc}</p>
                </div>
                <a
                  href={c.href}
                  className="text-sm font-semibold text-primary hover:underline flex items-center gap-1.5"
                >
                  <span>{c.linkText}</span>
                  <span>&rarr;</span>
                </a>
              </FadeUp>
            ))}
          </div>
        </div>
      </section>

      <MarketingCTA
        title="Ready to Deploy Veritas RAG?"
        description="Experience deterministic, verifiable knowledge intelligence across your organization."
      />
    </div>
  )
}
