import React, { createContext, useContext, useEffect, useState } from 'react';
import { featureFlagService, type FeatureFlagEvaluation } from '@/services/featureFlagService';

interface FeatureFlagContextType {
  flags: Record<string, FeatureFlagEvaluation>;
  isLoading: boolean;
  evaluate: (flagKey: string, fallback?: boolean) => boolean;
  getVariant: (flagKey: string) => Record<string, any>;
  refreshFlags: () => Promise<void>;
}

const FeatureFlagContext = createContext<FeatureFlagContextType | undefined>(undefined);

export function FeatureFlagProvider({
  workspaceId,
  children,
}: {
  workspaceId?: string;
  children: React.ReactNode;
}) {
  const [flags, setFlags] = useState<Record<string, FeatureFlagEvaluation>>({});
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const fetchFlags = async () => {
    if (!workspaceId) return;
    setIsLoading(true);
    try {
      const res = await featureFlagService.evaluateWorkspaceFlags(workspaceId);
      if (res.success && res.flags) {
        setFlags(res.flags);
      }
    } catch (err) {
      console.error('Failed to evaluate feature flags', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (workspaceId) {
      fetchFlags();
    }
  }, [workspaceId]);

  const evaluate = (flagKey: string, fallback: boolean = false): boolean => {
    const flag = flags[flagKey];
    if (!flag) return fallback;
    return flag.is_enabled;
  };

  const getVariant = (flagKey: string): Record<string, any> => {
    return flags[flagKey]?.variant || {};
  };

  return (
    <FeatureFlagContext.Provider
      value={{
        flags,
        isLoading,
        evaluate,
        getVariant,
        refreshFlags: fetchFlags,
      }}
    >
      {children}
    </FeatureFlagContext.Provider>
  );
}

export function useFeatureFlags(): FeatureFlagContextType {
  const context = useContext(FeatureFlagContext);
  if (!context) {
    throw new Error('useFeatureFlags must be used within a FeatureFlagProvider');
  }
  return context;
}

export function useFeatureFlag(flagKey: string, fallback: boolean = false): boolean {
  const context = useContext(FeatureFlagContext);
  if (!context) return fallback;
  return context.evaluate(flagKey, fallback);
}

export function FeatureFlagGuard({
  flagKey,
  fallback = null,
  children,
}: {
  flagKey: string;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}) {
  const isEnabled = useFeatureFlag(flagKey, false);
  if (!isEnabled) {
    return <>{fallback}</>;
  }
  return <>{children}</>;
}
