import * as React from 'react'
import { useState, useEffect } from 'react'
import {
  FileText,
  Download,
  Calendar,
  CheckCircle2,
  AlertCircle,
  Clock,
  ShieldCheck,
  RefreshCw,
  Sliders,
  History,
} from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  Button,
  Badge,
} from '@/components/common'
import { analyticsService } from '@/services/analyticsService'
import { apiClient } from '@/api/client'
import type { ReportType, ReportFormat, ReportMetadataDTO } from '@/types'

interface ReportExportDialogProps {
  isOpen: boolean
  onClose: () => void
}

const REPORT_OPTIONS: Array<{
  id: ReportType
  title: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  badgeText: string
  badgeColor: 'default' | 'secondary' | 'success' | 'warning'
}> = [
  {
    id: 'sla_compliance',
    title: 'SLA Compliance & Performance Audit',
    description:
      'Formal enterprise audit documenting uptime, P95 latency guarantees, query volume, and overall SLA adherence.',
    icon: ShieldCheck,
    badgeText: 'SLA Guard',
    badgeColor: 'success',
  },
  {
    id: 'reliability_audit',
    title: 'AI Reliability & Self-Correction Audit',
    description:
      'Comprehensive breakdown of pre-generation grounding confidence, post-gen hallucination metrics, and rewrite loops.',
    icon: Sliders,
    badgeText: 'Forensic Audit',
    badgeColor: 'default',
  },
  {
    id: 'knowledge_health',
    title: 'Knowledge Base Health & Parity Audit',
    description:
      'Detailed audit of collection index synchronization, chunk orphan checks, double-linked graph health, and embedding parity.',
    icon: FileText,
    badgeText: 'Index Parity',
    badgeColor: 'secondary',
  },
  {
    id: 'executive_summary',
    title: 'Executive Overview & System Activity',
    description:
      'High-level summary of total queries served, clarification rates, and system efficiency tailored for stakeholders.',
    icon: Clock,
    badgeText: 'Executive Summary',
    badgeColor: 'warning',
  },
]

export function ReportExportDialog({ isOpen, onClose }: ReportExportDialogProps): React.JSX.Element {
  const [selectedType, setSelectedType] = useState<ReportType>('sla_compliance')
  const [selectedFormat, setSelectedFormat] = useState<ReportFormat>('pdf')
  const [dateRangeMode, setDateRangeMode] = useState<'all' | 'custom'>('all')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [includeStageBreakdown, setIncludeStageBreakdown] = useState<boolean>(true)
  const [includeAnomalies, setIncludeAnomalies] = useState<boolean>(true)

  const [isGenerating, setIsGenerating] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [generatedReports, setGeneratedReports] = useState<ReportMetadataDTO[]>([])
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  const loadReportHistory = React.useCallback(async () => {
    try {
      setIsLoadingHistory(true)
      const reports = await analyticsService.listGeneratedReports()
      setGeneratedReports(reports)
    } catch {
      // Silently ignore if history fetch fails
    } finally {
      setIsLoadingHistory(false)
    }
  }, [])

  useEffect(() => {
    if (isOpen) {
      loadReportHistory()
    }
  }, [isOpen, loadReportHistory])

  const handleGenerateReport = async () => {
    setIsGenerating(true)
    setError(null)
    try {
      const payload = {
        report_type: selectedType,
        format: selectedFormat,
        include_stage_breakdown: includeStageBreakdown,
        include_anomalies: includeAnomalies,
        start_date: dateRangeMode === 'custom' && startDate ? new Date(startDate).toISOString() : undefined,
        end_date: dateRangeMode === 'custom' && endDate ? new Date(endDate).toISOString() : undefined,
      }

      const metadata = await analyticsService.exportReport(payload)
      setGeneratedReports((prev) => [metadata, ...prev.filter((r) => r.report_id !== metadata.report_id)])
      await handleDownloadFile(metadata.report_id, metadata.report_type, metadata.title, selectedFormat)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to generate enterprise report.')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleDownloadFile = async (
    reportId: string,
    reportType: string,
    _title: string,
    format: ReportFormat = 'pdf',
  ) => {
    setDownloadingId(reportId)
    try {
      const response = await apiClient.get(`/analytics/reports/download/${reportId}`, {
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `Veritas_RAG_${reportType}_${reportId}.${format}`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch {
      setError('Failed to download report file. The report may have expired from server cache.')
    } finally {
      setDownloadingId(null)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <FileText className="h-5 w-5" />
            </div>
            <div>
              <DialogTitle className="text-xl font-bold">Enterprise Reporting Center</DialogTitle>
              <DialogDescription>
                Generate ReportLab PDF audit reports, compliance certificates, and technical reliability exports.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {error ? (
          <div className="mt-4 flex items-center gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        ) : null}

        <div className="mt-4 space-y-6">
          {/* 1. Report Type Selection */}
          <div className="space-y-3">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              1. Select Report Type & Template
            </label>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {REPORT_OPTIONS.map((opt) => {
                const Icon = opt.icon
                const isSelected = selectedType === opt.id
                return (
                  <div
                    key={opt.id}
                    onClick={() => setSelectedType(opt.id)}
                    className={`cursor-pointer rounded-xl border p-4 transition-all ${
                      isSelected
                        ? 'border-primary bg-primary/5 shadow-md ring-1 ring-primary'
                        : 'border-border bg-surface hover:border-border-strong hover:bg-surface-elevated'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Icon className={`h-5 w-5 ${isSelected ? 'text-primary' : 'text-muted-foreground'}`} />
                        <span className="font-semibold text-foreground">{opt.title}</span>
                      </div>
                      <Badge variant={opt.badgeColor}>{opt.badgeText}</Badge>
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{opt.description}</p>
                  </div>
                )
              })}
            </div>
          </div>

          {/* 2. Date Range & Granularity */}
          <div className="space-y-3">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              2. Observation Window & Scope
            </label>
            <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface p-3">
              <button
                type="button"
                onClick={() => setDateRangeMode('all')}
                className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  dateRangeMode === 'all'
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'bg-muted text-muted-foreground hover:text-foreground'
                }`}
              >
                <Calendar className="h-3.5 w-3.5" />
                <span>All Recorded Activity / Standard Scope</span>
              </button>
              <button
                type="button"
                onClick={() => setDateRangeMode('custom')}
                className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  dateRangeMode === 'custom'
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'bg-muted text-muted-foreground hover:text-foreground'
                }`}
              >
                <span>Custom Date Window</span>
              </button>

              {dateRangeMode === 'custom' ? (
                <div className="mt-2 flex w-full flex-wrap items-center gap-2 sm:mt-0 sm:w-auto">
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="rounded border border-border bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <span className="text-xs text-muted-foreground">to</span>
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="rounded border border-border bg-background px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
              ) : null}
            </div>
          </div>

          {/* 3. Breakdown & Export Options */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-3">
              <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                3. Content Breakdown Options
              </label>
              <div className="space-y-2 rounded-lg border border-border bg-surface p-3">
                <label className="flex cursor-pointer items-center justify-between text-xs font-medium text-foreground">
                  <span>Include Stage Latency Waterfall Table</span>
                  <input
                    type="checkbox"
                    checked={includeStageBreakdown}
                    onChange={(e) => setIncludeStageBreakdown(e.target.checked)}
                    className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
                  />
                </label>
                <label className="flex cursor-pointer items-center justify-between text-xs font-medium text-foreground">
                  <span>Include Anomaly & Self-Correction Audit Log</span>
                  <input
                    type="checkbox"
                    checked={includeAnomalies}
                    onChange={(e) => setIncludeAnomalies(e.target.checked)}
                    className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
                  />
                </label>
              </div>
            </div>

            <div className="space-y-3">
              <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                4. Output File Format
              </label>
              <div className="flex gap-3 rounded-lg border border-border bg-surface p-3">
                <button
                  type="button"
                  onClick={() => setSelectedFormat('pdf')}
                  className={`flex flex-1 items-center justify-center gap-2 rounded-md py-2 text-xs font-semibold transition-all ${
                    selectedFormat === 'pdf'
                      ? 'bg-primary text-primary-foreground shadow-sm ring-1 ring-primary'
                      : 'bg-muted text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <FileText className="h-4 w-4" />
                  <span>ReportLab PDF (Formatted)</span>
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedFormat('json')}
                  className={`flex flex-1 items-center justify-center gap-2 rounded-md py-2 text-xs font-semibold transition-all ${
                    selectedFormat === 'json'
                      ? 'bg-primary text-primary-foreground shadow-sm ring-1 ring-primary'
                      : 'bg-muted text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <Download className="h-4 w-4" />
                  <span>Raw JSON Export</span>
                </button>
              </div>
            </div>
          </div>

          {/* 5. Recent Report History / Quick Downloads */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                <History className="h-3.5 w-3.5" />
                <span>Recently Generated Audit Reports ({generatedReports.length})</span>
              </label>
              <button
                type="button"
                onClick={loadReportHistory}
                disabled={isLoadingHistory}
                className="flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <RefreshCw className={`h-3 w-3 ${isLoadingHistory ? 'animate-spin' : ''}`} />
                <span>Refresh List</span>
              </button>
            </div>

            <div className="max-h-40 divide-y divide-border overflow-y-auto rounded-lg border border-border bg-surface">
              {generatedReports.length === 0 ? (
                <div className="p-4 text-center text-xs text-muted-foreground">
                  No reports generated during this session yet. Choose a template above and generate one.
                </div>
              ) : (
                generatedReports.map((rpt) => (
                  <div key={rpt.report_id} className="flex items-center justify-between p-2.5 text-xs hover:bg-muted/50">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-success" />
                      <div>
                        <div className="font-semibold text-foreground">{rpt.title}</div>
                        <div className="text-[10px] text-muted-foreground">
                          ID: {rpt.report_id} &nbsp;|&nbsp; {new Date(rpt.generated_at).toLocaleString()}
                        </div>
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDownloadFile(rpt.report_id, rpt.report_type, rpt.title, 'pdf')}
                      disabled={downloadingId === rpt.report_id}
                      className="h-7 text-[11px]"
                    >
                      <Download className={`mr-1 h-3 w-3 ${downloadingId === rpt.report_id ? 'animate-bounce' : ''}`} />
                      {downloadingId === rpt.report_id ? 'Downloading...' : 'Download'}
                    </Button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <DialogFooter className="mt-6 border-t border-border pt-4">
          <Button variant="outline" onClick={onClose} disabled={isGenerating}>
            Cancel
          </Button>
          <Button variant="default" onClick={handleGenerateReport} disabled={isGenerating} className="min-w-[200px]">
            {isGenerating ? (
              <span className="flex items-center gap-2">
                <RefreshCw className="h-4 w-4 animate-spin" />
                Generating ReportLab PDF...
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <Download className="h-4 w-4" />
                Generate & Download Report
              </span>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
