import { useState, useEffect } from 'react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Link, useNavigate } from 'react-router-dom'
import { LogOut, Settings, LayoutDashboard } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { getAssetUrl } from '@/api/client'
import { cn } from '@/utils/cn'

export function UserMenu() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [imageFailed, setImageFailed] = useState(false)
  const [imageLoaded, setImageLoaded] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const avatarUrl = getAssetUrl(user?.avatar_url)

  useEffect(() => {
    setImageFailed(false)
    setImageLoaded(false)
  }, [avatarUrl])

  // Precedence:
  // 1. Saved non-empty profile name (username, full_name, display_name)
  // 2. Role fallback: "Admin" for admin/owner/platform_admin, "User" for user/member/viewer/etc.
  const rawSavedName =
    user?.username?.trim() ||
    user?.full_name?.trim() ||
    user?.display_name?.trim() ||
    (typeof user?.profile_data?.full_name === 'string' && user.profile_data.full_name.trim()) ||
    ''

  const roleStr = (user?.role ? String(user.role) : '').toLowerCase()
  const isAdminRole = ['admin', 'owner', 'platform_admin'].includes(roleStr)
  const displayName = rawSavedName || (isAdminRole ? 'Admin' : 'User')

  const initials = displayName.charAt(0).toUpperCase() || user?.email?.charAt(0).toUpperCase() || 'U'

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          className="relative inline-flex h-9 w-9 items-center justify-center rounded-full border border-border bg-surface hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary transition-colors overflow-hidden"
          aria-label="User menu"
        >
          {/* Always render initials fallback so there is zero layout shift or empty frame while image loads */}
          <span className="text-sm font-semibold select-none">{initials}</span>

          {avatarUrl && !imageFailed && (
            <img
              src={avatarUrl}
              alt="Avatar"
              className={cn(
                "absolute inset-0 h-full w-full object-cover transition-opacity duration-200",
                imageLoaded ? "opacity-100" : "opacity-0"
              )}
              onLoad={() => setImageLoaded(true)}
              onError={() => setImageFailed(true)}
            />
          )}
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          className="z-50 w-56 overflow-hidden rounded-md border border-border bg-surface-elevated p-1 shadow-md animate-in data-[side=bottom]:slide-in-from-top-2 mt-2"
        >
          <div className="flex flex-col space-y-1 p-2">
            <p className="text-sm font-medium leading-none">{displayName}</p>
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
