import { get, post } from '@/api/wrapper';

export interface BrandingSettings {
  workspace_logo_url?: string | null;
  workspace_dark_logo_url?: string | null;
  workspace_logo_version: number;
  workspace_logo_etag?: string | null;
  workspace_favicon_url?: string | null;
  company_name?: string | null;
  product_name?: string | null;
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  success_color: string;
  warning_color: string;
  danger_color: string;
  info_color: string;
  neutral_background?: string | null;
  neutral_surface?: string | null;
  neutral_text?: string | null;
  login_background_url?: string | null;
  dashboard_background_url?: string | null;
  font_family: string;
  border_radius: string;
  theme_mode: 'LIGHT' | 'DARK' | 'SYSTEM';
  custom_css_variables?: Record<string, string>;
}

export interface ResolvedBrandingData {
  workspace_id: string;
  branding: BrandingSettings;
  css_variables: Record<string, string>;
  css_string: string;
  tailwind_tokens: Record<string, any>;
  theme_mode: string;
  version: number;
  settings_hash: string;
  is_preview: boolean;
}

export interface BrandingResponse {
  success: boolean;
  data: ResolvedBrandingData;
}

export interface BrandingDiffResponse {
  success: boolean;
  workspace_id: string;
  from_version: number;
  to_version: number;
  diff: Record<string, { from: any; to: any }>;
}

class BrandingService {
  async getBranding(workspaceId: string, preview: boolean = false): Promise<BrandingResponse> {
    return get<BrandingResponse>(`/api/v1/workspaces/${workspaceId}/branding?preview=${preview}`);
  }

  async stagePreview(workspaceId: string, branding: Partial<BrandingSettings>): Promise<BrandingResponse> {
    return post<BrandingResponse>(`/api/v1/workspaces/${workspaceId}/branding/preview`, {
      branding
    });
  }

  async publishBranding(
    workspaceId: string,
    expectedUpdatedAt: string,
    branding: Partial<BrandingSettings>,
    changeReason: string = 'Updated workspace branding'
  ): Promise<BrandingResponse> {
    return post<BrandingResponse>(`/api/v1/workspaces/${workspaceId}/branding/publish`, {
      expected_updated_at: expectedUpdatedAt,
      branding,
      change_reason: changeReason
    });
  }

  async rollbackBranding(
    workspaceId: string,
    expectedUpdatedAt: string,
    targetVersion: number,
    changeReason: string = 'Rollback workspace branding'
  ): Promise<BrandingResponse> {
    return post<BrandingResponse>(`/api/v1/workspaces/${workspaceId}/branding/rollback`, {
      expected_updated_at: expectedUpdatedAt,
      target_version: targetVersion,
      change_reason: changeReason
    });
  }

  async diffBranding(
    workspaceId: string,
    fromVersion: number,
    toVersion: number
  ): Promise<BrandingDiffResponse> {
    return get<BrandingDiffResponse>(
      `/api/v1/workspaces/${workspaceId}/branding/diff?from_version=${fromVersion}&to_version=${toVersion}`
    );
  }
}

export const brandingService = new BrandingService();
export default brandingService;
