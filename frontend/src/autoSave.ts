// Saved as soon as something changes (UX review 2026-11-06), one request after the other, so an older answer never
// wins over a newer change. A failed save isn't lost: it goes again with the next change, unless that change replaced
// it. Leaving the page, closing or hiding the tab sends what's still waiting. Kept apart from React (useAutoSave) so
// it can be tested on its own.

export type SaveStatus = 'idle' | 'saving' | 'saved';

export interface AutoSaveOptions<T> {
    // Saves the changed fields; answers with the whole saved object
    save: (fields: Partial<T>) => Promise<T>;
    // The same, as a request that outlives the page (sent while it closes or hides)
    saveOnLeave?: (fields: Partial<T>) => Promise<T>;
    // A save's answer, with the fields it was for; `changedSince(key)`: that field was changed again meanwhile, so
    // what's shown is newer than the answer
    onSaved?: (saved: T, fields: Partial<T>, changedSince: (key: keyof T) => boolean) => void;
}

// What the page shows: the status, and the error of the last save (null once one worked)
export interface AutoSaveReport {
    status: (status: SaveStatus) => void;
    error: (error: unknown | null) => void;
}

export class AutoSaver<T extends object> {
    private pending: Partial<T> = {};
    private timer: ReturnType<typeof setTimeout> | null = null;
    private queue: Promise<void> = Promise.resolve();
    private sending = 0;
    // How often each field was changed: an answer is older than the field if it changed since
    private versions = new Map<keyof T, number>();
    // The page's newest options (they change with each render), and where status and error go
    private readonly options: () => AutoSaveOptions<T>;
    private readonly report: AutoSaveReport;

    constructor(options: () => AutoSaveOptions<T>, report: AutoSaveReport) {
        this.options = options;
        this.report = report;
    }

    // `wait`: a pause before sending, so typing "12" isn't saved as 1 first; a newer change restarts it
    change(fields: Partial<T>, wait = 0): void {
        this.pending = { ...this.pending, ...fields };
        for (const key of Object.keys(fields) as (keyof T)[]) this.versions.set(key, (this.versions.get(key) ?? 0) + 1);
        this.report.status('saving');
        if (this.timer) clearTimeout(this.timer);
        this.timer = setTimeout(() => this.send(), wait);
    }

    // A change that isn't one after all (a half-typed number) leaves what's waiting
    drop(key: keyof T): void {
        delete this.pending[key];
        if (this.timer && !this.hasPending()) {
            clearTimeout(this.timer);
            this.timer = null;
        }
        if (!this.waiting()) this.report.status('idle');
    }

    // The page goes away (unmount): what's waiting is sent now, without the pause
    flush(): void {
        if (this.hasPending()) this.send();
    }

    // The tab closes or hides: what's waiting goes as a request that outlives the page, started right now. If the page
    // comes back (back button, tab shown again), its answer counts
    leave(): void {
        const onLeave = this.options().saveOnLeave;
        if (!onLeave || !this.hasPending()) return;
        const { fields, sentAt } = this.take();
        const request = onLeave(fields);
        void this.settle(fields, sentAt, () => request);
    }

    private hasPending(): boolean {
        return Object.keys(this.pending).length > 0;
    }

    private waiting(): boolean {
        return this.timer !== null || this.hasPending() || this.sending > 0;
    }

    // What's waiting leaves pending, with the field versions it was sent at
    private take(): { fields: Partial<T>; sentAt: Map<keyof T, number> } {
        if (this.timer) clearTimeout(this.timer);
        this.timer = null;
        const fields = this.pending;
        this.pending = {};
        this.sending += 1;
        return { fields, sentAt: new Map(this.versions) };
    }

    private send(): void {
        const { fields, sentAt } = this.take();
        this.queue = this.queue.then(() => this.settle(fields, sentAt, () => this.options().save(fields)));
    }

    // The answer is applied here, whichever way it was sent
    private async settle(fields: Partial<T>, sentAt: Map<keyof T, number>, request: () => Promise<T>): Promise<void> {
        let saved: T;
        try {
            saved = await request();
        } catch (error) {
            this.sending -= 1;
            this.pending = { ...fields, ...this.pending };
            this.report.error(error);
            this.report.status('idle');
            return;
        }
        this.sending -= 1;
        this.report.error(null);
        // Only "saved" once nothing else waits
        if (!this.waiting()) this.report.status('saved');
        // After the bookkeeping, so a caller's mistake here can't count a save twice
        this.options().onSaved?.(saved, fields, (key) => this.versions.get(key) !== sentAt.get(key));
    }
}
