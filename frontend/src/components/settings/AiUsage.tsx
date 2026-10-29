import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import api, { errorMessage } from '../../api';
import { CARD, ERROR } from '../../ui';

interface Usage {
    month: { user_name: string; calls: number }[];
    total: number;
}

// Who started how many AI calls this month; what they cost shows in Infomaniak's manager
export default function AiUsage() {
    const { t } = useTranslation();
    const [usage, setUsage] = useState<Usage | null>(null);
    const [enabled, setEnabled] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        let current = true;
        Promise.all([api.get<Usage>('/api/ai/usage'), api.get<{ enabled: boolean }>('/api/ai/status')])
            .then(([u, s]) => {
                if (!current) return;
                setUsage(u.data);
                setEnabled(s.data.enabled);
            })
            .catch((err) => current && setError(errorMessage(err)));
        return () => {
            current = false;
        };
    }, []);

    return (
        <section className={`${CARD} space-y-3`} aria-labelledby="ai-usage">
            <h2 id="ai-usage" className="text-lg">
                {t('settings.aiUsage')}
            </h2>
            {!enabled && <p className="text-sm text-amber-200">{t('errors.ai_off')}</p>}
            {usage && (
                <>
                    {usage.month.length === 0 ? (
                        <p className="text-sm text-slate-400">{t('settings.aiNoCalls')}</p>
                    ) : (
                        <ul className="text-sm">
                            {usage.month.map((row) => (
                                <li key={row.user_name}>
                                    {row.user_name}: {row.calls}
                                </li>
                            ))}
                        </ul>
                    )}
                    <p className="text-xs text-slate-400">{t('settings.aiTotal', { count: usage.total })}</p>
                </>
            )}
            {error && <p className={ERROR}>{error}</p>}
        </section>
    );
}
