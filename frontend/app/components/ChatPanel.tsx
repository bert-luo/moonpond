'use client';

import { useState, useRef, useEffect } from 'react';
import type { GameSession, ControlMapping } from '@/types/generation';

interface ChatPanelProps {
  session: GameSession;
  onSubmit: (prompt: string) => void;
  onReset: () => void;
}

export function ChatPanel({ session, onSubmit, onReset }: ChatPanelProps) {
  const [prompt, setPrompt] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  }, [session.messages]);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    const trimmed = prompt.trim();
    if (!trimmed || session.status === 'generating') return;
    onSubmit(trimmed);
    setPrompt('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFocus = () => {
    if (session.status === 'done') {
      onReset();
    }
  };

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Messages area */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto px-4 py-4 space-y-3"
      >
        {session.messages.length === 0 && session.status === 'idle' && (
          <div className="flex items-center justify-center h-full">
            <p className="text-[var(--color-text-muted)] text-sm text-center">
              Describe a game and watch it come to life
            </p>
          </div>
        )}

        {session.messages.map((msg) => (
          <div key={msg.id} className="flex justify-start">
            {msg.type === 'spec_info' ? (
              <div className="max-w-[90%] rounded-lg px-3 py-2 text-sm bg-[var(--color-surface)] border-l-2 border-[var(--color-accent)]">
                <span className="font-bold text-[var(--color-text)]">
                  {(msg.data?.title as string) ?? msg.text}
                </span>
                {msg.data?.description && (
                  <p className="text-[var(--color-text-muted)] mt-1">
                    {msg.data.description as string}
                  </p>
                )}
              </div>
            ) : msg.type === 'file_written' ? (
              <div className="max-w-[90%] rounded-lg px-3 py-2 text-sm bg-[var(--color-surface)] text-[var(--color-text-muted)]">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500 mr-2 align-middle" />
                <span data-testid="file-name">{msg.data?.filename as string}</span>
                <span className="ml-2 text-xs opacity-70" data-testid="file-lines">
                  {(msg.data?.lines as number) ?? 0} lines
                </span>
              </div>
            ) : msg.type === 'controls' ? (
              <div className="max-w-[90%] bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-3">
                <h3 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2">
                  Controls
                </h3>
                <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                  {((msg.data?.controls as ControlMapping[]) ?? []).map((ctrl, i) => (
                    <div key={i} className="contents text-sm">
                      <kbd className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded px-1.5 py-0.5 text-xs font-mono text-[var(--color-text)]">
                        {ctrl.key}
                      </kbd>
                      <span className="text-[var(--color-text-muted)]">{ctrl.action}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div
                className={`max-w-[90%] rounded-lg px-3 py-2 text-sm ${
                  msg.type === 'stage'
                    ? 'bg-[var(--color-surface)] text-[var(--color-text-muted)]'
                    : msg.type === 'complete'
                      ? 'bg-[var(--color-surface)] border border-[var(--color-accent)] text-[var(--color-text)]'
                      : 'bg-red-900/30 border border-red-700/50 text-red-300'
                }`}
              >
                {msg.type === 'stage' && (
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-[var(--color-accent)] mr-2 align-middle animate-pulse" />
                )}
                {msg.text}
              </div>
            )}
          </div>
        ))}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <form
        onSubmit={handleSubmit}
        className="px-4 py-3 border-t border-[var(--color-border)] flex gap-2"
      >
        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={handleFocus}
          placeholder="Describe a game... e.g. A space shooter where you dodge asteroids"
          disabled={session.status === 'generating'}
          className="flex-1 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg px-3 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] disabled:opacity-50 transition-colors"
        />
        <button
          type="submit"
          disabled={session.status === 'generating' || !prompt.trim()}
          className="bg-[var(--color-accent)] text-white font-medium px-4 py-2 rounded-lg text-sm hover:opacity-90 disabled:opacity-40 transition-opacity"
        >
          {session.status === 'generating' ? 'Generating...' : 'Generate'}
        </button>
      </form>
    </div>
  );
}
