'use client';

import type { Status } from '@/types/generation';

interface GameViewerProps {
  status: Status;
  gameUrl: string | null;
}

export function GameViewer({ status, gameUrl }: GameViewerProps) {
  // Show game iframe if we have a URL (persist through error state)
  if (gameUrl) {
    return (
      <div className="w-full h-full rounded-xl overflow-hidden shadow-2xl">
        <iframe
          src={gameUrl}
          className="w-full h-full border-0"
          sandbox="allow-scripts allow-same-origin"
          allow="cross-origin-isolated"
          title="Generated game"
        />
      </div>
    );
  }

  // Loading skeleton with shimmer animation
  if (status === 'generating') {
    return (
      <div className="w-full h-full rounded-xl overflow-hidden relative">
        <div className="absolute inset-0 animate-shimmer rounded-xl" />
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="text-[var(--color-text-muted)] text-lg font-medium">
            Building your game...
          </p>
        </div>
      </div>
    );
  }

  // Idle placeholder
  return (
    <div className="w-full h-full rounded-xl border-2 border-dashed border-[var(--color-border)] flex items-center justify-center">
      <div className="text-center">
        <div className="text-4xl mb-3 opacity-30">
          <svg
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="mx-auto text-[var(--color-text-muted)]"
          >
            <rect x="2" y="6" width="20" height="12" rx="2" />
            <circle cx="8" cy="12" r="2" />
            <circle cx="16" cy="12" r="2" />
            <path d="M9 17v1M15 17v1" />
          </svg>
        </div>
        <p className="text-[var(--color-text-muted)] text-sm">
          Your game will appear here
        </p>
      </div>
    </div>
  );
}
