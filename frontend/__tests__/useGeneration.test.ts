import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useGeneration } from '@/hooks/useGeneration';

// --- Mock EventSource ---
type Listener = (e: Event) => void;

class MockEventSource {
  static instance: MockEventSource | null = null;
  url: string;
  listeners: Record<string, Listener[]> = {};
  onerror: ((e: Event) => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instance = this;
  }

  addEventListener(type: string, listener: Listener) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(listener);
  }

  close() {
    this.closed = true;
  }

  // Test helper: simulate a named SSE event
  emit(type: string, data: string) {
    const event = { data } as MessageEvent;
    for (const fn of this.listeners[type] ?? []) {
      fn(event);
    }
  }
}

// --- Setup ---
const SESSION_ID = 'test-session-1';

let dispatch: ReturnType<typeof vi.fn>;

beforeEach(() => {
  dispatch = vi.fn();
  vi.stubGlobal('EventSource', MockEventSource);
  vi.stubGlobal('fetch', vi.fn());
  MockEventSource.instance = null;
});

afterEach(() => {
  vi.restoreAllMocks();
});

function mockFetchSuccess(jobId = 'job-1') {
  (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: true,
    json: async () => ({ job_id: jobId }),
  });
}

describe('useGeneration', () => {
  it('submit dispatches SUBMIT with sessionId then opens EventSource', async () => {
    mockFetchSuccess();
    const { result } = renderHook(() => useGeneration(dispatch));

    await act(async () => {
      await result.current.submit('make a game', SESSION_ID);
    });

    expect(dispatch).toHaveBeenCalledWith({ type: 'SUBMIT', sessionId: SESSION_ID });
    expect(MockEventSource.instance).toBeTruthy();
    expect(MockEventSource.instance!.url).toContain('/api/stream/job-1');
  });

  it('stage_start event dispatches SSE_STAGE with sessionId', async () => {
    mockFetchSuccess();
    const { result } = renderHook(() => useGeneration(dispatch));

    await act(async () => {
      await result.current.submit('make a game', SESSION_ID);
    });

    const es = MockEventSource.instance!;
    act(() => {
      es.emit('stage_start', JSON.stringify({ message: 'Designing...' }));
    });

    expect(dispatch).toHaveBeenCalledWith({
      type: 'SSE_STAGE',
      sessionId: SESSION_ID,
      message: 'Designing...',
    });
  });

  it('spec_complete event dispatches SSE_SPEC_COMPLETE with title and description', async () => {
    mockFetchSuccess();
    const { result } = renderHook(() => useGeneration(dispatch));

    await act(async () => {
      await result.current.submit('make a game', SESSION_ID);
    });

    const es = MockEventSource.instance!;
    act(() => {
      es.emit(
        'spec_complete',
        JSON.stringify({
          data: { title: 'Space Blaster', description: 'A space shooter', genre: 'shooter' },
        }),
      );
    });

    expect(dispatch).toHaveBeenCalledWith({
      type: 'SSE_SPEC_COMPLETE',
      sessionId: SESSION_ID,
      title: 'Space Blaster',
      description: 'A space shooter',
    });
  });

  it('file_generated event dispatches SSE_FILE_WRITTEN with filename and bytes', async () => {
    mockFetchSuccess();
    const { result } = renderHook(() => useGeneration(dispatch));

    await act(async () => {
      await result.current.submit('make a game', SESSION_ID);
    });

    const es = MockEventSource.instance!;
    act(() => {
      es.emit(
        'file_generated',
        JSON.stringify({
          data: { filename: 'player.gd', size_bytes: 2048 },
        }),
      );
    });

    expect(dispatch).toHaveBeenCalledWith({
      type: 'SSE_FILE_WRITTEN',
      sessionId: SESSION_ID,
      filename: 'player.gd',
      bytes: 2048,
    });
  });

  it('done event dispatches SSE_DONE with sessionId and closes EventSource', async () => {
    mockFetchSuccess();
    const { result } = renderHook(() => useGeneration(dispatch));

    await act(async () => {
      await result.current.submit('make a game', SESSION_ID);
    });

    const es = MockEventSource.instance!;
    act(() => {
      es.emit(
        'done',
        JSON.stringify({
          data: { job_id: 'job-1', controls: [{ key: 'space', action: 'jump' }] },
        }),
      );
    });

    expect(dispatch).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'SSE_DONE',
        sessionId: SESSION_ID,
        controls: [{ key: 'space', action: 'jump' }],
      }),
    );
    expect(es.closed).toBe(true);
  });

  it('error event dispatches SSE_ERROR with sessionId and closes EventSource', async () => {
    mockFetchSuccess();
    const { result } = renderHook(() => useGeneration(dispatch));

    await act(async () => {
      await result.current.submit('make a game', SESSION_ID);
    });

    const es = MockEventSource.instance!;
    act(() => {
      es.emit('error', JSON.stringify({ message: 'Pipeline failed' }));
    });

    expect(dispatch).toHaveBeenCalledWith({
      type: 'SSE_ERROR',
      sessionId: SESSION_ID,
      message: 'Pipeline failed',
    });
    expect(es.closed).toBe(true);
  });

  it('cleanup closes EventSource on unmount', async () => {
    mockFetchSuccess();
    const { result, unmount } = renderHook(() => useGeneration(dispatch));

    await act(async () => {
      await result.current.submit('make a game', SESSION_ID);
    });

    const es = MockEventSource.instance!;
    expect(es.closed).toBe(false);

    unmount();
    expect(es.closed).toBe(true);
  });
});
