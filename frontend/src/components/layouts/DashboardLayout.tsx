import { Outlet } from 'react-router-dom'
import { Sidebar } from '../navigation/Sidebar'
import { Header } from '../navigation/Header'
import { Footer } from '../navigation/Footer'
import { BackgroundProvider } from '../backgrounds'

export function DashboardLayout() {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-foreground selection:bg-primary/30 selection:text-primary">
      <BackgroundProvider type="grid" />
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden relative z-10">
        <Header />
        <main className="flex-1 overflow-x-hidden overflow-y-auto bg-transparent px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto w-full max-w-7xl">
            <Outlet />
          </div>
        </main>
        <Footer />
      </div>
    </div>
  )
}
