import axios from 'axios'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

export const getAssetUrl = (path: string | null | undefined) => {
  if (!path) return null
  if (path.startsWith('http')) return path
  return `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`
}

export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
})

