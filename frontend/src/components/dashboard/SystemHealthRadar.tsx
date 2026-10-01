import React from 'react'
import { Server, Database, HardDrive, Cpu, Users, Building2, CheckCircle2, AlertCircle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import type { CommandSystemHealthDTO, CommandHealthComponentDTO } from '@/types'

interface SystemHealthRadarProps {
  systemHealth: CommandSystemHealthDTO
  activeTenants: number
  activeWorkspaces: number
  isLoading: boolean
}

export const SystemHealthRadar: React.FC<SystemHealthRadarProps> = ({
  systemHealth,
  activeTenants,
  activeWorkspaces,
  isLoading,
}) => {
  const getComponentIcon = (name: string) => {
    const lower = name.toLowerCase()
    if (lower.includes('postgre') || lower.includes('database')) return Database
    if (lower.includes('redis')) return Server
    if (lower.includes('qdrant') || lower.includes('vector')) return HardDrive
    return Cpu
  }

  return (
    <Card className="bg-card/60 backdrop-blur-md border border-border/70 shadow-sm flex flex-col h-full">
      <CardHeader className="pb-3 border-b border-border/40">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base font-bold flex items-center gap-2">
              <Server className="h-4 w-4 text-primary" />
              Subsystem & Infrastructure Health
            </CardTitle>
            <CardDescription className="text-xs">
              Live telemetry and latency probes across core dependencies.
            </CardDescription>
          </div>
          <Badge
            variant={
              systemHealth.status === 'OPERATIONAL'
                ? 'success'
                : systemHealth.status === 'DEGRADED'
                ? 'warning'
                : 'destructive'
            }
            className="text-[11px]"
          >
            {systemHealth.status}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="p-4 flex-1 flex flex-col justify-between space-y-4">
        {/* Component Health Cards */}
        <div className="space-y-2.5">
          {systemHealth.components.map((comp: CommandHealthComponentDTO) => {
            const Icon = getComponentIcon(comp.name)
            const isOk = comp.status === 'healthy'

            return (
              <div
                key={comp.name}
                className="flex items-center justify-between p-2.5 rounded-lg bg-background/50 border border-border/50 hover:border-border transition-colors text-xs"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className={`p-1.5 rounded-md ${isOk ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'}`}>
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="font-semibold text-foreground truncate">{comp.name}</p>
                    <p className="text-[11px] text-muted-foreground truncate">{comp.detail || 'Service probe normal'}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {comp.latency_ms !== null && (
                    <span className="font-mono text-[11px] text-muted-foreground">
                      {comp.latency_ms.toFixed(1)}ms
                    </span>
                  )}
                  {isOk ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-500" aria-label="Healthy" />
                  ) : (
                    <AlertCircle className="h-4 w-4 text-amber-500" aria-label="Degraded" />
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {/* Multi-Tenant Boundary Telemetry */}
        <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border/40 text-xs">
          <div className="flex items-center gap-2 p-2 rounded bg-muted/30 border border-border/30">
            <Users className="h-4 w-4 text-sky-400 shrink-0" />
            <div className="min-w-0">
              <span className="text-[10px] uppercase font-semibold text-muted-foreground block">Active Tenants</span>
              <span className="font-mono font-bold text-sm text-foreground">
                {isLoading ? '...' : activeTenants.toLocaleString()}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2 p-2 rounded bg-muted/30 border border-border/30">
            <Building2 className="h-4 w-4 text-indigo-400 shrink-0" />
            <div className="min-w-0">
              <span className="text-[10px] uppercase font-semibold text-muted-foreground block">Workspaces</span>
              <span className="font-mono font-bold text-sm text-foreground">
                {isLoading ? '...' : activeWorkspaces.toLocaleString()}
              </span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
