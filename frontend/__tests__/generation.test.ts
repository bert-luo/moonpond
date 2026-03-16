import { describe, it, expect } from 'vitest';
import { generationReducer, initialState } from '@/types/generation';

describe('generationReducer', () => {
  it('should return initial state', () => {
    expect(initialState.status).toBe('idle');
  });

  it.todo('SUBMIT resets state and sets status to generating');
  it.todo('SSE_STAGE appends a stage message');
  it.todo('SSE_DONE sets gameUrl and controls');
  it.todo('SSE_ERROR sets error message');
  it.todo('RESET sets status to idle but keeps gameUrl');
});
