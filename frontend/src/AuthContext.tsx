import axios from 'axios';
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import api, { errorCode, goToHubLogout } from './api';
import { applyLanguage } from './i18n';
import { guestLanguage } from './language';
import type { User } from './types';

// in: logged in; no_access: logged in at the hub, but not ticked for the planner; hub_unavailable: the hub doesn't
// answer; away: on the way to the hub's login (the API's 401 sends the browser there)
export type AuthState = 'loading' | 'in' | 'no_access' | 'hub_unavailable' | 'away';

interface AuthContextType {
    user: User | null;
    state: AuthState;
    isLoading: boolean;
    logout: () => Promise<void>;
    refreshUser: () => Promise<User>;
    retry: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

// Who is logged in: the family hub's login (spec 2026-10-30); the backend asks the hub
export const AuthProvider = ({ children }: { children: ReactNode }) => {
    const [user, setUser] = useState<User | null>(null);
    const [state, setState] = useState<AuthState>('loading');

    // The person's language follows them (from the hub): applied whenever their data is loaded
    const loadUser = useCallback(async () => {
        const me = (await api.get<User>('/api/me')).data;
        applyLanguage(me.language);
        setUser(me);
        return me;
    }, []);

    // Raised by "Try again" (hub_unavailable): asks the backend once more
    const [attempt, setAttempt] = useState(0);

    useEffect(() => {
        const check = async () => {
            try {
                await loadUser();
                setState('in');
            } catch (error) {
                // 401: the API has sent the browser to the hub's login. Anything else but "no access" (the hub down, a
                // NAS restarting) says so and offers to try again
                const code = errorCode(error);
                const away = axios.isAxiosError(error) && error.response?.status === 401;
                setState(code === 'no_access' ? 'no_access' : away ? 'away' : 'hub_unavailable');
                applyLanguage(await guestLanguage());
            }
        };
        void check();
    }, [loadUser, attempt]);

    const logout = useCallback(async () => {
        await goToHubLogout();
    }, []);

    const retry = useCallback(() => {
        setState('loading');
        setAttempt((n) => n + 1);
    }, []);

    return (
        <AuthContext.Provider value={{ user, state, isLoading: state === 'loading', logout, refreshUser: loadUser, retry }}>
            {children}
        </AuthContext.Provider>
    );
};

// eslint-disable-next-line react-refresh/only-export-components -- the hook belongs with its provider
export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
