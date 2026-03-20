import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ChatPanel } from '@/app/components/ChatPanel';
import type { GameSession, ChatMessage } from '@/types/generation';

function makeSession(overrides: Partial<GameSession> = {}): GameSession {
  return {
    id: 'session-1',
    title: null,
    description: null,
    status: 'idle',
    messages: [],
    gameUrl: null,
    controls: [],
    errorMessage: null,
    ...overrides,
  };
}

function makeMessage(overrides: Partial<ChatMessage>): ChatMessage {
  return {
    id: crypto.randomUUID(),
    type: 'stage',
    text: '',
    ...overrides,
  };
}

describe('ChatPanel', () => {
  it('renders prompt input with placeholder', () => {
    render(<ChatPanel session={makeSession()} onSubmit={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByPlaceholderText(/Describe a game/)).toBeDefined();
  });

  it('disables input when status is generating', () => {
    render(
      <ChatPanel session={makeSession({ status: 'generating' })} onSubmit={vi.fn()} onReset={vi.fn()} />
    );
    const input = screen.getByPlaceholderText(/Describe a game/) as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });

  it('renders stage messages as chat bubbles', () => {
    const session = makeSession({
      status: 'generating',
      messages: [makeMessage({ type: 'stage', text: 'Designing game...' })],
    });
    render(<ChatPanel session={session} onSubmit={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByText('Designing game...')).toBeDefined();
  });

  it('calls onSubmit with prompt text', () => {
    const onSubmit = vi.fn();
    render(<ChatPanel session={makeSession()} onSubmit={onSubmit} onReset={vi.fn()} />);
    const input = screen.getByPlaceholderText(/Describe a game/) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'my game idea' } });
    fireEvent.submit(input.closest('form')!);
    expect(onSubmit).toHaveBeenCalledWith('my game idea');
  });

  it('renders error messages with error styling', () => {
    const session = makeSession({
      status: 'error',
      messages: [makeMessage({ type: 'error', text: 'Something failed' })],
    });
    render(<ChatPanel session={session} onSubmit={vi.fn()} onReset={vi.fn()} />);
    const errorEl = screen.getByText('Something failed');
    expect(errorEl.closest('div')?.className).toContain('bg-red-900/30');
  });

  it('spec_info message renders title and description', () => {
    const session = makeSession({
      status: 'generating',
      messages: [
        makeMessage({
          type: 'spec_info',
          text: 'Game: Cool Game',
          data: { title: 'Cool Game', description: 'A really cool game' },
        }),
      ],
    });
    render(<ChatPanel session={session} onSubmit={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByText('Cool Game')).toBeDefined();
    expect(screen.getByText('A really cool game')).toBeDefined();
  });

  it('file_written message renders filename and line count', () => {
    const session = makeSession({
      status: 'generating',
      messages: [
        makeMessage({
          type: 'file_written',
          text: 'Generated player.gd (42 lines)',
          data: { filename: 'player.gd', lines: 42 },
        }),
      ],
    });
    render(<ChatPanel session={session} onSubmit={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByTestId('file-name').textContent).toBe('player.gd');
    expect(screen.getByTestId('file-lines').textContent).toContain('42');
  });

  it('controls message renders key/action grid inline', () => {
    const session = makeSession({
      status: 'done',
      messages: [
        makeMessage({
          type: 'controls',
          text: 'Controls',
          data: { controls: [{ key: 'Arrow Keys', action: 'Move' }, { key: 'Space', action: 'Jump' }] },
        }),
      ],
    });
    render(<ChatPanel session={session} onSubmit={vi.fn()} onReset={vi.fn()} />);
    expect(screen.getByText('Arrow Keys')).toBeDefined();
    expect(screen.getByText('Move')).toBeDefined();
    expect(screen.getByText('Space')).toBeDefined();
    expect(screen.getByText('Jump')).toBeDefined();
  });

  it('does not render standalone controls block (controls are inline messages only)', () => {
    // With controls in session but no controls message, no controls grid should appear
    const session = makeSession({
      status: 'done',
      controls: [{ key: 'W', action: 'Up' }],
      messages: [makeMessage({ type: 'complete', text: 'Your game is ready!' })],
    });
    const { container } = render(<ChatPanel session={session} onSubmit={vi.fn()} onReset={vi.fn()} />);
    // The old standalone controls block had an uppercase "Controls" heading outside the message loop
    // With the new design, "Controls" heading only appears inside a controls-type message
    const controlsHeadings = container.querySelectorAll('h3');
    expect(controlsHeadings.length).toBe(0);
  });
});
