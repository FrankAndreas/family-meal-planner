import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import api, { errorMessage } from '../../api';
import { useAuth } from '../../AuthContext';
import type { Role, User } from '../../types';
import { BUTTON, BUTTON_DANGER, BUTTON_SECONDARY, CARD, ERROR, FIELD, INPUT } from '../../ui';
import PinInput from '../PinInput';

type Editing = { id: number; kind: 'name' | 'pin'; value: string } | null;

export default function FamilyMembers() {
    const { t } = useTranslation();
    const { user: me, refreshUser } = useAuth();
    const [users, setUsers] = useState<User[]>([]);
    const [name, setName] = useState('');
    const [pin, setPin] = useState('');
    const [role, setRole] = useState<Role>('CHILD');
    const [editing, setEditing] = useState<Editing>(null);
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        setUsers((await api.get<User[]>('/api/users')).data);
    }, []);

    useEffect(() => {
        api.get<User[]>('/api/users')
            .then((response) => setUsers(response.data))
            .catch((err) => setError(errorMessage(err)));
    }, []);

    // Every change reloads the list; a change to oneself (name, role) also reloads the logged-in person
    const run = async (action: () => Promise<unknown>) => {
        setError('');
        try {
            await action();
            await load();
            await refreshUser();
            return true;
        } catch (err) {
            setError(errorMessage(err));
            return false;
        }
    };

    const add = async (e: FormEvent) => {
        e.preventDefault();
        if (await run(() => api.post('/api/users', { name, pin, role }))) {
            setName('');
            setPin('');
        }
    };

    const saveEdit = async (e: FormEvent) => {
        e.preventDefault();
        if (!editing) return;
        const ok = await run(() =>
            editing.kind === 'name'
                ? api.patch(`/api/users/${editing.id}`, { name: editing.value })
                : api.post(`/api/users/${editing.id}/pin`, { pin: editing.value }),
        );
        if (ok) setEditing(null);
    };

    return (
        <section className={`${CARD} space-y-4`}>
            <h2 className="text-lg">{t('settings.members')}</h2>
            <ul className="divide-y divide-white/10">
                {users.map((u) => (
                    <li key={u.id} className="space-y-2 py-3">
                        <div className="flex flex-wrap items-center gap-2">
                            <span className="mr-auto font-semibold">
                                {u.name}
                                <span className="ml-2 rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-300">
                                    {t(`roles.${u.role}`)}
                                </span>
                            </span>
                            <select
                                className={FIELD}
                                aria-label={t('settings.roleOf', { name: u.name })}
                                value={u.role}
                                onChange={(e) =>
                                    run(() => api.patch(`/api/users/${u.id}`, { role: e.target.value as Role }))
                                }
                            >
                                <option value="PARENT">{t('roles.PARENT')}</option>
                                <option value="CHILD">{t('roles.CHILD')}</option>
                            </select>
                            <button
                                type="button"
                                className={BUTTON_SECONDARY}
                                onClick={() => setEditing({ id: u.id, kind: 'name', value: u.name })}
                            >
                                {t('settings.rename')}
                            </button>
                            <button
                                type="button"
                                className={BUTTON_SECONDARY}
                                onClick={() => setEditing({ id: u.id, kind: 'pin', value: '' })}
                            >
                                {t('settings.resetPin')}
                            </button>
                            {u.id !== me?.id && (
                                <button
                                    type="button"
                                    className={BUTTON_DANGER}
                                    onClick={() => {
                                        if (confirm(t('settings.confirmDelete', { name: u.name }))) {
                                            run(() => api.delete(`/api/users/${u.id}`));
                                        }
                                    }}
                                >
                                    {t('common.delete')}
                                </button>
                            )}
                        </div>
                        {editing?.id === u.id && (
                            <form onSubmit={saveEdit} className="flex flex-wrap items-center gap-2">
                                {editing.kind === 'name' ? (
                                    <input
                                        className={`${FIELD} w-48`}
                                        aria-label={t('settings.newName')}
                                        value={editing.value}
                                        maxLength={50}
                                        onChange={(e) => setEditing({ ...editing, value: e.target.value })}
                                        autoFocus
                                    />
                                ) : (
                                    <div className="w-40">
                                        <PinInput
                                            id={`pin-${u.id}`}
                                            value={editing.value}
                                            onChange={(value) => setEditing({ ...editing, value })}
                                            autoComplete="new-password"
                                            autoFocus
                                        />
                                    </div>
                                )}
                                <button type="submit" className={BUTTON}>
                                    {t('common.save')}
                                </button>
                                <button type="button" className={BUTTON_SECONDARY} onClick={() => setEditing(null)}>
                                    {t('common.cancel')}
                                </button>
                            </form>
                        )}
                    </li>
                ))}
            </ul>
            <form onSubmit={add} className="grid gap-3 sm:grid-cols-[1fr_8rem_9rem_auto] sm:items-end">
                <div>
                    <label htmlFor="new-name" className="mb-1 block text-xs text-slate-400">
                        {t('settings.newPersonName')}
                    </label>
                    <input
                        id="new-name"
                        className={INPUT}
                        value={name}
                        maxLength={50}
                        onChange={(e) => setName(e.target.value)}
                    />
                </div>
                <div>
                    <label htmlFor="new-person-pin" className="mb-1 block text-xs text-slate-400">
                        {t('settings.newPersonPin')}
                    </label>
                    <PinInput id="new-person-pin" value={pin} onChange={setPin} autoComplete="new-password" />
                </div>
                <div>
                    <label htmlFor="new-role" className="mb-1 block text-xs text-slate-400">
                        {t('settings.newPersonRole')}
                    </label>
                    <select
                        id="new-role"
                        className={INPUT}
                        value={role}
                        onChange={(e) => setRole(e.target.value as Role)}
                    >
                        <option value="CHILD">{t('roles.CHILD')}</option>
                        <option value="PARENT">{t('roles.PARENT')}</option>
                    </select>
                </div>
                <button type="submit" className={BUTTON} disabled={!name.trim() || pin.length < 4}>
                    {t('settings.addPerson')}
                </button>
            </form>
            {error && <p className={ERROR}>{error}</p>}
        </section>
    );
}
