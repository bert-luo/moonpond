/** Status of the generation flow. */
export type Status = 'idle' | 'generating' | 'done' | 'error';

/** A single message in the chat panel. */
export interface ChatMessage {
  id: string;
  type: 'stage' | 'complete' | 'error' | 'spec_info' | 'file_written' | 'asset_generated' | 'controls';
  text: string;
  data?: Record<string, unknown>;
}

/** A keyboard/mouse control mapping for the generated game. */
export interface ControlMapping {
  key: string;
  action: string;
}

/** A single game generation session. */
export interface GameSession {
  id: string;
  title: string | null;
  description: string | null;
  status: Status;
  messages: ChatMessage[];
  gameUrl: string | null;
  controls: ControlMapping[];
  errorMessage: string | null;
}

/** Top-level app state holding multiple game sessions. */
export interface AppState {
  sessions: GameSession[];
  activeSessionIdx: number;
}

/** @deprecated Use AppState instead. Alias kept for backward compatibility during migration. */
export type GenerationState = GameSession;

/** SSE event shape mirroring backend ProgressEvent. */
export interface SSEProgressEvent {
  type: 'stage_start' | 'done' | 'error';
  message: string;
  data: Record<string, unknown>;
}

/** Create a fresh GameSession with default values. */
export function initialSession(): GameSession {
  return {
    id: crypto.randomUUID(),
    title: null,
    description: null,
    status: 'idle',
    messages: [],
    gameUrl: null,
    controls: [],
    errorMessage: null,
  };
}

/** Initial app state with one idle session. */
export const initialState: AppState = {
  sessions: [initialSession()],
  activeSessionIdx: 0,
};

/** Discriminated union of all generation actions. */
export type GenerationAction =
  | { type: 'NEW_SESSION' }
  | { type: 'SELECT_SESSION'; idx: number }
  | { type: 'SUBMIT'; sessionId: string }
  | { type: 'SSE_STAGE'; sessionId: string; message: string }
  | { type: 'SSE_SPEC_COMPLETE'; sessionId: string; title: string; description: string }
  | { type: 'SSE_FILE_WRITTEN'; sessionId: string; filename: string; lines: number }
  | { type: 'SSE_ASSET_GENERATED'; sessionId: string; assetName: string; dim: string }
  | { type: 'SSE_DONE'; sessionId: string; gameUrl: string; controls: ControlMapping[] }
  | { type: 'SSE_ERROR'; sessionId: string; message: string }
  | { type: 'RESET'; sessionId: string };

/**
 * Map over sessions, applying updater to the session matching the given ID.
 */
function updateSession(
  sessions: GameSession[],
  id: string,
  updater: (s: GameSession) => GameSession,
): GameSession[] {
  return sessions.map((s) => (s.id === id ? updater(s) : s));
}

/** Reducer for generation state transitions. */
export function generationReducer(
  state: AppState,
  action: GenerationAction,
): AppState {
  switch (action.type) {
    case 'NEW_SESSION': {
      const newSession = initialSession();
      return {
        sessions: [...state.sessions, newSession],
        activeSessionIdx: state.sessions.length,
      };
    }

    case 'SELECT_SESSION': {
      const idx = Math.max(0, Math.min(action.idx, state.sessions.length - 1));
      return { ...state, activeSessionIdx: idx };
    }

    case 'SUBMIT':
      return {
        ...state,
        sessions: updateSession(state.sessions, action.sessionId, (s) => ({
          ...s,
          status: 'generating' as const,
          messages: [],
          gameUrl: null,
          controls: [],
          errorMessage: null,
        })),
      };

    case 'SSE_STAGE':
      return {
        ...state,
        sessions: updateSession(state.sessions, action.sessionId, (s) => ({
          ...s,
          messages: [
            ...s.messages,
            { id: crypto.randomUUID(), type: 'stage' as const, text: action.message },
          ],
        })),
      };

    case 'SSE_SPEC_COMPLETE':
      return {
        ...state,
        sessions: updateSession(state.sessions, action.sessionId, (s) => ({
          ...s,
          title: action.title,
          description: action.description,
          messages: [
            ...s.messages,
            {
              id: crypto.randomUUID(),
              type: 'spec_info' as const,
              text: `Game: ${action.title}`,
              data: { title: action.title, description: action.description },
            },
          ],
        })),
      };

    case 'SSE_FILE_WRITTEN':
      return {
        ...state,
        sessions: updateSession(state.sessions, action.sessionId, (s) => ({
          ...s,
          messages: [
            ...s.messages,
            {
              id: crypto.randomUUID(),
              type: 'file_written' as const,
              text: `Generated ${action.filename} (${action.lines} lines)`,
              data: { filename: action.filename, lines: action.lines },
            },
          ],
        })),
      };

    case 'SSE_ASSET_GENERATED':
      return {
        ...state,
        sessions: updateSession(state.sessions, action.sessionId, (s) => ({
          ...s,
          messages: [
            ...s.messages,
            {
              id: crypto.randomUUID(),
              type: 'asset_generated' as const,
              text: `Generated ${action.dim ?? '2D'} asset: ${action.assetName}`,
              data: { assetName: action.assetName, dim: action.dim ?? '2D' },
            },
          ],
        })),
      };

    case 'SSE_DONE':
      return {
        ...state,
        sessions: updateSession(state.sessions, action.sessionId, (s) => ({
          ...s,
          status: 'done' as const,
          gameUrl: action.gameUrl,
          controls: action.controls,
          messages: [
            ...s.messages,
            { id: crypto.randomUUID(), type: 'complete' as const, text: 'Your game is ready!' },
            ...(action.controls.length > 0
              ? [{
                  id: crypto.randomUUID(),
                  type: 'controls' as const,
                  text: 'Controls',
                  data: { controls: action.controls },
                }]
              : []),
          ],
        })),
      };

    case 'SSE_ERROR':
      return {
        ...state,
        sessions: updateSession(state.sessions, action.sessionId, (s) => ({
          ...s,
          status: 'error' as const,
          errorMessage: action.message,
          messages: [
            ...s.messages,
            { id: crypto.randomUUID(), type: 'error' as const, text: action.message },
          ],
        })),
      };

    case 'RESET':
      return {
        ...state,
        sessions: updateSession(state.sessions, action.sessionId, (s) => ({
          ...s,
          status: 'idle' as const,
          messages: [],
          errorMessage: null,
        })),
      };

    default:
      return state;
  }
}
