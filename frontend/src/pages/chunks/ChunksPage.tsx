import { PageHeader } from '@/components/common'
import { PageTransition } from '@/components/layouts'
import { ChunksStageView } from './components'

/**
 * Legacy ChunksPage container preserved for backward compatibility.
 * Delegates directly to the single authoritative ChunksStageView implementation.
 */
export function ChunksPage() {
  return (
    <PageTransition className="pb-12">
      <PageHeader
        title="Knowledge Layer: Chunking Foundation"
        description="Transform normalized document text into structured, doubly-linked, and validated chunks with zero embedding leakage."
      />
      <ChunksStageView />
    </PageTransition>
  )
}
