import { useTranslation } from 'react-i18next';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../AuthContext';

const NAV = [
    { to: '/', key: 'nav.plan', icon: '📅', end: true },
    { to: '/rezepte', key: 'nav.recipes', icon: '📖', end: false },
    { to: '/verlauf', key: 'nav.history', icon: '🕘', end: false },
    { to: '/einstellungen', key: 'nav.settings', icon: '⚙️', end: false },
] as const;

const topLink = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-2 text-sm font-medium ${
        isActive ? 'bg-white/10 text-white' : 'text-slate-300 hover:bg-white/5 hover:text-white'
    }`;

const bottomLink = ({ isActive }: { isActive: boolean }) =>
    `flex flex-1 flex-col items-center gap-0.5 py-2 text-xs ${isActive ? 'text-cyan-300' : 'text-slate-400'}`;

export default function Layout() {
    const { t } = useTranslation();
    const { user, logout } = useAuth();

    return (
        <div className="min-h-screen pb-20 sm:pb-0">
            <header className="sticky top-0 z-10 border-b border-white/10 bg-slate-900/70 backdrop-blur-md">
                <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3">
                    <span className="mr-auto text-lg font-bold">
                        🍽️ <span className="bg-gradient-to-r from-cyan-300 to-fuchsia-300 bg-clip-text text-transparent">{t('common.appName')}</span>
                    </span>
                    <nav className="hidden gap-1 sm:flex">
                        {NAV.map((item) => (
                            <NavLink key={item.to} to={item.to} end={item.end} className={topLink}>
                                {t(item.key)}
                            </NavLink>
                        ))}
                    </nav>
                    <span className="text-sm text-slate-400">{user?.name}</span>
                    <button type="button" onClick={logout} className="text-sm text-slate-400 hover:text-white">
                        {t('nav.logout')}
                    </button>
                </div>
            </header>
            <main className="mx-auto max-w-7xl px-4 py-6">
                <Outlet />
            </main>
            {/* Phones: the navigation sits at the bottom, within reach of the thumb */}
            <nav className="fixed inset-x-0 bottom-0 z-10 flex border-t border-white/10 bg-slate-900/90 backdrop-blur-md sm:hidden">
                {NAV.map((item) => (
                    <NavLink key={item.to} to={item.to} end={item.end} className={bottomLink}>
                        <span className="text-lg">{item.icon}</span>
                        {t(item.key)}
                    </NavLink>
                ))}
            </nav>
        </div>
    );
}
