import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { errorMessage } from '../../api';
import type { User } from '../../types';
import { deleteUser, fetchRemovedUsers, fetchUsers } from '../../users';
import { BUTTON_DANGER, CARD, ERROR } from '../../ui';

// The planner's people come from the family hub (spec 2026-10-30): added, renamed and given access there. Someone the
// hub no longer lists is hidden here with their stars and favourites until a parent deletes them
export default function FamilyMembers() {
    const { t } = useTranslation();
    const [users, setUsers] = useState<User[]>([]);
    const [removed, setRemoved] = useState<User[]>([]);
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        const [active, hidden] = await Promise.all([fetchUsers(), fetchRemovedUsers()]);
        setUsers(active);
        setRemoved(hidden);
    }, []);

    useEffect(() => {
        Promise.all([fetchUsers(), fetchRemovedUsers()])
            .then(([active, hidden]) => {
                setUsers(active);
                setRemoved(hidden);
            })
            .catch((err) => setError(errorMessage(err)));
    }, []);

    const remove = async (person: User) => {
        if (!confirm(t('settings.confirmDelete', { name: person.name }))) return;
        setError('');
        try {
            await deleteUser(person.id);
            await load();
        } catch (err) {
            setError(errorMessage(err));
        }
    };

    return (
        <section className={`${CARD} space-y-4`}>
            <h2 className="text-lg">{t('settings.members')}</h2>
            <p className="text-sm text-slate-400">{t('settings.membersFromHub')}</p>
            <ul className="divide-y divide-white/10">
                {users.map((u) => (
                    <li key={u.id} className="flex flex-wrap items-center gap-2 py-3">
                        <span className="font-semibold">{u.name}</span>
                        <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-300">{t(`roles.${u.role}`)}</span>
                        {/* The address recipe mails come from: the one confirmed in the hub */}
                        <span className={`text-sm ${u.email ? 'text-slate-300' : 'text-slate-400'}`}>
                            {u.email ?? t('settings.memberNoMail')}
                        </span>
                    </li>
                ))}
            </ul>
            {removed.length > 0 && (
                <div className="space-y-2">
                    <h3 className="text-sm font-semibold text-slate-300">{t('settings.removedTitle')}</h3>
                    <p className="text-sm text-slate-400">{t('settings.removedHint')}</p>
                    <ul className="divide-y divide-white/10">
                        {removed.map((u) => (
                            <li key={u.id} className="flex flex-wrap items-center gap-2 py-3">
                                <span className="mr-auto">{u.name}</span>
                                <button type="button" className={BUTTON_DANGER} onClick={() => void remove(u)}>
                                    {t('settings.deleteData', { name: u.name })}
                                </button>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
            {error && <p role="alert" className={ERROR}>{error}</p>}
        </section>
    );
}
