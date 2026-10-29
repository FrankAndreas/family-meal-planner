import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import api, { errorMessage } from '../../api';
import { WEEKDAYS, type FamilySettings as Settings } from '../../types';
import { BUTTON, CARD, ERROR, FIELD } from '../../ui';

export default function FamilySettings() {
    const { t } = useTranslation();
    const [settings, setSettings] = useState<Settings | null>(null);
    const [saved, setSaved] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        // A late answer must not overwrite what someone already typed
        let current = true;
        api.get<Settings>('/api/settings')
            .then((response) => current && setSettings(response.data))
            .catch((err) => current && setError(errorMessage(err)));
        return () => {
            current = false;
        };
    }, []);

    const save = async (e: FormEvent) => {
        e.preventDefault();
        if (!settings) return;
        setError('');
        setSaved(false);
        try {
            setSettings((await api.patch<Settings>('/api/settings', settings)).data);
            setSaved(true);
        } catch (err) {
            setError(errorMessage(err));
        }
    };

    return (
        <section className={`${CARD} space-y-4`}>
            <h2 className="text-lg">{t('settings.family')}</h2>
            {settings && (
                <form onSubmit={save} className="space-y-4">
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
                                value={settings.family_size}
                                onChange={(e) => setSettings({ ...settings, family_size: Number(e.target.value) })}
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
                                onChange={(e) => setSettings({ ...settings, week_start: Number(e.target.value) })}
                            >
                                {WEEKDAYS.map((day, number) => (
                                    <option key={day} value={number}>
                                        {t(`weekdays.${day}`)}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>
                    <button type="submit" className={BUTTON} aria-label={t('settings.saveFamily')}>
                        {t('common.save')}
                    </button>
                    {saved && <span className="ml-3 text-sm text-emerald-300">{t('common.saved')}</span>}
                </form>
            )}
            {error && <p className={ERROR}>{error}</p>}
        </section>
    );
}
