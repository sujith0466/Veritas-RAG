import { get } from '@/api/wrapper'
import type {
  ExecutiveDashboardDTO,
  KnowledgeIntelligenceSummaryDTO,
} from '@/types'

export const dashboardService = {
  getExecutiveDashboard: async (): Promise<ExecutiveDashboardDTO> => {
    return get<ExecutiveDashboardDTO>('/dashboard/executive')
  },

  getKnowledgeIntelligenceSummary: async (): Promise<KnowledgeIntelligenceSummaryDTO> => {
    return get<KnowledgeIntelligenceSummaryDTO>('/dashboard/knowledge-intelligence')
  },
}
