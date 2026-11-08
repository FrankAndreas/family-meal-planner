import { useCallback, useEffect, useRef, useState } from 'react';
import { errorMessage } from '../api';
import { AutoSaver, type AutoSaveOptions, type SaveStatus } from '../autoSave';

export type { SaveStatus } from '../autoSave';

// The page's side of the auto-save engine (autoSave.ts, where the rules are and are tested): its status and error as
// state, the newest options each render, and sending what's waiting when the page goes away or the tab closes
export function useAutoSave<T extends object>(options: AutoSaveOptions<T>) {
    const [status, setStatus] = useState<SaveStatus>('idle');
    const [error, setError] = useState('');
    // The caller's functions as of the last render; the engine reads them when it needs them
    const latest = useRef(options);
    useEffect(() => {
        latest.current = options;
    });
    // One engine for the page's whole life, made on first use (never while rendering)
    const engine = useRef<AutoSaver<T> | null>(null);
    const saver = useCallback(() => {
        engine.current ??= new AutoSaver<T>(() => latest.current, {
            status: setStatus,
            error: (e) => setError(e === null ? '' : errorMessage(e)),
        });
        return engine.current;
    }, []);

    // Leaving the page doesn't lose a change that is still waiting
    useEffect(() => () => saver().flush(), [saver]);

    // Closing, reloading or hiding the tab doesn't wait for the pause or the next change
    useEffect(() => {
        const leave = () => saver().leave();
        const hidden = () => document.visibilityState === 'hidden' && leave();
        window.addEventListener('pagehide', leave);
        document.addEventListener('visibilitychange', hidden);
        return () => {
            window.removeEventListener('pagehide', leave);
            document.removeEventListener('visibilitychange', hidden);
        };
    }, [saver]);

    const change = useCallback((fields: Partial<T>, wait = 0) => saver().change(fields, wait), [saver]);
    const drop = useCallback((key: keyof T) => saver().drop(key), [saver]);
    return { status, error, setError, change, drop };
}
