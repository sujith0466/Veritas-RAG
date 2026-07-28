import { useState, useEffect } from 'react'
import { Card, Input, Label, Button, SectionHeader } from '@/components/common'
import { useAuthStore } from '@/stores/authStore'
import { userService } from '@/services/userService'
import { useToast } from '@/hooks/useToast'
import { getAssetUrl } from '@/api/client'
import { User, Mail, Building, MapPin, Globe, Loader2, Camera } from 'lucide-react'

export function ProfileSettings() {
  const user = useAuthStore(s => s.user)
  const setAuth = useAuthStore(s => s.setAuth)
  const token = useAuthStore(s => s.token)
  const { toast } = useToast()
  
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  
  const [formData, setFormData] = useState({
    username: '',
    bio: '',
    phone: '',
    organization: '',
    department: '',
    designation: '',
    website: '',
    timezone: '',
    location: '',
  })
  
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null)

  useEffect(() => {
    loadProfile()
  }, [])

  const loadProfile = async () => {
    try {
      const { data } = await userService.getProfile()
      setFormData({
        username: data.username || '',
        bio: data.profile_data?.bio || '',
        phone: data.profile_data?.phone || '',
        organization: data.profile_data?.organization || '',
        department: data.profile_data?.department || '',
        designation: data.profile_data?.designation || '',
        website: data.profile_data?.website || '',
        timezone: data.profile_data?.timezone || '',
        location: data.profile_data?.location || '',
      })
      setAvatarPreview(getAssetUrl(data.avatar_url) || null)
    } catch (error) {
      toast({ title: 'Error', message: 'Failed to load profile data', type: 'error' })
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData(prev => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const { username, ...profile_data } = formData
      const { data } = await userService.updateProfile({ username, profile_data })
      
      // Update global store user context if needed
      if (user && token) {
        setAuth({ ...user, ...data }, token)
      }
      toast({ title: 'Success', message: 'Profile updated successfully', type: 'success' })
    } catch (error) {
      toast({ title: 'Error', message: 'Failed to update profile', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    // Quick preview
    const objectUrl = URL.createObjectURL(file)
    setAvatarPreview(objectUrl)
    
    setUploading(true)
    try {
      const { data } = await userService.uploadAvatar(file)
      setAvatarPreview(getAssetUrl(data.avatar_url) || null)
      
      if (user && token) {
        setAuth({ ...user, ...data }, token)
      }
      toast({ title: 'Success', message: 'Avatar updated successfully', type: 'success' })
    } catch (error) {
      toast({ title: 'Error', message: 'Failed to upload avatar', type: 'error' })
      setAvatarPreview(getAssetUrl(user?.avatar_url) || null)
    } finally {
      setUploading(false)
    }
  }

  if (loading) {
    return <div className="flex justify-center items-center h-64"><Loader2 className="animate-spin text-primary h-8 w-8" /></div>
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <SectionHeader 
        title="Public Profile" 
        description="This information will be displayed publicly so be careful what you share."
      />
      
      <div className="flex gap-8 items-start">
        <div className="flex-1 space-y-6">
          <Card className="p-6 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <div className="relative">
                  <User className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input id="username" name="username" className="pl-10" value={formData.username} onChange={handleChange} placeholder="johndoe" />
                </div>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input id="email" className="pl-10 bg-muted cursor-not-allowed" value={user?.email || ''} readOnly />
                </div>
                <p className="text-xs text-muted-foreground">Email cannot be changed here.</p>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="organization">Organization</Label>
                <div className="relative">
                  <Building className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input id="organization" name="organization" className="pl-10" value={formData.organization} onChange={handleChange} placeholder="Acme Corp" />
                </div>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="designation">Role / Designation</Label>
                <Input id="designation" name="designation" value={formData.designation} onChange={handleChange} placeholder="Software Engineer" />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="location">Location</Label>
                <div className="relative">
                  <MapPin className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input id="location" name="location" className="pl-10" value={formData.location} onChange={handleChange} placeholder="San Francisco, CA" />
                </div>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="website">Website</Label>
                <div className="relative">
                  <Globe className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input id="website" name="website" className="pl-10" value={formData.website} onChange={handleChange} placeholder="https://example.com" />
                </div>
              </div>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="bio">Bio</Label>
              <textarea 
                id="bio" 
                name="bio"
                rows={4}
                className="w-full flex min-h-[80px] rounded-md border border-input bg-transparent px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50" 
                value={formData.bio} 
                onChange={handleChange} 
                placeholder="A brief description about yourself"
              />
            </div>
          </Card>
          
          <div className="flex justify-end gap-4">
            <Button variant="outline" onClick={loadProfile} disabled={saving}>Cancel</Button>
            <Button onClick={handleSave} isLoading={saving}>Save Changes</Button>
          </div>
        </div>
        
        {/* Avatar Sidebar */}
        <Card className="p-6 w-64 flex flex-col items-center text-center space-y-4">
          <h3 className="font-medium text-sm w-full text-left">Profile Picture</h3>
          <div className="relative w-32 h-32 rounded-full border-4 border-muted overflow-hidden group">
            {avatarPreview ? (
              <img src={avatarPreview} alt="Avatar" className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full bg-muted flex items-center justify-center">
                <User className="h-12 w-12 text-muted-foreground/50" />
              </div>
            )}
            
            <label className="absolute inset-0 bg-black/60 flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer">
              {uploading ? (
                <Loader2 className="h-6 w-6 text-white animate-spin" />
              ) : (
                <>
                  <Camera className="h-6 w-6 text-white mb-2" />
                  <span className="text-white text-xs font-medium">Upload</span>
                </>
              )}
              <input type="file" className="hidden" accept="image/*" onChange={handleAvatarUpload} disabled={uploading} />
            </label>
          </div>
          <p className="text-xs text-muted-foreground">
            JPG, GIF or PNG. Max size of 5MB.
          </p>
        </Card>
      </div>
    </div>
  )
}
