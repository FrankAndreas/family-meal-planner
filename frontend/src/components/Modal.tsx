import { useEffect, useRef, useState, type FormEvent, type MouseEvent, type ReactNode } from 'react';

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
    // Where focus was when the dialog opened, taken while rendering: by the time effects run, a control with autoFocus
    // inside has it already
    const [before] = useState(() => (document.activeElement instanceof HTMLElement ? document.activeElement : null));
    const latestClose = useRef(onClose);
    useEffect(() => {
        latestClose.current = onClose;
    });

    useEffect(() => {
        const dialog = box.current;
        // Focus starts on the control marked data-autofocus, else the first one, unless the dialog's own effect has
        // already put it somewhere inside
        if (dialog && !dialog.contains(document.activeElement)) {
            (dialog.querySelector<HTMLElement>('[data-autofocus]') ?? dialog.querySelector<HTMLElement>(FOCUSABLE) ?? dialog).focus();
        }
        const keys = (e: KeyboardEvent) => {
            // Handled already (by a dialog above this one, or a control inside)
            if (e.defaultPrevented || !dialog) return;
            if (e.key === 'Escape') {
                // A search field with text clears it first, as Escape does there
                const field = document.activeElement;
                if (field instanceof HTMLInputElement && field.type === 'search' && field.value) return;
                e.preventDefault();
                latestClose.current();
                return;
            }
            if (e.key !== 'Tab') return;
            const inside = [...dialog.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null);
            if (inside.length === 0) {
                e.preventDefault();
                dialog.focus();
                return;
            }
            // Where focus is among the dialog's tabbable controls: -1 on the dialog itself, its heading, or outside
            const at = inside.indexOf(document.activeElement as HTMLElement);
            const outside = !dialog.contains(document.activeElement);
            if (e.shiftKey && at <= 0) {
                e.preventDefault();
                inside[inside.length - 1].focus();
            } else if (!e.shiftKey && (outside || at === inside.length - 1)) {
                e.preventDefault();
                inside[0].focus();
            }
        };
        document.addEventListener('keydown', keys);
        return () => {
            document.removeEventListener('keydown', keys);
            // Unless the page moved focus on purpose meanwhile (to a new place), back to where it was
            const lost = !document.activeElement || document.activeElement === document.body || dialog?.contains(document.activeElement);
            if (lost && before?.isConnected) before.focus();
        };
    }, [before]);

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
