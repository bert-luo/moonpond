'use client';

import { useReducer } from 'react';
import { generationReducer, initialState } from '@/types/generation';
import { useGeneration } from '@/hooks/useGeneration';
import { ChatPanel } from './components/ChatPanel';
import { GameViewer } from './components/GameViewer';

export default function Home() {
  const [state, dispatch] = useReducer(generationReducer, initialState);
  const { submit } = useGeneration(dispatch);
  const handleReset = () => dispatch({ type: 'RESET' });

  return (
    <main className="flex h-screen">
      {/* ChatPanel: fixed width sidebar on the left */}
      <div className="w-[420px] min-w-[320px] flex-shrink-0 flex flex-col border-r border-[var(--color-border)] bg-[var(--color-bg)]">
        <ChatPanel state={state} onSubmit={submit} onReset={handleReset} />
      </div>
      {/* GameViewer: fills remaining space — the hero */}
      <div className="flex-1 flex items-center justify-center p-6 bg-black/20">
        <GameViewer status={state.status} gameUrl={state.gameUrl} stageMessage={state.messages.filter(m => m.type === 'stage').at(-1)?.text ?? null} />
      </div>
    </main>
  );
}
