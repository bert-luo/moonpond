import { describe, it } from 'vitest';

describe('useGeneration', () => {
  it.todo('submit dispatches SUBMIT then opens EventSource');
  it.todo('stage_start event dispatches SSE_STAGE');
  it.todo('done event dispatches SSE_DONE and closes EventSource');
  it.todo('error event dispatches SSE_ERROR and closes EventSource');
  it.todo('cleanup closes EventSource on unmount');
});
