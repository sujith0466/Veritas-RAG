/**
 * AIAssistant — Replaced with official Veritas RAG AuthBranding.
 * Maintained as a compatibility adapter for any existing imports.
 */
import { AuthBranding, type AuthBrandingProps, type AIAssistantState } from './AuthBranding'

export type { AIAssistantState }
export type AIAssistantProps = AuthBrandingProps

export function AIAssistant(props: AIAssistantProps) {
  return <AuthBranding {...props} />
}
