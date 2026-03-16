/** Status of the generation flow. */
export type Status = 'idle' | 'generating' | 'done' | 'error';

/** A single message in the chat panel. */
export interface ChatMessage {
  id: string;
  type: 'stage' | 'complete' | 'error';
  text: string;
}

/** A keyboard/mouse control mapping for the generated game. */
export interface ControlMapping {
  key: string;
  action: string;
}

/** Full state of the generation flow. */
export interface GenerationState {
  status: Status;
  messages: ChatMessage[];
  gameUrl: string | null;
  controls: ControlMapping[];
  errorMessage: string | null;
}

/** SSE event shape mirroring backend ProgressEvent. */
export interface SSEProgressEvent {
  type: 'stage_start' | 'done' | 'error';
  message: string;
  data: Record<string, unknown>;
}

/** Discriminated union of all generation actions. */
export type GenerationAction =
  | { type: 'SUBMIT' }
  | { type: 'SSE_STAGE'; message: string }
  | { type: 'SSE_DONE'; gameUrl: string; controls: ControlMapping[] }
  | { type: 'SSE_ERROR'; message: string }
  | { type: 'RESET' };

/** Initial generation state. */
export const initialState: GenerationState = {
  status: 'idle',
  messages: [],
  gameUrl: null,
  controls: [],
  errorMessage: null,
};

/** Reducer for generation state transitions. */
export function generationReducer(
  state: GenerationState,
  action: GenerationAction,
): GenerationState {
  switch (action.type) {
    case 'SUBMIT':
      return {
        ...state,
        status: 'generating',
        messages: [],
        gameUrl: null,
        controls: [],
        errorMessage: null,
      };

    case 'SSE_STAGE':
      return {
        ...state,
        messages: [
          ...state.messages,
          { id: crypto.randomUUID(), type: 'stage', text: action.message },
        ],
      };

    case 'SSE_DONE':
      return {
        ...state,
        status: 'done',
        gameUrl: action.gameUrl,
        controls: action.controls,
        messages: [
          ...state.messages,
          { id: crypto.randomUUID(), type: 'complete', text: 'Your game is ready!' },
        ],
      };

    case 'SSE_ERROR':
      return {
        ...state,
        status: 'error',
        errorMessage: action.message,
        messages: [
          ...state.messages,
          { id: crypto.randomUUID(), type: 'error', text: action.message },
        ],
      };

    case 'RESET':
      return {
        ...state,
        status: 'idle',
        messages: [],
        errorMessage: null,
        // Keep gameUrl and controls visible (game stays in iframe)
      };

    default:
      return state;
  }
}
