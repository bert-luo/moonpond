import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { GameTabs } from '@/app/components/GameTabs';
import type { GameSession } from '@/types/generation';

function makeSession(overrides: Partial<GameSession> = {}): GameSession {
  return {
    id: crypto.randomUUID(),
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

describe('GameTabs', () => {
  it('renders tab for each session with title fallback to "Game N"', () => {
    const sessions = [makeSession(), makeSession()];
    render(<GameTabs sessions={sessions} activeIdx={0} onSelect={vi.fn()} onNew={vi.fn()} />);
    expect(screen.getByText('Game 1')).toBeDefined();
    expect(screen.getByText('Game 2')).toBeDefined();
  });

  it('renders actual title when session.title is set', () => {
    const sessions = [makeSession({ title: 'Space Blaster' })];
    render(<GameTabs sessions={sessions} activeIdx={0} onSelect={vi.fn()} onNew={vi.fn()} />);
    expect(screen.getByText('Space Blaster')).toBeDefined();
  });

  it('clicking a tab calls onSelect with correct index', () => {
    const onSelect = vi.fn();
    const sessions = [makeSession(), makeSession()];
    render(<GameTabs sessions={sessions} activeIdx={0} onSelect={onSelect} onNew={vi.fn()} />);
    fireEvent.click(screen.getByText('Game 2'));
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it('clicking plus button calls onNew', () => {
    const onNew = vi.fn();
    const sessions = [makeSession()];
    render(<GameTabs sessions={sessions} activeIdx={0} onSelect={vi.fn()} onNew={onNew} />);
    fireEvent.click(screen.getByLabelText('New game'));
    expect(onNew).toHaveBeenCalled();
  });

  it('active tab has accent border styling', () => {
    const sessions = [makeSession(), makeSession()];
    render(<GameTabs sessions={sessions} activeIdx={0} onSelect={vi.fn()} onNew={vi.fn()} />);
    const activeTab = screen.getByText('Game 1').closest('button')!;
    expect(activeTab.className).toContain('border-[var(--color-accent)]');
  });
});
