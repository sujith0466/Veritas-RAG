import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'

export type StrengthLevel = 'empty' | 'weak' | 'medium' | 'strong'

interface PasswordStrengthProps {
  password?: string
  onChangeStrength?: (strength: StrengthLevel) => void
}

export function PasswordStrength({ password = '', onChangeStrength }: PasswordStrengthProps) {
  const [strength, setStrength] = useState<StrengthLevel>('empty')

  useEffect(() => {
    let newStrength: StrengthLevel = 'empty'
    
    if (password.length > 0) {
      let score = 0
      if (password.length > 7) score += 1
      if (/[A-Z]/.test(password)) score += 1
      if (/[0-9]/.test(password)) score += 1
      if (/[^A-Za-z0-9]/.test(password)) score += 1

      if (score < 2) newStrength = 'weak'
      else if (score < 4) newStrength = 'medium'
      else newStrength = 'strong'
    }

    setStrength(newStrength)
    if (onChangeStrength) {
      onChangeStrength(newStrength)
    }
  }, [password, onChangeStrength])

  const colors = {
    empty: 'bg-muted/50',
    weak: 'bg-orange-500',
    medium: 'bg-purple-500',
    strong: 'bg-blue-500'
  }

  const widths = {
    empty: '0%',
    weak: '33%',
    medium: '66%',
    strong: '100%'
  }

  if (strength === 'empty') return null

  return (
    <div className="space-y-1.5 mt-2">
      <div className="h-1.5 w-full bg-muted/30 rounded-full overflow-hidden">
        <motion.div
          className={`h-full rounded-full ${colors[strength]}`}
          initial={{ width: 0 }}
          animate={{ width: widths[strength], backgroundColor: colors[strength] === 'bg-orange-500' ? '#f97316' : colors[strength] === 'bg-purple-500' ? '#a855f7' : '#3b82f6' }}
          transition={{ duration: 0.3 }}
        />
      </div>
      <div className="flex justify-between text-xs font-medium">
        <span className="text-muted-foreground">Password strength</span>
        <span className={
          strength === 'weak' ? 'text-orange-500' :
          strength === 'medium' ? 'text-purple-500' : 'text-blue-500'
        }>
          {strength === 'weak' ? 'Weak' : strength === 'medium' ? 'Good' : 'Strong'}
        </span>
      </div>
    </div>
  )
}
