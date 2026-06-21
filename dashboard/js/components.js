/**
 * OpenInstaFlow Dashboard — UI Components
 * 
 * Reusable HTML component generators.
 */

const UI = {
    // ── Toast notifications ───────────────────────────────────────────
    _toastContainer: null,

    _ensureToastContainer() {
        if (!this._toastContainer) {
            this._toastContainer = document.createElement('div');
            this._toastContainer.className = 'toast-container';
            document.body.appendChild(this._toastContainer);
        }
        return this._toastContainer;
    },

    toast(message, type = 'info') {
        const container = this._ensureToastContainer();
        const icons = { success: '✓', error: '✕', info: 'ℹ' };
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || 'ℹ'}</span>
            <span>${this.esc(message)}</span>
        `;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100px)';
            toast.style.transition = 'all 0.3s ease-out';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    },

    // ── Escape HTML ───────────────────────────────────────────────────
    esc(str) {
        if (str == null) return '';
        const div = document.createElement('div');
        div.textContent = String(str);
        return div.innerHTML;
    },

    // ── Status badge ──────────────────────────────────────────────────
    badge(status) {
        const s = (status || 'unknown').toLowerCase();
        return `<span class="badge badge-${s}">${this.esc(s)}</span>`;
    },

    // ── Relative time ─────────────────────────────────────────────────
    timeAgo(isoString) {
        if (!isoString) return '—';
        const date = new Date(isoString);
        const now = new Date();
        const diff = Math.floor((now - date) / 1000);
        if (diff < 60) return 'just now';
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
        return date.toLocaleDateString();
    },

    formatDate(isoString) {
        if (!isoString) return '—';
        return new Date(isoString).toLocaleString();
    },

    // ── Loading state ─────────────────────────────────────────────────
    loading(text = 'Loading...') {
        return `
            <div class="loading-overlay">
                <div class="spinner"></div>
                <span>${this.esc(text)}</span>
            </div>
        `;
    },

    // ── Empty state ───────────────────────────────────────────────────
    emptyState(icon, title, message, actionBtn = '') {
        return `
            <div class="empty-state">
                <div class="empty-icon">${icon}</div>
                <h3>${this.esc(title)}</h3>
                <p>${this.esc(message)}</p>
                ${actionBtn}
            </div>
        `;
    },

    // ── Modal ─────────────────────────────────────────────────────────
    showModal(title, bodyHtml, footerHtml = '') {
        // Remove existing modal
        this.closeModal();

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.id = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal">
                <div class="modal-header">
                    <h2>${this.esc(title)}</h2>
                    <button class="modal-close" onclick="UI.closeModal()">✕</button>
                </div>
                <div class="modal-body">${bodyHtml}</div>
                ${footerHtml ? `<div class="modal-footer">${footerHtml}</div>` : ''}
            </div>
        `;
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) this.closeModal();
        });
        document.body.appendChild(overlay);
    },

    closeModal() {
        const m = document.getElementById('modal-overlay');
        if (m) m.remove();
    },

    // ── Stat card ─────────────────────────────────────────────────────
    statCard(icon, value, label, accentClass = '') {
        return `
            <div class="stat-card ${accentClass}">
                <div class="stat-icon">${icon}</div>
                <div class="stat-value">${this.esc(String(value))}</div>
                <div class="stat-label">${this.esc(label)}</div>
            </div>
        `;
    },

    // ── Confirmation dialog ───────────────────────────────────────────
    confirm(title, message) {
        return new Promise((resolve) => {
            this.showModal(
                title,
                `<p class="text-sm">${this.esc(message)}</p>`,
                `
                    <button class="btn btn-secondary" onclick="UI.closeModal(); window._confirmResolve(false)">Cancel</button>
                    <button class="btn btn-danger" onclick="UI.closeModal(); window._confirmResolve(true)">Confirm</button>
                `
            );
            window._confirmResolve = resolve;
        });
    },

    // ── Copy to clipboard ─────────────────────────────────────────────
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.toast('Copied to clipboard!', 'success');
        } catch {
            // Fallback
            const input = document.createElement('textarea');
            input.value = text;
            document.body.appendChild(input);
            input.select();
            document.execCommand('copy');
            document.body.removeChild(input);
            this.toast('Copied to clipboard!', 'success');
        }
    },
};
