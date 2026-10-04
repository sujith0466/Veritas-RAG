/**
 * Safe redirect URL resolution and open redirect defense.
 * Ensures destinations are relative, internal paths and rejects protocol-relative,
 * absolute, scheme-based, or malicious redirect targets.
 */

const DANGEROUS_SCHEMES = ['javascript:', 'data:', 'vbscript:', 'file:', 'blob:'];
const DISALLOWED_TARGET_PREFIXES = ['/auth/login', '/auth/register', '/auth/callback'];

export function getSafeRedirectUrl(
  target: string | null | undefined,
  fallback: string = '/dashboard'
): string {
  if (!target || typeof target !== 'string') {
    return fallback;
  }

  const trimmed = target.trim();
  if (!trimmed) {
    return fallback;
  }

  // 1. Must start with a single '/' and NOT with '//' or '/\' (protocol-relative/UNC bypass)
  if (!trimmed.startsWith('/') || trimmed.startsWith('//') || trimmed.startsWith('/\\')) {
    return fallback;
  }

  // 2. Reject absolute URLs with schemes (http://, https://, etc.)
  if (trimmed.includes('://')) {
    return fallback;
  }

  // 3. Reject dangerous pseudo-protocols
  const lower = trimmed.toLowerCase();
  for (const scheme of DANGEROUS_SCHEMES) {
    if (lower.startsWith(scheme)) {
      return fallback;
    }
  }

  // 4. Reject redirecting back to authentication loops
  for (const prefix of DISALLOWED_TARGET_PREFIXES) {
    if (lower === prefix || lower.startsWith(prefix + '?') || lower.startsWith(prefix + '/')) {
      return fallback;
    }
  }

  return trimmed;
}
