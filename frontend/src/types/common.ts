export interface OptionItem<T = string> {
  label: string
  value: T
  disabled?: boolean
  description?: string
}

export interface BreadcrumbItem {
  label: string
  href?: string
}

export interface TableColumn<T = Record<string, unknown>> {
  key: keyof T | string
  header: string
  width?: string
  sortable?: boolean
  render?: (value: unknown, row: T) => React.ReactNode
}

export interface NotificationItem {
  id: string
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message?: string
  duration?: number
}

export interface NavItem {
  id: string
  label: string
  href: string
  icon?: string
  badge?: string | number
  children?: NavItem[]
  requiredRole?: import('./auth').Role
}

export interface SidebarGroup {
  id: string
  label?: string
  items: NavItem[]
}
