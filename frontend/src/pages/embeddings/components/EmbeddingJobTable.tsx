import * as React from 'react'
import { motion } from 'framer-motion'
import {
  Play,
  RefreshCw,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  Layers,
  Sparkles,
} from 'lucide-react'
import {
  Badge,
  Button,
  Card,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  EmptyState,
  Input,
  Label,
  TooltipProvider,
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from '@/components/common'
import type {
  DocumentResponse,
  EmbeddingJobDTO,
  EmbeddingProcessRequestDTO,
  ProviderInfoDTO,
} from '@/types'

interface EmbeddingJobTableProps {
  jobs: EmbeddingJobDTO[]
  isLoading: boolean
  totalJobs: number
  page: number
  onPageChange: (newPage: number) => void
  statusFilter: string
  onStatusFilterChange: (newStatus: string) => void
  onRefresh: () => void
  documents: DocumentResponse[]
  providers: ProviderInfoDTO[]
  onCreateJob: (payload: EmbeddingProcessRequestDTO) => Promise<void>
  isCreating: boolean
}

export function EmbeddingJobTable({
  jobs,
  isLoading,
  totalJobs,
  page,
  onPageChange,
  statusFilter,
  onStatusFilterChange,
  onRefresh,
  documents,
  providers,
  onCreateJob,
  isCreating,
}: EmbeddingJobTableProps) {
  const [isModalOpen, setIsModalOpen] = React.useState<boolean>(false)
  const [selectedDocId, setSelectedDocId] = React.useState<string>('')
  const [selectedProvider, setSelectedProvider] = React.useState<string>('openai')
  const [selectedModel, setSelectedModel] = React.useState<string>('text-embedding-3-large')
  const [batchSize, setBatchSize] = React.useState<number>(100)
  const [forceReembed, setForceReembed] = React.useState<boolean>(false)

  // Update selected model when provider changes
  React.useEffect(() => {
    const prov = providers.find((p) => p.provider === selectedProvider)
    if (prov && prov.models.length > 0) {
      const def = prov.models.find((m) => m.is_default) || prov.models[0]
      setSelectedModel(def.model_name)
    }
  }, [selectedProvider, providers])

  // Set default document if available
  React.useEffect(() => {
    if (documents.length > 0 && !selectedDocId) {
      setSelectedDocId(documents[0].id)
    }
  }, [documents, selectedDocId])

  const handleSubmitNewJob = async () => {
    if (!selectedDocId) return
    const doc = documents.find((d) => d.id === selectedDocId)
    const versionId = doc?.latest_version_id || selectedDocId

    await onCreateJob({
      document_id: selectedDocId,
      document_version_id: versionId,
      provider: selectedProvider,
      model_name: selectedModel,
      batch_size: batchSize,
      force_reembed: forceReembed,
    })
    setIsModalOpen(false)
  }

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case 'COMPLETED':
        return (
          <Badge variant="success" className="flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>Completed</span>
          </Badge>
        )
      case 'PROCESSING':
        return (
          <Badge variant="default" className="flex items-center gap-1 animate-pulse">
            <Loader2 className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
            <span>Processing</span>
          </Badge>
        )
      case 'PENDING':
        return (
          <Badge variant="secondary" className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5 text-slate-400" />
            <span>Pending</span>
          </Badge>
        )
      case 'FAILED':
        return (
          <Badge variant="destructive" className="flex items-center gap-1">
            <XCircle className="w-3.5 h-3.5 text-rose-400" />
            <span>Failed</span>
          </Badge>
        )
      default:
        return <Badge variant="secondary">{status}</Badge>
    }
  }

  const currentProviderObj = providers.find((p) => p.provider === selectedProvider)
  const availableModels = currentProviderObj?.models || []

  return (
    <Card className="border-slate-800/80 bg-slate-900/60 backdrop-blur">
      <div className="p-5 border-b border-slate-800/80 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <Layers className="w-4 h-4 text-indigo-400" />
            Embedding Pipeline Jobs
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time batch vectorization tracking across active document versions (`ADR-M2-003`)
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => onStatusFilterChange(e.target.value)}
            className="rounded-md border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="PROCESSING">Processing</option>
            <option value="PENDING">Pending</option>
            <option value="COMPLETED">Completed</option>
            <option value="FAILED">Failed</option>
          </select>

          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={isLoading}
            className="flex items-center gap-1.5 text-xs bg-slate-950/60 border-slate-800 hover:bg-slate-800"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </Button>

          <Button
            variant="default"
            size="sm"
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1.5 text-xs bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>New Embedding Job</span>
          </Button>
        </div>
      </div>

      {isLoading && jobs.length === 0 ? (
        <div className="p-12 text-center">
          <Loader2 className="w-8 h-8 text-indigo-400 animate-spin mx-auto mb-3" />
          <p className="text-sm text-slate-400">Loading embedding jobs history...</p>
        </div>
      ) : jobs.length === 0 ? (
        <div className="p-12">
          <EmptyState
            title="No Embedding Jobs Found"
            description={
              statusFilter === 'ALL'
                ? 'No batch vectorization jobs have been initiated yet. Select a document version to start embedding.'
                : `No embedding jobs found matching status "${statusFilter}".`
            }
          />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800/80 bg-slate-950/40 text-slate-400 uppercase font-semibold">
                <th className="p-3 pl-5">Job ID & Document</th>
                <th className="p-3">Provider & Model</th>
                <th className="p-3">Status</th>
                <th className="p-3 w-48">Progress</th>
                <th className="p-3">Tokens Used</th>
                <th className="p-3">Created</th>
                <th className="p-3 pr-5 text-right">Error info</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-200">
              {jobs.map((job) => {
                const doc = documents.find((d) => d.id === job.document_id)
                const docTitle = doc ? (doc.original_filename || doc.filename) : `${job.document_id.slice(0, 8)}...`
                const progress = job.progress_percentage || 0

                return (
                  <motion.tr
                    key={job.job_id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="hover:bg-slate-800/30 transition-colors"
                  >
                    <td className="p-3 pl-5 font-mono text-[11px]">
                      <div className="font-semibold text-slate-200 truncate max-w-[180px]" title={docTitle}>
                        {docTitle}
                      </div>
                      <div className="text-slate-500 text-[10px] mt-0.5">
                        ID: {job.job_id.slice(0, 8)}...
                      </div>
                    </td>
                    <td className="p-3">
                      <div className="font-medium text-slate-200 uppercase text-[11px]">
                        {job.provider}
                      </div>
                      <div className="text-slate-400 text-[10px] mt-0.5 flex items-center gap-1">
                        <Sparkles className="w-3 h-3 text-indigo-400" />
                        {job.model_name}
                      </div>
                    </td>
                    <td className="p-3">{getStatusBadge(job.status)}</td>
                    <td className="p-3">
                      <div className="flex items-center justify-between text-[11px] mb-1">
                        <span className="font-semibold text-slate-300">
                          {progress.toFixed(1)}%
                        </span>
                        <span className="text-slate-500 text-[10px]">
                          {job.processed_chunks} / {job.total_chunks} chunks
                        </span>
                      </div>
                      <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                        <div
                          className={`h-full transition-all duration-500 ${
                            job.status === 'FAILED'
                              ? 'bg-rose-500'
                              : job.status === 'COMPLETED'
                              ? 'bg-emerald-500'
                              : 'bg-indigo-500 animate-pulse'
                          }`}
                          style={{ width: `${Math.min(100, progress)}%` }}
                        />
                      </div>
                    </td>
                    <td className="p-3 font-mono text-slate-300">
                      {job.total_tokens_consumed.toLocaleString()}{' '}
                      <span className="text-[10px] text-slate-500">tok</span>
                    </td>
                    <td className="p-3 text-slate-400 text-[11px]">
                      {new Date(job.created_at).toLocaleDateString()} {new Date(job.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td className="p-3 pr-5 text-right">
                      {job.error_message ? (
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="inline-flex items-center gap-1 text-rose-400 cursor-help font-medium text-[11px]">
                                <XCircle className="w-3.5 h-3.5" />
                                View Error
                              </span>
                            </TooltipTrigger>
                            <TooltipContent className="max-w-xs text-xs">
                              {job.error_message}
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                  </motion.tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination Footer */}
      {totalJobs > 0 && (
        <div className="p-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
          <div>
            Showing {jobs.length} of {totalJobs} jobs
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="px-2.5 py-1 text-xs"
            >
              Previous
            </Button>
            <span className="px-2 font-medium text-slate-300">Page {page}</span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(page + 1)}
              disabled={jobs.length < 20}
              className="px-2.5 py-1 text-xs"
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Modal for Creating Job */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="max-w-lg bg-slate-900 border border-slate-800 text-slate-100">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-indigo-400">
              <Play className="w-4 h-4 fill-current" />
              Initiate Batch Embedding Job
            </DialogTitle>
            <DialogDescription className="text-xs text-slate-400">
              Select a document to vector-encode all unindexed chunks. Idempotent content hashes will automatically bypass re-generation unless forced.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-3 text-xs">
            <div>
              <Label className="text-slate-300 font-semibold mb-1.5 block">Target Document</Label>
              <select
                value={selectedDocId}
                onChange={(e) => setSelectedDocId(e.target.value)}
                className="w-full rounded-md border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                {documents.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.original_filename || doc.filename} ({doc.page_count || 0} pages)
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-slate-300 font-semibold mb-1.5 block">Embedding Provider</Label>
                <select
                  value={selectedProvider}
                  onChange={(e) => setSelectedProvider(e.target.value)}
                  className="w-full rounded-md border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-100 uppercase focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  {providers.map((p) => (
                    <option key={p.provider} value={p.provider} disabled={!p.is_available}>
                      {p.display_name} {!p.is_available ? '(Offline)' : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <Label className="text-slate-300 font-semibold mb-1.5 block">Target Model</Label>
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="w-full rounded-md border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-100 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  {availableModels.map((m) => (
                    <option key={m.model_name} value={m.model_name}>
                      {m.model_name} ({m.dimension}d)
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <Label className="text-slate-300 font-semibold mb-1.5 flex items-center justify-between">
                <span>Batch Size per Request</span>
                <span className="text-[11px] font-normal text-slate-500">Recommended: 100</span>
              </Label>
              <Input
                type="number"
                min={1}
                max={500}
                value={batchSize}
                onChange={(e) => setBatchSize(Number(e.target.value))}
                className="w-full bg-slate-950 border-slate-800 text-xs font-mono"
              />
            </div>

            <div className="pt-2 border-t border-slate-800/60">
              <label className="flex items-start gap-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={forceReembed}
                  onChange={(e) => setForceReembed(e.target.checked)}
                  className="mt-0.5 rounded border-slate-700 bg-slate-950 text-indigo-600 focus:ring-indigo-500"
                />
                <div>
                  <span className="text-slate-200 font-medium block">Force Re-embedding</span>
                  <span className="text-[11px] text-slate-400 block mt-0.5 leading-relaxed">
                    Bypasses SHA-256 idempotency check and regenerates vectors for all chunks even if existing vectors are present in cache.
                  </span>
                </div>
              </label>
            </div>
          </div>

          <DialogFooter className="gap-2 pt-2 border-t border-slate-800/80">
            <Button variant="outline" size="sm" onClick={() => setIsModalOpen(false)} disabled={isCreating}>
              Cancel
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={handleSubmitNewJob}
              disabled={isCreating || !selectedDocId}
              className="bg-indigo-600 hover:bg-indigo-500 text-white flex items-center gap-1.5"
            >
              {isCreating ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Initiating...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Start Vectorization</span>
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
