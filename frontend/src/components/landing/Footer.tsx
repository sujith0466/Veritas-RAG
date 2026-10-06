import { Shield } from 'lucide-react'
import { Link } from 'react-router-dom'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

export function Footer() {
  const footerSections = [
    {
      title: 'Platform',
      links: [
        { label: 'Knowledge Intelligence', href: '/platform/knowledge-intelligence' },
        { label: 'Hybrid Retrieval', href: '/platform/hybrid-retrieval' },
        { label: 'Reliability Engine', href: '/platform/reliability-engine' },
        { label: 'Enterprise Security', href: '/platform/security' },
      ]
    },
    {
      title: 'Solutions',
      links: [
        { label: 'Financial Services', href: '/solutions/financial-services' },
        { label: 'Healthcare', href: '/solutions/healthcare' },
        { label: 'Legal Tech', href: '/solutions/legal-tech' },
        { label: 'Customer Support', href: '/solutions/customer-support' },
      ]
    },
    {
      title: 'Resources',
      links: [
        { label: 'Documentation', href: '/resources/documentation' },
        { label: 'API Reference', href: '/resources/api-reference' },
        { label: 'Blog', href: '/resources/blog' },
        { label: 'Case Studies', href: '/resources/case-studies' },
      ]
    },
    {
      title: 'Company',
      links: [
        { label: 'About Us', href: '/about' },
        { label: 'Careers', href: '/careers' },
        { label: 'Contact', href: '/contact' },
        { label: 'Privacy Policy', href: '/privacy' },
      ]
    }
  ]

  return (
    <footer className="bg-background border-t border-border/40 pt-20 pb-10">
      <div className="container mx-auto px-4 md:px-8 max-w-7xl">
        <Stagger className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-8 lg:gap-12 mb-16" staggerDelay={0.1}>
          {/* Brand Column */}
          <FadeUp className="col-span-2 lg:col-span-1 flex flex-col items-start" yOffset={20}>
            <Link to="/" className="flex items-center space-x-2.5 outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-md mb-6">
              <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
                <Shield className="w-5 h-5" />
              </div>
              <span className="font-semibold text-lg tracking-tight text-foreground">Veritas RAG</span>
            </Link>
            <p className="text-sm text-muted-foreground leading-relaxed mb-6">
              Enterprise Knowledge Reliability Platform. Build trustworthy AI applications with secure retrieval and hallucination-resistant generation.
            </p>
          </FadeUp>

          {/* Link Columns */}
          {footerSections.map((section) => (
            <FadeUp key={section.title} className="flex flex-col space-y-4" yOffset={20}>
              <h4 className="font-medium text-foreground tracking-tight">{section.title}</h4>
              <ul className="flex flex-col space-y-3">
                {section.links.map((link) => (
                  <li key={link.label}>
                    <Link
                      to={link.href}
                      className="text-sm text-muted-foreground hover:text-primary transition-colors outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-sm"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </FadeUp>
          ))}
        </Stagger>

        {/* Bottom Bar */}
        <FadeUp delay={0.3} yOffset={10}>
          <div className="flex flex-col md:flex-row items-center justify-between pt-8 border-t border-border/40">
            <p className="text-sm text-muted-foreground mb-4 md:mb-0">
              © {new Date().getFullYear()} Veritas RAG, Inc. All rights reserved.
            </p>
            <div className="flex items-center space-x-6">
              <Link to="/terms" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Terms</Link>
              <Link to="/privacy" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Privacy</Link>
              <Link to="/security" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Security</Link>
            </div>
          </div>
        </FadeUp>
      </div>
    </footer>
  )
}
