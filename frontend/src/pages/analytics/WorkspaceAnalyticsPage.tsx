import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Activity, FileText, Users } from 'lucide-react'
import { analyticsService } from '@/services/analyticsService'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Skeleton } from '@/components/common/Skeleton'
import { ErrorState } from '@/components/common/ErrorState'

import { PopularTopicsCard } from '@/components/analytics/PopularTopicsCard'
import { UnansweredQueriesCard } from '@/components/analytics/UnansweredQueriesCard'
import { MostCitedDocumentsCard } from '@/components/analytics/MostCitedDocumentsCard'
import { StalenessReportCard } from '@/components/analytics/StalenessReportCard'

export function WorkspaceAnalyticsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['workspace-overview'],
    queryFn: () => analyticsService.getWorkspaceOverview(),
    staleTime: 5 * 60 * 1000,
  })

  return (
    <div className="container max-w-6xl mx-auto p-6 space-y-8 animate-in fade-in duration-500">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight">Workspace Analytics</h1>
        <p className="text-muted-foreground text-lg">
          High-level snapshot of your workspace activity and usage.
        </p>
      </div>

      {error ? (
        <ErrorState 
          title="Error"
          error={error}
        />
      ) : null}

      <div className="grid gap-6 md:grid-cols-3">
        <MetricCard
          title="Active Users"
          value={data?.active_users}
          icon={<Users className="w-6 h-6 text-blue-500" />}
          description="Unique users active in the current period"
          isLoading={isLoading}
        />
        <MetricCard
          title="Document Count"
          value={data?.document_count}
          icon={<FileText className="w-6 h-6 text-green-500" />}
          description="Total active, processed documents"
          isLoading={isLoading}
        />
        <MetricCard
          title="Total Queries"
          value={data?.total_queries}
          icon={<Activity className="w-6 h-6 text-purple-500" />}
          description="Total AI queries processed"
          isLoading={isLoading}
        />
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <PopularTopicsCard />
        <UnansweredQueriesCard />
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <MostCitedDocumentsCard />
        <StalenessReportCard />
      </div>
    </div>
  )
}

function MetricCard({
  title,
  value,
  icon,
  description,
  isLoading
}: {
  title: string
  value?: number
  icon: React.ReactNode
  description: string
  isLoading: boolean
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <Card className="h-full border-border/50 bg-card/50 backdrop-blur-sm transition-all hover:shadow-md hover:bg-card/80">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {title}
          </CardTitle>
          <div className="p-2 bg-background rounded-full shadow-sm ring-1 ring-border/20">
            {icon}
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-9 w-24 mb-1" />
          ) : (
            <div className="text-3xl font-bold tracking-tight">
              {value?.toLocaleString() ?? 0}
            </div>
          )}
          <CardDescription className="text-xs mt-2 line-clamp-2">
            {description}
          </CardDescription>
        </CardContent>
      </Card>
    </motion.div>
  )
}
