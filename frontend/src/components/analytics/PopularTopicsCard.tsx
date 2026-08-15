import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Hash } from 'lucide-react'
import { analyticsService } from '@/services/analyticsService'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/common/Card'
import { Skeleton } from '@/components/common/Skeleton'

export function PopularTopicsCard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['popular-topics'],
    queryFn: () => analyticsService.getPopularTopics(),
    staleTime: 5 * 60 * 1000,
  })

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 }}
      className="h-full"
    >
      <Card className="h-full border-border/50 bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Hash className="w-5 h-5 text-blue-500" />
            <CardTitle>Popular Topics</CardTitle>
          </div>
          <CardDescription>
            Most frequent query themes across the workspace.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : error ? (
            <div className="text-sm text-destructive">Failed to load topics.</div>
          ) : data?.length === 0 ? (
            <div className="text-sm text-muted-foreground text-center py-4">No topics found.</div>
          ) : (
            <div className="space-y-4">
              {data?.map((topic, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{topic.topic}</span>
                  </div>
                  <span className="text-sm text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                    {topic.count}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
