import { useState } from 'react'
import { Card, Button, SectionHeader } from '@/components/common'
import { useToast } from '@/hooks/useToast'
import { useAuthStore } from '@/stores/authStore'
import { Lock, Download, AlertTriangle } from 'lucide-react'
import * as Dialog from '@radix-ui/react-dialog'

export function PrivacySettings() {
  const { toast } = useToast()
  const user = useAuthStore(s => s.user)

  const [exporting, setExporting] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)

  const handleExportData = async () => {
    setExporting(true)
    try {
      // Simulate data compilation delay
      await new Promise(resolve => setTimeout(resolve, 1500))

      const dataStr = JSON.stringify(user, null, 2)
      const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr)

      const exportFileDefaultName = `veritas-rag-data-export-${new Date().toISOString().slice(0, 10)}.json`

      const linkElement = document.createElement('a')
      linkElement.setAttribute('href', dataUri)
      linkElement.setAttribute('download', exportFileDefaultName)
      linkElement.click()

      toast({ title: 'Export Complete', message: 'Your data has been successfully downloaded.', type: 'success' })
    } catch (error) {
      toast({ title: 'Error', message: 'Failed to export data', type: 'error' })
    } finally {
      setExporting(false)
    }
  }

  const handleDeleteAccount = async () => {
    setDeleting(true)
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000))

      // In a real enterprise app, this might just flag the account for deletion or require admin approval
      toast({
        title: 'Action Restricted',
        message: 'Account deletion is restricted for enterprise tenants. Please contact your workspace administrator.',
        type: 'warning'
      })
      setDeleteDialogOpen(false)
    } catch (error) {
      toast({ title: 'Error', message: 'Failed to process deletion request', type: 'error' })
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <SectionHeader
        title="Privacy & Data"
        description="Manage your personal data, exports, and account lifecycle."
      />

      <div className="grid gap-8">
        <Card className="p-6 space-y-6">
          <div className="flex items-center gap-3 border-b border-border pb-4 mb-4">
            <div className="p-2 bg-primary/10 rounded-lg text-primary">
              <Download className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Export Data</h3>
              <p className="text-sm text-muted-foreground">Download a copy of your personal profile data and preferences.</p>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground max-w-md">
              Your export will be generated as a JSON file containing all information associated with your specific user account. Workspace-level documents and vectors are not included.
            </p>
            <Button onClick={handleExportData} isLoading={exporting} variant="secondary">
              Request Export
            </Button>
          </div>
        </Card>

        <Card className="p-6 space-y-6 border-danger/20 bg-danger/5">
          <div className="flex items-center gap-3 border-b border-danger/20 pb-4 mb-4">
            <div className="p-2 bg-danger/10 rounded-lg text-danger">
              <Lock className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-danger">Danger Zone</h3>
              <p className="text-sm text-danger/80">Irreversible account actions.</p>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-1 max-w-md">
              <h4 className="text-sm font-medium text-foreground">Delete Account</h4>
              <p className="text-xs text-muted-foreground">
                Permanently remove your personal account and remove your access from all workspaces.
              </p>
            </div>

            <Dialog.Root open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
              <Dialog.Trigger asChild>
                <Button variant="destructive">Delete Account</Button>
              </Dialog.Trigger>
              <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
                <Dialog.Content className="fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border border-border bg-surface-elevated p-6 shadow-xl duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-xl">
                  <div className="flex flex-col items-center justify-center space-y-4 text-center">
                    <div className="h-12 w-12 rounded-full bg-danger/10 flex items-center justify-center">
                      <AlertTriangle className="h-6 w-6 text-danger" />
                    </div>
                    <div className="space-y-2">
                      <Dialog.Title className="text-lg font-semibold text-foreground">
                        Are you absolutely sure?
                      </Dialog.Title>
                      <Dialog.Description className="text-sm text-muted-foreground">
                        This action cannot be undone. This will permanently delete your account
                        and remove your data from our servers.
                      </Dialog.Description>
                    </div>
                  </div>
                  <div className="flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2 mt-6">
                    <Button variant="outline" onClick={() => setDeleteDialogOpen(false)} disabled={deleting}>
                      Cancel
                    </Button>
                    <Button variant="destructive" onClick={handleDeleteAccount} isLoading={deleting}>
                      Yes, delete account
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
