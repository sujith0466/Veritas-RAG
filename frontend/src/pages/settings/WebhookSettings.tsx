import { useState, useEffect } from 'react'
import { Card, Input, Label, Button, SectionHeader } from '@/components/common'
import { useToast } from '@/hooks/useToast'
import { useAuthStore } from '@/stores/authStore'
import { Webhook, Plus, Trash2, Loader2, Send, History, CheckCircle2, XCircle, Clock, ChevronDown, ChevronUp, Copy, Check } from 'lucide-react'
import { format } from 'date-fns'

interface WebhookEndpoint {
  id: string
  endpoint_url: string
  events: string[]
  is_active: boolean
  created_at: string
}

interface WebhookDeliveryLog {
  id: string
  target: string
  status: string
  attempt_count: number
  error_message?: string | null
  created_at: string
  event_type?: string | null
  payload_summary?: {
    keys: string[]
    tenant_id: string
  }
}

interface EventCategory {
  category: string
  events: { id: string; name: string }[]
}

export function WebhookSettings() {
  const { toast } = useToast()
  const user = useAuthStore(s => s.user)
  const token = useAuthStore(s => s.token)
  
  const [loading, setLoading] = useState(true)
  const [webhooks, setWebhooks] = useState<WebhookEndpoint[]>([])
  
  // Event Catalog State
  const [eventCategories, setEventCategories] = useState<EventCategory[]>([])
  const [selectedEvents, setSelectedEvents] = useState<string[]>(['*'])
  const [isSelectAll, setIsSelectAll] = useState(true)
  
  // New Webhook State
  const [isCreating, setIsCreating] = useState(false)
  const [newUrl, setNewUrl] = useState('')
  const [newSecret, setNewSecret] = useState<string | null>(null)
  const [copiedSecret, setCopiedSecret] = useState(false)
  
  // Delivery Logs & Testing State
  const [logs, setLogs] = useState<WebhookDeliveryLog[]>([])
  const [loadingLogs, setLoadingLogs] = useState(false)
  const [selectedWebhookId, setSelectedWebhookId] = useState<string | null>(null)
  const [testingId, setTestingId] = useState<string | null>(null)
  const [showEventSelector, setShowEventSelector] = useState(false)
  
  const tenantId = user?.tenant_id || user?.workspace_id

  useEffect(() => {
    loadWebhooks()
    loadEventCatalog()
    loadDeliveryLogs()
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

  const loadEventCatalog = async () => {
    if (!tenantId) return
    try {
      const res = await fetch(`/api/v1/workspaces/${tenantId}/webhooks/events`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setEventCategories(data)
      }
    } catch {
      // Non-critical background failure fallback
    }
  }

  const loadDeliveryLogs = async (whId?: string | null) => {
    if (!tenantId) return
    setLoadingLogs(true)
    try {
      const url = whId
        ? `/api/v1/workspaces/${tenantId}/webhooks/logs?webhook_id=${whId}&limit=20`
        : `/api/v1/workspaces/${tenantId}/webhooks/logs?limit=20`
      const res = await fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setLogs(data.items || [])
      }
    } catch {
      toast({ title: 'Notice', message: 'Could not fetch delivery logs', type: 'info' })
    } finally {
      setLoadingLogs(false)
    }
  }

  const handleToggleEvent = (eventId: string) => {
    if (eventId === '*') {
      setSelectedEvents(['*'])
      setIsSelectAll(true)
      return
    }
    setIsSelectAll(false)
    let updated = selectedEvents.filter(e => e !== '*')
    if (updated.includes(eventId)) {
      updated = updated.filter(e => e !== eventId)
      if (updated.length === 0) {
        updated = ['*']
        setIsSelectAll(true)
      }
    } else {
      updated.push(eventId)
    }
    setSelectedEvents(updated)
  }

  const handleCreate = async () => {
    if (!newUrl) {
      toast({ title: 'Error', message: 'Endpoint URL is required', type: 'error' })
      return
    }
    
    setIsCreating(true)
    setNewSecret(null)
    setCopiedSecret(false)
    try {
      const res = await fetch(`/api/v1/workspaces/${tenantId}/webhooks`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          endpoint_url: newUrl,
          events: selectedEvents,
          is_active: true
        })
      })
      
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to create webhook')
      
      setNewSecret(data.secret)
      setNewUrl('')
      setSelectedEvents(['*'])
      setIsSelectAll(true)
      await loadWebhooks()
      toast({ title: 'Success', message: 'Webhook endpoint securely created', type: 'success' })
    } catch (err: any) {
      toast({ title: 'Error', message: err.message, type: 'error' })
    } finally {
      setIsCreating(false)
    }
  }

  const handleSendTestPing = async (id: string) => {
    setTestingId(id)
    try {
      const res = await fetch(`/api/v1/workspaces/${tenantId}/webhooks/${id}/test`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to dispatch test ping')
      toast({ title: 'Dispatched', message: 'Test ping queued for HMAC delivery', type: 'success' })
      // Reload logs after 1.5 seconds
      setTimeout(() => loadDeliveryLogs(selectedWebhookId), 1500)
    } catch (err: any) {
      toast({ title: 'Error', message: err.message, type: 'error' })
    } finally {
      setTestingId(null)
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
      if (selectedWebhookId === id) {
        setSelectedWebhookId(null)
        loadDeliveryLogs(null)
      }
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
      toast({ title: 'Updated', message: `Webhook ${!currentStatus ? 'enabled' : 'disabled'}`, type: 'info' })
    } catch (err) {
      toast({ title: 'Error', message: 'Failed to update webhook', type: 'error' })
    }
  }

  const copySecretToClipboard = () => {
    if (!newSecret) return
    navigator.clipboard.writeText(newSecret)
    setCopiedSecret(true)
    setTimeout(() => setCopiedSecret(false), 2000)
  }

  if (loading) {
    return <div className="flex justify-center items-center h-64"><Loader2 className="animate-spin text-primary h-8 w-8" /></div>
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <SectionHeader
        title="Webhook Endpoints"
        description="Configure cryptographic HMAC-SHA256 endpoints to receive real-time domain events with SSRF protection."
      />

      {/* Create New Webhook */}
      <Card className="p-6 space-y-4">
        <h3 className="font-semibold text-foreground">Add Endpoint</h3>
        <div className="space-y-4">
          <div className="flex gap-4 items-end">
            <div className="flex-1 space-y-2">
              <Label htmlFor="url">Payload URL (HTTPS Required)</Label>
              <Input
                id="url"
                placeholder="https://api.yourdomain.com/webhooks/raguard"
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
              />
            </div>
            <Button onClick={handleCreate} disabled={isCreating || !newUrl}>
              {isCreating ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Plus className="w-4 h-4 mr-2" />}
              Add Webhook
            </Button>
          </div>

          {/* Granular Event Selection Accordion */}
          <div className="border border-border/60 rounded-lg p-3 bg-muted/20">
            <button
              type="button"
              className="flex items-center justify-between w-full text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setShowEventSelector(!showEventSelector)}
            >
              <span>
                Subscribed Topics: {selectedEvents.includes('*') ? 'All Domain Events (*)' : `${selectedEvents.length} selected topics`}
              </span>
              {showEventSelector ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>

            {showEventSelector && (
              <div className="mt-3 pt-3 border-t border-border/40 space-y-4 animate-in fade-in duration-200">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="all-events"
                    checked={isSelectAll}
                    onChange={() => handleToggleEvent('*')}
                    className="rounded border-border"
                  />
                  <label htmlFor="all-events" className="text-xs font-semibold text-foreground cursor-pointer">
                    Wildcard: Subscribe to All Domain Events (*)
                  </label>
                </div>

                {!isSelectAll && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {eventCategories.map((cat) => (
                      <div key={cat.category} className="space-y-1.5 p-2 rounded bg-background/50 border border-border/30">
                        <div className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">
                          {cat.category}
                        </div>
                        <div className="space-y-1 max-h-32 overflow-y-auto pr-1">
                          {cat.events.map((ev) => (
                            <label key={ev.id} className="flex items-center gap-2 text-xs text-foreground cursor-pointer hover:bg-muted/30 p-1 rounded">
                              <input
                                type="checkbox"
                                checked={selectedEvents.includes(ev.id)}
                                onChange={() => handleToggleEvent(ev.id)}
                                className="rounded border-border text-primary"
                              />
                              <span className="truncate">{ev.name}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
        
        {newSecret && (
          <div className="mt-4 p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-amber-400 font-semibold text-sm">Save your HMAC Signing Secret</h4>
              <button
                onClick={copySecretToClipboard}
                className="flex items-center gap-1 text-xs text-amber-300 hover:text-amber-200 bg-amber-500/20 px-2.5 py-1 rounded transition-colors"
              >
                {copiedSecret ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                {copiedSecret ? 'Copied' : 'Copy Secret'}
              </button>
            </div>
            <p className="text-muted-foreground text-xs">
              This secret is securely encrypted at rest (AES-256-GCM) and used to sign delivery payloads (`X-RAGuard-Signature`). It will not be shown again.
            </p>
            <code className="bg-background/80 p-2.5 rounded block text-xs font-mono border border-border text-foreground break-all select-all">
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
              <div key={wh.id} className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-muted/30 transition-colors">
                <div className="space-y-1">
                  <div className="font-medium text-sm flex items-center gap-2 font-mono">
                    <span data-testid="webhook-endpoint-url" className="truncate max-w-md">{wh.endpoint_url}</span>
                    {!wh.is_active ? (
                      <span className="text-[10px] uppercase tracking-wider font-bold bg-muted text-muted-foreground px-2 py-0.5 rounded-full">
                        Inactive
                      </span>
                    ) : (
                      <span className="text-[10px] uppercase tracking-wider font-bold bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded-full">
                        Active
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Created {format(new Date(wh.created_at), 'MMM d, yyyy')} • {wh.events.includes('*') ? 'All Events (*)' : `${wh.events.length} Subscribed Events`}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs"
                    disabled={testingId === wh.id}
                    onClick={() => handleSendTestPing(wh.id)}
                  >
                    {testingId === wh.id ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Send className="w-3.5 h-3.5 mr-1.5" />}
                    Test Ping
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-xs"
                    onClick={() => {
                      const nextId = selectedWebhookId === wh.id ? null : wh.id
                      setSelectedWebhookId(nextId)
                      loadDeliveryLogs(nextId)
                    }}
                  >
                    <History className="w-3.5 h-3.5 mr-1.5" />
                    {selectedWebhookId === wh.id ? 'All Logs' : 'Filter Logs'}
                  </Button>
                  <Button 
                    variant="outline" 
                    size="sm"
                    className="text-xs"
                    onClick={() => toggleActive(wh.id, wh.is_active)}
                  >
                    {wh.is_active ? 'Disable' : 'Enable'}
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="icon" 
                    className="text-red-500 hover:text-red-600 hover:bg-red-500/10"
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
      
      {/* Authentic Delivery Logs Table */}
      <Card className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-foreground">
              {selectedWebhookId ? 'Filtered Delivery Logs' : 'Recent Webhook Delivery Logs'}
            </h3>
            <p className="text-xs text-muted-foreground">
              Audit log of dispatched domain events and response statuses.
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="text-xs"
            disabled={loadingLogs}
            onClick={() => loadDeliveryLogs(selectedWebhookId)}
          >
            {loadingLogs ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <History className="w-3.5 h-3.5 mr-1.5" />}
            Refresh
          </Button>
        </div>

        {loadingLogs ? (
          <div className="py-8 text-center text-muted-foreground">
            <Loader2 className="w-6 h-6 mx-auto animate-spin mb-2" />
            <p className="text-xs">Loading delivery logs...</p>
          </div>
        ) : logs.length === 0 ? (
          <div className="text-sm text-muted-foreground bg-muted/30 p-8 rounded-lg text-center border border-border/40">
            No delivery logs recorded yet. Use the "Test Ping" button above to verify delivery.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border/50">
            <table className="w-full text-xs text-left">
              <thead className="bg-muted/50 text-muted-foreground border-b border-border/50">
                <tr>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Event Topic</th>
                  <th className="py-2.5 px-3">Destination</th>
                  <th className="py-2.5 px-3">Attempts</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/30">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-muted/20 transition-colors">
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      {log.status === 'SUCCESS' ? (
                        <span className="inline-flex items-center gap-1 text-emerald-400 font-medium">
                          <CheckCircle2 className="w-3.5 h-3.5" /> 200 OK
                        </span>
                      ) : log.status === 'PENDING' ? (
                        <span className="inline-flex items-center gap-1 text-amber-400 font-medium">
                          <Clock className="w-3.5 h-3.5" /> Pending
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-red-400 font-medium" title={log.error_message || ''}>
                          <XCircle className="w-3.5 h-3.5" /> Failed
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-muted-foreground">
                      {log.event_type || 'domain.event'}
                    </td>
                    <td className="py-2.5 px-3 font-mono truncate max-w-xs text-muted-foreground">
                      {log.target}
                    </td>
                    <td className="py-2.5 px-3 text-muted-foreground">
                      {log.attempt_count}
                    </td>
                    <td className="py-2.5 px-3 text-muted-foreground whitespace-nowrap">
                      {format(new Date(log.created_at), 'MMM d, HH:mm:ss')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
