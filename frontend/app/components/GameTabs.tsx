'use client';

import type { GameSession } from '@/types/generation';

interface GameTabsProps {
  sessions: GameSession[];
  activeIdx: number;
  onSelect: (idx: number) => void;
  onNew: () => void;
}

export function GameTabs({ sessions, activeIdx, onSelect, onNew }: GameTabsProps) {
  return (
    <div className="flex items-center overflow-x-auto border-b border-[var(--color-border)] bg-[var(--color-bg)]">
      {sessions.map((session, idx) => (
        <button
          key={session.id}
          type="button"
          onClick={() => onSelect(idx)}
          className={`px-4 py-2.5 text-sm font-light tracking-wide whitespace-nowrap flex-shrink-0 transition-colors ${
            idx === activeIdx
              ? 'bg-[var(--color-surface)] border-b-2 border-[var(--color-accent)] text-[var(--color-text)]'
              : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
          }`}
        >
          <span className="max-w-[120px] truncate inline-block">
            {session.title ?? `Game ${idx + 1}`}
          </span>
        </button>
      ))}
      <button
        type="button"
        onClick={onNew}
        className="px-3 py-2.5 text-lg text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors flex-shrink-0"
        aria-label="New game"
      >
        +
      </button>
    </div>
  );
}
