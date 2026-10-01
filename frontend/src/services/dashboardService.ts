import { get } from '@/api/wrapper'
import type {
  ExecutiveDashboardDTO,
  KnowledgeIntelligenceSummaryDTO,
} from '@/types'

export const dashboardService = {
  getExecutiveDashboard: async (timeWindow: string = '24h'): Promise<ExecutiveDashboardDTO> => {
    return get<ExecutiveDashboardDTO>(`/dashboard/executive?time_window=${encodeURIComponent(timeWindow)}`)
  },

  getKnowledgeIntelligenceSummary: async (): Promise<KnowledgeIntelligenceSummaryDTO> => {
    return get<KnowledgeIntelligenceSummaryDTO>('/dashboard/knowledge-intelligence')
  },
}
