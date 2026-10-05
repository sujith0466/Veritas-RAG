import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ActionButton, MessageActionBar } from '@/components/chat/MessageActionBar'
import { UserMessageActions } from '@/components/chat/UserMessageActions'
import { AssistantMessageActions } from '@/components/chat/AssistantMessageActions'

describe('WS-C C2: Message Action Bar & Action Components', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })
  })

  it('ActionButton renders icon without any visible text children', () => {
    render(
      <MessageActionBar>
        <ActionButton
          icon={<svg data-testid="test-icon" />}
          tooltip="Copy text"
          ariaLabel="Copy text to clipboard"
          onClick={() => {}}
        />
      </MessageActionBar>
    )

    const button = screen.getByRole('button', { name: 'Copy text to clipboard' })
    expect(button).toBeInTheDocument()
    expect(screen.getByTestId('test-icon')).toBeInTheDocument()

    // Assert strictly ICON-ONLY: textContent of button must be empty string
    expect(button.textContent).toBe('')
  })

  it('UserMessageActions renders Edit and Copy buttons as icons only', () => {
    const onEdit = vi.fn()
    render(
      <UserMessageActions content="Hello world prompt" onEdit={onEdit} />
    )

    const editButton = screen.getByRole('button', { name: 'Edit message' })
    const copyButton = screen.getByRole('button', { name: 'Copy user message to clipboard' })

    expect(editButton).toBeInTheDocument()
    expect(copyButton).toBeInTheDocument()

    // Non-negotiable UI contract: NO visible text beside icons
    expect(editButton.textContent).toBe('')
    expect(copyButton.textContent).toBe('')

    // Trigger edit
    fireEvent.click(editButton)
    expect(onEdit).toHaveBeenCalledTimes(1)

    // Trigger copy
    fireEvent.click(copyButton)
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Hello world prompt')
  })

  it('AssistantMessageActions renders Copy, Like, Dislike, Share as icons only and toggles feedback', async () => {
    const onFeedback = vi.fn()
    const onShare = vi.fn()

    render(
      <AssistantMessageActions
        content="Grounded assistant answer"
        feedback={null}
        onFeedback={onFeedback}
        onShare={onShare}
      />
    )

    const copyBtn = screen.getByRole('button', { name: 'Copy response to clipboard' })
    const likeBtn = screen.getByRole('button', { name: 'Like response' })
    const dislikeBtn = screen.getByRole('button', { name: 'Dislike response' })
    const shareBtn = screen.getByRole('button', { name: 'Share response' })

    // Strict icon-only contract verification
    expect(copyBtn.textContent).toBe('')
    expect(likeBtn.textContent).toBe('')
    expect(dislikeBtn.textContent).toBe('')
    expect(shareBtn.textContent).toBe('')

    // Feedback clicks
    fireEvent.click(likeBtn)
    expect(onFeedback).toHaveBeenCalledWith('like')

    fireEvent.click(dislikeBtn)
    expect(onFeedback).toHaveBeenCalledWith('dislike')

    // Share click
    fireEvent.click(shareBtn)
    expect(onShare).toHaveBeenCalledTimes(1)
  })

  it('AssistantMessageActions toggles off active feedback', () => {
    const onFeedback = vi.fn()

    render(
      <AssistantMessageActions
        content="Grounded assistant answer"
        feedback="like"
        onFeedback={onFeedback}
      />
    )

    const likeBtn = screen.getByRole('button', { name: 'Remove like rating' })
    fireEvent.click(likeBtn)
    expect(onFeedback).toHaveBeenCalledWith(null)
  })
})
