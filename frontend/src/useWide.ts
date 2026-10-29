import { useSyncExternalStore } from 'react';

// Tablet and up (Tailwind's md): the week grid with the suggestion panel; below it the day view
const QUERY = '(min-width: 768px)';

export function useWide(): boolean {
    return useSyncExternalStore(
        (changed) => {
            const media = window.matchMedia(QUERY);
            media.addEventListener('change', changed);
            return () => media.removeEventListener('change', changed);
        },
        () => window.matchMedia(QUERY).matches,
    );
}
