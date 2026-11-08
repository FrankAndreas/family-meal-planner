import { vi } from 'vitest';

// The tests run in Node: what i18n.ts touches when it is imported (the browser's language, <html lang>), and a
// localStorage the test controls (`fail`: it throws, as in a private window)
export function stubBrowser(language = 'en') {
    const stored = new Map<string, string>();
    const storage = {
        fail: false,
        getItem(key: string) {
            if (storage.fail) throw new Error('blocked');
            return stored.get(key) ?? null;
        },
        setItem(key: string, value: string) {
            if (storage.fail) throw new Error('blocked');
            stored.set(key, value);
        },
        removeItem(key: string) {
            if (storage.fail) throw new Error('blocked');
            stored.delete(key);
        },
    };
    vi.stubGlobal('navigator', { language });
    vi.stubGlobal('document', { documentElement: {} });
    vi.stubGlobal('localStorage', storage);
    return storage;
}
