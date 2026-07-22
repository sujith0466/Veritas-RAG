import { motion } from 'framer-motion'
import { Cpu, CheckCircle2, XCircle, Sparkles, Layers } from 'lucide-react'
import { Badge, Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/common'
import type { ProviderInfoDTO } from '@/types'

interface ProviderConfigCardProps {
  provider: ProviderInfoDTO
  onSelectDefaultModel?: (providerCode: string, modelName: string) => void
}

export function ProviderConfigCard({ provider }: ProviderConfigCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="h-full"
    >
      <Card className="h-full flex flex-col border-border/80 bg-surface/60 backdrop-blur hover:border-border/80 transition-colors">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-10 h-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                <Cpu className="w-5 h-5" />
              </div>
              <div>
                <CardTitle className="text-base text-foreground flex items-center gap-2">
                  {provider.display_name}
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground mt-0.5">
                  {provider.provider.toUpperCase()} ENGINE
                </CardDescription>
              </div>
            </div>
            <Badge
              variant={provider.is_available ? 'success' : 'secondary'}
              className="flex items-center gap-1.5 text-xs px-2.5 py-1"
            >
              {provider.is_available ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Available</span>
                </>
              ) : (
                <>
                  <XCircle className="w-3.5 h-3.5 text-muted-foreground" />
                  <span>Offline</span>
                </>
              )}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-3 leading-relaxed">
            {provider.description}
          </p>
        </CardHeader>

        <CardContent className="flex-1 flex flex-col justify-end pt-2">
          <div className="space-y-2">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
              Supported Models
            </p>
            <div className="space-y-1.5">
              {provider.models.map((model) => (
                <div
                  key={model.model_name}
                  className="flex items-center justify-between p-2.5 rounded-lg bg-background/60 border border-border/60 hover:border-border/60 transition-colors"
                >
                  <div className="flex flex-col">
                    <span className="text-xs font-medium text-foreground flex items-center gap-1.5">
                      {model.model_name}
                      {model.is_default && (
                        <Badge variant="subtle" className="text-[10px] px-1.5 py-0">
                          Default
                        </Badge>
                      )}
                    </span>
                    <span className="text-[11px] text-muted-foreground flex items-center gap-2 mt-0.5">
                      <span className="flex items-center gap-1">
                        <Layers className="w-3 h-3 text-cyan-400" />
                        {model.dimension} dimensions
                      </span>
                      <span>•</span>
                      <span>Max {model.max_input_tokens.toLocaleString()} tokens</span>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}
