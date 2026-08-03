import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { UploadCloud, XCircle, FileText, CheckCircle2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { useToast } from '@/components/ui/use-toast';
import { apiClient } from '@/lib/api';

interface FileUploadState {
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  error?: string;
}

export function BulkUploadDropzone() {
  const [files, setFiles] = useState<FileUploadState[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batchProgress, setBatchProgress] = useState(0);
  const { toast } = useToast();

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setFiles((prev) => [
      ...prev,
      ...acceptedFiles.map((file) => ({
        file,
        progress: 0,
        status: 'pending' as const,
      })),
    ]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
    },
    maxSize: 50 * 1024 * 1024, // 50MB
  });

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setIsUploading(true);

    try {
      // 1. Initiate Batch
      const payload = {
        files: files.map((f) => ({
          filename: f.file.name,
          size_bytes: f.file.size,
          mime_type: f.file.type || 'application/octet-stream',
        })),
      };

      const res = await apiClient.post('/api/v1/bulk-uploads', payload);
      const { batch_id, presigned_urls } = res.data.data;
      setBatchId(batch_id);

      // 2. Upload to Presigned URLs concurrently
      await Promise.all(
        files.map(async (fileState, i) => {
          const urlData = presigned_urls[i];
          if (!urlData) return;

          setFiles((prev) => {
            const next = [...prev];
            next[i].status = 'uploading';
            return next;
          });

          try {
            // Mocking the S3 upload for now as requested
            // const formData = new FormData();
            // Object.entries(urlData.fields).forEach(([k, v]) => formData.append(k, v as string));
            // formData.append('file', fileState.file);
            // await fetch(urlData.url, { method: 'POST', body: formData });
            
            // Simulating upload time
            await new Promise((r) => setTimeout(r, 1000 + Math.random() * 2000));

            setFiles((prev) => {
              const next = [...prev];
              next[i].status = 'completed';
              next[i].progress = 100;
              return next;
            });
            
            // Optionally hit a finalize endpoint here to trigger indexing
            
          } catch (err: any) {
            setFiles((prev) => {
              const next = [...prev];
              next[i].status = 'error';
              next[i].error = err.message;
              return next;
            });
          }
        })
      );

      toast({ title: 'Upload complete', description: 'All files have been uploaded and queued for processing.' });

      // Start polling for batch progress here if desired.
      
    } catch (err: any) {
      toast({ title: 'Batch failed', description: err.message, variant: 'destructive' });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
          isDragActive ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
        }`}
      >
        <input {...getInputProps()} />
        <UploadCloud className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
        <h3 className="text-lg font-semibold mb-1">Drag & drop files here</h3>
        <p className="text-sm text-muted-foreground">or click to select files</p>
        <p className="text-xs text-muted-foreground mt-4">Supported formats: PDF, TXT, MD (Max 50MB)</p>
      </div>

      {files.length > 0 && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h4 className="font-semibold text-sm">Selected Files ({files.length})</h4>
            <Button onClick={handleUpload} disabled={isUploading || files.every(f => f.status === 'completed')}>
              {isUploading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
              {isUploading ? 'Uploading...' : 'Start Upload'}
            </Button>
          </div>

          <div className="max-h-64 overflow-y-auto space-y-2 pr-2">
            {files.map((file, i) => (
              <div key={i} className="flex items-center gap-4 p-3 border rounded-md bg-card">
                <FileText className="w-8 h-8 text-primary shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{file.file.name}</p>
                  <p className="text-xs text-muted-foreground">{(file.file.size / 1024 / 1024).toFixed(2)} MB</p>
                  {file.status === 'uploading' && (
                    <Progress value={file.progress} className="h-1 mt-2" />
                  )}
                </div>
                
                <div className="shrink-0 flex items-center">
                  {file.status === 'completed' && <CheckCircle2 className="w-5 h-5 text-green-500" />}
                  {file.status === 'error' && <XCircle className="w-5 h-5 text-destructive" />}
                  {file.status === 'pending' && (
                    <Button variant="ghost" size="icon" onClick={() => removeFile(i)}>
                      <XCircle className="w-4 h-4 text-muted-foreground" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
