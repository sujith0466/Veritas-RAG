import { apiClient } from '@/api/client'
import { del, get, post } from '@/api/wrapper'
import type {
  DocumentDetailResponse,
  DocumentListResponse,
  ProcessingStatusResponse,
  SuccessResponse,
  UploadResponse,
  UrlIngestResponse,
  UrlRefreshResponse,
} from '@/types'
import { ApiError } from '@/types'

export const documentService = {
  async uploadDocument(
    file: File,
    onProgress?: (percent: number) => void,
    relativePath?: string,
  ): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)
    if (relativePath) {
      formData.append('relative_path', relativePath)
    }

    const response = await apiClient.post<SuccessResponse<UploadResponse>>(
      '/documents/upload',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (event) => {
          if (onProgress && event.total) {
            const percentCompleted = Math.round((event.loaded * 100) / event.total)
            onProgress(percentCompleted)
          }
        },
      },
    )

    if (!response.data.success) {
      throw new ApiError(
        'Upload failed unexpectedly',
        'UPLOAD_ERROR',
        500,
        'unknown',
      )
    }

    return response.data.data
  },

  async ingestUrl(
    url: string,
    userMetadata?: Record<string, unknown>,
  ): Promise<UrlIngestResponse> {
    return post<UrlIngestResponse>('/documents/urls', {
      url,
      user_metadata: userMetadata,
    })
  },

  async refreshWebsiteDocument(id: string): Promise<UrlRefreshResponse> {
    return post<UrlRefreshResponse>(`/documents/${id}/refresh`)
  },

  async getDocumentStatus(id: string): Promise<ProcessingStatusResponse> {
    return get<ProcessingStatusResponse>(`/documents/${id}/status`)
  },

  async getDocumentDetail(id: string): Promise<DocumentDetailResponse> {
    return get<DocumentDetailResponse>(`/documents/${id}`)
  },

  async listDocuments(
    page = 1,
    pageSize = 20,
    status?: string,
    search?: string,
    sortBy = 'created_at',
    sortOrder: 'asc' | 'desc' = 'desc',
  ): Promise<DocumentListResponse> {
    const params: Record<string, unknown> = {
      page,
      page_size: pageSize,
      sort_by: sortBy,
      sort_order: sortOrder,
    }
    if (status && status !== 'ALL') {
      params.status = status
    }
    if (search && search.trim()) {
      params.q = search.trim()
    }
    return get<DocumentListResponse>('/documents', params)
  },

  async deleteDocument(id: string): Promise<{ deleted: boolean; document_id: string }> {
    return del<{ deleted: boolean; document_id: string }>(`/documents/${id}`)
  },

  async archiveDocument(id: string): Promise<{ archived: boolean; document_id: string }> {
    return post<{ archived: boolean; document_id: string }>(`/documents/${id}/archive`)
  },

  async restoreDocument(id: string): Promise<{ restored: boolean; document_id: string }> {
    return post<{ restored: boolean; document_id: string }>(`/documents/${id}/restore`)
  },

  async uploadDocumentVersion(
    id: string,
    file: File,
    onProgress?: (percent: number) => void,
  ): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await apiClient.post<SuccessResponse<UploadResponse>>(
      `/documents/${id}/versions`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (event) => {
          if (onProgress && event.total) {
            const percentCompleted = Math.round((event.loaded * 100) / event.total)
            onProgress(percentCompleted)
          }
        },
      },
    )

    if (!response.data.success) {
      throw new ApiError(
        'Version upload failed unexpectedly',
        'UPLOAD_ERROR',
        500,
        'unknown',
      )
    }

    return response.data.data
  },

  async rollbackDocumentVersion(id: string, versionId: string): Promise<UploadResponse> {
    return post<UploadResponse>(`/documents/${id}/versions/${versionId}/rollback`)
  },

  async retryDocument(id: string): Promise<{ retried: boolean; document_id: string; job_id: string; status: string }> {
    return post<{ retried: boolean; document_id: string; job_id: string; status: string }>(`/documents/${id}/retry`)
  },

  async reingestDocument(id: string): Promise<{ reingested: boolean; document_id: string; job_id: string; status: string }> {
    return post<{ reingested: boolean; document_id: string; job_id: string; status: string }>(`/documents/${id}/reingest`)
  },

  async downloadOriginal(id: string, filename = 'document.bin', versionId?: string): Promise<void> {
    const url = versionId ? `/documents/${id}/download?version_id=${versionId}` : `/documents/${id}/download`
    const response = await apiClient.get(url, {
      responseType: 'blob',
    })
    const blob = new Blob([response.data])
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(downloadUrl)
  },

  async downloadExtractedText(id: string, filename = 'document.extracted.txt', versionId?: string): Promise<void> {
    const url = versionId ? `/documents/${id}/extracted-text?version_id=${versionId}` : `/documents/${id}/extracted-text`
    const response = await apiClient.get(url, {
      responseType: 'blob',
    })
    const blob = new Blob([response.data], { type: 'text/plain;charset=utf-8' })
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(downloadUrl)
  },
}

