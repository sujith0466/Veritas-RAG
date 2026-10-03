import { PageHeader } from '@/components/common'
import { PageTransition } from '@/components/layouts'
import { VectorsStageView } from './components'

/**
 * Legacy standalone route for Vectors (/vectors).
 * Preserved for backward compatibility, delegating directly to VectorsStageView.
 */
export function VectorsPage() {
  return (
    <PageTransition className="space-y-8 pb-12">
      <PageHeader
        title="Vector Storage Foundation"
        description="Qdrant Payload Filter Indexing & HNSW Quantization"
      />
      <VectorsStageView />
    </PageTransition>
  )
}
