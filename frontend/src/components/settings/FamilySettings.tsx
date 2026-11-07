import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { errorMessage } from '../../api';
import { fetchSettings, saveSettings, saveSettingsOnLeave } from '../../settings';
import { WEEKDAYS, type FamilySettings as Settings } from '../../types';
import { CARD, ERROR, FIELD } from '../../ui';
import IngredientChips from '../recipes/IngredientChips';

export default function FamilySettings() {
    const { t } = useTranslation();
    const [settings, setSettings] = useState<Settings | null>(null);
    const [status, setStatus] = useState<'idle' | 'saving' | 'saved'>('idle');
    const [error, setError] = useState('');
    // Saved as soon as something changes, like the mail addresses and Bring! (UX review 2026-11-06).
    // What's still to send, one request after the other, so an older answer never wins over a newer change
    const pending = useRef<Partial<Settings>>({});
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const queue = useRef<Promise<void>>(Promise.resolve());
    const sending = useRef(0);
    // Counts staples changes: the server's cleaned staples are shown only for the newest one
    const staplesVersion = useRef(0);
    // The family size last saved: a size that isn't one yet (an empty field) goes back to it
    const savedSize = useRef(0);

    useEffect(() => {
        // A late answer must not overwrite what someone already typed
        let current = true;
        fetchSettings()
            .then((loaded) => {
                if (!current) return;
                savedSize.current = loaded.family_size;
                setSettings(loaded);
            })
            .catch((err) => current && setError(errorMessage(err)));
        return () => {
            current = false;
        };
    }, []);

    const waiting = useCallback(
        () => timer.current !== null || Object.keys(pending.current).length > 0 || sending.current > 0,
        [],
    );

    // What's waiting leaves pending; the answer is applied here, whichever way it was sent.
    // Uses only refs and state setters, so the same functions for the page's whole life
    const take = useCallback(() => {
        if (timer.current) clearTimeout(timer.current);
        timer.current = null;
        const fields = pending.current;
        pending.current = {};
        sending.current += 1;
        return { fields, version: staplesVersion.current };
    }, []);

    const settle = useCallback(
        async (fields: Partial<Settings>, version: number, request: () => Promise<Settings>) => {
            try {
                const saved = await request();
                savedSize.current = saved.family_size;
                // The server's staples, cleaned (it keeps "Straße" and "STRASSE" once), unless they changed since
                if (fields.staples && version === staplesVersion.current)
                    setSettings((shown) => (shown ? { ...shown, staples: saved.staples } : shown));
                sending.current -= 1;
                setError('');
                // Only "saved" once nothing else waits
                if (!waiting()) setStatus('saved');
            } catch (err) {
                sending.current -= 1;
                // Not lost: sent again with the next change, unless that change replaced it
                pending.current = { ...fields, ...pending.current };
                setError(errorMessage(err));
                setStatus('idle');
            }
        },
        [waiting],
    );

    const send = useCallback(() => {
        const { fields, version } = take();
        queue.current = queue.current.then(() =>
            settle(fields, version, () => saveSettings(fields)),
        );
    }, [take, settle]);

    // Typing a number waits a moment, so "12" isn't saved as 1 first; everything else goes at once
    const change = (fields: Partial<Settings>, wait = 0) => {
        setSettings((shown) => (shown ? { ...shown, ...fields } : shown));
        pending.current = { ...pending.current, ...fields };
        if (fields.staples) staplesVersion.current += 1;
        setStatus('saving');
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(send, wait);
    };

    // Leaving the page doesn't lose a change that is still waiting
    useEffect(
        () => () => {
            if (Object.keys(pending.current).length) send();
        },
        [send],
    );

    // Closing, reloading or hiding the tab doesn't wait for the size's pause or the next change: a request that
    // outlives the page takes what's waiting. If the page comes back (back button, tab shown again), its answer counts
    useEffect(() => {
        const leave = () => {
            if (!Object.keys(pending.current).length) return;
            const { fields, version } = take();
            // Sent now, while the page still exists; settle only waits for its answer
            const request = saveSettingsOnLeave(fields);
            void settle(fields, version, () => request);
        };
        const hidden = () => document.visibilityState === 'hidden' && leave();
        window.addEventListener('pagehide', leave);
        document.addEventListener('visibilitychange', hidden);
        return () => {
            window.removeEventListener('pagehide', leave);
            document.removeEventListener('visibilitychange', hidden);
        };
    }, [take, settle]);

    const changeSize = (text: string) => {
        const size = Number(text);
        if (text !== '' && Number.isInteger(size) && size >= 1 && size <= 20) {
            change({ family_size: size }, 600);
            return;
        }
        setSettings((shown) => (shown ? { ...shown, family_size: text === '' ? NaN : size } : shown));
        // A half-typed size before it ("2" of "25") isn't saved either
        delete pending.current.family_size;
        if (timer.current && !Object.keys(pending.current).length) {
            clearTimeout(timer.current);
            timer.current = null;
        }
        if (!waiting()) setStatus('idle');
    };

    return (
        <section className={`${CARD} space-y-4`}>
            <h2 className="text-lg">{t('settings.family')}</h2>
            {settings && (
                <div className="space-y-4">
                    <div className="grid gap-4 sm:grid-cols-2">
                        <div>
                            <label htmlFor="family-size" className="mb-1 block text-sm text-slate-300">
                                {t('settings.familySize')}
                            </label>
                            <input
                                id="family-size"
                                type="number"
                                min={1}
                                max={20}
                                className={`${FIELD} w-24`}
                                value={Number.isNaN(settings.family_size) ? '' : settings.family_size}
                                onChange={(e) => changeSize(e.target.value)}
                                onBlur={() => {
                                    const size = settings.family_size;
                                    if (!(Number.isInteger(size) && size >= 1 && size <= 20))
                                        setSettings({ ...settings, family_size: savedSize.current });
                                }}
                            />
                            <p className="mt-1 text-xs text-slate-400">{t('settings.familySizeHint')}</p>
                        </div>
                        <div>
                            <label htmlFor="week-start" className="mb-1 block text-sm text-slate-300">
                                {t('settings.weekStart')}
                            </label>
                            <select
                                id="week-start"
                                className={FIELD}
                                value={settings.week_start}
                                onChange={(e) => change({ week_start: Number(e.target.value) })}
                            >
                                {WEEKDAYS.map((day, number) => (
                                    <option key={day} value={number}>
                                        {t(`weekdays.${day}`)}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>
                    <div>
                        <IngredientChips
                            values={settings.staples}
                            onChange={(staples) => change({ staples })}
                            label={t('settings.staples')}
                            // As many as the server takes (backend/app/schemas.py SettingsPatch)
                            max={50}
                        />
                        <p className="mt-1 text-xs text-slate-400">{t('settings.staplesHint')}</p>
                    </div>
                    <p role="status" className="min-h-5 text-sm text-emerald-300">
                        {status === 'saving' ? t('common.saving') : status === 'saved' && !error ? t('common.saved') : ''}
                    </p>
                </div>
            )}
            {error && (
                <p role="alert" className={ERROR}>
                    {error}
                </p>
            )}
        </section>
    );
}
