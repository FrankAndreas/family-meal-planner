import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { errorMessage } from '../../api';
import { bringLogin, bringLogout, chooseBringList, fetchBring, fetchBringLists, type BringList, type BringLogin } from '../../bring';
import { BUTTON, BUTTON_SECONDARY, CARD, ERROR, FIELD, INPUT } from '../../ui';

// Parents sign in to Bring! once; the shopping list goes to the list they choose here
export default function BringSettings() {
    const { t } = useTranslation();
    const [login, setLogin] = useState<BringLogin | null>(null);
    const [lists, setLists] = useState<BringList[]>([]);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        let current = true;
        fetchBring()
            .then((found) => {
                if (!current) return;
                setLogin(found);
                // Signed in without a list (a new login): offer the account's lists
                if (found.email && !found.list_uuid) fetchBringLists().then((l) => current && setLists(l)).catch(() => {});
            })
            .catch((err) => current && setError(errorMessage(err)));
        return () => {
            current = false;
        };
    }, []);

    const run = async (action: () => Promise<void>) => {
        setError('');
        setBusy(true);
        try {
            await action();
        } catch (err) {
            setError(errorMessage(err));
        } finally {
            setBusy(false);
        }
    };

    const signIn = (e: FormEvent) => {
        e.preventDefault();
        run(async () => {
            setLists(await bringLogin(email.trim(), password));
            setLogin({ email: email.trim(), list_uuid: null, list_name: null });
            setPassword('');
        });
    };

    const choose = (uuid: string) => run(async () => setLogin(await chooseBringList(uuid)));

    const signOut = () =>
        run(async () => {
            await bringLogout();
            setLogin({ email: null, list_uuid: null, list_name: null });
            setLists([]);
            setEmail('');
        });

    return (
        <section className={`${CARD} space-y-4`} aria-labelledby="bring-settings">
            <div>
                <h2 id="bring-settings" className="text-lg">
                    {t('bring.title')}
                </h2>
                <p className="text-sm text-slate-400">{t('bring.hint')}</p>
            </div>
            {login?.email ? (
                <div className="space-y-3">
                    {login.list_uuid ? (
                        <p>{t('bring.signedIn', { email: login.email, list: login.list_name })}</p>
                    ) : (
                        <p>{t('bring.signedInNoList', { email: login.email })}</p>
                    )}
                    {!login.list_uuid && (
                        <label className="block space-y-1">
                            <span className="text-sm text-slate-300">{t('bring.list')}</span>
                            <select
                                className={INPUT}
                                value=""
                                disabled={busy}
                                onChange={(e) => e.target.value && choose(e.target.value)}
                            >
                                <option value="">{t('bring.chooseList')}</option>
                                {lists.map((list) => (
                                    <option key={list.uuid} value={list.uuid}>
                                        {list.name}
                                    </option>
                                ))}
                            </select>
                        </label>
                    )}
                    <button type="button" className={BUTTON_SECONDARY} disabled={busy} onClick={signOut}>
                        {t('bring.signOut')}
                    </button>
                </div>
            ) : (
                login && (
                    <form className="flex flex-wrap items-end gap-3" onSubmit={signIn}>
                        <label className="space-y-1">
                            <span className="block text-sm text-slate-300">{t('bring.email')}</span>
                            <input
                                className={FIELD}
                                type="email"
                                autoComplete="off"
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                            />
                        </label>
                        <label className="space-y-1">
                            <span className="block text-sm text-slate-300">{t('bring.password')}</span>
                            <input
                                className={FIELD}
                                type="password"
                                autoComplete="new-password"
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                            />
                        </label>
                        <button type="submit" className={BUTTON} disabled={busy}>
                            {t('bring.signIn')}
                        </button>
                    </form>
                )
            )}
            {error && (
                <p role="alert" className={ERROR}>
                    {error}
                </p>
            )}
        </section>
    );
}
