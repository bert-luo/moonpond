import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  generationReducer,
  initialState,
  initialSession,
  type AppState,
  type GameSession,
} from '@/types/generation';

// Deterministic UUIDs for testing
let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  vi.stubGlobal('crypto', {
    randomUUID: () => `test-uuid-${++uuidCounter}`,
  });
});

function makeSession(overrides: Partial<GameSession> = {}): GameSession {
  return {
    id: `session-${++uuidCounter}`,
    title: null,
    description: null,
    status: 'idle',
    messages: [],
    gameUrl: null,
    jobId: null,
    controls: [],
    errorMessage: null,
    ...overrides,
  };
}

describe('initialState', () => {
  it('initializes with one idle session', () => {
    expect(initialState.sessions.length).toBe(1);
    expect(initialState.activeSessionIdx).toBe(0);
    expect(initialState.sessions[0].status).toBe('idle');
  });
});

describe('initialSession', () => {
  it('returns a new GameSession with default values', () => {
    const s = initialSession();
    expect(s.id).toBeTruthy();
    expect(s.title).toBeNull();
    expect(s.description).toBeNull();
    expect(s.status).toBe('idle');
    expect(s.messages).toEqual([]);
    expect(s.gameUrl).toBeNull();
    expect(s.controls).toEqual([]);
    expect(s.errorMessage).toBeNull();
  });
});

describe('generationReducer', () => {
  it('NEW_SESSION adds a session and sets activeSessionIdx to new index', () => {
    const state: AppState = { sessions: [makeSession()], activeSessionIdx: 0 };
    const next = generationReducer(state, { type: 'NEW_SESSION' });
    expect(next.sessions.length).toBe(2);
    expect(next.activeSessionIdx).toBe(1);
    expect(next.sessions[1].status).toBe('idle');
  });

  it('SELECT_SESSION updates activeSessionIdx without changing sessions', () => {
    const s0 = makeSession({ id: 's0' });
    const s1 = makeSession({ id: 's1' });
    const state: AppState = { sessions: [s0, s1], activeSessionIdx: 0 };
    const next = generationReducer(state, { type: 'SELECT_SESSION', idx: 1 });
    expect(next.activeSessionIdx).toBe(1);
    expect(next.sessions).toEqual(state.sessions);
  });

  it('SSE_STAGE with sessionId appends a stage message to the correct session', () => {
    const s0 = makeSession({ id: 's0' });
    const s1 = makeSession({ id: 's1' });
    const state: AppState = { sessions: [s0, s1], activeSessionIdx: 0 };
    const next = generationReducer(state, {
      type: 'SSE_STAGE',
      sessionId: 's1',
      message: 'Generating...',
    });
    // s1 gets the message, not s0
    expect(next.sessions[1].messages.length).toBe(1);
    expect(next.sessions[1].messages[0].type).toBe('stage');
    expect(next.sessions[1].messages[0].text).toBe('Generating...');
    expect(next.sessions[0].messages.length).toBe(0);
  });

  it('SSE_SPEC_COMPLETE sets title and description on the targeted session', () => {
    const s0 = makeSession({ id: 's0' });
    const state: AppState = { sessions: [s0], activeSessionIdx: 0 };
    const next = generationReducer(state, {
      type: 'SSE_SPEC_COMPLETE',
      sessionId: 's0',
      title: 'Space Blaster',
      description: 'A space shooter game',
    });
    expect(next.sessions[0].title).toBe('Space Blaster');
    expect(next.sessions[0].description).toBe('A space shooter game');
    // Should append a spec_info message
    expect(next.sessions[0].messages.length).toBe(1);
    expect(next.sessions[0].messages[0].type).toBe('spec_info');
    expect(next.sessions[0].messages[0].data).toEqual({
      title: 'Space Blaster',
      description: 'A space shooter game',
    });
  });

  it('SSE_FILE_WRITTEN appends a file_written message with filename and line count', () => {
    const s0 = makeSession({ id: 's0' });
    const state: AppState = { sessions: [s0], activeSessionIdx: 0 };
    const next = generationReducer(state, {
      type: 'SSE_FILE_WRITTEN',
      sessionId: 's0',
      filename: 'player.gd',
      lines: 42,
    });
    expect(next.sessions[0].messages.length).toBe(1);
    const msg = next.sessions[0].messages[0];
    expect(msg.type).toBe('file_written');
    expect(msg.text).toContain('player.gd');
    expect(msg.text).toContain('42');
    expect(msg.data).toEqual({ filename: 'player.gd', lines: 42 });
  });

  it('SSE_DONE sets status=done, gameUrl, appends complete and controls messages', () => {
    const s0 = makeSession({ id: 's0', status: 'generating' });
    const state: AppState = { sessions: [s0], activeSessionIdx: 0 };
    const controls = [{ key: 'arrow_left', action: 'move_left' }];
    const next = generationReducer(state, {
      type: 'SSE_DONE',
      sessionId: 's0',
      gameUrl: 'http://example.com/game',
      jobId: 'job-1',
      controls,
    });
    expect(next.sessions[0].status).toBe('done');
    expect(next.sessions[0].gameUrl).toBe('http://example.com/game');
    expect(next.sessions[0].controls).toEqual(controls);
    // Should have complete message AND controls message
    expect(next.sessions[0].messages.length).toBe(2);
    expect(next.sessions[0].messages[0].type).toBe('complete');
    expect(next.sessions[0].messages[1].type).toBe('controls');
    expect(next.sessions[0].messages[1].data).toEqual({ controls });
  });

  it('SSE_ERROR sets status=error and appends error message', () => {
    const s0 = makeSession({ id: 's0', status: 'generating' });
    const state: AppState = { sessions: [s0], activeSessionIdx: 0 };
    const next = generationReducer(state, {
      type: 'SSE_ERROR',
      sessionId: 's0',
      message: 'Something went wrong',
    });
    expect(next.sessions[0].status).toBe('error');
    expect(next.sessions[0].errorMessage).toBe('Something went wrong');
    expect(next.sessions[0].messages.length).toBe(1);
    expect(next.sessions[0].messages[0].type).toBe('error');
    expect(next.sessions[0].messages[0].text).toBe('Something went wrong');
  });

  it('RESET keeps gameUrl and controls but sets status=idle and clears messages', () => {
    const s0 = makeSession({
      id: 's0',
      status: 'done',
      gameUrl: 'http://example.com/game',
      controls: [{ key: 'space', action: 'jump' }],
      messages: [{ id: 'm1', type: 'complete', text: 'Done' }],
      errorMessage: 'old error',
    });
    const state: AppState = { sessions: [s0], activeSessionIdx: 0 };
    const next = generationReducer(state, { type: 'RESET', sessionId: 's0' });
    expect(next.sessions[0].status).toBe('idle');
    expect(next.sessions[0].messages).toEqual([]);
    expect(next.sessions[0].errorMessage).toBeNull();
    // Kept
    expect(next.sessions[0].gameUrl).toBe('http://example.com/game');
    expect(next.sessions[0].controls).toEqual([{ key: 'space', action: 'jump' }]);
  });

  it('SUBMIT clears session state and sets status=generating', () => {
    const s0 = makeSession({
      id: 's0',
      status: 'done',
      gameUrl: 'http://old.com',
      controls: [{ key: 'a', action: 'move' }],
      messages: [{ id: 'm1', type: 'complete', text: 'Done' }],
    });
    const state: AppState = { sessions: [s0], activeSessionIdx: 0 };
    const next = generationReducer(state, { type: 'SUBMIT', sessionId: 's0' });
    expect(next.sessions[0].status).toBe('generating');
    expect(next.sessions[0].messages).toEqual([]);
    expect(next.sessions[0].gameUrl).toBeNull();
    expect(next.sessions[0].controls).toEqual([]);
    expect(next.sessions[0].errorMessage).toBeNull();
  });
});
