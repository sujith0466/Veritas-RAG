import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from '../navigation/Sidebar'
import { Header } from '../navigation/Header'
import { Footer } from '../navigation/Footer'
import { BackgroundProvider } from '../backgrounds'
import { WorkspaceThemeProvider } from '@/providers/WorkspaceThemeProvider'

export function DashboardLayout() {
  const location = useLocation()
  const [isIndexing, setIsIndexing] = useState(false)
  const [docStats, setDocStats] = useState({ total: 0, processed: 0 })
  
  useEffect(() => {
    if (location.pathname && !location.pathname.startsWith('/auth')) {
      localStorage.setItem('raguard-last-page', location.pathname + location.search)
    }
  }, [location])

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const { documentService } = await import('@/services/documentService')
        const docs = await documentService.listDocuments(1, 100)
        const processing = docs.items.some(d => d.status === 'processing' || d.status === 'pending')
        const processedCount = docs.items.filter(d => d.status === 'processed').length
        setIsIndexing(processing)
        setDocStats({ total: docs.items.length, processed: processedCount })
      } catch (e) {
        // ignore
      }
    }
    checkStatus()
    const interval = setInterval(checkStatus, 3000)
    return () => clearInterval(interval)
  }, [])

  return (
    <WorkspaceThemeProvider>
      <div className="flex h-screen w-full overflow-hidden bg-background text-foreground selection:bg-primary/30 selection:text-primary">
        <BackgroundProvider type="grid" />
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden relative z-10">
          <Header />
          {isIndexing && (
            <div className="bg-primary/10 border-b border-primary/20 px-4 py-2 flex items-center justify-between text-sm">
              <div className="flex items-center gap-2 text-primary">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                </span>
                <span className="font-medium">Enterprise Knowledge Base</span>
                <span className="text-muted-foreground ml-2">Status: Preparing...</span>
              </div>
              <div className="text-muted-foreground">
                {docStats.processed} / {docStats.total} documents indexed
              </div>
            </div>
          )}
          <main className="flex-1 overflow-x-hidden overflow-y-auto bg-transparent px-4 py-6 sm:px-6 lg:px-8">
            <div className="mx-auto w-full max-w-7xl">
              <Outlet />
            </div>
          </main>
          <Footer />
        </div>
      </div>
    </WorkspaceThemeProvider>
  )
}
