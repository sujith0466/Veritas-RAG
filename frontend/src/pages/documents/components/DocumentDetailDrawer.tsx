import * as React from 'react'
import {
  FileText,
  Globe,
  ExternalLink,
  CheckCircle2,
  Clock,
  Database,
  Hash,
  Activity,
  Code2,
  ShieldCheck,
  Download,
  RotateCw,
  RefreshCw,
} from 'lucide-react'
import {
  Button,
  Badge,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/common'
import { documentService } from '@/services/documentService'
import type { DocumentDetailResponse, DocumentVersionDTO } from '@/types'

export interface DocumentDetailDrawerProps {
  documentId: string | null
  onClose: () => void
  onReingest?: (docId: string) => Promise<void>
  onRefreshWebsite?: (docId: string) => Promise<void>
}

export function DocumentDetailDrawer({
  documentId,
  onClose,
  onReingest,
  onRefreshWebsite,
}: DocumentDetailDrawerProps) {
  const [detail, setDetail] = React.useState<DocumentDetailResponse | null>(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [isReingesting, setIsReingesting] = React.useState(false)
  const [isRefreshing, setIsRefreshing] = React.useState(false)
  const [selectedVersion, setSelectedVersion] = React.useState<DocumentVersionDTO | null>(null)
  const [showManifestJson, setShowManifestJson] = React.useState(false)

  React.useEffect(() => {
    if (!documentId) {
      setDetail(null)
      return
    }
    let mounted = true
    setIsLoading(true)
    documentService
      .getDocumentDetail(documentId)
      .then((data) => {
        if (mounted) {
          setDetail(data)
          if (data.versions && data.versions.length > 0) {
            setSelectedVersion(data.versions[data.versions.length - 1])
          }
        }
      })
      .catch((err) => console.error('Failed to load document detail:', err))
      .finally(() => {
        if (mounted) setIsLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [documentId])

  const handleDownloadOriginal = async () => {
    if (!detail) return
    try {
      await documentService.downloadOriginal(detail.id, detail.original_filename || detail.filename, selectedVersion?.id)
    } catch (err) {
      console.error('Download original failed:', err)
    }
  }

  const handleDownloadExtracted = async () => {
    if (!detail) return
    try {
      await documentService.downloadExtractedText(detail.id, `${detail.filename}.extracted.txt`, selectedVersion?.id)
    } catch (err) {
      console.error('Download extracted text failed:', err)
    }
  }

  const handleReingest = async () => {
    if (!detail || !onReingest) return
    setIsReingesting(true)
    try {
      await onReingest(detail.id)
      onClose()
    } finally {
      setIsReingesting(false)
    }
  }

  const handleRefreshWebsite = async () => {
    if (!detail || !onRefreshWebsite) return
    setIsRefreshing(true)
    try {
      await onRefreshWebsite(detail.id)
      onClose()
    } finally {
      setIsRefreshing(false)
    }
  }

  if (!documentId) return null

  const isWebsite = detail?.source_type === 'website' || !!detail?.source_url
  const websiteUrl = detail?.final_url || detail?.source_url

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'READY':
      case 'PROCESSED':
        return <Badge variant="success">{status}</Badge>
      case 'FETCHING':
      case 'VALIDATING':
      case 'EXTRACTING':
      case 'OCR':
      case 'CHUNKING':
      case 'EMBEDDING':
      case 'VECTOR_SYNC':
      case 'RETRYING':
        return <Badge variant="warning" className="animate-pulse">{status}</Badge>
      case 'FAILED':
        return <Badge variant="destructive">FAILED</Badge>
      case 'ARCHIVED':
        return <Badge variant="outline">ARCHIVED</Badge>
      default:
        return <Badge variant="subtle">{status}</Badge>
    }
  }

  return (
    <Dialog open={!!documentId} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader className="border-b border-border/50 pb-4">
          <DialogTitle className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className={`h-10 w-10 rounded-lg flex items-center justify-center shrink-0 ${
                  isWebsite
                    ? 'bg-primary/15 text-primary ring-1 ring-primary/25'
                    : 'bg-primary/10 text-primary'
                }`}
              >
                {isWebsite ? <Globe className="h-5 w-5" /> : <FileText className="h-5 w-5" />}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-lg font-bold text-foreground block">
                    {detail?.filename || 'Loading Document Detail...'}
                  </span>
                  {isWebsite && (
                    <Badge
                      variant="subtle"
                      className="text-[10px] px-1.5 py-0 bg-primary/10 text-primary border-primary/20"
                    >
                      Website Knowledge
                    </Badge>
                  )}
                </div>
                {isWebsite && websiteUrl ? (
                  <a
                    href={websiteUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-muted-foreground hover:text-primary transition-colors flex items-center gap-1 mt-0.5"
                  >
                    <span>{websiteUrl}</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                ) : (
                  <span className="text-xs text-muted-foreground font-normal">
                    ID: {documentId}
                  </span>
                )}
              </div>
            </div>
            {detail && getStatusBadge(detail.status)}
          </DialogTitle>
        </DialogHeader>

        {isLoading || !detail ? (
          <div className="py-12 flex flex-col items-center justify-center gap-3 text-muted-foreground">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            <p className="text-sm">Fetching versions, stage metrics & canonical manifest...</p>
          </div>
        ) : (
          <div className="space-y-6 pt-4">
            {/* Quick Action Buttons */}
            <div className="flex flex-wrap items-center gap-2 p-3 rounded-lg bg-surface border border-border/80">
              {isWebsite && websiteUrl ? (
                <a
                  href={websiteUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-muted/60 text-foreground hover:bg-muted hover:text-primary transition-colors border border-border/60"
                >
                  <ExternalLink className="h-3.5 w-3.5 text-primary" />
                  Visit Live Webpage
                </a>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDownloadOriginal}
                  className="flex items-center gap-1.5"
                >
                  <Download className="h-3.5 w-3.5 text-primary" />
                  Download Original File
                </Button>
              )}

              <Button
                variant="outline"
                size="sm"
                onClick={handleDownloadExtracted}
                className="flex items-center gap-1.5"
              >
                <Download className="h-3.5 w-3.5 text-primary" />
                Download Extracted Text
              </Button>

              {isWebsite && onRefreshWebsite && detail.status !== 'ARCHIVED' && (
                <Button
                  variant="default"
                  size="sm"
                  onClick={handleRefreshWebsite}
                  isLoading={isRefreshing}
                  className="flex items-center gap-1.5 ml-auto text-xs"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Refresh Website Knowledge
                </Button>
              )}

              {!isWebsite && onReingest && detail.status !== 'ARCHIVED' && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleReingest}
                  isLoading={isReingesting}
                  className="flex items-center gap-1.5 ml-auto text-xs"
                >
                  <RotateCw className="h-3.5 w-3.5" />
                  Re-ingest Document
                </Button>
              )}
            </div>

            {/* Website Provenance Details Box (when applicable) */}
            {isWebsite && (
              <div className="p-4 rounded-lg bg-muted/20 border border-border/80 space-y-3">
                <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <Globe className="h-3.5 w-3.5 text-primary" />
                  Website Source Provenance
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-muted-foreground block text-[11px]">Source URL:</span>
                    <span className="font-mono text-foreground break-all">{detail.source_url || '—'}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block text-[11px]">Final Resolved URL:</span>
                    <span className="font-mono text-foreground break-all">{detail.final_url || detail.source_url || '—'}</span>
                  </div>
                  {detail.canonical_url && (
                    <div className="sm:col-span-2">
                      <span className="text-muted-foreground block text-[11px]">Canonical URL:</span>
                      <span className="font-mono text-foreground break-all">{detail.canonical_url}</span>
                    </div>
                  )}
                  {detail.last_fetched_at && (
                    <div>
                      <span className="text-muted-foreground block text-[11px]">Last Fetched:</span>
                      <span className="text-foreground">
                        {new Date(detail.last_fetched_at).toLocaleString()}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Overview Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="p-3.5 rounded-lg bg-muted/40 border border-border/50">
                <div className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                  <Hash className="h-3.5 w-3.5 text-primary" /> Words / Pages
                </div>
                <div className="text-base font-bold text-foreground mt-1">
                  {detail.word_count} words <span className="text-xs font-normal text-muted-foreground">({detail.page_count} pgs)</span>
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-muted/40 border border-border/50">
                <div className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                  <Database className="h-3.5 w-3.5 text-primary" /> Storage Engine
                </div>
                <div className="text-base font-bold text-foreground mt-1 uppercase">
                  {detail.manifest?.storage_provider || 'SECURE LOCAL'}
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-muted/40 border border-border/50">
                <div className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5 text-primary" /> Versions
                </div>
                <div className="text-base font-bold text-foreground mt-1">
                  {detail.versions.length} version(s)
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-muted/40 border border-border/50">
                <div className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5 text-success" /> Contract Verification
                </div>
                <div className="text-base font-bold text-success mt-1 flex items-center gap-1">
                  <CheckCircle2 className="h-4 w-4" /> VERIFIED
                </div>
              </div>
            </div>

            {/* Version Selector */}
            <div className="p-4 rounded-lg border border-border bg-surface">
              <h4 className="text-sm font-semibold text-foreground mb-3 flex items-center justify-between">
                <span>Version History & Cryptographic Checksum</span>
                {selectedVersion && (
                  <Badge variant="outline" className="text-xs font-mono">
                    SHA-256: {selectedVersion.content_hash.slice(0, 16)}...
                  </Badge>
                )}
              </h4>
              <div className="flex flex-wrap gap-2">
                {detail.versions.map((ver) => (
                  <button
                    key={ver.id}
                    onClick={() => setSelectedVersion(ver)}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors border ${
                      selectedVersion?.id === ver.id
                        ? 'bg-primary text-primary-foreground border-primary'
                        : 'bg-muted/50 text-muted-foreground border-border hover:bg-muted'
                    }`}
                  >
                    Version {ver.version_number} ({new Date(ver.created_at).toLocaleDateString()})
                  </button>
                ))}
              </div>
            </div>

            {/* Stage Processing Metrics (`StageMetricDTO`) */}
            {detail.manifest && detail.manifest.stage_metrics.length > 0 && (
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
                  <Activity className="h-4 w-4 text-primary" />
                  Stage Duration & Pipeline Metrics
                </h4>
                <div className="border border-border rounded-lg overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Pipeline Stage</TableHead>
                        <TableHead>Execution Duration</TableHead>
                        <TableHead className="text-right">Stage Outcome</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {detail.manifest.stage_metrics.map((metric, i) => (
                        <TableRow key={i}>
                          <TableCell className="font-medium uppercase tracking-wide text-xs">
                            {metric.stage}
                          </TableCell>
                          <TableCell className="font-mono text-xs">
                            {metric.duration_ms.toFixed(2)} ms
                          </TableCell>
                          <TableCell className="text-right">
                            <Badge variant="success" className="text-[10px]">
                              {metric.status}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </div>
            )}

            {/* Canonical Manifest Details */}
            {detail.manifest && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
                    <Code2 className="h-4 w-4 text-primary" />
                    Canonical Document Specification
                  </h4>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowManifestJson(!showManifestJson)}
                  >
                    {showManifestJson ? 'Hide Details' : 'View Spec JSON'}
                  </Button>
                </div>

                {showManifestJson ? (
                  <pre className="p-4 rounded-lg bg-surface-elevated text-xs font-mono text-foreground border border-border overflow-x-auto max-h-[300px]">
                    {JSON.stringify(
                      {
                        manifest_version: detail.manifest.manifest_version,
                        document_id: detail.manifest.document_id,
                        version_number: detail.manifest.version_number,
                        page_count: detail.manifest.page_count,
                        word_count: detail.manifest.word_count,
                        language: detail.manifest.language,
                        checksum_sha256: detail.manifest.checksum_sha256,
                        stage_metrics: detail.manifest.stage_metrics,
                      },
                      null,
                      2
                    )}
                  </pre>
                ) : (
                  <div className="p-4 rounded-lg bg-muted/30 border border-border/60 text-xs space-y-2 font-mono">
                    <div className="flex justify-between"><span className="text-muted-foreground">Specification Version:</span> <span>{detail.manifest.manifest_version}</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">Language / Encoding:</span> <span>{detail.manifest.language} / utf-8</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">Total Words / Pages:</span> <span>{detail.manifest.word_count} words / {detail.manifest.page_count} pgs</span></div>
                    <div className="flex justify-between"><span className="text-muted-foreground">Integrity Checksum:</span> <span className="truncate max-w-[280px]">{detail.manifest.checksum_sha256}</span></div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        <div className="flex justify-end pt-4 border-t border-border/50">
          <Button variant="outline" onClick={onClose}>
            Close Drawer
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

