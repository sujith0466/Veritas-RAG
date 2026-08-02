import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Link, useNavigate } from 'react-router-dom'
import { LogOut, User as UserIcon, Settings, LayoutDashboard } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { getAssetUrl } from '@/api/client'

export function UserMenu() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const avatarUrl = getAssetUrl(user?.avatar_url)
  const initials = user?.full_name?.charAt(0).toUpperCase() || user?.email?.charAt(0).toUpperCase() || 'U'

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-border bg-surface hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary transition-colors overflow-hidden">
          {avatarUrl ? (
            <img src={avatarUrl} alt="Avatar" className="h-full w-full object-cover" />
          ) : (
            <span className="text-sm font-semibold">{initials}</span>
          )}
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          className="z-50 w-56 overflow-hidden rounded-md border border-border bg-surface-elevated p-1 shadow-md animate-in data-[side=bottom]:slide-in-from-top-2 mt-2"
        >
          <div className="flex flex-col space-y-1 p-2">
            <p className="text-sm font-medium leading-none">{user?.full_name || 'User'}</p>
            <p className="text-xs leading-none text-muted-foreground truncate">{user?.email}</p>
          </div>
          <DropdownMenu.Separator className="-mx-1 my-1 h-px bg-border-subtle" />

          <DropdownMenu.Item className="flex cursor-default select-none items-center rounded-sm text-sm outline-none hover:bg-muted focus:bg-muted" asChild>
            <Link to="/dashboard" className="flex items-center px-2 py-1.5 w-full">
              <LayoutDashboard className="mr-2 h-4 w-4" />
              <span>Dashboard</span>
            </Link>
          </DropdownMenu.Item>

          <DropdownMenu.Item className="flex cursor-default select-none items-center rounded-sm text-sm outline-none hover:bg-muted focus:bg-muted" asChild>
            <Link to="/settings/profile" className="flex items-center px-2 py-1.5 w-full">
              <UserIcon className="mr-2 h-4 w-4" />
              <span>Profile</span>
            </Link>
          </DropdownMenu.Item>

          <DropdownMenu.Item className="flex cursor-default select-none items-center rounded-sm text-sm outline-none hover:bg-muted focus:bg-muted" asChild>
            <Link to="/settings" className="flex items-center px-2 py-1.5 w-full">
              <Settings className="mr-2 h-4 w-4" />
              <span>Settings</span>
            </Link>
          </DropdownMenu.Item>

          <DropdownMenu.Separator className="-mx-1 my-1 h-px bg-border-subtle" />

          <DropdownMenu.Item
            onClick={handleLogout}
            className="flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-danger/10 hover:text-danger focus:bg-danger/10 focus:text-danger text-danger"
          >
            <LogOut className="mr-2 h-4 w-4" />
            <span>Log out</span>
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
