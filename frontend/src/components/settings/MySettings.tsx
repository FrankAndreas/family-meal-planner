import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import api, { errorMessage } from '../../api';
import { useAuth } from '../../AuthContext';
import { BUTTON, CARD, ERROR, FIELD } from '../../ui';
import PinInput from '../PinInput';

export default function MySettings() {
    const { t } = useTranslation();
    const { user, refreshUser, setToken } = useAuth();
    const [currentPin, setCurrentPin] = useState('');
    const [newPin, setNewPin] = useState('');
    const [message, setMessage] = useState('');
    const [error, setError] = useState('');

    // '' = no choice of their own: the app's default language
    const changeLanguage = async (value: string) => {
        setError('');
        try {
            await api.patch('/api/me', { language: value || null });
            await refreshUser();
        } catch (err) {
            setError(errorMessage(err));
        }
    };

    const changePin = async (e: FormEvent) => {
        e.preventDefault();
        setError('');
        setMessage('');
        try {
            const response = await api.post('/api/me/pin', { current_pin: currentPin, new_pin: newPin });
            setToken(response.headers['x-new-token']);
            setCurrentPin('');
            setNewPin('');
            setMessage(t('settings.pinChanged'));
        } catch (err) {
            setError(errorMessage(err));
        }
    };

    return (
        <section className={`${CARD} space-y-5`}>
            <h2 className="text-lg">{t('settings.mine')}</h2>
            <div className="flex flex-wrap items-center gap-3">
                <label htmlFor="language" className="text-sm text-slate-300">
                    {t('settings.language')}
                </label>
                <select
                    id="language"
                    className={FIELD}
                    value={user?.language_chosen ? user.language : ''}
                    onChange={(e) => changeLanguage(e.target.value)}
                >
                    <option value="">{t('settings.languageDefault')}</option>
                    <option value="de">{t('settings.german')}</option>
                    <option value="en">{t('settings.english')}</option>
                </select>
            </div>
            <form onSubmit={changePin} className="space-y-3">
                <h3 className="text-sm font-semibold text-slate-300">{t('settings.changePin')}</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                        <label htmlFor="current-pin" className="mb-1 block text-xs text-slate-400">
                            {t('settings.currentPin')}
                        </label>
                        <PinInput id="current-pin" value={currentPin} onChange={setCurrentPin} />
                    </div>
                    <div>
                        <label htmlFor="new-pin" className="mb-1 block text-xs text-slate-400">
                            {t('settings.newPin')}
                        </label>
                        <PinInput id="new-pin" value={newPin} onChange={setNewPin} autoComplete="new-password" />
                    </div>
                </div>
                <button type="submit" className={BUTTON} disabled={currentPin.length < 4 || newPin.length < 4}>
                    {t('settings.changePin')}
                </button>
            </form>
            {message && <p className="text-sm text-emerald-300">{message}</p>}
            {error && <p className={ERROR}>{error}</p>}
        </section>
    );
}
