import { motion } from 'framer-motion'
import { Database, CheckCircle2, Shield, Layers, HardDrive } from 'lucide-react'
import { Badge, Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/common'
import type { CollectionDetailDTO } from '@/types'

interface CollectionHealthCardProps {
  collection: CollectionDetailDTO
  status?: string
}

export function CollectionHealthCard({ collection, status = 'ONLINE' }: CollectionHealthCardProps) {
  const isHealthy = status === 'ONLINE'

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="h-full">
      <Card className="h-full flex flex-col border-border/80 bg-surface/60 backdrop-blur hover:border-border/80 transition-colors">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-10 h-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                <Database className="w-5 h-5" />
              </div>
              <div>
                <CardTitle className="text-base text-foreground flex items-center gap-2">
                  {collection.collection_name}
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground mt-0.5">
                  QDRANT TENANT NAMESPACE
                </CardDescription>
              </div>
            </div>
            <Badge
              variant={isHealthy ? 'success' : 'secondary'}
              className="flex items-center gap-1.5 text-xs px-2.5 py-1"
            >
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>{status}</span>
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="flex-1 flex flex-col justify-end pt-2 space-y-4">
          <div className="grid grid-cols-2 gap-3 bg-background/40 border border-border/60 rounded-lg p-3">
            <div className="flex flex-col">
              <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
                <Layers className="w-3.5 h-3.5 text-indigo-400" />
                Total Points
              </span>
              <span className="text-lg font-bold text-foreground mt-1">
                {collection.total_points.toLocaleString()}
              </span>
            </div>
            <div className="flex flex-col">
              <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
                <Shield className="w-3.5 h-3.5 text-emerald-400" />
                Versions Indexed
              </span>
              <span className="text-lg font-bold text-foreground mt-1">
                {collection.indexed_versions_count}
              </span>
            </div>
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground bg-indigo-500/5 border border-indigo-500/10 rounded-md px-3 py-2">
            <span className="flex items-center gap-1.5">
              <HardDrive className="w-3.5 h-3.5 text-indigo-400" />
              Scalar Quantization:
            </span>
            <span className="font-semibold text-indigo-300">INT8 Enabled (75% RAM Saved)</span>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}
