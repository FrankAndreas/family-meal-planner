import { useEffect, useRef, type FormEvent, type MouseEvent, type ReactNode } from 'react';

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface ModalProps {
    // What a screen reader announces the dialog as
    label: string;
    onClose: () => void;
    // The dimmed layer behind (where the dialog sits: centred, a sheet at the bottom, ...) and the dialog itself
    overlayClassName: string;
    className: string;
    // A dialog that is a form (submitting it is its main action)
    onSubmit?: (e: FormEvent) => void;
    children: ReactNode;
}

// A dialog as screen readers and keyboards expect it (accessibility review 2026-11-08): announced as modal, Escape or a
// tap beside it closes it, Tab stays inside, focus starts inside and goes back to where it was when it closes
export default function Modal({ label, onClose, overlayClassName, className, onSubmit, children }: ModalProps) {
    const box = useRef<HTMLElement | null>(null);
    const latestClose = useRef(onClose);
    useEffect(() => {
        latestClose.current = onClose;
    });

    useEffect(() => {
        const before = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        const dialog = box.current;
        // A control with autoFocus (or the dialog's own effect) may have taken focus already
        if (dialog && !dialog.contains(document.activeElement)) {
            (dialog.querySelector<HTMLElement>(FOCUSABLE) ?? dialog).focus();
        }
        const keys = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                latestClose.current();
                return;
            }
            if (e.key !== 'Tab' || !dialog) return;
            const inside = [...dialog.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null);
            if (inside.length === 0) return;
            const first = inside[0];
            const last = inside[inside.length - 1];
            if (e.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {
                e.preventDefault();
                first.focus();
            }
        };
        document.addEventListener('keydown', keys);
        return () => {
            document.removeEventListener('keydown', keys);
            // Unless the page moved focus on purpose meanwhile (to a new place), back to where it was
            const lost = !document.activeElement || document.activeElement === document.body || dialog?.contains(document.activeElement);
            if (lost && before?.isConnected) before.focus();
        };
    }, []);

    const shared = {
        role: 'dialog',
        'aria-modal': true,
        'aria-label': label,
        tabIndex: -1,
        className,
        onClick: (e: MouseEvent) => e.stopPropagation(),
    } as const;
    return (
        <div className={overlayClassName} onClick={onClose}>
            {onSubmit ? (
                <form ref={(el) => void (box.current = el)} {...shared} onSubmit={onSubmit}>
                    {children}
                </form>
            ) : (
                <div ref={(el) => void (box.current = el)} {...shared}>
                    {children}
                </div>
            )}
        </div>
    );
}
