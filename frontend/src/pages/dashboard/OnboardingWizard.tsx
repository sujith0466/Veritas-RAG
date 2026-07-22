import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Shield, 
  Database, 
  FileText, 
  Layers, 
  Cpu, 
  CheckCircle2, 
  ChevronRight, 
  ChevronLeft,
  UploadCloud,
  Loader2,
  Settings2
} from 'lucide-react'
import { Button } from '@/components/common/Button'
import { MotionCard, CardContent } from '@/components/common/Card'
import { Label } from '@/components/common/Label'
import { Input } from '@/components/common/Input'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/common/Select'
import { documentService } from '@/services/documentService'
import { chunkService } from '@/services/chunkService'
import { embeddingService } from '@/services/embeddingService'
import { useToast } from '@/hooks/useToast'
import { fadeVariants } from '@/motion'
import type { UploadResponse } from '@/types'

const steps = [
  { id: 'welcome', title: 'Welcome', icon: Shield },
  { id: 'source', title: 'Data Source', icon: Database },
  { id: 'document', title: 'Document', icon: FileText },
  { id: 'chunking', title: 'Chunking', icon: Layers },
  { id: 'embedding', title: 'Embedding', icon: Cpu },
  { id: 'processing', title: 'Processing', icon: CheckCircle2 },
]

export function OnboardingWizard({ onComplete }: { onComplete: () => void }) {
  const [currentStep, setCurrentStep] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const { toast } = useToast()

  // State
  const [file, setFile] = useState<File | null>(null)
  const [uploadedDoc, setUploadedDoc] = useState<UploadResponse | null>(null)
  const [chunkStrategy, setChunkStrategy] = useState('semantic')
  const [embeddingModel, setEmbeddingModel] = useState('text-embedding-3-small')

  const handleNext = async () => {
    try {
      if (currentStep === 2 && file && !uploadedDoc) {
        setIsLoading(true)
        const doc = await documentService.uploadDocument(file)
        setUploadedDoc(doc)
        setIsLoading(false)
      } else if (currentStep === 5) {
        // Run full ingestion
        setIsLoading(true)
        if (uploadedDoc) {
          await chunkService.processDocument(uploadedDoc.document_id, { strategy: chunkStrategy }, false)
          await embeddingService.createJob({
            document_id: uploadedDoc.document_id,
            document_version_id: uploadedDoc.version_id,
            provider: 'openai',
            model_name: embeddingModel
          })
          toast({ title: 'Ingestion complete', message: 'Your workspace is now ready.', type: 'success' })
        }
        setIsLoading(false)
        onComplete()
        return
      }
      setCurrentStep((prev) => Math.min(prev + 1, steps.length - 1))
    } catch (error: any) {
      toast({ title: 'Error', message: error.message || 'An error occurred', type: 'error' })
      setIsLoading(false)
    }
  }

  const handlePrev = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 0))
  }

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Workspace Setup</h1>
        <p className="text-muted-foreground mt-2">Configure your intelligence pipeline to activate dashboards.</p>
      </div>

      <div className="flex items-center justify-between mb-8 overflow-x-auto pb-4 scrollbar-none">
        {steps.map((step, index) => {
          const isActive = index === currentStep
          const isCompleted = index < currentStep
          return (
            <div key={step.id} className="flex items-center min-w-max">
              <div className={`flex items-center justify-center h-10 w-10 rounded-full border-2 transition-colors ${
                isActive ? 'border-primary bg-primary text-primary-foreground' :
                isCompleted ? 'border-success bg-success text-success-foreground' :
                'border-border bg-surface text-muted-foreground'
              }`}>
                <step.icon className="h-5 w-5" />
              </div>
              <div className="ml-3 mr-6">
                <p className={`text-sm font-medium ${isActive || isCompleted ? 'text-foreground' : 'text-muted-foreground'}`}>
                  {step.title}
                </p>
              </div>
              {index < steps.length - 1 && (
                <div className={`h-0.5 w-12 mr-6 ${isCompleted ? 'bg-success' : 'bg-border'}`} />
              )}
            </div>
          )
        })}
      </div>

      <MotionCard variants={fadeVariants} initial="hidden" animate="visible" className="min-h-[400px] flex flex-col shadow-card">
        <CardContent className="flex-1 p-8 flex flex-col justify-center">
          <AnimatePresence mode="wait">
            {currentStep === 0 && (
              <motion.div key="step0" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="text-center max-w-md mx-auto space-y-6">
                <div className="h-20 w-20 bg-primary/10 rounded-full flex items-center justify-center mx-auto">
                  <Shield className="h-10 w-10 text-primary" />
                </div>
                <h2 className="text-2xl font-bold">Welcome to Enterprise AI</h2>
                <p className="text-muted-foreground">To unlock your intelligence dashboards, we need to connect a data source and process your first document. This will establish your initial vector index.</p>
              </motion.div>
            )}

            {currentStep === 1 && (
              <motion.div key="step1" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="max-w-lg mx-auto space-y-6">
                <div className="text-center mb-8">
                  <h2 className="text-2xl font-bold">Data Source Connection</h2>
                  <p className="text-muted-foreground">Select where your knowledge lives.</p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="border-2 border-primary bg-primary/5 rounded-xl p-6 text-center cursor-pointer transition-all">
                    <UploadCloud className="h-8 w-8 text-primary mx-auto mb-3" />
                    <div className="font-semibold text-foreground">Local Upload</div>
                  </div>
                  <div className="border border-border bg-surface rounded-xl p-6 text-center opacity-50 cursor-not-allowed">
                    <Database className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
                    <div className="font-semibold text-foreground">Google Drive</div>
                    <div className="text-[10px] text-muted-foreground uppercase mt-1">Coming Soon</div>
                  </div>
                </div>
              </motion.div>
            )}

            {currentStep === 2 && (
              <motion.div key="step2" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="max-w-lg mx-auto space-y-6">
                <div className="text-center mb-8">
                  <h2 className="text-2xl font-bold">Upload Document</h2>
                  <p className="text-muted-foreground">Upload a PDF or text file to ingest.</p>
                </div>
                <div className="border-2 border-dashed border-border rounded-xl p-8 text-center bg-surface hover:bg-muted/50 transition-colors">
                  <Input type="file" accept=".pdf,.txt,.md" className="hidden" id="file-upload" onChange={(e) => setFile(e.target.files?.[0] || null)} />
                  <Label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center">
                    <FileText className="h-12 w-12 text-muted-foreground mb-4" />
                    <span className="text-sm font-medium text-primary hover:underline">{file ? file.name : 'Click to select a file'}</span>
                  </Label>
                </div>
              </motion.div>
            )}

            {currentStep === 3 && (
              <motion.div key="step3" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="max-w-lg mx-auto space-y-6">
                <div className="text-center mb-8">
                  <h2 className="text-2xl font-bold">Chunking Configuration</h2>
                  <p className="text-muted-foreground">How should we split your document?</p>
                </div>
                <div className="space-y-4">
                  <Label>Strategy</Label>
                  <Select value={chunkStrategy} onValueChange={setChunkStrategy}>
                    <SelectTrigger><SelectValue placeholder="Select strategy" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="semantic">Semantic (Context-aware)</SelectItem>
                      <SelectItem value="fixed_size">Fixed Size (500 tokens)</SelectItem>
                      <SelectItem value="paragraph">Paragraph Boundaries</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </motion.div>
            )}

            {currentStep === 4 && (
              <motion.div key="step4" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="max-w-lg mx-auto space-y-6">
                <div className="text-center mb-8">
                  <h2 className="text-2xl font-bold">Embedding Configuration</h2>
                  <p className="text-muted-foreground">Select the model to vectorize your knowledge.</p>
                </div>
                <div className="space-y-4">
                  <Label>Model</Label>
                  <Select value={embeddingModel} onValueChange={setEmbeddingModel}>
                    <SelectTrigger><SelectValue placeholder="Select model" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="text-embedding-3-small">OpenAI: text-embedding-3-small</SelectItem>
                      <SelectItem value="text-embedding-3-large">OpenAI: text-embedding-3-large</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </motion.div>
            )}

            {currentStep === 5 && (
              <motion.div key="step5" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="text-center max-w-md mx-auto space-y-6">
                <div className="h-20 w-20 bg-primary/10 rounded-full flex items-center justify-center mx-auto mb-6">
                  <Settings2 className="h-10 w-10 text-primary" />
                </div>
                <h2 className="text-2xl font-bold">Ready to Process</h2>
                <p className="text-muted-foreground">We will now run the ingestion pipeline. This entails parsing, chunking using your selected strategy, embedding, and indexing into Qdrant.</p>
              </motion.div>
            )}
          </AnimatePresence>
        </CardContent>
        <div className="border-t border-border/50 p-4 flex justify-between bg-surface/50 rounded-b-xl">
          <Button variant="outline" onClick={handlePrev} disabled={currentStep === 0 || isLoading}>
            <ChevronLeft className="h-4 w-4 mr-2" /> Back
          </Button>
          <Button onClick={handleNext} disabled={(currentStep === 2 && !file) || isLoading}>
            {isLoading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
            {currentStep === steps.length - 1 ? 'Start Processing' : 'Continue'} 
            {!isLoading && currentStep !== steps.length - 1 && <ChevronRight className="h-4 w-4 ml-2" />}
          </Button>
        </div>
      </MotionCard>
    </div>
  )
}
