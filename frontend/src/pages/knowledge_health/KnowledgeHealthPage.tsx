import { PageTransition } from '@/components/layouts'
import { PageHeader } from '@/components/common/PageHeader'
import { KnowledgeHealthPanel } from '@/components/knowledge'

export function KnowledgeHealthPage() {
  return (
    <PageTransition>
      <PageHeader
        title="Knowledge Health & Lifecycle"
        description="Autonomous vector cluster synchronization, orphan sweep engines, count parity auditing, and zero-downtime model rotation (`ADR-M6-001`, `ADR-M6-002`)."
      />
      <div className="mt-6">
        <KnowledgeHealthPanel />
      </div>
    </PageTransition>
  )
}
