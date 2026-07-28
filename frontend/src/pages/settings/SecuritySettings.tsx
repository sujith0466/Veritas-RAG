import { useState } from 'react'
import { Card, Input, Label, Button, SectionHeader } from '@/components/common'
import { useToast } from '@/hooks/useToast'
import { supabaseClient } from '@/services/auth/supabaseClient'
import { Lock, ShieldCheck } from 'lucide-react'

export function SecuritySettings() {
  const { toast } = useToast()
  
  const [saving, setSaving] = useState(false)
  const [formData, setFormData] = useState({
    newPassword: '',
    confirmPassword: '',
  })

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleUpdatePassword = async () => {
    if (!formData.newPassword || !formData.confirmPassword) {
      toast({ title: 'Error', message: 'Please fill out all fields', type: 'error' })
      return
    }
    
    if (formData.newPassword !== formData.confirmPassword) {
      toast({ title: 'Error', message: 'Passwords do not match', type: 'error' })
      return
    }
    
    if (formData.newPassword.length < 8) {
      toast({ title: 'Error', message: 'Password must be at least 8 characters long', type: 'error' })
      return
    }

    setSaving(true)
    try {
      const { error } = await supabaseClient.auth.updateUser({ password: formData.newPassword })
      if (error) throw error
      
      toast({ title: 'Success', message: 'Password updated successfully', type: 'success' })
      setFormData({ newPassword: '', confirmPassword: '' })
    } catch (error: any) {
      toast({ title: 'Error', message: error.message || 'Failed to update password', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <SectionHeader 
        title="Security Settings" 
        description="Manage your account password and security preferences." 
      />
      
      <div className="grid gap-8">
        <Card className="p-6 space-y-6">
          <div className="flex items-center gap-3 border-b border-border pb-4 mb-4">
            <div className="p-2 bg-primary/10 rounded-lg text-primary">
              <Lock className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Change Password</h3>
              <p className="text-sm text-muted-foreground">Update the password associated with your account.</p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-2xl">
            <div className="space-y-2">
              <Label htmlFor="newPassword">New Password</Label>
              <Input 
                id="newPassword" 
                name="newPassword" 
                type="password" 
                value={formData.newPassword} 
                onChange={handleChange} 
                placeholder="••••••••" 
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm New Password</Label>
              <Input 
                id="confirmPassword" 
                name="confirmPassword" 
                type="password" 
                value={formData.confirmPassword} 
                onChange={handleChange} 
                placeholder="••••••••" 
              />
            </div>
          </div>
          
          <div className="flex justify-end pt-4">
            <Button onClick={handleUpdatePassword} isLoading={saving} disabled={saving || !formData.newPassword}>
              Update Password
            </Button>
          </div>
        </Card>
        
        <Card className="p-6 space-y-6">
          <div className="flex items-center gap-3 border-b border-border pb-4 mb-4">
            <div className="p-2 bg-success-subtle text-success rounded-lg">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Two-Factor Authentication</h3>
              <p className="text-sm text-muted-foreground">Add an extra layer of security to your account.</p>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Two-factor authentication is enforced at the enterprise level by your identity provider (SSO).
            </p>
            <Button variant="outline" disabled>Managed by Admin</Button>
          </div>
        </Card>
      </div>
    </div>
  )
}
