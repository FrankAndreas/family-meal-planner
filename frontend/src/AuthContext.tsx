import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import api from './api';
import { applyLanguage, browserLanguage } from './i18n';
import type { User } from './types';

interface AuthContextType {
    user: User | null;
    isLoading: boolean;
    login: (name: string, pin: string) => Promise<void>;
    logout: () => void;
    refreshUser: () => Promise<void>;
    setToken: (token: string) => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    // The person's language follows them: applied whenever their data is loaded
    const loadUser = async () => {
        const me = (await api.get<User>('/api/me')).data;
        applyLanguage(me.language);
        setUser(me);
    };

    useEffect(() => {
        const checkAuth = async () => {
            if (localStorage.getItem('token')) {
                try {
                    await loadUser();
                } catch {
                    localStorage.removeItem('token');
                }
            }
            setIsLoading(false);
        };
        checkAuth();
    }, []);

    const login = async (name: string, pin: string) => {
        const response = await api.post<{ access_token: string }>('/api/token', { name, pin });
        localStorage.setItem('token', response.data.access_token);
        await loadUser();
    };

    const logout = () => {
        localStorage.removeItem('token');
        setUser(null);
        applyLanguage(browserLanguage());
    };

    // A new PIN ends all logins; the backend hands this device a fresh token
    const setToken = (token: string) => localStorage.setItem('token', token);

    return (
        <AuthContext.Provider value={{ user, isLoading, login, logout, refreshUser: loadUser, setToken }}>
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
