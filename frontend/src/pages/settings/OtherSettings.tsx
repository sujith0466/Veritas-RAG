import { Card, SectionHeader } from '@/components/common'

export function DeveloperSettings() {
  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <SectionHeader title="Developer" description="Manage API keys and webhooks." />
      <Card className="p-6"><p className="text-sm text-muted-foreground">API key generation.</p></Card>
    </div>
  )
}

export function ActivitySettings() {
  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <SectionHeader title="Activity Log" description="View recent account activity." />
      <Card className="p-6"><p className="text-sm text-muted-foreground">Activity table.</p></Card>
    </div>
  )
}
