/**
 * Guru Tracker — Client-side interactivity
 *
 * Provides:
 * - Number formatting utilities
 * - Generic table sort/filter helpers
 */

'use strict';

// ===== Number formatting =====

function formatValue(val) {
    if (val == null || isNaN(val)) return '$0';
    const abs = Math.abs(val);
    if (abs >= 1e9) return '$' + (val / 1e9).toFixed(1) + 'B';
    if (abs >= 1e6) return '$' + (val / 1e6).toFixed(1) + 'M';
    if (abs >= 1e3) return '$' + (val / 1e3).toFixed(1) + 'K';
    return '$' + val.toLocaleString();
}

function formatShares(val) {
    if (val == null || isNaN(val)) return '0';
    return val.toLocaleString();
}

function formatPct(val) {
    if (val == null || isNaN(val)) return '0.0%';
    return (val > 0 ? '+' : '') + val.toFixed(1) + '%';
}

// ===== Utility =====

// Debounce helper for search inputs
function debounce(fn, ms) {
    let timer;
    return function () {
        clearTimeout(timer);
        const args = arguments;
        const ctx = this;
        timer = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
}

// ===== Init =====
// Page-specific init is handled via inline <script> blocks in templates.
// This file provides shared utilities.
