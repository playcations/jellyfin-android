// APK-owned navigation for the current mobile web UI. No server layout/device detection.
const candidates = 'a[href],button,input:not([type="hidden"]),textarea,select,[tabindex],.focusable,[role="button"],[role="menuitem"]';
const directions = { ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down' };
const nativeEnter = 'a[href],button,input,textarea,select';

export function isEditing(element) {
    if (!element) return false;
    const input = element.closest('input');
    if (input && !['button', 'checkbox', 'radio', 'submit', 'reset', 'image', 'file', 'color', 'hidden'].includes(input.type)) return true;
    return element.isContentEditable || !!element.closest('textarea,select,[role="textbox"],[role="slider"]');
}

export class PhysicalInputAdapter {
    constructor(inputManager, win = window) {
        this.win = win;
        this.doc = win.document;
        this.input = inputManager;
        this.physical = true;
        this.memory = new Map();
        this.scopeMemory = new WeakMap();
        this.onKey = this.onKey.bind(this);
        this.onCommand = this.onCommand.bind(this);
        this.onFocus = this.onFocus.bind(this);
        this.onPointer = () => {
            this.physical = false;
            this.doc.documentElement.classList.remove('familyfin-physical-input');
        };
        this.schedule = () => {
            if (this.frame) return;
            this.frame = win.requestAnimationFrame(() => {
                this.frame = null;
                this.restore();
            });
        };
        this.style = this.doc.createElement('style');
        this.style.textContent = '.familyfin-physical-input :focus { outline: 3px solid #00a4dc !important; outline-offset: -3px !important; }';
        this.doc.head.append(this.style);
        // Let native controls and React/MUI key handlers consume their keys first.
        win.addEventListener('keydown', this.onKey);
        win.addEventListener('focusin', this.onFocus);
        win.addEventListener('pointerdown', this.onPointer, true);
        win.addEventListener('hashchange', this.schedule);
        win.addEventListener('popstate', this.schedule);
        win.addEventListener('pageshow', this.schedule);
        win.addEventListener('focus', this.schedule);
        win.addEventListener('transitionend', this.schedule, true);
        win.addEventListener('animationend', this.schedule, true);
        this.doc.addEventListener('viewshow', this.schedule, true);
        inputManager.on(this.doc, this.onCommand);
        this.observer = new win.MutationObserver(this.schedule);
        this.observer.observe(this.doc.body, { subtree: true, childList: true, attributes: true,
            attributeFilter: ['class', 'style', 'hidden', 'open', 'aria-hidden'] });
        this.schedule();
    }

    route() {
        return this.win.location.pathname + this.win.location.search + this.win.location.hash;
    }

    visible(element) {
        if (!element?.isConnected || element.closest('[hidden],[inert],[aria-hidden="true"],.hide,.mainDrawer:not(.drawer-open)')) return false;
        if (element.matches(':disabled,[aria-disabled="true"]')) return false;
        for (let ancestor = element; ancestor && ancestor !== this.doc.body; ancestor = ancestor.parentElement) {
            if (this.win.getComputedStyle(ancestor).opacity === '0') return false;
        }
        const style = this.win.getComputedStyle(element);
        return style.visibility !== 'hidden' && style.display !== 'none' && element.getClientRects().length > 0;
    }

    scope() {
        const overlays = [...this.doc.querySelectorAll('.dialog.opened,dialog[open],[aria-modal="true"],[role="menu"],.MuiModal-root,.MuiDrawer-root .MuiPaper-root,.mainDrawer.drawer-open')];
        const visible = overlays.filter(e => this.visible(e));
        return visible[visible.length - 1] || this.doc.body;
    }

    elements(scope) {
        return [...scope.querySelectorAll(candidates)].filter(e => this.visible(e)
            && (e.getAttribute('tabindex') !== '-1' || e.classList.contains('focusable')));
    }

    onFocus(event) {
        const element = event.target;
        const scope = this.scope();
        if (!scope.contains(element) || element === this.doc.body || !this.visible(element)) return;
        this.scopeMemory.set(scope, element);
        if (scope === this.doc.body) {
            this.memory.delete(this.route());
            this.memory.set(this.route(), { element, id: element.id, href: element.getAttribute('href'),
                item: element.closest('[data-id]')?.dataset.id });
            if (this.memory.size > 40) this.memory.delete(this.memory.keys().next().value);
        }
        if (this.physical) this.reveal(element);
    }

    reveal(element) {
        element.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'instant' });
    }

    focus(element) {
        if (!element) return;
        // role=button elements and legacy .focusable containers need a programmatic tab stop.
        if (!element.matches('a[href],button,input,textarea,select,[tabindex]')) element.tabIndex = 0;
        element.focus({ preventScroll: true });
        this.reveal(element);
    }

    restore() {
        if (!this.physical) return;
        const scope = this.scope();
        const active = this.doc.activeElement;
        const changedScope = scope !== this.lastScope;
        const changedRoute = this.route() !== this.lastRoute;
        this.lastScope = scope;
        this.lastRoute = this.route();
        this.doc.documentElement.classList.add('familyfin-physical-input');
        if (!changedScope && !changedRoute && scope.contains(active) && this.visible(active) && active !== this.doc.body) return;
        const saved = this.memory.get(this.route());
        const elements = this.elements(scope);
        const remembered = scope === this.doc.body ? saved?.element : this.scopeMemory.get(scope);
        const matching = saved && elements.find(e => (saved.id && e.id === saved.id)
            || (saved.item && e.closest('[data-id]')?.dataset.id === saved.item && e.getAttribute('href') === saved.href)
            || (saved.href && e.getAttribute('href') === saved.href));
        const target = this.visible(remembered) && scope.contains(remembered) ? remembered : matching;
        this.focus(target || elements.find(e => e.hasAttribute('autofocus')) || elements[0]);
    }

    onKey(event) {
        if (this.syntheticBack || event.defaultPrevented || event.isComposing || event.keyCode === 229
            || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
        const key = event.key || event.code;
        const command = directions[key] || (['Escape', 'BrowserBack', 'GoBack'].includes(key) ? 'back' : null);
        const enter = key === 'Enter' || key === 'NumpadEnter';
        if (!command && !enter) return; // Tab, text, media-session keys retain their normal path.
        if (isEditing(event.target) && command !== 'back') return;
        this.physical = true;
        // Enter retains browser form submission and button/link activation semantics.
        if (enter && event.target.matches(nativeEnter) && !event.repeat) {
            this.doc.documentElement.classList.add('familyfin-physical-input');
            return;
        }
        event.preventDefault();
        event.stopImmediatePropagation(); // stock keyboardNavigation must not dispatch twice.
        if (event.repeat && (enter || command === 'back')) return;
        this.restore();
        this.input.handleCommand(enter ? 'select' : command);
        this.schedule();
    }

    back() {
        this.physical = true;
        this.restore();
        this.input.handleCommand('back');
        this.schedule();
    }

    onCommand(event) {
        const direction = event.detail.command;
        if (direction === 'back' && !event.defaultPrevented) {
            const scope = this.scope();
            const modal = scope.closest('.MuiModal-root');
            if (modal) {
                event.preventDefault();
                this.syntheticBack = true;
                try {
                    // MUI owns its dismiss lifecycle and consumes Escape through React.
                    (scope.contains(this.doc.activeElement) ? this.doc.activeElement : scope).dispatchEvent(
                        new this.win.KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', keyCode: 27,
                            bubbles: true, cancelable: true })
                    );
                } finally { this.syntheticBack = false; }
            } else if (scope.matches('.mainDrawer.drawer-open')) {
                const toggle = this.doc.querySelector('.mainDrawerButton');
                if (toggle) { event.preventDefault(); toggle.click(); }
            }
            return;
        }
        if (!this.physical || !['left', 'right', 'up', 'down'].includes(direction) || event.defaultPrevented) return;
        // Commands first bubble through web controls/dialogs, preserving their own key handling.
        event.preventDefault();
        const scope = this.scope();
        const active = this.doc.activeElement;
        if (!scope.contains(active) || active === this.doc.body) { this.restore(); return; }
        const rect = active.getBoundingClientRect();
        const horizontal = direction === 'left' || direction === 'right';
        const sign = direction === 'left' || direction === 'up' ? -1 : 1;
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;
        let nearest;
        let distance = Infinity;
        for (const element of this.elements(scope)) {
            if (element === active || element.contains(active) || active.contains(element)) continue;
            const other = element.getBoundingClientRect();
            const dx = other.left + other.width / 2 - x;
            const dy = other.top + other.height / 2 - y;
            const primary = (horizontal ? dx : dy) * sign;
            if (primary <= 1) continue;
            const overlap = horizontal ? other.top < rect.bottom && other.bottom > rect.top
                : other.left < rect.right && other.right > rect.left;
            const cross = Math.abs(horizontal ? dy : dx);
            const score = primary + (overlap ? cross * 0.1 : cross * 3);
            if (score < distance) { distance = score; nearest = element; }
        }
        this.focus(nearest);
    }

    destroy() {
        this.observer.disconnect();
        if (this.frame) this.win.cancelAnimationFrame(this.frame);
        this.win.removeEventListener('keydown', this.onKey);
        this.win.removeEventListener('focusin', this.onFocus);
        this.win.removeEventListener('pointerdown', this.onPointer, true);
        for (const event of ['hashchange', 'popstate', 'pageshow', 'focus']) this.win.removeEventListener(event, this.schedule);
        this.win.removeEventListener('transitionend', this.schedule, true);
        this.win.removeEventListener('animationend', this.schedule, true);
        this.doc.removeEventListener('viewshow', this.schedule, true);
        this.input.off(this.doc, this.onCommand);
        this.style.remove();
        this.doc.documentElement.classList.remove('familyfin-physical-input');
    }
}
