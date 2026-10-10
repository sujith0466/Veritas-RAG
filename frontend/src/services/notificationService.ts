import { apiClient } from '@/api/client'

export interface NotificationItem {
  id: string
  tenant_id: string
  user_id: string | null
  category: 'SYSTEM' | 'SECURITY' | 'DOCUMENT' | 'WORKSPACE'
  severity: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'
  title: string
  message: string
  action_url: string | null
  payload_json: Record<string, any> | null
  is_read: boolean
  read_at: string | null
  created_at: string
}

export interface NotificationListResponse {
  items: NotificationItem[]
  total: number
  page: number
  page_size: number
  unread_count: number
}

export interface UnreadCountResponse {
  unread_count: number
}

export interface NotificationActionResponse {
  success: boolean
  affected_count: number
  message: string
}

export const notificationService = {
  listNotifications: (params?: { category?: string; unread_only?: boolean; page?: number; page_size?: number }) =>
    apiClient.get<NotificationListResponse>('/notifications', { params }),

  getUnreadCount: () =>
    apiClient.get<UnreadCountResponse>('/notifications/unread-count'),

  markAsRead: (id: string) =>
    apiClient.patch<NotificationItem>(`/notifications/${id}/read`),

  markAllAsRead: () =>
    apiClient.post<NotificationActionResponse>('/notifications/read-all'),

  dismissNotification: (id: string) =>
    apiClient.delete<NotificationActionResponse>(`/notifications/${id}`),
}
