import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { ApiError } from '@/types'

export const appQueryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30, // 30 seconds
      retry: (failureCount: number, error: any) => {
        if (error instanceof ApiError) {
          // Do not retry Auth or Validation errors
          if (error.isAuthError() || error.isValidationError()) {
            return false
          }
        }
        return failureCount < 2
      },
      refetchOnWindowFocus: false,
    },
  },
})

export function QueryProvider({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={appQueryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}
