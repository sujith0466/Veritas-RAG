import { motion } from 'framer-motion'
import { Shield, User } from 'lucide-react'
import { cn } from '@/utils/cn'

interface RoleSelectorProps {
  mode: 'login' | 'register'
  onSelect: (role: 'admin' | 'viewer') => void
}

export function RoleSelector({ mode, onSelect }: RoleSelectorProps) {
  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1 }
    },
    exit: { opacity: 0, scale: 0.95, transition: { duration: 0.2 } }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 300, damping: 24 } }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any



  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="show"
      exit="exit"
      className="flex flex-col items-center justify-center space-y-5 w-full max-w-lg mx-auto"
    >
      <div className="text-center mb-1">
        <h2 className="text-2xl font-semibold text-foreground tracking-tight mb-1.5">
          {mode === 'login' ? 'Welcome to RAGuard AI' : 'Select Workspace Role'}
        </h2>
        <p className="text-sm text-muted-foreground">
          {mode === 'login' ? 'Select your role to access your workspace' : 'Choose how you will participate in the workspace'}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full">
        {/* Admin Card */}
        <motion.button
          layoutId="auth-form-admin"
          variants={itemVariants}
          onClick={() => onSelect('admin')}
          whileHover={{ scale: 1.02, y: -4 }}
          whileTap={{ scale: 0.98 }}
          className={cn(
            "group relative flex flex-col items-start p-6 rounded-2xl border border-border/50 bg-surface/40 backdrop-blur-md transition-all duration-300 overflow-hidden text-left",
            "hover:border-primary/50 hover:shadow-lg hover:shadow-primary/10 hover:bg-surface-elevated/60"
          )}
        >
          {/* Glass reflection */}
          <div className="absolute inset-0 bg-gradient-to-br from-white/[0.05] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />

          <div className="h-12 w-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-4 group-hover:scale-110 group-hover:bg-primary/20 transition-all duration-300">
            <Shield className="h-6 w-6" />
          </div>

          <div className="font-semibold text-foreground text-lg group-hover:text-primary transition-colors mb-1">
            Admin Workspace
          </div>
          <div className="text-sm text-muted-foreground mb-4">
            Workspace Owner
          </div>


        </motion.button>

        {/* User Card */}
        <motion.button
          layoutId="auth-form-user"
          variants={itemVariants}
          onClick={() => onSelect('viewer')}
          whileHover={{ scale: 1.02, y: -4 }}
          whileTap={{ scale: 0.98 }}
          className={cn(
            "group relative flex flex-col items-start p-6 rounded-2xl border border-border/50 bg-surface/40 backdrop-blur-md transition-all duration-300 overflow-hidden text-left",
            "hover:border-primary/50 hover:shadow-lg hover:shadow-primary/10 hover:bg-surface-elevated/60"
          )}
        >
          {/* Glass reflection */}
          <div className="absolute inset-0 bg-gradient-to-br from-white/[0.05] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />

          <div className="h-12 w-12 rounded-xl bg-muted text-muted-foreground flex items-center justify-center mb-4 group-hover:bg-primary/10 group-hover:text-primary group-hover:scale-110 transition-all duration-300">
            <User className="h-6 w-6" />
          </div>

          <div className="font-semibold text-foreground text-lg group-hover:text-primary transition-colors mb-1">
            Workspace Member
          </div>
          <div className="text-sm text-muted-foreground mb-4">
            Workspace User
          </div>


        </motion.button>
      </div>
    </motion.div>
  )
}
