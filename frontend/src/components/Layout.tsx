import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { fetchInboxCount } from '../inbox';
import { useAuth } from '../AuthContext';

const NAV = [
    { to: '/', key: 'nav.plan', icon: '📅', end: true },
    { to: '/rezepte', key: 'nav.recipes', icon: '📖', end: false },
    { to: '/posteingang', key: 'nav.inbox', icon: '📥', end: false },
    { to: '/verlauf', key: 'nav.history', icon: '🕘', end: false },
    { to: '/einstellungen', key: 'nav.settings', icon: '⚙️', end: false },
] as const;

// The browser tab's (and a screen reader's) name of each part of the app, by the start of its address
const TITLES = [
    ['/einkaufsliste', 'shopping.title'],
    ['/woche-abschliessen', 'close.title'],
    ['/rezepte', 'nav.recipes'],
    ['/posteingang', 'nav.inbox'],
    ['/verlauf', 'nav.history'],
    ['/einstellungen', 'nav.settings'],
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
    const location = useLocation();
    const [waiting, setWaiting] = useState(0);

    // Each page its own title, so tabs and screen readers tell them apart (accessibility review 2026-11-08)
    useEffect(() => {
        const part = TITLES.find(([start]) => location.pathname.startsWith(start))?.[1] ?? 'nav.plan';
        document.title = `${t(part)} · ${t('common.appName')}`;
    }, [location.pathname, t]);

    // The inbox badge, looked at again whenever the page changes
    useEffect(() => {
        let current = true;
        fetchInboxCount()
            .then((count) => current && setWaiting(count))
            .catch(() => {});
        return () => {
            current = false;
        };
    }, [location.pathname]);

    const badge = (key: string) =>
        key === 'nav.inbox' && waiting > 0 ? (
            <span className="ml-1 rounded-full bg-fuchsia-500/80 px-1.5 text-xs text-white">{waiting}</span>
        ) : null;

    return (
        <div className="min-h-screen pb-20 sm:pb-0">
            {/* The first thing a keyboard reaches: past the navigation to the page (shown only while focused) */}
            <a
                href="#main"
                onClick={(e) => {
                    e.preventDefault();
                    document.getElementById('main')?.focus();
                }}
                className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-slate-900 focus:px-3 focus:py-2 focus:text-white"
            >
                {t('nav.skipToContent')}
            </a>
            <header className="sticky top-0 z-10 border-b border-white/10 bg-slate-900/70 backdrop-blur-md">
                <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3">
                    <span className="mr-auto text-lg font-bold">
                        <span aria-hidden>🍽️</span> <span className="bg-gradient-to-r from-cyan-300 to-fuchsia-300 bg-clip-text text-transparent">{t('common.appName')}</span>
                    </span>
                    <nav className="hidden gap-1 sm:flex">
                        {NAV.map((item) => (
                            <NavLink key={item.to} to={item.to} end={item.end} className={topLink}>
                                {t(item.key)}
                                {badge(item.key)}
                            </NavLink>
                        ))}
                    </nav>
                    <span className="text-sm text-slate-400">{user?.name}</span>
                    <button type="button" onClick={logout} className="text-sm text-slate-400 hover:text-white">
                        {t('nav.logout')}
                    </button>
                </div>
            </header>
            <main id="main" tabIndex={-1} className="mx-auto max-w-7xl px-4 py-6 focus:outline-none">
                <Outlet />
            </main>
            {/* Phones: the navigation sits at the bottom, within reach of the thumb */}
            <nav className="fixed inset-x-0 bottom-0 z-10 flex border-t border-white/10 bg-slate-900/90 backdrop-blur-md sm:hidden">
                {NAV.map((item) => (
                    <NavLink key={item.to} to={item.to} end={item.end} className={bottomLink}>
                        <span className="text-lg">{item.icon}</span>
                        <span>
                            {t(item.key)}
                            {badge(item.key)}
                        </span>
                    </NavLink>
                ))}
            </nav>
        </div>
    );
}
