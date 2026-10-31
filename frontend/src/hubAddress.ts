// Where the family hub is (HUB_PUBLIC_URL) and where "Log out" goes: at home the hub, outside Cloudflare Access, whose
// logout is an address on this site
export interface HubLinks {
    login_url: string;
    logout_url: string;
}

// Where a login that ended goes: at home the hub's login, which sends the browser back to `next` afterwards. Outside
// nowhere: the hub's home address is out of reach there, and Cloudflare Access asks for its e-mail code by itself
// (security review 2026-10-31)
export function loginAddress(links: HubLinks, next: string | null): string | null {
    if (links.logout_url.startsWith('/')) return null;
    return next ? `${links.login_url}/?next=${encodeURIComponent(next)}` : links.login_url;
}
