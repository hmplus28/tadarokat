/* ============================================================================
   سامانه تدارکات - Frontend Logic
   ============================================================================ */
/**
 * تبدیل اعداد لاتین به فارسی
 * استفاده: toPersianDigits(12345) → "۱۲۳۴۵"
 */
function toPersianDigits(value) {
    if (value === null || value === undefined) return '';
    const persianDigits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
    return String(value).replace(/[0-9]/g, d => persianDigits[d]);
}

/**
 * تبدیل اعداد به فارسی با جداکننده هزارگان
 * استفاده: toPersianNumber(1234567) → "۱٬۲۳۴٬۵۶۷"
 */
function toPersianNumber(value, decimals = 0) {
    if (value === null || value === undefined) return '۰';
    const num = parseFloat(value);
    if (isNaN(num)) return toPersianDigits(value);
    
    const formatted = num.toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    }).replace(/,/g, '٬');
    
    return toPersianDigits(formatted);
}

const PURCHASE_STATUS_LABELS = {
    waiting_inquiry: 'در انتظار استعلام',
    inquiry_issued: 'استعلام صادر شده',
    order_issued: 'دستور خرید صادر شده',
    order_placed: 'سفارش صادر شده',
    waiting_payment: 'در انتظار پرداخت',
    paid: 'پرداخت شده',
    delivered: 'تحویل شده',
};

function statusLabel(code) {
    return PURCHASE_STATUS_LABELS[code] || code || '—';
}

// Export globally
window.toPersianDigits = toPersianDigits;
window.toPersianNumber = toPersianNumber;
window.statusLabel = statusLabel;
window.PURCHASE_STATUS_LABELS = PURCHASE_STATUS_LABELS;

/**
 * مدیریت dropdown اعلان‌ها
 */
function toggleNotifications() {
    const dropdown = document.getElementById('notifDropdown');
    if (!dropdown) return;
    dropdown.classList.toggle('hidden');
    
    if (!dropdown.classList.contains('hidden')) {
        loadNotifications();
    }
}

function getCsrfToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
}

function updateNotificationBadge(count) {
    const badge = document.querySelector('[onclick="toggleNotifications()"] .animate-pulse, [onclick="toggleNotifications()"] span.absolute');
    if (!badge) return;
    if (count > 0) {
        badge.textContent = toPersianDigits(String(count));
        badge.style.display = 'flex';
    } else {
        badge.style.display = 'none';
    }
}

async function markNotificationsRead() {
    try {
        await fetch('/notifications/api/mark-read/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });
        updateNotificationBadge(0);
    } catch (e) {
        /* silent */
    }
}

async function loadNotifications() {
    const list = document.getElementById('notifList');
    if (!list) return;
    
    try {
        const res = await fetch('/notifications/api/list/');
        const data = await res.json();
        updateNotificationBadge(data.unread_count || 0);
        
        if (!data.items || data.items.length === 0) {
            list.innerHTML = '<p class="text-xs text-slate-400 text-center py-4">اعلان جدیدی نیست</p>';
            return;
        }
        
        list.innerHTML = data.items.map(n => `
            <a href="${n.url || '#'}" class="block px-4 py-3 hover:bg-slate-50 border-b border-slate-50 transition">
                <div class="flex justify-between items-start mb-1">
                    <span class="text-xs font-bold text-slate-800">${n.title}</span>
                    <span class="text-[10px] text-slate-400 whitespace-nowrap mr-2">${toPersianDigits(n.time)}</span>
                </div>
                <p class="text-[11px] text-slate-500 leading-relaxed">${n.message.substring(0, 80)}</p>
            </a>
        `).join('');

        await markNotificationsRead();
    } catch(e) {
        list.innerHTML = '<p class="text-xs text-red-400 text-center py-4">خطا در بارگذاری</p>';
    }
}

// بستن dropdown با کلیک بیرون
document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('notifDropdown');
    if (!dropdown) return;
    if (!e.target.closest('.group') && !dropdown.classList.contains('hidden')) {
        dropdown.classList.add('hidden');
    }
});

// Export globally
window.toggleNotifications = toggleNotifications;
window.loadNotifications = loadNotifications;



const TadarokatApp = {
    // Toast notifications
    toast: {
        show(message, type = 'info', duration = 3500) {
            let container = document.getElementById('toast-container');
            if (!container) {
                container = document.createElement('div');
                container.id = 'toast-container';
                container.className = 'toast-container';
                document.body.appendChild(container);
            }

            const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.innerHTML = `
                <div class="toast-icon">${icons[type] || 'ℹ'}</div>
                <div class="flex-1">${message}</div>
            `;
            container.appendChild(toast);

            setTimeout(() => {
                toast.style.animation = 'toastOut 0.3s ease-out forwards';
                setTimeout(() => toast.remove(), 300);
            }, duration);
        },
        success(msg) { this.show(msg, 'success'); },
        error(msg) { this.show(msg, 'error', 5000); },
        warning(msg) { this.show(msg, 'warning'); },
        info(msg) { this.show(msg, 'info'); },
    },

    // Modal management
    modal: {
        open(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.remove('hidden');
                document.body.style.overflow = 'hidden';
            }
        },
        close(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.add('hidden');
                document.body.style.overflow = '';
            }
        },
        closeOnOverlay(event, modalId) {
            if (event.target === event.currentTarget) {
                this.close(modalId);
            }
        }
    },

    // Loading state
    loading: {
        show(text = 'در حال پردازش...') {
            let loader = document.getElementById('global-loader');
            if (!loader) {
                loader = document.createElement('div');
                loader.id = 'global-loader';
                loader.className = 'modal-overlay';
                loader.style.zIndex = '300';
                loader.innerHTML = `
                    <div class="bg-white rounded-2xl shadow-2xl p-8 flex flex-col items-center gap-4">
                        <div class="spinner" style="width:3rem;height:3rem;border-width:3px;"></div>
                        <p class="text-sm font-medium text-slate-700" id="global-loader-text">${text}</p>
                    </div>
                `;
                document.body.appendChild(loader);
            } else {
                document.getElementById('global-loader-text').textContent = text;
                loader.classList.remove('hidden');
            }
        },
        hide() {
            const loader = document.getElementById('global-loader');
            if (loader) loader.classList.add('hidden');
        }
    },

    // AJAX helper
    async api(url, options = {}) {
        const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                    document.cookie.split('; ').find(r => r.startsWith('csrftoken='))?.split('=')[1];
        
        const defaults = {
            headers: {
                'X-CSRFToken': csrf,
                'Content-Type': 'application/json',
            },
        };

        const config = { ...defaults, ...options };
        if (options.body && typeof options.body === 'object') {
            config.body = JSON.stringify(options.body);
        }

        try {
            const response = await fetch(url, config);
            const contentType = response.headers.get('content-type');
            
            if (contentType && contentType.includes('application/json')) {
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'خطا در درخواست');
                return data;
            }
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response;
        } catch (error) {
            this.toast.error(error.message || 'خطا در ارتباط با سرور');
            throw error;
        }
    },

    // Confirm dialog
    confirm(message, onConfirm) {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.style.zIndex = '250';
        modal.innerHTML = `
            <div class="bg-white rounded-2xl shadow-2xl p-6 max-w-sm w-full">
                <div class="flex items-start gap-3 mb-4">
                    <div class="w-10 h-10 bg-amber-100 text-amber-600 rounded-full flex items-center justify-center text-xl flex-shrink-0">⚠</div>
                    <div>
                        <h3 class="font-bold text-slate-900">تایید عملیات</h3>
                        <p class="text-sm text-slate-600 mt-1">${message}</p>
                    </div>
                </div>
                <div class="flex gap-2">
                    <button class="btn btn-ghost flex-1" id="confirm-cancel">انصراف</button>
                    <button class="btn btn-primary flex-1" id="confirm-ok">تایید</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        modal.querySelector('#confirm-cancel').onclick = () => modal.remove();
        modal.querySelector('#confirm-ok').onclick = () => {
            modal.remove();
            onConfirm();
        };
    },

    fitKpiValue(el) {
        const wrap = el.closest('.kpi-value-fit-wrap');
        if (!wrap) return;

        const available = wrap.getBoundingClientRect().width;
        if (available <= 0) return;

        const BASE_PX = 10;
        const MIN_SCALE = 0.48;

        el.style.setProperty('--kpi-fit-size', BASE_PX + 'px');
        el.style.transform = 'translateY(-50%) scale(1)';

        const textWidth = el.getBoundingClientRect().width;
        if (textWidth <= 0) return;

        const scale = textWidth <= available
            ? 1
            : Math.max(MIN_SCALE, available / textWidth);
        el.style.transform = 'translateY(-50%) scale(' + scale + ')';
    },

    fitKpiValues() {
        document.querySelectorAll('[data-fit-kpi]').forEach((el) => this.fitKpiValue(el));
    },

    // Initialize on DOM ready
    init() {
        // ESC key closes modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                document.querySelectorAll('.modal-overlay:not(.hidden)').forEach(m => {
                    m.classList.add('hidden');
                    document.body.style.overflow = '';
                });
            }
        });

        // Auto-close Django messages after 5s
        setTimeout(() => {
            document.querySelectorAll('[data-auto-dismiss]').forEach(el => {
                el.style.animation = 'toastOut 0.3s ease-out forwards';
                setTimeout(() => el.remove(), 300);
            });
        }, 5000);

        const scheduleFitKpi = () => {
            this.fitKpiValues();
            requestAnimationFrame(() => this.fitKpiValues());
        };

        scheduleFitKpi();
        window.addEventListener('load', scheduleFitKpi);

        let fitTimer = null;
        const debouncedFit = () => {
            clearTimeout(fitTimer);
            fitTimer = setTimeout(() => scheduleFitKpi(), 80);
        };
        window.addEventListener('resize', debouncedFit);
        if (window.visualViewport) {
            window.visualViewport.addEventListener('resize', debouncedFit);
        }

        if (typeof ResizeObserver !== 'undefined') {
            const observer = new ResizeObserver(debouncedFit);
            document.querySelectorAll('.kpi-value-fit-wrap, .kpi-card').forEach((el) => observer.observe(el));
        }

        console.log('🚀 Tadarokat App initialized');
    }
};

// Export globally
window.TadarokatApp = TadarokatApp;
window.showToast = TadarokatApp.toast.show.bind(TadarokatApp.toast);
window.fitKpiValues = () => TadarokatApp.fitKpiValues();

// Auto-init
document.addEventListener('DOMContentLoaded', () => TadarokatApp.init());