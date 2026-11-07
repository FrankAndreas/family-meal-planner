import { useCallback, useEffect, useRef, useState } from 'react';
import { errorMessage } from '../api';

export type SaveStatus = 'idle' | 'saving' | 'saved';

interface AutoSaveOptions<T> {
    // Saves the changed fields; answers with the whole saved object
    save: (fields: Partial<T>) => Promise<T>;
    // The same, as a request that outlives the page (sent while it closes or hides)
    saveOnLeave?: (fields: Partial<T>) => Promise<T>;
    // A save's answer, with the fields it was for; `changedSince(key)`: that field was changed again meanwhile, so
    // what's shown is newer than the answer
    onSaved?: (saved: T, fields: Partial<T>, changedSince: (key: keyof T) => boolean) => void;
}

// Saved as soon as something changes (UX review 2026-11-06), one request after the other, so an older answer never
// wins over a newer change. A failed save isn't lost: it goes again with the next change, unless that change replaced
// it. Leaving the page, closing or hiding the tab sends what's still waiting.
export function useAutoSave<T extends object>(options: AutoSaveOptions<T>) {
    const [status, setStatus] = useState<SaveStatus>('idle');
    const [error, setError] = useState('');
    // The caller's functions as of the last render, so the ones below stay the same for the page's whole life
    const latest = useRef(options);
    useEffect(() => {
        latest.current = options;
    });
    const pending = useRef<Partial<T>>({});
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const queue = useRef<Promise<void>>(Promise.resolve());
    const sending = useRef(0);
    // How often each field was changed: an answer is older than the field if it changed since
    const versions = useRef(new Map<keyof T, number>());

    const waiting = useCallback(
        () => timer.current !== null || Object.keys(pending.current).length > 0 || sending.current > 0,
        [],
    );

    // What's waiting leaves pending, with the field versions it was sent at
    const take = useCallback(() => {
        if (timer.current) clearTimeout(timer.current);
        timer.current = null;
        const fields = pending.current;
        pending.current = {};
        sending.current += 1;
        return { fields, versions: new Map(versions.current) };
    }, []);

    // The answer is applied here, whichever way it was sent
    const settle = useCallback(
        async (fields: Partial<T>, sentAt: Map<keyof T, number>, request: () => Promise<T>) => {
            try {
                const saved = await request();
                sending.current -= 1;
                latest.current.onSaved?.(saved, fields, (key) => versions.current.get(key) !== sentAt.get(key));
                setError('');
                // Only "saved" once nothing else waits
                if (!waiting()) setStatus('saved');
            } catch (err) {
                sending.current -= 1;
                pending.current = { ...fields, ...pending.current };
                setError(errorMessage(err));
                setStatus('idle');
            }
        },
        [waiting],
    );

    const send = useCallback(() => {
        const { fields, versions: sentAt } = take();
        queue.current = queue.current.then(() => settle(fields, sentAt, () => latest.current.save(fields)));
    }, [take, settle]);

    // `wait`: a pause before sending, so typing "12" isn't saved as 1 first; a newer change restarts it
    const change = useCallback(
        (fields: Partial<T>, wait = 0) => {
            pending.current = { ...pending.current, ...fields };
            for (const key of Object.keys(fields) as (keyof T)[])
                versions.current.set(key, (versions.current.get(key) ?? 0) + 1);
            setStatus('saving');
            if (timer.current) clearTimeout(timer.current);
            timer.current = setTimeout(send, wait);
        },
        [send],
    );

    // A change that isn't one after all (a half-typed number) leaves what's waiting
    const drop = useCallback(
        (key: keyof T) => {
            delete pending.current[key];
            if (timer.current && !Object.keys(pending.current).length) {
                clearTimeout(timer.current);
                timer.current = null;
            }
            if (!waiting()) setStatus('idle');
        },
        [waiting],
    );

    // Leaving the page doesn't lose a change that is still waiting
    useEffect(
        () => () => {
            if (Object.keys(pending.current).length) send();
        },
        [send],
    );

    // Closing, reloading or hiding the tab doesn't wait for the pause or the next change: a request that outlives the
    // page takes what's waiting. If the page comes back (back button, tab shown again), its answer counts
    useEffect(() => {
        const leave = () => {
            const onLeave = latest.current.saveOnLeave;
            if (!onLeave || !Object.keys(pending.current).length) return;
            const { fields, versions: sentAt } = take();
            // Sent now, while the page still exists; settle only waits for its answer
            const request = onLeave(fields);
            void settle(fields, sentAt, () => request);
        };
        const hidden = () => document.visibilityState === 'hidden' && leave();
        window.addEventListener('pagehide', leave);
        document.addEventListener('visibilitychange', hidden);
        return () => {
            window.removeEventListener('pagehide', leave);
            document.removeEventListener('visibilitychange', hidden);
        };
    }, [take, settle]);

    return { status, error, setError, change, drop };
}
