import type { ReactElement } from 'react';
import { useTranslation } from 'react-i18next';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Placeholder from './pages/Placeholder';

function RequireAuth({ children }: { children: ReactElement }) {
    const { t } = useTranslation();
    const { user, isLoading } = useAuth();
    if (isLoading) return <p className="p-6 text-slate-400">{t('common.loading')}</p>;
    return user ? children : <Navigate to="/login" replace />;
}

export default function App() {
    return (
        <AuthProvider>
            <BrowserRouter>
                <Routes>
                    <Route path="/login" element={<Login />} />
                    <Route
                        element={
                            <RequireAuth>
                                <Layout />
                            </RequireAuth>
                        }
                    >
                        <Route index element={<Placeholder titleKey="nav.plan" />} />
                        <Route path="rezepte" element={<Placeholder titleKey="nav.recipes" />} />
                        <Route path="einstellungen" element={<Placeholder titleKey="nav.settings" />} />
                    </Route>
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </BrowserRouter>
        </AuthProvider>
    );
}
