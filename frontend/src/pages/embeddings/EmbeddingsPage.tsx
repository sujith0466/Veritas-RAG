import { PageHeader } from '@/components/common'
import { PageTransition } from '@/components/layouts'
import { EmbeddingsStageView } from './components'

/**
 * Legacy standalone route for Embeddings (/embeddings).
 * Preserved for backward compatibility, delegating directly to EmbeddingsStageView.
 */
export function EmbeddingsPage() {
  return (
    <PageTransition className="p-8 space-y-8 max-w-7xl mx-auto pb-12">
      <PageHeader
        title="Knowledge Vectorization (Embeddings)"
        description="Manage semantic embedding models, monitor token budget consumption, and orchestrate batch chunk vector encoding."
      />
      <EmbeddingsStageView />
    </PageTransition>
  )
}
