import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, useNavigate } from 'react-router-dom';
import api, { errorMessage } from '../api';
import { useAuth } from '../AuthContext';
import PinInput from '../components/PinInput';
import type { PublicUser } from '../types';
import { BUTTON, CARD, ERROR } from '../ui';

export default function Login() {
    const { t } = useTranslation();
    const { login, user } = useAuth();
    const navigate = useNavigate();
    const [users, setUsers] = useState<PublicUser[]>([]);
    const [name, setName] = useState('');
    const [pin, setPin] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        api.get<PublicUser[]>('/api/users/public')
            .then((response) => setUsers(response.data))
            .catch((err) => setError(errorMessage(err)));
    }, []);

    const submit = async (e: FormEvent) => {
        e.preventDefault();
        setBusy(true);
        setError('');
        try {
            await login(name, pin);
            navigate('/');
        } catch (err) {
            setError(errorMessage(err));
            setPin('');
        } finally {
            setBusy(false);
        }
    };

    // Still logged in (e.g. the login page was reached while the NAS was restarting): straight back to the app
    if (user) return <Navigate to="/" replace />;

    return (
        <div className="flex min-h-screen items-center justify-center p-4">
            <form onSubmit={submit} className={`${CARD} w-full max-w-md space-y-5`}>
                <div className="text-center">
                    <div className="text-4xl">🍽️</div>
                    <h1 className="mt-2 text-2xl">{t('common.appName')}</h1>
                    <p className="text-sm text-slate-400">{t('login.intro')}</p>
                </div>
                {/* Big name buttons: kids tap their name on the iPad instead of typing it */}
                <div className="grid grid-cols-2 gap-3">
                    {users.map((u) => (
                        <button
                            key={u.id}
                            type="button"
                            onClick={() => {
                                setName(u.name);
                                setPin('');
                                setError('');
                            }}
                            className={`rounded-xl border p-4 text-lg font-semibold transition ${
                                name === u.name
                                    ? 'border-cyan-400 bg-cyan-400/15 text-white'
                                    : 'border-white/10 bg-slate-900/40 hover:bg-white/5'
                            }`}
                        >
                            {u.name}
                        </button>
                    ))}
                </div>
                {name && (
                    <div className="space-y-3">
                        <label htmlFor="pin" className="block text-sm text-slate-400">
                            {t('login.pinFor', { name })}
                        </label>
                        <PinInput id="pin" value={pin} onChange={setPin} autoFocus />
                        <button type="submit" disabled={busy || pin.length < 4} className={`${BUTTON} w-full`}>
                            {t('login.submit')}
                        </button>
                    </div>
                )}
                {error && <p className={ERROR}>{error}</p>}
            </form>
        </div>
    );
}
