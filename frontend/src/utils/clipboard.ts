/**
 * Utility for copying text to the clipboard with browser compatibility fallback.
 * Uses navigator.clipboard.writeText as primary, with a legacy textarea fallback.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  // 1. Try modern Async Clipboard API first
  if (navigator?.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch (err) {
      console.warn('navigator.clipboard.writeText failed, falling back to execCommand:', err)
    }
  }

  // 2. Legacy fallback for non-secure / iframe / restricted contexts
  try {
    if (typeof document !== 'undefined' && typeof document.execCommand === 'function') {
      const textArea = document.createElement('textarea')
      textArea.value = text
      textArea.style.position = 'fixed'
      textArea.style.left = '-999999px'
      textArea.style.top = '-999999px'
      textArea.setAttribute('aria-hidden', 'true')
      textArea.setAttribute('readonly', '')
      document.body.appendChild(textArea)
      textArea.focus()
      textArea.select()
      const successful = document.execCommand('copy')
      document.body.removeChild(textArea)
      return successful
    }
  } catch (fallbackErr) {
    console.error('Fallback execCommand copy failed:', fallbackErr)
  }

  return false
}
