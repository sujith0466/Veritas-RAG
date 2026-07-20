import { create } from 'zustand'
import { storage, STORAGE_KEYS } from '@/utils'

interface UIStoreState {
  sidebarCollapsed: boolean
  activeModalId: string | null
  mobileDrawerOpen: boolean
}

interface UIStoreActions {
  setSidebarCollapsed: (collapsed: boolean) => void
  toggleSidebar: () => void
  setActiveModal: (id: string | null) => void
  setMobileDrawerOpen: (open: boolean) => void
}

export const useUIStore = create<UIStoreState & UIStoreActions>()((set, get) => ({
  sidebarCollapsed: storage.get<boolean>(STORAGE_KEYS.SIDEBAR_COLLAPSED, false),
  activeModalId: null,
  mobileDrawerOpen: false,

  setSidebarCollapsed: (collapsed) => {
    storage.set(STORAGE_KEYS.SIDEBAR_COLLAPSED, collapsed)
    set({ sidebarCollapsed: collapsed })
  },

  toggleSidebar: () => {
    const next = !get().sidebarCollapsed
    storage.set(STORAGE_KEYS.SIDEBAR_COLLAPSED, next)
    set({ sidebarCollapsed: next })
  },

  setActiveModal: (id) => set({ activeModalId: id }),

  setMobileDrawerOpen: (open) => set({ mobileDrawerOpen: open }),
}))
