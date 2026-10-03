/**
 * Telemetry scale and presentation adapters.
 * Translates between canonical backend storage scale (0.0000–1.0000)
 * and frontend display scale (0.0%–100.0%).
 */

/**
 * Converts a raw score (which could be in 0.0–1.0 canonical format or legacy 0–100 format)
 * into a presentation percentage (0.0–100.0).
 *
 * @param score The raw score from backend or DTO
 * @param fallback Fallback value if score is null or undefined (default: 0.0)
 * @returns Number in range 0.0 to 100.0 rounded to 1 decimal place
 */
export function toPresentationPercentage(
  score: number | null | undefined,
  fallback = 0.0
): number {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return fallback
  }

  // If score is already in 0.0–1.0 canonical range (e.g., 0.854)
  if (score >= 0 && score <= 1.0) {
    return Math.round(score * 1000) / 10
  }

  // If score is legacy or already in 0–100 range (e.g., 85.4)
  if (score > 1.0 && score <= 100.0) {
    return Math.round(score * 10) / 10
  }

  // Handle clamped bounds
  if (score < 0) return 0.0
  if (score > 100.0) return 100.0

  return fallback
}

/**
 * Formats a score as a percentage string (e.g., "85.4%").
 *
 * @param score The raw score
 * @param decimals Number of decimal digits (default: 1)
 * @param fallback Fallback string if score is null/undefined (default: 'N/A')
 */
export function formatPresentationPercentage(
  score: number | null | undefined,
  decimals = 1,
  fallback = 'N/A'
): string {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return fallback
  }
  const pct = toPresentationPercentage(score)
  return `${pct.toFixed(decimals)}%`
}

/**
 * Converts a presentation percentage (0.0–100.0) to canonical storage float (0.0000–1.0000).
 */
export function toCanonicalScore(
  percentage: number | null | undefined,
  decimals = 4
): number | null {
  if (percentage === null || percentage === undefined || Number.isNaN(percentage)) {
    return null
  }
  const clamped = Math.max(0, Math.min(100, percentage))
  return Number((clamped / 100).toFixed(decimals))
}
