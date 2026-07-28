import { apiClient } from '@/api/client'

export interface UserProfileUpdate {
  username?: string
  profile_data?: Record<string, any>
}

export interface UserPreferencesUpdate {
  preferences: Record<string, any>
}

export interface UserWorkspaceUpdate {
  workspace_settings: Record<string, any>
}

export const userService = {
  getProfile: () => apiClient.get('/users/me'),
  
  updateProfile: (data: UserProfileUpdate) => 
    apiClient.patch('/users/me/profile', data),
    
  updatePreferences: (data: UserPreferencesUpdate) => 
    apiClient.patch('/users/me/preferences', data),
    
  updateWorkspace: (data: UserWorkspaceUpdate) => 
    apiClient.patch('/users/me/workspace', data),
    
  uploadAvatar: async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post('/users/me/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}
