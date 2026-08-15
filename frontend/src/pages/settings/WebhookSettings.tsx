import { useState, useEffect } from 'react'
import { Card, Input, Label, Button, SectionHeader } from '@/components/common'
import { useToast } from '@/hooks/useToast'
import { useAuthStore } from '@/stores/authStore'
import { Webhook, Plus, Trash2, Loader2 } from 'lucide-react'
import { format } from 'date-fns'

interface WebhookEndpoint {
  id: string
  endpoint_url: string
  events: string[]
  is_active: boolean
  created_at: string
}

export function WebhookSettings() {
  const { toast } = useToast()
  const user = useAuthStore(s => s.user)
  const token = useAuthStore(s => s.token)
  
  const [loading, setLoading] = useState(true)
  const [webhooks, setWebhooks] = useState<WebhookEndpoint[]>([])
  
  // New Webhook State
  const [isCreating, setIsCreating] = useState(false)
  const [newUrl, setNewUrl] = useState('')
  const [newSecret, setNewSecret] = useState<string | null>(null)
  
  const tenantId = user?.tenant_id || user?.workspace_id

  useEffect(() => {
    loadWebhooks()
  }, [])

  const loadWebhooks = async () => {
    if (!tenantId) return
    try {
      const res = await fetch(`/api/v1/workspaces/${tenantId}/webhooks`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('Failed to load webhooks')
      const data = await res.json()
      setWebhooks(data)
    } catch (err) {
      toast({ title: 'Error', message: 'Failed to load webhooks', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async () => {
    if (!newUrl) {
      toast({ title: 'Error', message: 'Endpoint URL is required', type: 'error' })
      return
    }
    
    setIsCreating(true)
    setNewSecret(null)
    try {
      const res = await fetch(`/api/v1/workspaces/${tenantId}/webhooks`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          endpoint_url: newUrl,
          events: ['*'], // Default to all events for now
          is_active: true
        })
      })
      
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to create webhook')
      
      setNewSecret(data.secret)
      setNewUrl('')
      await loadWebhooks()
      toast({ title: 'Success', message: 'Webhook created', type: 'success' })
    } catch (err: any) {
      toast({ title: 'Error', message: err.message, type: 'error' })
    } finally {
      setIsCreating(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/workspaces/${tenantId}/webhooks/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (!res.ok) throw new Error('Failed to delete webhook')
      
      await loadWebhooks()
      toast({ title: 'Success', message: 'Webhook deleted', type: 'success' })
    } catch (err) {
      toast({ title: 'Error', message: 'Failed to delete webhook', type: 'error' })
    }
  }

  const toggleActive = async (id: string, currentStatus: boolean) => {
    try {
      const res = await fetch(`/api/v1/workspaces/${tenantId}/webhooks/${id}`, {
        method: 'PUT',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ is_active: !currentStatus })
      })
      if (!res.ok) throw new Error('Failed to update webhook')
      
      await loadWebhooks()
    } catch (err) {
      toast({ title: 'Error', message: 'Failed to update webhook', type: 'error' })
    }
  }

  if (loading) {
    return <div className="flex justify-center items-center h-64"><Loader2 className="animate-spin text-primary h-8 w-8" /></div>
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <SectionHeader
        title="Webhook Endpoints"
        description="Manage webhooks to receive real-time notifications for workspace events."
      />

      {/* Create New Webhook */}
      <Card className="p-6 space-y-4">
        <h3 className="font-semibold text-foreground">Add Endpoint</h3>
        <div className="flex gap-4 items-end">
          <div className="flex-1 space-y-2">
            <Label htmlFor="url">Payload URL</Label>
            <Input
              id="url"
              placeholder="https://example.com/webhook"
              value={newUrl}
              onChange={(e) => setNewUrl(e.target.value)}
            />
          </div>
          <Button onClick={handleCreate} disabled={isCreating || !newUrl}>
            {isCreating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Plus className="w-4 h-4 mr-2" />}
            Add Webhook
          </Button>
        </div>
        
        {newSecret && (
          <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded-md">
            <h4 className="text-amber-800 font-semibold text-sm mb-2">Save this secret!</h4>
            <p className="text-amber-700 text-xs mb-3">
              This secret is used to sign webhook payloads via HMAC-SHA256. It will not be shown again.
            </p>
            <code className="bg-white p-2 rounded block text-sm border border-amber-100 break-all">
              {newSecret}
            </code>
          </div>
        )}
      </Card>

      {/* List Existing Webhooks */}
      <Card className="overflow-hidden">
        {webhooks.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            <Webhook className="w-12 h-12 mx-auto mb-4 opacity-20" />
            <p>No webhooks configured.</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {webhooks.map(wh => (
              <div key={wh.id} className="p-4 flex items-center justify-between hover:bg-muted/50 transition-colors">
                <div className="space-y-1">
                  <div className="font-medium text-sm flex items-center gap-2">
                    {wh.endpoint_url}
                    {!wh.is_active && (
                      <span className="text-[10px] uppercase tracking-wider font-bold bg-muted text-muted-foreground px-2 py-0.5 rounded-full">
                        Inactive
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Added {format(new Date(wh.created_at), 'MMM d, yyyy')} • Subscribed to {wh.events.length} events
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => toggleActive(wh.id, wh.is_active)}
                  >
                    {wh.is_active ? 'Disable' : 'Enable'}
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="text-red-500 hover:text-red-600 hover:bg-red-50"
                    onClick={() => handleDelete(wh.id)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
      
      {/* Delivery Logs Placeholder - F11.5 */}
      <Card className="p-6">
        <h3 className="font-semibold text-foreground mb-4">Recent Delivery Logs</h3>
        <div className="text-sm text-muted-foreground bg-muted p-4 rounded text-center">
          Delivery logs will appear here after events are processed.
        </div>
      </Card>
    </div>
  )
}
