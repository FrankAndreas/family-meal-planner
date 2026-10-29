import type { ReactElement } from 'react';
import { useTranslation } from 'react-i18next';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Placeholder from './pages/Placeholder';
import RecipeEdit from './pages/RecipeEdit';
import Recipes from './pages/Recipes';
import RecipeView from './pages/RecipeView';
import SettingsPage from './pages/SettingsPage';

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
                        <Route path="rezepte" element={<Recipes />} />
                        <Route path="rezepte/neu" element={<RecipeEdit />} />
                        <Route path="rezepte/:id" element={<RecipeView />} />
                        <Route path="rezepte/:id/bearbeiten" element={<RecipeEdit key="edit" />} />
                        <Route path="einstellungen" element={<SettingsPage />} />
                    </Route>
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </BrowserRouter>
        </AuthProvider>
    );
}
