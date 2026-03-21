'use client';

import { useReducer } from 'react';
import { generationReducer, initialState } from '@/types/generation';
import { useGeneration } from '@/hooks/useGeneration';
import { LandingPage } from './components/LandingPage';
import { GameTabs } from './components/GameTabs';
import { ChatPanel } from './components/ChatPanel';
import { GameViewer } from './components/GameViewer';

export default function Home() {
  const [state, dispatch] = useReducer(generationReducer, initialState);
  const { submit } = useGeneration(dispatch);

  const activeSession = state.sessions[state.activeSessionIdx];

  // Landing page shows only when every session is idle (no game ever started)
  const showLanding = state.sessions.every((s) => s.status === 'idle');

  const handleSubmit = (prompt: string) => {
    submit(prompt, activeSession.id);
  };

  return (
    <main className="flex h-screen relative">
      {showLanding && (
        <LandingPage
          onSubmit={handleSubmit}
          isGenerating={activeSession.status === 'generating'}
        />
      )}
      <div className={showLanding ? 'hidden' : 'flex w-full h-full'}>
        {/* Left column: tabs + chat */}
        <div className="w-[420px] min-w-[320px] flex-shrink-0 flex flex-col border-r border-[var(--color-border)] bg-[var(--color-bg)]">
          <GameTabs
            sessions={state.sessions}
            activeIdx={state.activeSessionIdx}
            onSelect={(idx) => dispatch({ type: 'SELECT_SESSION', idx })}
            onNew={() => dispatch({ type: 'NEW_SESSION' })}
          />
          <ChatPanel session={activeSession} onSubmit={handleSubmit} />
        </div>
        {/* Right column: game viewer */}
        <div className="flex-1 flex items-center justify-center p-6 bg-black/20">
          <GameViewer
            status={activeSession.status}
            gameUrl={activeSession.gameUrl}
            stageMessage={activeSession.messages.filter((m) => m.type === 'stage').at(-1)?.text ?? null}
          />
        </div>
      </div>
    </main>
  );
}
