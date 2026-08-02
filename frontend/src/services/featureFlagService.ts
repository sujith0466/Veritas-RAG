import { get, post, patch, put, del } from '@/api/wrapper';

export interface FeatureFlag {
  id: string;
  key: string;
  name: string;
  description?: string | null;
  category: string;
  lifecycle_state: string;
  flag_type: string;
  default_enabled: boolean;
  is_killswitch_active: boolean;
  prerequisite_flag_keys: string[];
  default_variant: Record<string, any>;
  target_environments: string[];
  version: number;
  created_at: string;
  updated_at: string;
}

export interface FeatureFlagEvaluation {
  flag_key: string;
  is_enabled: boolean;
  variant: Record<string, any>;
  reason: string;
  tier_served: string;
  evaluated_at: string;
}

export interface FeatureFlagWorkspaceRule {
  id: string;
  flag_id: string;
  workspace_id: string;
  is_enabled: boolean;
  rollout_percentage: number;
  activation_start_at?: string | null;
  activation_end_at?: string | null;
  targeting_conditions: Array<{ type: string; values: string[] }>;
  custom_variant: Record<string, any>;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface FeatureFlagListResponse {
  success: boolean;
  data: FeatureFlag[];
}

export interface FeatureFlagResponse {
  success: boolean;
  data: FeatureFlag;
}

export interface FeatureFlagBulkEvaluationResponse {
  success: boolean;
  workspace_id: string;
  flags: Record<string, FeatureFlagEvaluation>;
}

export interface FeatureFlagEvaluationResponse {
  success: boolean;
  data: FeatureFlagEvaluation;
}

export interface FeatureFlagWorkspaceRuleResponse {
  success: boolean;
  data: FeatureFlagWorkspaceRule;
}

class FeatureFlagService {
  async listFlags(category?: string): Promise<FeatureFlagListResponse> {
    const url = category ? `/api/v1/feature-flags?category=${category}` : '/api/v1/feature-flags';
    return get<FeatureFlagListResponse>(url);
  }

  async getFlag(flagKey: string): Promise<FeatureFlagResponse> {
    return get<FeatureFlagResponse>(`/api/v1/feature-flags/${flagKey}`);
  }

  async createFlag(data: {
    key: string;
    name: string;
    description?: string;
    category?: string;
    lifecycle_state?: string;
    flag_type?: string;
    default_enabled?: boolean;
    prerequisite_flag_keys?: string[];
    default_variant?: Record<string, any>;
  }): Promise<FeatureFlagResponse> {
    return post<FeatureFlagResponse>('/api/v1/feature-flags', data);
  }

  async updateFlag(flagKey: string, data: Partial<FeatureFlag>): Promise<FeatureFlagResponse> {
    return patch<FeatureFlagResponse>(`/api/v1/feature-flags/${flagKey}`, data);
  }

  async toggleKillswitch(flagKey: string, isActive: boolean, reason: string): Promise<FeatureFlagResponse> {
    return post<FeatureFlagResponse>(`/api/v1/feature-flags/${flagKey}/killswitch`, {
      is_active: isActive,
      reason
    });
  }

  async evaluateWorkspaceFlags(workspaceId: string): Promise<FeatureFlagBulkEvaluationResponse> {
    return get<FeatureFlagBulkEvaluationResponse>(`/api/v1/workspaces/${workspaceId}/feature-flags`);
  }

  async evaluateFlag(workspaceId: string, flagKey: string): Promise<FeatureFlagEvaluationResponse> {
    return get<FeatureFlagEvaluationResponse>(`/api/v1/workspaces/${workspaceId}/feature-flags/${flagKey}/evaluate`);
  }

  async setWorkspaceRule(
    workspaceId: string,
    flagKey: string,
    rule: Partial<FeatureFlagWorkspaceRule>
  ): Promise<FeatureFlagWorkspaceRuleResponse> {
    return put<FeatureFlagWorkspaceRuleResponse>(
      `/api/v1/workspaces/${workspaceId}/feature-flags/${flagKey}`,
      rule
    );
  }

  async deleteWorkspaceRule(workspaceId: string, flagKey: string): Promise<void> {
    return del<void>(`/api/v1/workspaces/${workspaceId}/feature-flags/${flagKey}`);
  }
}

export const featureFlagService = new FeatureFlagService();
export default featureFlagService;
