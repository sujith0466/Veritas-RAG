import { get } from '@/api/wrapper'

export interface HealthStatus {
  status: 'ok' | 'error'
  version: string
  environment: string
  timestamp: string
}

export const healthService = {
  async getBasicHealth(): Promise<HealthStatus> {
    return await get<HealthStatus>('/health')
  },
}
