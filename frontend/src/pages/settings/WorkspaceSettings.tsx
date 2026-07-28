import { useState, useEffect } from 'react'
import { Card, Input, Label, Button, SectionHeader } from '@/components/common'
import { useToast } from '@/hooks/useToast'
import { userService } from '@/services/userService'
import { useAuthStore } from '@/stores/authStore'
import { Briefcase, Database, Users, Loader2 } from 'lucide-react'

export function WorkspaceSettings() {
  const { toast } = useToast()
  const user = useAuthStore(s => s.user)
  const setAuth = useAuthStore(s => s.setAuth)
  const token = useAuthStore(s => s.token)
  
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [formData, setFormData] = useState({
    workspace_name: '',
    retention_policy: '90',
    data_region: 'us-east',
  })

  useEffect(() => {
    loadWorkspace()
  }, [])

  const loadWorkspace = async () => {
    try {
      const { data } = await userService.getProfile()
      const ws = data.workspace_settings || {}
      setFormData({
        workspace_name: user?.workspace_name || data.profile_data?.workspace_name || 'My Workspace',
        retention_policy: ws.retention_policy || '90',
        data_region: ws.data_region || 'us-east',
      })
    } catch (error) {
      toast({ title: 'Error', message: 'Failed to load workspace settings', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleSave = async () => {
    if (!formData.workspace_name.trim()) {
      toast({ title: 'Error', message: 'Workspace name is required', type: 'error' })
      return
    }

    setSaving(true)
    try {
      const { data } = await userService.updateWorkspace({
        workspace_settings: {
          ...user?.workspace_settings,
          retention_policy: formData.retention_policy,
          data_region: formData.data_region,
        }
      })
      
      // Also update the profile data to keep workspace name in sync if needed
      await userService.updateProfile({
        profile_data: {
          ...user?.profile_data,
          workspace_name: formData.workspace_name
        }
      })
      
      if (user && token) {
        setAuth({ 
          ...user, 
          ...data,
          workspace_name: formData.workspace_name, 
          profile_data: { ...user.profile_data, workspace_name: formData.workspace_name }
        }, token)
      }
      
      toast({ title: 'Success', message: 'Workspace settings updated successfully', type: 'success' })
    } catch (error) {
      toast({ title: 'Error', message: 'Failed to update workspace settings', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="flex justify-center items-center h-64"><Loader2 className="animate-spin text-primary h-8 w-8" /></div>
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <SectionHeader 
        title="Workspace Configuration" 
        description="Manage your enterprise workspace identity and data policies." 
      />
      
      <div className="grid gap-8">
        <Card className="p-6 space-y-6">
          <div className="flex items-center gap-3 border-b border-border pb-4 mb-4">
            <div className="p-2 bg-primary/10 rounded-lg text-primary">
              <Briefcase className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">General Info</h3>
              <p className="text-sm text-muted-foreground">Basic workspace identity details.</p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <Label htmlFor="workspace_name">Workspace Name</Label>
              <Input 
                id="workspace_name" 
                name="workspace_name" 
                value={formData.workspace_name} 
                onChange={handleChange} 
                placeholder="Acme Corp" 
              />
            </div>
            
            <div className="space-y-2">
              <Label>Tenant ID</Label>
              <Input 
                value={user?.tenant_id || 'Not Assigned'} 
                readOnly 
                className="bg-muted cursor-not-allowed font-mono text-xs" 
              />
              <p className="text-xs text-muted-foreground mt-1">Unique isolation identifier.</p>
            </div>
          </div>
        </Card>
        
        <Card className="p-6 space-y-6">
          <div className="flex items-center gap-3 border-b border-border pb-4 mb-4">
            <div className="p-2 bg-primary/10 rounded-lg text-primary">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Data Management</h3>
              <p className="text-sm text-muted-foreground">Compliance and retention configurations.</p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-3">
              <Label htmlFor="retention_policy">Log Retention Policy</Label>
              <select 
                id="retention_policy" 
                name="retention_policy" 
                value={formData.retention_policy}
                onChange={handleChange}
                className="w-full flex h-10 items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              >
                <option value="30">30 Days</option>
                <option value="90">90 Days</option>
                <option value="180">180 Days</option>
                <option value="365">1 Year</option>
                <option value="indefinite">Indefinite (Requires Enterprise Plan)</option>
              </select>
            </div>
            
            <div className="space-y-3">
              <Label htmlFor="data_region">Primary Data Region</Label>
              <select 
                id="data_region" 
                name="data_region" 
                value={formData.data_region}
                onChange={handleChange}
                className="w-full flex h-10 items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              >
                <option value="us-east">US East (N. Virginia)</option>
                <option value="us-west">US West (Oregon)</option>
                <option value="eu-central">EU Central (Frankfurt)</option>
                <option value="ap-southeast">AP Southeast (Sydney)</option>
              </select>
            </div>
          </div>
        </Card>
        
        <Card className="p-6 space-y-6">
          <div className="flex items-center justify-between border-b border-border pb-4 mb-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-primary/10 rounded-lg text-primary">
                <Users className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground">Workspace Members</h3>
                <p className="text-sm text-muted-foreground">Invite and manage users in this tenant.</p>
              </div>
            </div>
            <Button variant="outline">Manage Team</Button>
          </div>
          
          <div className="bg-surface-elevated rounded-lg p-4 text-center border border-border">
            <p className="text-sm text-muted-foreground">Team management is currently handled through your SSO Provider.</p>
          </div>
        </Card>
      </div>
      
      <div className="flex justify-end pt-4">
        <Button onClick={handleSave} isLoading={saving}>
          Save Workspace Settings
        </Button>
      </div>
    </div>
  )
}
