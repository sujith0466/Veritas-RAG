import React, { createContext, useContext, useEffect, useState } from 'react';
import { brandingService, type BrandingSettings, type ResolvedBrandingData } from '@/services/brandingService';

interface BrandingContextType {
  branding: BrandingSettings | null;
  cssVariables: Record<string, string>;
  isLoading: boolean;
  isPreview: boolean;
  refreshBranding: () => Promise<void>;
  previewDraft: (draft: Partial<BrandingSettings>) => Promise<void>;
}

const BrandingContext = createContext<BrandingContextType | undefined>(undefined);

export function BrandingProvider({
  workspaceId,
  children,
}: {
  workspaceId?: string;
  children: React.ReactNode;
}) {
  const [brandingData, setBrandingData] = useState<ResolvedBrandingData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isPreview, setIsPreview] = useState<boolean>(false);

  const applyCssVariables = (vars: Record<string, string>) => {
    const root = document.documentElement;
    Object.entries(vars).forEach(([key, value]) => {
      root.style.setProperty(key, value);
    });
  };

  const fetchBranding = async (preview: boolean = false) => {
    if (!workspaceId) return;
    setIsLoading(true);
    try {
      const response = await brandingService.getBranding(workspaceId, preview);
      if (response.success && response.data) {
        setBrandingData(response.data);
        setIsPreview(response.data.is_preview);
        applyCssVariables(response.data.css_variables);
      }
    } catch (err) {
      console.error('Failed to load workspace branding', err);
    } finally {
      setIsLoading(false);
    }
  };

  const previewDraft = async (draft: Partial<BrandingSettings>) => {
    if (!workspaceId) return;
    try {
      const res = await brandingService.stagePreview(workspaceId, draft);
      if (res.success && res.data) {
        setBrandingData(res.data);
        setIsPreview(true);
        applyCssVariables(res.data.css_variables);
      }
    } catch (err) {
      console.error('Failed to stage branding preview', err);
    }
  };

  useEffect(() => {
    if (workspaceId) {
      fetchBranding(false);
    }
  }, [workspaceId]);

  return (
    <BrandingContext.Provider
      value={{
        branding: brandingData?.branding || null,
        cssVariables: brandingData?.css_variables || {},
        isLoading,
        isPreview,
        refreshBranding: () => fetchBranding(false),
        previewDraft,
      }}
    >
      {children}
    </BrandingContext.Provider>
  );
}

export function useBranding(): BrandingContextType {
  const context = useContext(BrandingContext);
  if (!context) {
    throw new Error('useBranding must be used within a BrandingProvider');
  }
  return context;
}
