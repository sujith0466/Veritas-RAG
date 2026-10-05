import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MessageEditInput } from '@/components/chat/MessageEditInput'
import { ShareModal, formatSafeMarkdownExport } from '@/components/chat/ShareModal'
import type { ChatMessage } from '@/stores/chatStore'

describe('WS-C C3 & C5: MessageEditInput & ShareModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })
  })

  describe('MessageEditInput', () => {
    it('renders with initial content and submits on Enter', async () => {
      const onSave = vi.fn().mockResolvedValue(undefined)
      const onCancel = vi.fn()

      render(
        <MessageEditInput
          initialContent="Original user prompt"
          onSave={onSave}
          onCancel={onCancel}
        />
      )

      const textarea = screen.getByRole('textbox', { name: 'Edit your message' })
      expect(textarea).toHaveValue('Original user prompt')

      fireEvent.change(textarea, { target: { value: 'Edited user prompt' } })
      expect(textarea).toHaveValue('Edited user prompt')

      // Press Enter
      fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' })

      await waitFor(() => {
        expect(onSave).toHaveBeenCalledWith('Edited user prompt')
      })
    })

    it('cancels on Escape key', () => {
      const onSave = vi.fn()
      const onCancel = vi.fn()

      render(
        <MessageEditInput
          initialContent="Some text"
          onSave={onSave}
          onCancel={onCancel}
        />
      )

      const textarea = screen.getByRole('textbox', { name: 'Edit your message' })
      fireEvent.keyDown(textarea, { key: 'Escape', code: 'Escape' })

      expect(onCancel).toHaveBeenCalledTimes(1)
      expect(onSave).not.toHaveBeenCalled()
    })

    it('disables save button when content is empty', () => {
      const onSave = vi.fn()
      const onCancel = vi.fn()

      render(
        <MessageEditInput
          initialContent=""
          onSave={onSave}
          onCancel={onCancel}
        />
      )

      const saveButton = screen.getByRole('button', { name: 'Save & Submit' })
      expect(saveButton).toBeDisabled()
    })
  })

  describe('formatSafeMarkdownExport', () => {
    it('produces sanitized markdown without internal IDs, vectors, or storage paths', () => {
      const mockMsg: ChatMessage = {
        id: 'msg-internal-uuid-1234',
        session_id: 'sess-internal-uuid-5678',
        role: 'assistant',
        message: 'According to corporate policy, standard PTO is 20 days [1].',
        citations: [
          {
            citation_index: 1,
            document_name: 'Employee_Handbook_2025.pdf',
            page_number: 14,
            section_title: 'PTO Policy',
            // internal fields that should NOT be in safe export:
            tenant_id: 'secret-tenant-uuid',
            qdrant_point_id: 'qdrant-internal-point-999',
            storage_path: 's3://internal-bucket/handbook.pdf',
          },
        ],
        reliability_score: 0.95,
        metadata_json: {
          feedback: 'like',
          internal_timing_ms: 450,
        },
        created_at: '2026-10-05T00:00:00Z',
      }

      const exported = formatSafeMarkdownExport(mockMsg)

      // Must include response and user-visible citation info
      expect(exported).toContain('According to corporate policy, standard PTO is 20 days [1].')
      expect(exported).toContain('[1] Employee_Handbook_2025.pdf (Page 14) [PTO Policy]')
      expect(exported).toContain('Reliability Score: 95% (Highly Grounded)')

      // Must NOT leak internal database IDs, Qdrant vectors, storage paths, or tenant UUIDs
      expect(exported).not.toContain('secret-tenant-uuid')
      expect(exported).not.toContain('qdrant-internal-point-999')
      expect(exported).not.toContain('s3://internal-bucket/handbook.pdf')
      expect(exported).not.toContain('msg-internal-uuid-1234')
      expect(exported).not.toContain('internal_timing_ms')
    })
  })

  describe('ShareModal', () => {
    const mockMsg: ChatMessage = {
      id: 'msg-456',
      session_id: 'sess-123',
      role: 'assistant',
      message: 'Here is the shared answer.',
      citations: [],
      created_at: '2026-10-05T00:00:00Z',
    }

    it('renders modal with safe markdown copy and private deep link options', async () => {
      const onClose = vi.fn()

      render(
        <ShareModal
          isOpen={true}
          onClose={onClose}
          message={mockMsg}
          sessionId="sess-123"
        />
      )

      expect(screen.getByText('Share Response')).toBeInTheDocument()
      expect(screen.getAllByText('Formatted Markdown').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('Private Deep Link')).toBeInTheDocument()
      expect(screen.getByText(/This link is private and accessible only by you in this workspace/i)).toBeInTheDocument()

      const copyMarkdownBtn = screen.getByRole('button', { name: /Copy formatted markdown/i })
      fireEvent.click(copyMarkdownBtn)

      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Here is the shared answer.')
    })
  })
})
