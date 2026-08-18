/**
 * Bot_loc_tin_nhan — Frontend Application
 *
 * Handles:
 * - Message filtering via API
 * - Copy to clipboard
 * - Bot connect/disconnect
 * - Status polling
 * - Toast notifications
 * - Keyboard shortcuts
 */

(function () {
    'use strict';

    // ── DOM Elements ──
    const $ = (sel) => document.querySelector(sel);
    const inputText = $('#input-text');
    const outputText = $('#output-text');
    const statsBar = $('#stats-bar');
    const statInput = $('#stat-input');
    const statOutput = $('#stat-output');
    const statDuplicate = $('#stat-duplicate');
    const statInvalid = $('#stat-invalid');

    const btnFilter = $('#btn-filter');
    const btnCopy = $('#btn-copy');
    const btnClear = $('#btn-clear');
    const btnToggleOptions = $('#btn-toggle-options');
    const filterOptionsPanel = $('#filter-options');

    // Bot elements
    const btnConnect = $('#btn-connect');
    const btnDisconnect = $('#btn-disconnect');
    const btnCopyUrl = $('#btn-copy-url');
    const botToken = $('#bot-token');
    const ngrokToken = $('#ngrok-token');
    const webhookPort = $('#webhook-port');
    const webhookSecret = $('#webhook-secret');
    const webhookUrlDisplay = $('#webhook-url-display');
    const publicUrl = $('#public-url');

    // Status dots
    const statusServer = $('#status-server .dot');
    const statusBot = $('#status-bot .dot');
    const statusNgrok = $('#status-ngrok .dot');

    // Filter options checkboxes
    const optRemoveTimestamp = $('#opt-remove-timestamp');
    const optRemoveSender = $('#opt-remove-sender');
    const optDeduplicate = $('#opt-deduplicate');
    const optNormalizeWs = $('#opt-normalize-ws');
    const optCaseSensitive = $('#opt-case-sensitive');

    const toastContainer = $('#toast-container');

    // ── State ──
    let statusPollInterval = null;
    let isConnected = false;

    // ── Toast Notifications ──
    function showToast(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('toast-out');
            toast.addEventListener('animationend', () => toast.remove());
        }, duration);
    }

    // ── Filter Options Toggle ──
    btnToggleOptions.addEventListener('click', () => {
        const isVisible = filterOptionsPanel.style.display !== 'none';
        filterOptionsPanel.style.display = isVisible ? 'none' : 'flex';
    });

    // ── Filter Messages ──
    async function filterMessages() {
        const text = inputText.value.trim();
        if (!text) {
            showToast('Vui lòng dán tin nhắn vào ô Input.', 'error');
            inputText.focus();
            return;
        }

        btnFilter.classList.add('loading');
        btnFilter.disabled = true;

        try {
            const options = {
                remove_timestamp: optRemoveTimestamp.checked,
                remove_sender: optRemoveSender.checked,
                deduplicate: optDeduplicate.checked,
                normalize_whitespace: optNormalizeWs.checked,
                case_sensitive: optCaseSensitive.checked,
            };

            const resp = await fetch('/api/filter', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, options }),
            });

            const data = await resp.json();

            if (resp.ok) {
                outputText.value = data.result;

                // Show stats
                statInput.textContent = data.input_count;
                statOutput.textContent = data.output_count;
                statDuplicate.textContent = data.duplicate_count;
                statInvalid.textContent = data.invalid_count;
                statsBar.style.display = 'flex';

                // Enable copy button
                btnCopy.disabled = !data.result;

                showToast(
                    `Đã lọc: ${data.output_count} dòng (loại ${data.duplicate_count} trùng)`,
                    'success'
                );
            } else {
                showToast(data.error || 'Lỗi khi lọc tin nhắn.', 'error');
            }
        } catch (err) {
            showToast('Không thể kết nối server.', 'error');
            console.error('Filter error:', err);
        } finally {
            btnFilter.classList.remove('loading');
            btnFilter.disabled = false;
        }
    }

    btnFilter.addEventListener('click', filterMessages);

    // ── Copy Result ──
    async function copyResult() {
        const text = outputText.value;
        if (!text) return;

        try {
            await navigator.clipboard.writeText(text);
            showToast('Đã sao chép kết quả!', 'success', 2000);

            // Visual feedback on button
            const originalHTML = btnCopy.innerHTML;
            btnCopy.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"/>
                </svg>
                <span>Copied!</span>
            `;
            setTimeout(() => {
                btnCopy.innerHTML = originalHTML;
            }, 1500);
        } catch (err) {
            // Fallback
            outputText.select();
            document.execCommand('copy');
            showToast('Đã sao chép kết quả!', 'success', 2000);
        }
    }

    btnCopy.addEventListener('click', copyResult);

    // ── Clear Form ──
    btnClear.addEventListener('click', () => {
        inputText.value = '';
        outputText.value = '';
        statsBar.style.display = 'none';
        btnCopy.disabled = true;
        inputText.focus();
    });

    // ── Keyboard Shortcuts ──
    document.addEventListener('keydown', (e) => {
        // Ctrl+Enter or Cmd+Enter to filter
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            filterMessages();
        }
    });

    // ═══════════════════════════════════════════════
    // Bot Management
    // ═══════════════════════════════════════════════

    // ── Connect Bot ──
    async function connectBot() {
        const token = botToken.value.trim();
        const ngrok = ngrokToken.value.trim();

        if (!token) {
            showToast('Vui lòng nhập Bot Token.', 'error');
            botToken.focus();
            return;
        }
        if (!ngrok) {
            showToast('Vui lòng nhập Ngrok Authtoken.', 'error');
            ngrokToken.focus();
            return;
        }

        btnConnect.classList.add('loading');
        btnConnect.disabled = true;
        setAllStatus('connecting');

        try {
            const resp = await fetch('/api/bot/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    bot_token: token,
                    ngrok_authtoken: ngrok,
                    webhook_port: parseInt(webhookPort.value) || 5001,
                    webhook_secret: webhookSecret.value.trim(),
                }),
            });

            const data = await resp.json();
            updateStatus(data);

            if (data.error) {
                showToast(data.error, 'error', 5000);
            } else {
                isConnected = true;
                showToast(`Bot @${data.bot_username} đã kết nối!`, 'success');
                btnConnect.disabled = true;
                btnDisconnect.disabled = false;
                startStatusPolling();
            }
        } catch (err) {
            showToast('Không thể kết nối. Kiểm tra server.', 'error');
            setAllStatus('offline');
            console.error('Connect error:', err);
        } finally {
            btnConnect.classList.remove('loading');
            if (!isConnected) {
                btnConnect.disabled = false;
            }
        }
    }

    btnConnect.addEventListener('click', connectBot);

    // ── Disconnect Bot ──
    async function disconnectBot() {
        btnDisconnect.classList.add('loading');
        btnDisconnect.disabled = true;

        try {
            const resp = await fetch('/api/bot/disconnect', { method: 'POST' });
            const data = await resp.json();
            updateStatus(data);

            isConnected = false;
            btnConnect.disabled = false;
            btnDisconnect.disabled = true;
            stopStatusPolling();

            showToast('Bot đã ngắt kết nối.', 'info');
        } catch (err) {
            showToast('Lỗi khi ngắt kết nối.', 'error');
            console.error('Disconnect error:', err);
        } finally {
            btnDisconnect.classList.remove('loading');
        }
    }

    btnDisconnect.addEventListener('click', disconnectBot);

    // ── Copy Webhook URL ──
    if (btnCopyUrl) {
        btnCopyUrl.addEventListener('click', async () => {
            const url = publicUrl.textContent;
            if (!url || url === '—') return;
            try {
                await navigator.clipboard.writeText(url);
                showToast('URL đã sao chép!', 'success', 2000);
            } catch (err) {
                console.error('Copy URL error:', err);
            }
        });
    }

    // ── Status Updates ──
    function updateStatus(data) {
        // Update dots
        setDotStatus(statusServer, data.local_server);
        setDotStatus(statusBot, data.bot_connected);
        setDotStatus(statusNgrok, data.ngrok_online);

        // Show/hide webhook URL
        if (data.public_url) {
            publicUrl.textContent = data.public_url;
            webhookUrlDisplay.style.display = 'block';
        } else {
            publicUrl.textContent = '—';
            webhookUrlDisplay.style.display = 'none';
        }
    }

    function setDotStatus(dot, online) {
        dot.className = 'dot';
        dot.classList.add(online ? 'dot-online' : 'dot-offline');
    }

    function setAllStatus(state) {
        const dots = [statusServer, statusBot, statusNgrok];
        dots.forEach((dot) => {
            dot.className = 'dot';
            dot.classList.add(`dot-${state}`);
        });
    }

    // ── Status Polling ──
    function startStatusPolling() {
        stopStatusPolling();
        statusPollInterval = setInterval(async () => {
            try {
                const resp = await fetch('/api/bot/status');
                const data = await resp.json();
                updateStatus(data);

                // Auto-detect disconnect
                if (!data.bot_connected && isConnected) {
                    isConnected = false;
                    btnConnect.disabled = false;
                    btnDisconnect.disabled = true;
                    stopStatusPolling();
                    showToast('Bot đã mất kết nối!', 'error');
                }
            } catch (err) {
                // Server might be down
                console.warn('Status poll failed:', err);
            }
        }, 5000);
    }

    function stopStatusPolling() {
        if (statusPollInterval) {
            clearInterval(statusPollInterval);
            statusPollInterval = null;
        }
    }

    // ── Initial Status Check ──
    (async function checkInitialStatus() {
        try {
            const resp = await fetch('/api/bot/status');
            const data = await resp.json();
            updateStatus(data);

            if (data.bot_connected) {
                isConnected = true;
                btnConnect.disabled = true;
                btnDisconnect.disabled = false;
                startStatusPolling();
            }
        } catch (err) {
            console.warn('Initial status check failed:', err);
        }
    })();

    // ── Auto-fill from .env defaults ──
    (async function loadDefaults() {
        try {
            const resp = await fetch('/api/bot/defaults');
            const data = await resp.json();

            if (data.bot_token && !botToken.value) {
                botToken.value = data.bot_token;
            }
            if (data.ngrok_authtoken && !ngrokToken.value) {
                ngrokToken.value = data.ngrok_authtoken;
            }
            if (data.webhook_port) {
                webhookPort.value = data.webhook_port;
            }
            if (data.webhook_secret && !webhookSecret.value) {
                webhookSecret.value = data.webhook_secret;
            }
        } catch (err) {
            console.warn('Failed to load defaults:', err);
        }
    })();

    // ── Auto-resize textarea ──
    inputText.addEventListener('input', function () {
        // Auto-adjust height
        this.style.height = 'auto';
        const maxHeight = 500;
        this.style.height = Math.min(this.scrollHeight, maxHeight) + 'px';
    });

})();
