import { RouterProvider } from 'react-router-dom'
import { router } from './routes'
import { AppBootstrap } from '@/components/bootstrap/AppBootstrap'

export function App() {
  return (
    <>
      <AppBootstrap />
      <RouterProvider router={router} />
    </>
  )
}
