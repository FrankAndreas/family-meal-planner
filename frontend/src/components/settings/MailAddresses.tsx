import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import api, { errorMessage } from '../../api';
import { useAuth } from '../../AuthContext';
import type { User } from '../../types';
import { BUTTON, CARD, ERROR, FIELD, INPUT } from '../../ui';

interface MailAddress {
    id: number;
    user_id: number;
    user_name: string;
    address: string;
}

// The addresses recipes may be mailed from: everyone their own, parents everybody's
export default function MailAddresses() {
    const { t } = useTranslation();
    const { user } = useAuth();
    const parent = user?.role === 'PARENT';
    const [addresses, setAddresses] = useState<MailAddress[]>([]);
    const [people, setPeople] = useState<User[]>([]);
    const [address, setAddress] = useState('');
    const [owner, setOwner] = useState<number | ''>('');
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        setAddresses((await api.get<MailAddress[]>('/api/emails', { params: parent ? { all: 1 } : {} })).data);
    }, [parent]);

    useEffect(() => {
        let current = true;
        api.get<MailAddress[]>('/api/emails', { params: parent ? { all: 1 } : {} })
            .then((r) => current && setAddresses(r.data))
            .catch((err) => current && setError(errorMessage(err)));
        if (parent) {
            api.get<User[]>('/api/users')
                .then((r) => current && setPeople(r.data))
                .catch(() => {});
        }
        return () => {
            current = false;
        };
    }, [parent]);

    const run = async (action: () => Promise<unknown>) => {
        setError('');
        try {
            await action();
            await load();
            return true;
        } catch (err) {
            setError(errorMessage(err));
            return false;
        }
    };

    const add = async (e: FormEvent) => {
        e.preventDefault();
        const body = { address, ...(owner ? { user_id: owner } : {}) };
        if (await run(() => api.post('/api/emails', body))) setAddress('');
    };

    return (
        <section className={`${CARD} space-y-4`} aria-labelledby="mail-addresses">
            <div>
                <h2 id="mail-addresses" className="text-lg">
                    {t('settings.mailAddresses')}
                </h2>
                <p className="text-sm text-slate-400">{t('settings.mailAddressesHint')}</p>
            </div>
            <ul className="divide-y divide-white/10">
                {addresses.map((entry) => (
                    <li key={entry.id} className="flex items-center gap-2 py-2">
                        <span className="mr-auto">
                            {entry.address}
                            {parent && <span className="ml-2 text-xs text-slate-400">{entry.user_name}</span>}
                        </span>
                        <button
                            type="button"
                            className="text-sm text-red-300 hover:text-red-200"
                            onClick={() => run(() => api.delete(`/api/emails/${entry.id}`))}
                        >
                            {t('common.delete')}
                        </button>
                    </li>
                ))}
            </ul>
            <form onSubmit={add} className="flex flex-wrap gap-2">
                <input
                    className={`${INPUT} min-w-60 flex-1`}
                    type="email"
                    aria-label={t('settings.newMailAddress')}
                    placeholder={t('settings.newMailAddressPlaceholder')}
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                />
                {parent && (
                    <select
                        className={FIELD}
                        aria-label={t('settings.mailAddressOf')}
                        value={owner}
                        onChange={(e) => setOwner(e.target.value ? Number(e.target.value) : '')}
                    >
                        <option value="">{t('settings.mine')}</option>
                        {people
                            .filter((p) => p.id !== user?.id)
                            .map((p) => (
                                <option key={p.id} value={p.id}>
                                    {p.name}
                                </option>
                            ))}
                    </select>
                )}
                <button type="submit" className={BUTTON} disabled={!address.trim()}>
                    {t('settings.addMailAddress')}
                </button>
            </form>
            {error && <p className={ERROR}>{error}</p>}
        </section>
    );
}
