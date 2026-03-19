'use client';

import { useCallback, useEffect, useRef } from 'react';
import type { GenerationAction, ControlMapping } from '@/types/generation';

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8000';

/**
 * SSE client hook that orchestrates the fetch + EventSource lifecycle.
 * Receives a dispatch function and returns { submit }.
 */
export function useGeneration(dispatch: React.Dispatch<GenerationAction>) {
  const esRef = useRef<EventSource | null>(null);

  const submit = useCallback(
    async (prompt: string) => {
      // Close previous connection if any
      esRef.current?.close();
      esRef.current = null;

      dispatch({ type: 'SUBMIT' });

      // Step 1: POST to start generation
      let jobId: string;
      try {
        const res = await fetch(`${BACKEND}/api/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt }),
        });
        if (!res.ok) {
          const text = await res.text().catch(() => res.statusText);
          dispatch({ type: 'SSE_ERROR', message: `Server error: ${text}` });
          return;
        }
        const body = await res.json();
        jobId = body.job_id;
      } catch (err) {
        dispatch({
          type: 'SSE_ERROR',
          message: err instanceof Error ? err.message : 'Network error',
        });
        return;
      }

      // Step 2: Open SSE stream
      const es = new EventSource(`${BACKEND}/api/stream/${jobId}`);
      esRef.current = es;

      // Named event: stage_start
      es.addEventListener('stage_start', (e: Event) => {
        const me = e as MessageEvent;
        try {
          const event = JSON.parse(me.data);
          dispatch({ type: 'SSE_STAGE', message: event.message });
        } catch {
          dispatch({ type: 'SSE_STAGE', message: me.data });
        }
      });

      // Named event: done
      es.addEventListener('done', (e: Event) => {
        // Close BEFORE dispatching so onerror sees esRef.current !== es and skips
        es.close();
        esRef.current = null;

        const me = e as MessageEvent;
        try {
          const event = JSON.parse(me.data);
          const data = event.data ?? event;
          // Use wasm_path from the backend (contains the actual game directory name)
          const gameUrl = data.wasm_path
            ? `${BACKEND}${data.wasm_path}`
            : `${BACKEND}/games/${data.job_id ?? jobId}/export/index.html`;
          const controls: ControlMapping[] = Array.isArray(data.controls)
            ? data.controls
            : [];
          dispatch({ type: 'SSE_DONE', gameUrl, controls });
        } catch {
          // Fallback if parsing fails
          const gameUrl = `${BACKEND}/games/${jobId}/export/index.html`;
          dispatch({ type: 'SSE_DONE', gameUrl, controls: [] });
        }
      });

      // Named event: error (backend-emitted error event)
      es.addEventListener('error', (e: Event) => {
        // Skip if already closed (e.g. after a successful done event)
        if (esRef.current !== es) return;
        const me = e as MessageEvent;
        // MessageEvent has .data, generic Event (network error) does not
        if (me.data !== undefined) {
          try {
            const event = JSON.parse(me.data);
            dispatch({ type: 'SSE_ERROR', message: event.message ?? 'Unknown error' });
          } catch {
            dispatch({ type: 'SSE_ERROR', message: me.data ?? 'Unknown error' });
          }
          es.close();
          esRef.current = null;
        }
        // If no .data, this is a network error handled by onerror below
      });

      // Network failure handler (separate from named error events)
      es.onerror = () => {
        // Only dispatch if connection is actually failing (not already closed)
        if (esRef.current === es) {
          dispatch({ type: 'SSE_ERROR', message: 'Connection lost' });
          es.close();
          esRef.current = null;
        }
      };
    },
    [dispatch],
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      esRef.current?.close();
      esRef.current = null;
    };
  }, []);

  return { submit };
}
