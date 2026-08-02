import * as React from 'react'
import JSZip from 'jszip'
import { X, Folder, FileText, CheckSquare, Square, ChevronRight, ChevronDown, CheckCircle2, AlertCircle } from 'lucide-react'
import { Button, Card } from '@/components/common'
import { cn } from '@/utils/cn'

const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.md', '.csv', '.json', '.yaml', '.xml', '.sql', '.py', '.js', '.log']
const MAX_FILE_SIZE = 50 * 1024 * 1024

export interface ZipNode {
  path: string
  name: string
  isDir: boolean
  size?: number
  blob?: Blob
  children?: Record<string, ZipNode>
  selected?: boolean
  supported?: boolean
  reason?: string
}

interface ZipPreviewDialogProps {
  zipFile: File | null
  onClose: () => void
  onConfirm: (files: Array<{ file: File; path: string }>) => void
}

export function ZipPreviewDialog({ zipFile, onClose, onConfirm }: ZipPreviewDialogProps) {
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [rootNode, setRootNode] = React.useState<ZipNode | null>(null)
  const [expandedFolders, setExpandedFolders] = React.useState<Set<string>>(new Set())

  React.useEffect(() => {
    if (!zipFile) return
    parseZip(zipFile)
  }, [zipFile])

  const parseZip = async (file: File) => {
    setLoading(true)
    setError(null)
    try {
      const jszip = new JSZip()
      const zip = await jszip.loadAsync(file)

      const root: ZipNode = { path: '', name: 'root', isDir: true, children: {}, selected: true, supported: true }
      const newExpanded = new Set<string>()

      zip.forEach((relativePath, zipEntry) => {
        if (zipEntry.dir) return

        const parts = relativePath.split('/')
        const name = parts.pop() || ''
        if (!name || name.startsWith('.')) return

        let current = root
        let currentPath = ''

        for (const part of parts) {
          if (!part || part.startsWith('.')) return
          currentPath += (currentPath ? '/' : '') + part
          if (!current.children) current.children = {}
          if (!current.children[part]) {
            current.children[part] = {
              path: currentPath,
              name: part,
              isDir: true,
              children: {},
              selected: true,
              supported: true
            }
            newExpanded.add(currentPath)
          }
          current = current.children[part]
        }

        const ext = '.' + name.split('.').pop()?.toLowerCase()
        const isSupportedExt = ALLOWED_EXTENSIONS.includes(ext)

        if (!current.children) current.children = {}
        current.children[name] = {
          path: relativePath,
          name: name,
          isDir: false,
          blob: null as any,
          selected: isSupportedExt,
          supported: isSupportedExt,
          reason: isSupportedExt ? undefined : `Unsupported extension ${ext}`,
          _zipEntry: zipEntry
        } as any
      })

      setRootNode(root)
      setExpandedFolders(newExpanded)
    } catch (err: any) {
      setError(err.message || 'Failed to parse ZIP file')
    } finally {
      setLoading(false)
    }
  }

  const toggleFolder = (path: string) => {
    const next = new Set(expandedFolders)
    if (next.has(path)) next.delete(path)
    else next.add(path)
    setExpandedFolders(next)
  }

  const toggleSelection = (node: ZipNode, currentSelected: boolean) => {
    const newRoot = JSON.parse(JSON.stringify(rootNode))

    const updateRecursively = (n: ZipNode, val: boolean) => {
      if (n.supported) n.selected = val
      if (n.children) {
        Object.values(n.children).forEach(c => updateRecursively(c, val))
      }
    }

    const findAndUpdate = (n: ZipNode) => {
      if (n.path === node.path && n.name === node.name) {
        updateRecursively(n, !currentSelected)
        return true
      }
      if (n.children) {
        for (const c of Object.values(n.children)) {
          if (findAndUpdate(c)) return true
        }
      }
      return false
    }

    findAndUpdate(newRoot)

    const updateFolderStates = (n: ZipNode): boolean => {
      if (!n.children) return n.selected || false
      let allSelected = true
      let anySelected = false
      Object.values(n.children).forEach(c => {
        const selected = updateFolderStates(c)
        if (selected) anySelected = true
        else allSelected = false
      })
      n.selected = allSelected && anySelected
      return n.selected
    }

    updateFolderStates(newRoot)
    setRootNode(newRoot)
  }

  const handleConfirm = async () => {
    if (!rootNode || !zipFile) return
    setLoading(true)

    const selectedFiles: Array<{file: File, path: string}> = []

    const gatherFiles = async (n: ZipNode) => {
      if (!n.isDir && n.selected && n.supported && (n as any)._zipEntry) {
        const entry = (n as any)._zipEntry
        const blob = await entry.async('blob')
        if (blob.size <= MAX_FILE_SIZE) {
          const file = new File([blob], n.name, { type: blob.type || 'application/octet-stream' })
          selectedFiles.push({ file, path: n.path })
        }
      }
      if (n.children) {
        for (const c of Object.values(n.children)) {
          await gatherFiles(c)
        }
      }
    }

    await gatherFiles(rootNode)
    setLoading(false)
    onConfirm(selectedFiles)
  }

  const renderTree = (node: ZipNode, depth = 0) => {
    if (depth > 0 && node.name === 'root') return null

    const isExpanded = expandedFolders.has(node.path)
    const hasChildren = node.children && Object.keys(node.children).length > 0

    return (
      <div key={node.path + node.name} style={{ marginLeft: depth > 1 ? 24 : 0 }}>
        {depth > 0 && (
          <div className="flex items-center gap-2 py-1 hover:bg-muted/50 rounded px-2 -mx-2">
            <button
              onClick={() => hasChildren && toggleFolder(node.path)}
              className="p-0.5 text-muted-foreground hover:text-foreground"
            >
              {hasChildren ? (isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />) : <span className="w-5" />}
            </button>

            <button
              onClick={() => toggleSelection(node, node.selected || false)}
              disabled={!node.supported && !node.isDir}
              className={cn("p-0.5", (!node.supported && !node.isDir) ? "opacity-30 cursor-not-allowed" : "text-primary")}
            >
              {node.selected ? <CheckSquare className="h-4 w-4" /> : <Square className="h-4 w-4" />}
            </button>

            {node.isDir ? <Folder className="h-4 w-4 text-primary/70" /> : <FileText className="h-4 w-4 text-muted-foreground" />}

            <span className={cn("text-sm", (!node.supported && !node.isDir) && "text-muted-foreground line-through opacity-70")}>
              {node.name}
            </span>

            {(!node.supported && !node.isDir) && (
              <span className="text-[10px] text-danger ml-2 bg-danger/10 px-1.5 py-0.5 rounded">
                {node.reason}
              </span>
            )}
          </div>
        )}

        {isExpanded && node.children && (
          <div className="mt-1">
            {Object.values(node.children)
              .sort((a, b) => (a.isDir === b.isDir ? a.name.localeCompare(b.name) : (a.isDir ? -1 : 1)))
              .map(c => renderTree(c, depth + 1))
            }
          </div>
        )}
      </div>
    )
  }

  if (!zipFile) return null

  let totalFiles = 0
  let selectedFiles = 0

  const countStats = (n: ZipNode) => {
    if (!n.isDir) {
      totalFiles++
      if (n.selected) selectedFiles++
    }
    if (n.children) {
      Object.values(n.children).forEach(countStats)
    }
  }
  if (rootNode) countStats(rootNode)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
      <Card className="w-full max-w-3xl max-h-[85vh] flex flex-col shadow-xl border-border/80 bg-surface">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div>
            <h2 className="text-lg font-semibold text-foreground">ZIP Archive Contents</h2>
            <p className="text-xs text-muted-foreground">{zipFile.name}</p>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-muted rounded-full transition-colors">
            <X className="h-5 w-5 text-muted-foreground" />
          </button>
        </div>

        <div className="p-4 flex-1 overflow-y-auto min-h-[300px]">
          {loading && !rootNode && (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground space-y-4">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
              <p>Parsing archive structure...</p>
            </div>
          )}

          {error && (
            <div className="p-4 bg-danger/10 text-danger rounded-md flex items-center gap-3">
              <AlertCircle className="h-5 w-5 shrink-0" />
              <p>{error}</p>
            </div>
          )}

          {rootNode && (
            <div className="text-foreground">
              {renderTree(rootNode)}
            </div>
          )}
        </div>

        <div className="p-4 border-t border-border bg-muted/20 flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            <span className="font-semibold text-foreground">{selectedFiles}</span> of <span className="font-semibold text-foreground">{totalFiles}</span> files selected
          </div>
          <div className="flex gap-3">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button
              onClick={handleConfirm}
              disabled={selectedFiles === 0 || loading}
              isLoading={loading}
            >
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Ingest Selected Files
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
