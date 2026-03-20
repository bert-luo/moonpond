'use client';

import { useState } from 'react';

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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = prompt.trim();
    if (!trimmed || isGenerating) return;
    onSubmit(trimmed);
  };

  return (
    <div className="absolute inset-0 z-10 landing-bg flex items-center justify-center">
      {/* Water reflection decorative element */}
      <div className="landing-reflection absolute inset-x-0 top-[55%] h-[120px] pointer-events-none">
        <div className="w-full h-full bg-gradient-to-b from-[oklch(0.72_0.18_265_/_0.15)] to-transparent rounded-full blur-2xl" />
      </div>

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
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe a game..."
            disabled={isGenerating}
            className="w-full bg-white/5 backdrop-blur-sm border border-[var(--color-border)] rounded-xl px-5 py-4 text-lg text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] disabled:opacity-50 transition-colors"
          />

          <button
            type="submit"
            disabled={isGenerating || !prompt.trim()}
            className="bg-[var(--color-accent)] text-white font-medium px-8 py-3 rounded-xl text-base hover:opacity-90 disabled:opacity-40 transition-opacity"
          >
            {isGenerating ? 'Generating...' : 'Generate Game'}
          </button>
        </form>

        {/* Example prompts */}
        <div className="flex flex-wrap justify-center gap-2">
          {EXAMPLE_PROMPTS.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => setPrompt(example)}
              className="bg-white/5 hover:bg-white/10 text-[var(--color-text-muted)] text-sm rounded-full px-4 py-2 cursor-pointer transition-colors"
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
