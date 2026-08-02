import { Shield } from 'lucide-react'
import { Link } from 'react-router-dom'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

export function Footer() {
  const footerSections = [
    {
      title: 'Platform',
      links: [
        { label: 'Knowledge Intelligence', href: '#' },
        { label: 'Hybrid Retrieval', href: '#' },
        { label: 'Reliability Engine', href: '#' },
        { label: 'Enterprise Security', href: '#' },
      ]
    },
    {
      title: 'Solutions',
      links: [
        { label: 'Financial Services', href: '#' },
        { label: 'Healthcare', href: '#' },
        { label: 'Legal Tech', href: '#' },
        { label: 'Customer Support', href: '#' },
      ]
    },
    {
      title: 'Resources',
      links: [
        { label: 'Documentation', href: '#' },
        { label: 'API Reference', href: '#' },
        { label: 'Blog', href: '#' },
        { label: 'Case Studies', href: '#' },
      ]
    },
    {
      title: 'Company',
      links: [
        { label: 'About Us', href: '#' },
        { label: 'Careers', href: '#' },
        { label: 'Contact', href: '#' },
        { label: 'Privacy Policy', href: '#' },
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
              <span className="font-semibold text-lg tracking-tight text-foreground">RAGuard AI</span>
            </Link>
            <p className="text-sm text-muted-foreground leading-relaxed mb-6">
              Enterprise RAG Reliability Platform. Build trustworthy AI applications with secure retrieval and hallucination-resistant generation.
            </p>
          </FadeUp>

          {/* Link Columns */}
          {footerSections.map((section) => (
            <FadeUp key={section.title} className="flex flex-col space-y-4" yOffset={20}>
              <h4 className="font-medium text-foreground tracking-tight">{section.title}</h4>
              <ul className="flex flex-col space-y-3">
                {section.links.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      className="text-sm text-muted-foreground hover:text-primary transition-colors outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-sm"
                    >
                      {link.label}
                    </a>
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
              © {new Date().getFullYear()} RAGuard AI, Inc. All rights reserved.
            </p>
            <div className="flex items-center space-x-6">
              <a href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Terms</a>
              <a href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Privacy</a>
              <a href="#" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Security</a>
            </div>
          </div>
        </FadeUp>
      </div>
    </footer>
  )
}
