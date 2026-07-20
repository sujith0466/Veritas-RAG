import { create } from 'zustand'

interface AppStoreState {
  initialized: boolean
  maintenanceMode: boolean
  appVersion: string
}

interface AppStoreActions {
  setInitialized: (initialized: boolean) => void
  setMaintenanceMode: (maintenance: boolean) => void
}

export const useAppStore = create<AppStoreState & AppStoreActions>()((set) => ({
  initialized: false,
  maintenanceMode: false,
  appVersion: '1.0.0',

  setInitialized: (initialized) => set({ initialized }),
  setMaintenanceMode: (maintenanceMode) => set({ maintenanceMode }),
}))
