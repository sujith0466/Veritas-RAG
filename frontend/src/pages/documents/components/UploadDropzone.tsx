import * as React from 'react'
import { motion } from 'framer-motion'
import { Upload, FileText, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import { Button, Card, Badge } from '@/components/common'
import { cn } from '@/utils/cn'

const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.md', '.csv', '.json']
const MAX_SIZE_BYTES = 50 * 1024 * 1024 // 50 MB

export interface UploadDropzoneProps {
  onUpload: (file: File, onProgress: (percent: number) => void) => Promise<void>
  isUploading: boolean
  uploadProgress: number
}

export function UploadDropzone({ onUpload, isUploading, uploadProgress }: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = React.useState(false)
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  const validateFile = (file: File): boolean => {
    setError(null)
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    
    if (ext === '.doc') {
      setError('Legacy Word documents (.doc) are not supported for reliability reasons. Please save or convert your file to .docx and try again.')
      return false
    }
    
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setError(`Disallowed file extension "${ext}". Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`)
      return false
    }
    if (file.size > MAX_SIZE_BYTES) {
      setError(`File size exceeds 50 MB quota (${(file.size / (1024 * 1024)).toFixed(2)} MB)`)
      return false
    }
    return true
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      if (validateFile(file)) {
        setSelectedFile(file)
      }
    }
  }

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0]
      if (validateFile(file)) {
        setSelectedFile(file)
      }
    }
  }

  const handleStartUpload = async () => {
    if (!selectedFile) return
    try {
      await onUpload(selectedFile, () => {})
      setSelectedFile(null)
    } catch (err: any) {
      setError(err.message || 'Upload failed')
    }
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
  }

  return (
    <Card className="p-6 relative overflow-hidden bg-surface-elevated/50 backdrop-blur-md border-border/80">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-foreground flex items-center gap-2">
            <Upload className="h-4 w-4 text-primary" />
            Ingest Document
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Provider-independent pipeline with NFC normalization, extraction, and SHA-256 duplicate screening.
          </p>
        </div>
        <Badge variant="subtle" className="text-[10px]">
          MAX 50 MB
        </Badge>
      </div>

      <motion.div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        animate={{ scale: isDragging ? 1.01 : 1, borderColor: isDragging ? 'var(--primary)' : undefined }}
        className={cn(
          'border-2 border-dashed rounded-lg p-8 text-center transition-all cursor-pointer flex flex-col items-center justify-center min-h-[180px]',
          isDragging ? 'border-primary bg-primary/5 shadow-inner' : 'border-border hover:border-primary/50 hover:bg-muted/30',
          isUploading && 'pointer-events-none opacity-60',
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept={ALLOWED_EXTENSIONS.join(',')}
          onChange={handleFileSelect}
          disabled={isUploading}
        />

        {selectedFile ? (
          <div className="flex flex-col items-center gap-3">
            <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center text-primary">
              <FileText className="h-6 w-6" />
            </div>
            <div>
              <p className="font-semibold text-foreground text-sm truncate max-w-xs">{selectedFile.name}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{formatSize(selectedFile.size)}</p>
            </div>
            <div className="flex items-center gap-2 mt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation()
                  setSelectedFile(null)
                }}
              >
                Change File
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center text-muted-foreground group-hover:text-primary transition-colors">
              <Upload className="h-6 w-6" />
            </div>
            <p className="text-sm font-medium text-foreground">
              Drag & drop document here, or <span className="text-primary underline underline-offset-4">browse</span>
            </p>
            <p className="text-xs text-muted-foreground">
              Supported: PDF, DOCX, TXT, MD, CSV, JSON
            </p>
          </div>
        )}
      </motion.div>

      {error && (
        <div className="mt-4 p-3 rounded-md bg-danger/10 border border-danger/30 flex items-center gap-2 text-xs text-danger">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {isUploading && (
        <div className="mt-4 space-y-2">
          <div className="flex justify-between text-xs font-medium text-muted-foreground">
            <span className="flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
              Uploading to Storage Volume...
            </span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
            <motion.div
              className="bg-primary h-full rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${uploadProgress}%` }}
              transition={{ duration: 0.2 }}
            />
          </div>
        </div>
      )}

      <div className="mt-6 flex justify-end">
        <Button
          type="button"
          onClick={handleStartUpload}
          disabled={!selectedFile || isUploading}
          isLoading={isUploading}
          className="w-full sm:w-auto"
        >
          {!isUploading && <CheckCircle2 className="mr-2 h-4 w-4" />}
          {isUploading ? 'Ingesting...' : 'Start Pipeline Ingestion'}
        </Button>
      </div>
    </Card>
  )
}
