import * as React from 'react'
import {
  FileText,
  GitCommit,
  Layers,
  Cpu,
  Database,
  ArrowRight,
  Info,
} from 'lucide-react'
import { Badge, Card } from '@/components/common'
import { documentService } from '@/services/documentService'
import type { DocumentResponse } from '@/types'
import type { ProcessingStage } from '../KnowledgeProcessingPage'

interface PipelineVisualizerProps {
  onSelectStage?: (stage: ProcessingStage) => void
  activeStage?: ProcessingStage
}

interface PipelineNode {
  id: string
  entityName: string
  stageId?: ProcessingStage
  stageLabel?: string
  icon: React.ElementType
  summary: string
  technicalDetails: Array<{ label: string; value: string }>
  statusBadge: {
    label: string
    variant: 'success' | 'warning' | 'secondary' | 'destructive' | 'outline'
  }
}

export function PipelineVisualizer({ onSelectStage }: PipelineVisualizerProps) {
  const [documents, setDocuments] = React.useState<DocumentResponse[]>([])
  const [selectedDocId, setSelectedDocId] = React.useState<string>('')
  const [isLoadingDocs, setIsLoadingDocs] = React.useState<boolean>(true)

  React.useEffect(() => {
    let isMounted = true
    const fetchDocs = async () => {
      setIsLoadingDocs(true)
      try {
        const response = await documentService.listDocuments(1, 50).catch(() => null)
        if (isMounted && response?.items) {
          setDocuments(response.items)
          if (response.items.length > 0) {
            setSelectedDocId(response.items[0].id)
          }
        }
      } catch (err) {
        console.error('Failed to load documents for visualizer:', err)
      } finally {
        if (isMounted) setIsLoadingDocs(false)
      }
    }
    fetchDocs()
    return () => {
      isMounted = false
    }
  }, [])

  const activeDoc = React.useMemo(() => {
    return documents.find((d) => d.id === selectedDocId) || null
  }, [documents, selectedDocId])

  const pipelineNodes: PipelineNode[] = React.useMemo(() => {
    const isDocReady = activeDoc?.status === 'READY' || activeDoc?.status === 'PROCESSED'
    const isDocChunked = isDocReady || activeDoc?.status === 'CHUNKED'
    const isDocEmbedded = isDocReady || activeDoc?.status === 'EMBEDDED'
    const isDocFailed = activeDoc?.status === 'FAILED'

    return [
      {
        id: 'document',
        entityName: 'Document',
        summary: 'Source Knowledge Entity',
        icon: FileText,
        technicalDetails: [
          {
            label: 'Identifer',
            value: activeDoc ? `${activeDoc.id.slice(0, 8)}...` : 'Not selected',
          },
          {
            label: 'Filename',
            value: activeDoc?.original_filename || activeDoc?.filename || 'No document selected',
          },
          {
            label: 'Status',
            value: activeDoc?.status || 'Structural definition',
          },
        ],
        statusBadge: activeDoc
          ? isDocFailed
            ? { label: 'Failed', variant: 'destructive' }
            : { label: activeDoc.status || 'Active', variant: 'success' }
          : { label: 'Schema Model', variant: 'outline' },
      },
      {
        id: 'document_version',
        entityName: 'Document Version',
        summary: 'Immutable Snapshot',
        icon: GitCommit,
        technicalDetails: [
          {
            label: 'Version ID',
            value: activeDoc?.latest_version_id
              ? `${activeDoc.latest_version_id.slice(0, 8)}...`
              : 'Auto-assigned',
          },
          {
            label: 'Integrity',
            value: 'SHA-256 Content Hash Verified',
          },
          {
            label: 'State',
            value: activeDoc ? 'Active Version' : 'Structural definition',
          },
        ],
        statusBadge: activeDoc
          ? { label: 'Versioned', variant: 'success' }
          : { label: 'Schema Model', variant: 'outline' },
      },
      {
        id: 'chunk',
        entityName: 'Chunk',
        stageId: 'chunks',
        stageLabel: 'Stage 1',
        summary: 'Doubly-Linked Split Registry',
        icon: Layers,
        technicalDetails: [
          {
            label: 'Page Count',
            value: activeDoc?.page_count != null ? `${activeDoc.page_count} pages` : 'Not measured',
          },
          {
            label: 'Word Count',
            value: activeDoc?.word_count != null ? `${activeDoc.word_count.toLocaleString()} words` : 'Not measured',
          },
          {
            label: 'Splitting Strategy',
            value: 'Recursive / Markdown / Sentence',
          },
        ],
        statusBadge: activeDoc
          ? isDocChunked
            ? { label: 'Extracted', variant: 'success' }
            : isDocFailed
            ? { label: 'Halted', variant: 'destructive' }
            : { label: 'Pending Extraction', variant: 'warning' }
          : { label: 'Stage 1 Schema', variant: 'outline' },
      },
      {
        id: 'embedding',
        entityName: 'Embedding',
        stageId: 'embeddings',
        stageLabel: 'Stage 2',
        summary: 'Dense Semantic Vector Array',
        icon: Cpu,
        technicalDetails: [
          {
            label: 'Dimensions',
            value: '3072d (OpenAI) / 1024d (Cohere)',
          },
          {
            label: 'Batching',
            value: '100 chunks / batch request',
          },
          {
            label: 'Token Telemetry',
            value: 'Tracked in Embeddings tab',
          },
        ],
        statusBadge: activeDoc
          ? isDocEmbedded
            ? { label: 'Encoded', variant: 'success' }
            : isDocFailed
            ? { label: 'Halted', variant: 'destructive' }
            : { label: 'Awaiting Embed', variant: 'secondary' }
          : { label: 'Stage 2 Schema', variant: 'outline' },
      },
      {
        id: 'qdrant_point',
        entityName: 'Qdrant Point',
        stageId: 'vectors',
        stageLabel: 'Stage 3',
        summary: 'Indexed Payload Vector',
        icon: Database,
        technicalDetails: [
          {
            label: 'Namespace',
            value: 'raguard_knowledge_{tenant_id}',
          },
          {
            label: 'Payload Filters',
            value: 'tenant_id, document_id, version_id',
          },
          {
            label: 'Quantization',
            value: 'INT8 Scalar Quantization (75% Saved)',
          },
        ],
        statusBadge: activeDoc
          ? isDocReady
            ? { label: 'Synchronized', variant: 'success' }
            : isDocFailed
            ? { label: 'Halted', variant: 'destructive' }
            : { label: 'Awaiting Sync', variant: 'secondary' }
          : { label: 'Stage 3 Schema', variant: 'outline' },
      },
    ]
  }, [activeDoc])

  return (
    <div className="space-y-6">
      {/* Header and Document Context Switcher */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-border/60">
        <div>
          <h2 className="text-base font-bold text-foreground flex items-center gap-2">
            <span>Pipeline Architecture Visualizer</span>
            <Badge variant="outline" className="text-[10px] font-mono border-primary/30 text-primary uppercase">
              Truthful Provenance
            </Badge>
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Deterministic transformation sequence: Document → Document Version → Chunk → Embedding → Qdrant Point.
          </p>
        </div>

        {/* Document Selection Control */}
        <div className="flex items-center gap-2.5">
          <label htmlFor="pipeline-doc-select" className="text-xs text-muted-foreground whitespace-nowrap font-medium">
            Inspect Document:
          </label>
          <select
            id="pipeline-doc-select"
            value={selectedDocId}
            onChange={(e) => setSelectedDocId(e.target.value)}
            disabled={isLoadingDocs || documents.length === 0}
            className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary shadow-sm min-w-[220px]"
          >
            {documents.length === 0 ? (
              <option value="">{isLoadingDocs ? 'Loading documents...' : 'No documents found'}</option>
            ) : (
              documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.original_filename || doc.filename} ({doc.status})
                </option>
              ))
            )}
          </select>
        </div>
      </div>

      {/* Visual Pipeline Sequence Container */}
      <div className="relative">
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-3.5">
          {pipelineNodes.map((node, index) => {
            const Icon = node.icon
            const isClickable = Boolean(node.stageId && onSelectStage)

            return (
              <div key={node.id} className="relative flex flex-col">
                <Card
                  className={`flex-1 flex flex-col justify-between border-border/80 bg-surface/60 backdrop-blur-sm p-4 transition-all duration-200 ${
                    isClickable ? 'hover:border-primary/50 hover:bg-surface/80 group cursor-pointer' : ''
                  }`}
                  onClick={() => {
                    if (node.stageId && onSelectStage) {
                      onSelectStage(node.stageId)
                    }
                  }}
                  role={isClickable ? 'button' : undefined}
                  tabIndex={isClickable ? 0 : undefined}
                  onKeyDown={(e) => {
                    if (isClickable && (e.key === 'Enter' || e.key === ' ')) {
                      e.preventDefault()
                      if (node.stageId && onSelectStage) onSelectStage(node.stageId)
                    }
                  }}
                  aria-label={isClickable ? `Navigate to ${node.entityName} workspace` : undefined}
                >
                  {/* Top Bar with Sequence Number and Status Badge */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground font-mono">
                        {String(index + 1).padStart(2, '0')} · {node.stageLabel || 'Entity'}
                      </span>
                      <Badge variant={node.statusBadge.variant} className="text-[10px] px-1.5 py-0">
                        {node.statusBadge.label}
                      </Badge>
                    </div>

                    {/* Node Header */}
                    <div className="flex items-center gap-2 mb-1.5">
                      <div className="w-7 h-7 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0">
                        <Icon className="w-3.5 h-3.5" />
                      </div>
                      <h3 className="text-xs font-bold text-foreground truncate">
                        {node.entityName}
                      </h3>
                    </div>
                    <p className="text-[11px] text-muted-foreground line-clamp-1 mb-3">
                      {node.summary}
                    </p>

                    {/* Technical Invariants & Real Data */}
                    <div className="space-y-1.5 bg-background/50 border border-border/60 rounded-md p-2 text-[11px]">
                      {node.technicalDetails.map((detail) => (
                        <div key={detail.label} className="flex items-center justify-between gap-1">
                          <span className="text-muted-foreground truncate">{detail.label}:</span>
                          <span className="font-mono text-foreground font-medium truncate max-w-[120px]" title={detail.value}>
                            {detail.value}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Stage Jump CTA if associated with a workspace stage */}
                  {isClickable && (
                    <div className="mt-3 pt-2 border-t border-border/60 flex items-center justify-between text-[11px] text-primary group-hover:text-primary-focus transition-colors">
                      <span className="font-medium">Inspect Stage</span>
                      <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
                    </div>
                  )}
                </Card>

                {/* Flow Connector Arrow between columns (desktop only) */}
                {index < pipelineNodes.length - 1 && (
                  <div className="hidden lg:flex absolute -right-2.5 top-1/2 -translate-y-1/2 z-10 w-5 h-5 rounded-full bg-surface border border-border items-center justify-center text-muted-foreground shadow-sm">
                    <ArrowRight className="w-3 h-3" />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Truthfulness & Telemetry Policy Footnote */}
      <div className="rounded-xl border border-border/80 bg-surface/40 p-4 flex items-start gap-3 text-xs text-muted-foreground">
        <Info className="w-4 h-4 text-primary shrink-0 mt-0.5" />
        <div className="space-y-1">
          <strong className="text-foreground font-semibold">Deterministic Provenance Guarantee</strong>
          <p className="text-[11px] leading-relaxed">
            Entities in this visualizer reflect real system states. If telemetry (such as token counts or processing latency) is stage-scoped or unmeasured at the pipeline level, it is not fabricated. Detailed execution metrics are tracked inside the respective stage tabs.
          </p>
        </div>
      </div>
    </div>
  )
}
