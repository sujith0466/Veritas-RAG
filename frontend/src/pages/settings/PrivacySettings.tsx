import { useState } from 'react'
import { Card, Button, Input, Label, SectionHeader } from '@/components/common'
import { useToast } from '@/hooks/useToast'
import { useAuthStore } from '@/stores/authStore'
import { Lock, Download, ShieldAlert, KeyRound, CheckCircle2 } from 'lucide-react'
import * as Dialog from '@radix-ui/react-dialog'

export function PrivacySettings() {
  const { toast } = useToast()
  const token = useAuthStore(s => s.token)
  const clearAuth = useAuthStore(s => s.clearAuth)

  const [exporting, setExporting] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)

  // Re-auth form states
  const [password, setPassword] = useState('')
  const [confirmationInput, setConfirmationInput] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const handleExportData = async () => {
    setExporting(true)
    try {
      const res = await fetch('/api/v1/users/me/export', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      })

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to generate user data archive')
      }

      const exportData = await res.json()
      const dataStr = JSON.stringify(exportData, null, 2)
      const dataBlob = new Blob([dataStr], { type: 'application/json;charset=utf-8' })
      const downloadUrl = URL.createObjectURL(dataBlob)

      const exportFileName = `veritas-rag-data-archive-${new Date().toISOString().slice(0, 10)}.json`
      const linkElement = document.createElement('a')
      linkElement.href = downloadUrl
      linkElement.download = exportFileName
      document.body.appendChild(linkElement)
      linkElement.click()
      document.body.removeChild(linkElement)
      URL.revokeObjectURL(downloadUrl)

      toast({
        title: 'Export Complete',
        message: 'Your personal data archive was compiled and securely downloaded.',
        type: 'success',
      })
    } catch (error: any) {
      toast({
        title: 'Export Failed',
        message: error.message || 'Failed to export data from server',
        type: 'error',
      })
    } finally {
      setExporting(false)
    }
  }

  const handleDeleteAccount = async () => {
    if (confirmationInput.trim().toUpperCase() !== 'DELETE') {
      setErrorMessage("Please type 'DELETE' exactly into the confirmation field.")
      return
    }

    setDeleting(true)
    setErrorMessage(null)

    try {
      const res = await fetch('/api/v1/users/me/deactivate', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          password: password || null,
          confirmation_text: confirmationInput.trim().toUpperCase(),
        }),
      })

      const data = await res.json().catch(() => ({}))

      if (!res.ok) {
        throw new Error(data.detail || 'Failed to deactivate account')
      }

      toast({
        title: 'Account Deactivated',
        message: 'Your account has been deactivated. Logging out...',
        type: 'success',
      })

      setDeleteDialogOpen(false)

      // Purge client authentication state and redirect to login
      setTimeout(() => {
        clearAuth()
        window.location.href = '/login?reason=account_deactivated'
      }, 1000)
    } catch (error: any) {
      setErrorMessage(error.message)
      toast({
        title: 'Deactivation Blocked',
        message: error.message,
        type: 'error',
      })
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <SectionHeader
        title="Privacy & Data Governance"
        description="Manage personal data exports, identity retention, and authenticated account lifecycle."
      />

      <div className="grid gap-8">
        {/* Authentic Data Export */}
        <Card className="p-6 space-y-6">
          <div className="flex items-center gap-3 border-b border-border pb-4 mb-4">
            <div className="p-2 bg-primary/10 rounded-lg text-primary">
              <Download className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Export Account Archive</h3>
              <p className="text-sm text-muted-foreground">Download a machine-readable JSON archive of your personal profile, preferences, and workspace records.</p>
            </div>
          </div>

          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-2 text-xs text-muted-foreground max-w-lg">
              <p>
                Your export contains personal profile settings, notification history, and workspace roles.
              </p>
              <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                <span>Strictly scrubs passwords, salts, tokens, and external tenant documents.</span>
              </div>
            </div>
            <Button onClick={handleExportData} isLoading={exporting} variant="secondary">
              {exporting ? 'Compiling Archive...' : 'Download Data Archive'}
            </Button>
          </div>
        </Card>

        {/* Danger Zone: Authenticated Account Deactivation */}
        <Card className="p-6 space-y-6 border-red-500/20 bg-red-500/[0.02]">
          <div className="flex items-center gap-3 border-b border-red-500/20 pb-4 mb-4">
            <div className="p-2 bg-red-500/10 rounded-lg text-red-500">
              <Lock className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-red-500">Danger Zone: Account Deactivation</h3>
              <p className="text-sm text-red-400/80">Irreversible personal account deactivation and session revocation.</p>
            </div>
          </div>

          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1 max-w-md">
              <h4 className="text-sm font-medium text-foreground">Deactivate Personal Account</h4>
              <p className="text-xs text-muted-foreground">
                Revokes active JWT sessions, disables login credentials, and removes access across all workspaces. Sole owners of active workspaces must transfer ownership before proceeding.
              </p>
            </div>

            <Dialog.Root open={deleteDialogOpen} onOpenChange={(open) => {
              setDeleteDialogOpen(open)
              if (!open) {
                setPassword('')
                setConfirmationInput('')
                setErrorMessage(null)
              }
            }}>
              <Dialog.Trigger asChild>
                <Button variant="destructive">Deactivate Account</Button>
              </Dialog.Trigger>
              <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
                <Dialog.Content className="fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border border-border bg-[#111827] p-6 shadow-2xl duration-200 sm:rounded-xl">
                  <div className="flex flex-col items-center justify-center space-y-3 text-center">
                    <div className="h-12 w-12 rounded-full bg-red-500/10 flex items-center justify-center text-red-500">
                      <ShieldAlert className="h-6 w-6" />
                    </div>
                    <div className="space-y-1">
                      <Dialog.Title className="text-lg font-semibold text-foreground">
                        Confirm Account Deactivation
                      </Dialog.Title>
                      <Dialog.Description className="text-xs text-muted-foreground max-w-sm">
                        This action soft-deletes your account and immediately invalidates all active sessions. You will be signed out permanently.
                      </Dialog.Description>
                    </div>
                  </div>

                  {errorMessage && (
                    <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-xs text-red-400">
                      {errorMessage}
                    </div>
                  )}

                  <div className="space-y-4 my-2">
                    <div className="space-y-1.5 text-left">
                      <Label htmlFor="deactivate-password" className="text-xs flex items-center gap-1.5">
                        <KeyRound className="w-3.5 h-3.5 text-muted-foreground" />
                        Enter Current Password
                      </Label>
                      <Input
                        id="deactivate-password"
                        type="password"
                        placeholder="••••••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="text-xs"
                      />
                    </div>

                    <div className="space-y-1.5 text-left">
                      <Label htmlFor="confirmation-delete" className="text-xs">
                        Type <span className="font-bold text-red-400">DELETE</span> to confirm
                      </Label>
                      <Input
                        id="confirmation-delete"
                        placeholder="DELETE"
                        value={confirmationInput}
                        onChange={(e) => setConfirmationInput(e.target.value)}
                        className="text-xs font-mono"
                      />
                    </div>
                  </div>

                  <div className="flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2 mt-4">
                    <Button
                      variant="outline"
                      onClick={() => setDeleteDialogOpen(false)}
                      disabled={deleting}
                      className="text-xs"
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={handleDeleteAccount}
                      isLoading={deleting}
                      disabled={deleting || confirmationInput.trim().toUpperCase() !== 'DELETE'}
                      className="text-xs"
                    >
                      Confirm Deactivation
                    </Button>
                  </div>
                </Dialog.Content>
              </Dialog.Portal>
            </Dialog.Root>
          </div>
        </Card>
      </div>
    </div>
  )
}
