import { apiClient } from '@/api/client'
import { del, get, post } from '@/api/wrapper'
import type {
  DocumentDetailResponse,
  DocumentListResponse,
  ProcessingStatusResponse,
  SuccessResponse,
  UploadResponse,
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
  ): Promise<DocumentListResponse> {
    const params: Record<string, unknown> = {
      page,
      page_size: pageSize,
    }
    if (status && status !== 'ALL') {
      params.status = status
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
}
