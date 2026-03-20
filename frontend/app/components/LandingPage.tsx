'use client';

import { useState, useEffect } from 'react';

interface LandingPageProps {
  onSubmit: (prompt: string) => void;
  isGenerating: boolean;
}

const EXAMPLE_PROMPTS = [
  'A space shooter where you dodge asteroids',
  'A platformer with bouncing slimes',
  'A puzzle game with sliding tiles',
  'A racing game through neon tunnels',
];

export function LandingPage({ onSubmit, isGenerating }: LandingPageProps) {
  const [prompt, setPrompt] = useState('');
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  const [fade, setFade] = useState(true);

  // Cycle placeholder text through examples
  useEffect(() => {
    if (prompt) return; // stop cycling when user types
    const interval = setInterval(() => {
      setFade(false);
      setTimeout(() => {
        setPlaceholderIdx((i) => (i + 1) % EXAMPLE_PROMPTS.length);
        setFade(true);
      }, 300);
    }, 3000);
    return () => clearInterval(interval);
  }, [prompt]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = prompt.trim();
    if (!trimmed || isGenerating) return;
    onSubmit(trimmed);
  };

  return (
    <div className="absolute inset-0 z-10 bg-[var(--color-bg)] flex items-center justify-center">
      <div className="relative z-10 flex flex-col items-center gap-8 max-w-xl w-full px-6">
        {/* Title */}
        <div className="text-center">
          <h1
            className="text-4xl font-bold text-[var(--color-accent)]"
            style={{ textShadow: '0 0 30px var(--color-glow)' }}
          >
            Moonpond
          </h1>
          <p className="text-[var(--color-text-muted)] mt-2 text-lg">
            Generate playable games from text
          </p>
        </div>

        {/* Prompt input */}
        <form onSubmit={handleSubmit} className="w-full flex flex-col items-center gap-4">
          <div className="relative w-full">
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder=""
              disabled={isGenerating}
              className="w-full bg-white/5 backdrop-blur-sm border border-[var(--color-border)] rounded-xl px-5 py-4 text-lg text-[var(--color-text)] focus:outline-none focus:border-[var(--color-accent)] disabled:opacity-50 transition-colors"
            />
            {/* Carousel placeholder */}
            {!prompt && (
              <span
                className={`absolute left-5 top-1/2 -translate-y-1/2 text-lg text-[var(--color-text-muted)] pointer-events-none transition-opacity duration-300 ${fade ? 'opacity-100' : 'opacity-0'}`}
              >
                {EXAMPLE_PROMPTS[placeholderIdx]}
              </span>
            )}
          </div>

          <button
            type="submit"
            disabled={isGenerating || !prompt.trim()}
            className="bg-[var(--color-accent)] text-white font-medium px-8 py-3 rounded-xl text-base hover:opacity-90 disabled:opacity-40 transition-opacity"
          >
            {isGenerating ? 'Generating...' : 'Generate Game'}
          </button>
        </form>
      </div>
    </div>
  );
}
