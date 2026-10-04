import { Button } from '../common'

interface GoogleAuthButtonProps {
  label?: string
  intentId?: string
  workspaceId?: string
  joinCode?: string
  invitationToken?: string
}

export function GoogleAuthButton({
  label = 'Google',
  intentId,
  workspaceId,
  joinCode,
  invitationToken,
}: GoogleAuthButtonProps) {
  const handleClick = async () => {
    let effectiveIntentId = intentId

    if (!effectiveIntentId) {
      let targetWorkspaceId = workspaceId
      let targetJoinCode = joinCode
      let targetInvitationToken = invitationToken

      if (!targetWorkspaceId && !targetInvitationToken) {
        try {
          const storedIntent = sessionStorage.getItem('join_intent')
          if (storedIntent) {
            const parsed = JSON.parse(storedIntent)
            if (parsed.intent_id) effectiveIntentId = parsed.intent_id
            if (parsed.workspace_id) targetWorkspaceId = parsed.workspace_id
            if (parsed.join_code) targetJoinCode = parsed.join_code
            if (parsed.invitation_token) targetInvitationToken = parsed.invitation_token
          }
        } catch {
          // Ignore sessionStorage parse failure
        }
      }

      // If credentials exist but no intent_id, create intent server-side first
      if (!effectiveIntentId && (targetWorkspaceId || targetJoinCode || targetInvitationToken)) {
        try {
          const res = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? ''}/api/v1/auth/join-intent`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              workspace_id: targetWorkspaceId || undefined,
              join_code: targetJoinCode || undefined,
              invitation_token: targetInvitationToken || undefined,
            }),
          })
          if (res.ok) {
            const data = await res.json()
            if (data?.data?.intent_id) {
              effectiveIntentId = data.data.intent_id
            }
          }
        } catch {
          // Fall back to clean login without intent if creation fails
        }
      }
    }

    const query = effectiveIntentId ? `?intent_id=${encodeURIComponent(effectiveIntentId)}` : ''
    window.location.href = `${import.meta.env.VITE_API_BASE_URL ?? ''}/api/v1/auth/sso/login/google${query}`
  }

  return (
    <>
      <div className="relative my-4">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-border/60" />
        </div>
        <div className="relative flex justify-center text-xs uppercase tracking-wider font-semibold">
          <span className="bg-surface px-3 text-muted-foreground">Or continue with</span>
        </div>
      </div>

      <Button
        type="button"
        variant="outline"
        className="w-full h-11 bg-surface hover:bg-surface-elevated border-border/60 shadow-sm transition-all"
        onClick={handleClick}
      >
        <svg className="mr-3 h-4 w-4" aria-hidden="true" focusable="false" data-prefix="fab" data-icon="google" role="img" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 488 512">
          <path fill="currentColor" d="M488 261.8C488 403.3 391.1 504 248 504 110.8 504 0 393.2 0 256S110.8 8 248 8c66.8 0 123 24.5 166.3 64.9l-67.5 64.9C258.5 52.6 94.3 116.6 94.3 256c0 86.5 69.1 156.6 153.7 156.6 98.2 0 135-70.4 140.8-106.9H248v-85.3h236.1c2.3 12.7 3.9 24.9 3.9 41.4z"></path>
        </svg>
        {label}
      </Button>
    </>
  )
}
