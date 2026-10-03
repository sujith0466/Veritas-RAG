import * as React from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import {
  Layers,
  Cpu,
  Database,
  Activity,
  ArrowRight,
  Workflow,
  Sparkles,
  Info,
} from 'lucide-react'
import { Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle, PageHeader } from '@/components/common'
import { PageTransition } from '@/components/layouts'
import { ChunksStageView } from '@/pages/chunks'
import { EmbeddingsStageView } from '@/pages/embeddings'
import { VectorsStageView } from '@/pages/vectors'
import { PipelineVisualizer } from './components'
import { cn } from '@/utils/cn'

export type ProcessingStage = 'overview' | 'chunks' | 'embeddings' | 'vectors' | 'activity'

interface StageTabConfig {
  id: ProcessingStage
  label: string
  icon: React.ElementType
  badge?: string
  description: string
}

const STAGE_TABS: StageTabConfig[] = [
  {
    id: 'overview',
    label: 'Overview',
    icon: Workflow,
    description: 'Unified pipeline status and architecture topology',
  },
  {
    id: 'chunks',
    label: 'Chunks',
    icon: Layers,
    badge: 'Stage 1',
    description: 'Document structure, boundary splitting, and doubly-linked registry',
  },
  {
    id: 'embeddings',
    label: 'Embeddings',
    icon: Cpu,
    badge: 'Stage 2',
    description: 'Batch vector encoding, model selection, and token budget telemetry',
  },
  {
    id: 'vectors',
    label: 'Vectors',
    icon: Database,
    badge: 'Stage 3',
    description: 'Qdrant cluster health, payload indexing, and version synchronization',
  },
  {
    id: 'activity',
    label: 'Activity',
    icon: Activity,
    description: 'Background Celery task execution, batch jobs, and audit logs',
  },
]

export function KnowledgeProcessingPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const prefersReducedMotion = useReducedMotion()

  // Resolve active stage from URL query parameter (?stage=...)
  const rawStage = searchParams.get('stage')?.toLowerCase()
  const activeStage: ProcessingStage = React.useMemo(() => {
    if (rawStage && ['chunks', 'embeddings', 'vectors', 'activity'].includes(rawStage)) {
      return rawStage as ProcessingStage
    }
    return 'overview'
  }, [rawStage])

  const handleSelectStage = (stage: ProcessingStage) => {
    if (stage === 'overview') {
      const nextParams = new URLSearchParams(searchParams)
      nextParams.delete('stage')
      setSearchParams(nextParams, { replace: true })
    } else {
      const nextParams = new URLSearchParams(searchParams)
      nextParams.set('stage', stage)
      setSearchParams(nextParams, { replace: true })
    }
  }

  const currentTab = STAGE_TABS.find((t) => t.id === activeStage) || STAGE_TABS[0]

  return (
    <PageTransition className="space-y-8 pb-16">
      {/* Page Header */}
      <PageHeader
        title="Knowledge Processing"
        description="Pipeline orchestration & vector storage foundation across Chunks → Embeddings → Vectors."
        actions={
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="border-primary/30 text-primary font-mono text-xs px-2.5 py-1">
              Active Stage: {currentTab.label}
            </Badge>
          </div>
        }
      />

      {/* Top Pipeline Stepper Visual Preview */}
      <div className="rounded-2xl border border-border/80 bg-surface/60 backdrop-blur-md p-4 sm:p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3.5 pb-3 border-b border-border/60">
          <div className="flex items-center gap-2">
            <Workflow className="w-4 h-4 text-primary" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Knowledge Transformation Sequence
            </h2>
          </div>
          <span className="text-[11px] text-muted-foreground hidden sm:inline">
            Deterministic Pipeline · Provenance Guaranteed
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Step 1 */}
          <div
            onClick={() => handleSelectStage('chunks')}
            className={cn(
              'group cursor-pointer rounded-xl border p-3.5 transition-all',
              activeStage === 'chunks'
                ? 'border-indigo-500/50 bg-indigo-500/10 shadow-sm'
                : 'border-border/60 bg-background/40 hover:border-border hover:bg-background/80'
            )}
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400">
                01 · Splitting
              </span>
              <Layers className="w-4 h-4 text-indigo-400" />
            </div>
            <h3 className="text-xs font-semibold text-foreground">Document Chunks</h3>
            <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1">
              Doubly-linked structural boundaries
            </p>
          </div>

          {/* Step 2 */}
          <div
            onClick={() => handleSelectStage('embeddings')}
            className={cn(
              'group cursor-pointer rounded-xl border p-3.5 transition-all',
              activeStage === 'embeddings'
                ? 'border-amber-500/50 bg-amber-500/10 shadow-sm'
                : 'border-border/60 bg-background/40 hover:border-border hover:bg-background/80'
            )}
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">
                02 · Vector Encoding
              </span>
              <Cpu className="w-4 h-4 text-amber-400" />
            </div>
            <h3 className="text-xs font-semibold text-foreground">Embeddings</h3>
            <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1">
              Dense semantic representations (1536d)
            </p>
          </div>

          {/* Step 3 */}
          <div
            onClick={() => handleSelectStage('vectors')}
            className={cn(
              'group cursor-pointer rounded-xl border p-3.5 transition-all',
              activeStage === 'vectors'
                ? 'border-emerald-500/50 bg-emerald-500/10 shadow-sm'
                : 'border-border/60 bg-background/40 hover:border-border hover:bg-background/80'
            )}
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">
                03 · Storage & Sync
              </span>
              <Database className="w-4 h-4 text-emerald-400" />
            </div>
            <h3 className="text-xs font-semibold text-foreground">Vector Store</h3>
            <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1">
              Qdrant collection payload indexing
            </p>
          </div>

          {/* Step 4 */}
          <div
            onClick={() => handleSelectStage('overview')}
            className={cn(
              'group cursor-pointer rounded-xl border p-3.5 transition-all',
              activeStage === 'overview'
                ? 'border-primary/50 bg-primary/10 shadow-sm'
                : 'border-border/60 bg-background/40 hover:border-border hover:bg-background/80'
            )}
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-bold uppercase tracking-wider text-primary">
                04 · Retrieval Ready
              </span>
              <Sparkles className="w-4 h-4 text-primary" />
            </div>
            <h3 className="text-xs font-semibold text-foreground">Hybrid Grounding</h3>
            <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-1">
              Self-correcting RAG query engine
            </p>
          </div>
        </div>
      </div>

      {/* Stage Navigation Tabs */}
      <div className="border-b border-border/80">
        <nav
          role="tablist"
          aria-label="Knowledge Processing Stages"
          className="flex space-x-2 overflow-x-auto pb-px scrollbar-none"
        >
          {STAGE_TABS.map((tab) => {
            const Icon = tab.icon
            const isSelected = activeStage === tab.id
            return (
              <button
                key={tab.id}
                role="tab"
                id={`tab-${tab.id}`}
                aria-selected={isSelected}
                aria-controls={`panel-${tab.id}`}
                tabIndex={isSelected ? 0 : -1}
                onClick={() => handleSelectStage(tab.id)}
                className={cn(
                  'group relative flex items-center gap-2 px-4 py-2.5 text-xs font-medium transition-colors whitespace-nowrap rounded-t-lg outline-none focus-visible:ring-2 focus-visible:ring-primary',
                  isSelected
                    ? 'text-foreground border-b-2 border-primary bg-surface/40'
                    : 'text-muted-foreground hover:text-foreground hover:bg-surface/20'
                )}
              >
                <Icon
                  className={cn(
                    'w-4 h-4 transition-colors',
                    isSelected ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground'
                  )}
                />
                <span>{tab.label}</span>
                {tab.badge && (
                  <span
                    className={cn(
                      'text-[10px] px-1.5 py-0.2 rounded font-mono',
                      isSelected
                        ? 'bg-primary/15 text-primary'
                        : 'bg-muted text-muted-foreground'
                    )}
                  >
                    {tab.badge}
                  </span>
                )}

                {/* Subtle active tab pill motion */}
                {isSelected && !prefersReducedMotion && (
                  <motion.div
                    layoutId="activeKnowledgeProcessingTab"
                    className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary"
                    transition={{ type: 'spring', stiffness: 450, damping: 35 }}
                  />
                )}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Stage Workspace Panel */}
      <section
        role="tabpanel"
        id={`panel-${activeStage}`}
        aria-labelledby={`tab-${activeStage}`}
        className="space-y-6"
      >
        {activeStage === 'overview' && (
          <div className="space-y-8">
            {/* Contextual Pipeline Visualizer (KP-06) */}
            <PipelineVisualizer onSelectStage={handleSelectStage} activeStage={activeStage} />

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Card 1 */}
              <Card className="border-border/80 bg-surface/60 backdrop-blur-sm shadow-sm flex flex-col justify-between">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-400">
                      Stage 01
                    </span>
                    <Layers className="w-5 h-5 text-indigo-400" />
                  </div>
                  <CardTitle className="text-base text-foreground mt-2">Chunking Foundation</CardTitle>
                  <CardDescription className="text-xs text-muted-foreground">
                    Content-aware splitting algorithms (`recursive`, `markdown`, `sentence`, `code`) ensuring structured boundaries.
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleSelectStage('chunks')}
                    className="w-full justify-between text-xs border-border/80 hover:bg-indigo-500/10 hover:text-indigo-400"
                  >
                    <span>Inspect Chunks</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Button>
                </CardContent>
              </Card>

              {/* Card 2 */}
              <Card className="border-border/80 bg-surface/60 backdrop-blur-sm shadow-sm flex flex-col justify-between">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-amber-400">
                      Stage 02
                    </span>
                    <Cpu className="w-5 h-5 text-amber-400" />
                  </div>
                  <CardTitle className="text-base text-foreground mt-2">Vector Embeddings</CardTitle>
                  <CardDescription className="text-xs text-muted-foreground">
                    Batch embedding orchestration with token quota consumption tracking and model provider rotation.
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleSelectStage('embeddings')}
                    className="w-full justify-between text-xs border-border/80 hover:bg-amber-500/10 hover:text-amber-400"
                  >
                    <span>View Embedding Jobs</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Button>
                </CardContent>
              </Card>

              {/* Card 3 */}
              <Card className="border-border/80 bg-surface/60 backdrop-blur-sm shadow-sm flex flex-col justify-between">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
                      Stage 03
                    </span>
                    <Database className="w-5 h-5 text-emerald-400" />
                  </div>
                  <CardTitle className="text-base text-foreground mt-2">Vector Storage (Qdrant)</CardTitle>
                  <CardDescription className="text-xs text-muted-foreground">
                    Multi-tenant collection topology, strict payload filter indexing, and point parity synchronization.
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleSelectStage('vectors')}
                    className="w-full justify-between text-xs border-border/80 hover:bg-emerald-500/10 hover:text-emerald-400"
                  >
                    <span>Manage Collections</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Button>
                </CardContent>
              </Card>
            </div>

            {/* Architecture Info Notice */}
            <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 flex items-start gap-3 text-xs text-foreground">
              <Info className="w-4 h-4 text-primary shrink-0 mt-0.5" />
              <div className="space-y-1">
                <strong className="font-semibold text-primary">Unified Processing Architecture (KP-01)</strong>
                <p className="text-muted-foreground text-[11px] leading-relaxed">
                  This workspace provides unified orchestration for all downstream knowledge transformations.
                  Stage workspaces (Chunks, Embeddings, Vectors, Activity) are seamlessly integrated here,
                  preserving backward-compatible route aliases for legacy navigation.
                </p>
              </div>
            </div>
          </div>
        )}

        {activeStage === 'chunks' && <ChunksStageView />}

        {activeStage === 'embeddings' && <EmbeddingsStageView />}

        {activeStage === 'vectors' && <VectorsStageView />}

        {activeStage === 'activity' && (
          <Card className="border-border/80 bg-surface/60 backdrop-blur-sm p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                  <Activity className="w-4 h-4 text-primary" />
                  Pipeline Processing Activity
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Cross-stage task history and asynchronous Celery pipeline execution status.
                </p>
              </div>
              <Badge variant="outline" className="border-primary/30 text-primary">
                Activity Log
              </Badge>
            </div>
            <div className="rounded-lg border border-border/60 bg-background/50 p-4 text-xs text-muted-foreground leading-relaxed">
              <p>
                Comprehensive cross-stage background jobs and event audit logs across chunking,
                embedding, and vector synchronization pipelines will appear here.
              </p>
            </div>
          </Card>
        )}
      </section>
    </PageTransition>
  )
}
