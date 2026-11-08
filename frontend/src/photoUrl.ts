// A recipe photo's address: a card (lists, suggestions) loads the small version the backend keeps (480 px), a recipe
// page the whole photo (performance review 2026-11-08)
export function photoSrc(url: string, size: 'card' | 'full'): string {
    if (size === 'full') return url;
    return `${url}${url.includes('?') ? '&' : '?'}size=card`;
}
