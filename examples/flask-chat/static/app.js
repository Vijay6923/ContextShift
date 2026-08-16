document.addEventListener('DOMContentLoaded', () => {
    // --- Elements ---
    const chatWindow = document.getElementById('chat-window');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    let typingBubble = null;
    
    const currentTokensEl = document.getElementById('current-tokens');
    const tokenProgress = document.getElementById('token-progress');
    const percentageLabel = document.getElementById('percentage-label');
    
    const summarizeBtn = document.getElementById('summarize-btn');
    const pruneBtn = document.getElementById('prune-btn');
    const resetBtn = document.getElementById('reset-btn');
    const autoContextToggle = document.getElementById('auto-context-toggle');
    const statusMessage = document.getElementById('status-message');
    const themeToggle = document.getElementById('theme-toggle');
    
    // --- Mobile Sidebar Elements ---
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const closeSidebarBtn = document.getElementById('close-sidebar-btn');
    const sidebar = document.getElementById('sidebar');
    const compactProgress = document.getElementById('compact-progress');
    const compactPercentage = document.getElementById('compact-percentage');

    // --- Upload Modal Elements ---
    const attachBtn = document.getElementById('attach-btn');
    const lockMessage = document.getElementById('lock-message');
    const inputWrapper = document.getElementById('input-wrapper');
    const fileInput = document.getElementById('file-input');
    const uploadModal = document.getElementById('upload-modal');
    const modalCloseBtn = document.getElementById('modal-close-btn');
    const modalCancelBtn = document.getElementById('modal-cancel-btn');
    const modalSubmitBtn = document.getElementById('modal-submit-btn');
    const dropZone = document.getElementById('drop-zone');
    const filePreview = document.getElementById('file-preview');
    const filePreviewIcon = document.getElementById('file-preview-icon');
    const filePreviewName = document.getElementById('file-preview-name');
    const filePreviewSize = document.getElementById('file-preview-size');
    const fileClearBtn = document.getElementById('file-clear-btn');
    const uploadPrompt = document.getElementById('upload-prompt');

    // --- State ---
    let isTyping = false;
    let autoContextEnabled = false;

    // --- Theme ---
    function applyTheme(isLight) {
        if (isLight) {
            document.body.classList.add('light-mode');
            themeToggle.querySelector('.theme-icon').textContent = '☀️';
            themeToggle.querySelector('.theme-label').textContent = 'Light';
        } else {
            document.body.classList.remove('light-mode');
            themeToggle.querySelector('.theme-icon').textContent = '🌙';
            themeToggle.querySelector('.theme-label').textContent = 'Dark';
        }
        localStorage.setItem('contextshift-theme', isLight ? 'light' : 'dark');
    }

    // Load saved theme preference
    const savedTheme = localStorage.getItem('contextshift-theme');
    applyTheme(savedTheme === 'light');

    themeToggle.addEventListener('click', () => {
        const isCurrentlyLight = document.body.classList.contains('light-mode');
        applyTheme(!isCurrentlyLight);
    });

    // --- Upload Modal Logic ---
    let selectedFile = null;

    function openModal() {
        uploadModal.style.display = 'flex';
        uploadPrompt.value = '';
        clearFile();
        // Slight delay so display:flex is painted before animation
        requestAnimationFrame(() => uploadModal.querySelector('.modal-card').style.opacity = '1');
    }

    function closeModal() {
        uploadModal.style.display = 'none';
        clearFile();
    }

    function formatBytes(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    function setFile(file) {
        const allowed = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf'];
        const isPdf = file.name.toLowerCase().endsWith('.pdf') || file.type === 'application/pdf';
        const isImage = file.type.startsWith('image/');

        if (!isPdf && !isImage) {
            showStatus('Unsupported file type. Use JPG, PNG, GIF, WEBP, or PDF.', 'danger');
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            showStatus('File too large. Max 10 MB.', 'danger');
            return;
        }

        selectedFile = file;
        filePreviewIcon.textContent = isPdf ? '📄' : '🖼️';
        filePreviewName.textContent = file.name;
        filePreviewSize.textContent = formatBytes(file.size);

        // Show preview, hide drop zone text
        filePreview.style.display = 'flex';
        modalSubmitBtn.disabled = false;
    }

    function clearFile() {
        selectedFile = null;
        fileInput.value = '';
        filePreview.style.display = 'none';
        modalSubmitBtn.disabled = true;
    }

    async function uploadFile() {
        if (!selectedFile || isTyping) return;

        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('prompt', uploadPrompt.value.trim());

        closeModal();
        setTyping(true);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.error) {
                showStatus(data.error, 'danger');
            } else {
                await loadMessages();
                if (autoContextEnabled && data.token_stats.percentage > 80) {
                    showStatus('Auto-management: Pruning context...', 'warning');
                    await pruneContext();
                }
            }
        } catch (error) {
            console.error('Upload error:', error);
            showStatus('Upload failed. Please try again.', 'danger');
        } finally {
            setTyping(false);
        }
    }

    // Attach button → open modal
    attachBtn.addEventListener('click', openModal);

    // Close buttons
    modalCloseBtn.addEventListener('click', closeModal);
    modalCancelBtn.addEventListener('click', closeModal);

    // Click outside modal card → close
    uploadModal.addEventListener('click', (e) => {
        if (e.target === uploadModal) closeModal();
    });

    // Submit button
    modalSubmitBtn.addEventListener('click', uploadFile);

    // Keyboard: Escape → close
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && uploadModal.style.display !== 'none') closeModal();
    });

    // Click on drop zone (not on the preview) → trigger file picker
    dropZone.addEventListener('click', (e) => {
        if (!e.target.closest('.file-preview')) {
            fileInput.click();
        }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files[0]) setFile(e.target.files[0]);
    });

    // Clear selected file
    fileClearBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearFile();
    });

    // Drag and drop on drop zone
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-active');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-active');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-active');
        const file = e.dataTransfer.files[0];
        if (file) setFile(file);
    });

    // --- Mobile Menu Toggle ---
    mobileMenuBtn.addEventListener('click', () => {
        sidebar.classList.add('open');
        // Add a backdrop if needed, or just let users click X
    });

    closeSidebarBtn.addEventListener('click', () => {
        sidebar.classList.remove('open');
    });

    // Close sidebar on window resize if it gets back to desktop
    window.addEventListener('resize', () => {
        if (window.innerWidth > 768 && sidebar.classList.contains('open')) {
            sidebar.classList.remove('open');
        }
    });

    // --- Initial Load ---
    loadMessages();

    // --- Functions ---
    async function loadMessages() {
        try {
            const response = await fetch('/messages');
            const data = await response.json();
            renderMessages(data.messages);
            updateTokenPanel(data.token_stats);
        } catch (error) {
            console.error('Error loading messages:', error);
            showStatus('Failed to load messages', 'danger');
        }
    }

    function renderMessages(messages) {
        if (messages.length === 0) {
            chatWindow.innerHTML = `
                <div class="welcome-message">
                    <h3>Welcome to ContextShift</h3>
                    <p>Start a conversation to see intelligent context management in action.</p>
                </div>
            `;
            return;
        }

        chatWindow.innerHTML = '';
        messages.forEach(msg => {
            const msgEl = createMessageElement(msg);
            chatWindow.appendChild(msgEl);
        });
        scrollToBottom();
    }

    function createMessageElement(msg) {
        const div = document.createElement('div');
        div.className = `message ${msg.role} ${msg.is_pinned ? 'pinned' : ''}`;
        div.dataset.id = msg.id;

        const timestamp = new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        // Handle markdown for assistant
        let contentHtml = msg.content;
        if (msg.role === 'assistant') {
            try {
                contentHtml = typeof marked !== 'undefined' ? marked.parse(msg.content) : msg.content;
            } catch (e) {
                console.error('Marked parsing error:', e);
                contentHtml = `<p>${escapeHtml(msg.content)}</p>`;
            }
        } else {
            contentHtml = `<p>${escapeHtml(msg.content)}</p>`;
        }

        const actionsHtml = msg.role === 'user' ? `
            <div class="message-actions">
                <button class="action-btn pin-btn ${msg.is_pinned ? 'active' : ''}" title="Pin message">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v2a10 10 0 0 0 5 8.66l3 1.73a2 2 0 0 0 2 0l3-1.73A10 10 0 0 0 21 10z"></path></svg>
                </button>
                <button class="action-btn delete-btn" title="Delete message">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                </button>
            </div>
        ` : '';

        div.innerHTML = `
            <div class="message-header">
                <span class="role-label">${msg.role === 'user' ? 'You' : msg.role === 'assistant' ? 'Assistant' : 'System'}</span>
                <span class="message-time">${timestamp}</span>
                <span class="message-tokens">${msg.token_count} tokens</span>
            </div>
            <div class="message-content">
                ${contentHtml}
            </div>
            ${actionsHtml}
        `;

        // Event listeners for actions (only if they exist)
        const pinBtn = div.querySelector('.pin-btn');
        if (pinBtn) pinBtn.addEventListener('click', () => togglePin(msg.id));
        
        const deleteBtn = div.querySelector('.delete-btn');
        if (deleteBtn) deleteBtn.addEventListener('click', () => deleteMessage(msg.id));

        return div;
    }

    // Immediately inject user message into chat (optimistic render)
    function addOptimisticUserMessage(text) {
        // Remove the welcome placeholder if it's still there
        const welcome = chatWindow.querySelector('.welcome-message');
        if (welcome) welcome.remove();

        const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const div = document.createElement('div');
        div.className = 'message user optimistic';
        div.innerHTML = `
            <div class="message-header">
                <span class="role-label">You</span>
                <span class="message-time">${now}</span>
            </div>
            <div class="message-content"><p>${escapeHtml(text)}</p></div>
        `;
        chatWindow.appendChild(div);
        scrollToBottom();
    }

    async function sendMessage() {
        const text = userInput.value.trim();
        if (!text || isTyping) return;

        userInput.value = '';
        userInput.style.height = 'auto';

        // 1. Show user message instantly
        addOptimisticUserMessage(text);

        // 2. Show thinking bubble
        setTyping(true);

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Server error');
            }

            // 3. Handle streaming response
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            // Remove thinking bubble and prepare assistant message
            setTyping(false);
            const assistantMsgEl = createMessageElement({
                role: 'assistant',
                content: '',
                timestamp: new Date().toISOString(),
                token_count: '...',
                id: 'temp-' + Date.now()
            });
            chatWindow.appendChild(assistantMsgEl);
            const contentEl = assistantMsgEl.querySelector('.message-content');
            
            let fullText = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        
                        if (data.startsWith('[STATS]')) {
                            const stats = JSON.parse(data.slice(7));
                            updateTokenPanel(stats);
                            // Also update the token count on the message itself
                            const tokenLabel = assistantMsgEl.querySelector('.message-tokens');
                            if (tokenLabel) tokenLabel.textContent = 'Calculated';
                        } else if (data.startsWith('[ERROR]')) {
                            showStatus(data.slice(7), 'danger');
                        } else {
                            // Normal token
                            fullText += data;
                            // Incremental update (simple append for now)
                            contentEl.innerHTML = `<p>${escapeHtml(fullText)}</p>`;
                            scrollToBottom();
                        }
                    }
                }
            }
            
            // Final render with Markdown
            if (typeof marked !== 'undefined') {
                contentEl.innerHTML = marked.parse(fullText);
            }
            
            // Refresh to get official IDs and correct formatting
            await loadMessages();

        } catch (error) {
            console.error('Error sending message:', error);
            showStatus(error.message || 'Connection error', 'danger');
            setTyping(false);
        }
    }

    async function togglePin(id) {
        try {
            const response = await fetch(`/pin/${id}`, { method: 'POST' });
            if (response.ok) {
                loadMessages();
            }
        } catch (error) {
            console.error('Error toggling pin:', error);
        }
    }

    async function deleteMessage(id) {
        if (!confirm('Archive this message?')) return;
        try {
            const response = await fetch(`/message/${id}`, { method: 'DELETE' });
            if (response.ok) {
                loadMessages();
            }
        } catch (error) {
            console.error('Error deleting message:', error);
        }
    }

    async function summarizeContext() {
        showStatus('Summarizing...', 'accent');
        try {
            const response = await fetch('/summarize', { method: 'POST' });
            const data = await response.json();
            showStatus(data.message || data.error, data.error ? 'danger' : 'success');
            loadMessages();
        } catch (error) {
            showStatus('Summarization failed', 'danger');
        }
    }

    async function pruneContext() {
        showStatus('Pruning...', 'accent');
        try {
            const response = await fetch('/prune', { method: 'POST' });
            const data = await response.json();
            showStatus(data.message || data.error, data.error ? 'danger' : 'success');
            loadMessages();
        } catch (error) {
            showStatus('Pruning failed', 'danger');
        }
    }

    async function resetChat() {
        if (!confirm('Are you sure you want to clear the entire conversation?')) return;
        try {
            const response = await fetch('/reset', { method: 'POST' });
            if (response.ok) {
                showStatus('Conversation reset', 'success');
                loadMessages();
            }
        } catch (error) {
            showStatus('Reset failed', 'danger');
        }
    }

    function updateTokenPanel(stats) {
        currentTokensEl.textContent = stats.current_tokens.toLocaleString();

        // Cap bar visually at 100% — never overflow the container
        const cappedPct = Math.min(stats.percentage, 100);
        tokenProgress.style.width = `${cappedPct}%`;

        // Check for context overflow to lock/unlock input
        const isOverflow = stats.percentage >= 100;
        
        if (isOverflow) {
            userInput.disabled = true;
            sendBtn.disabled = true;
            attachBtn.disabled = true;
            lockMessage.style.display = 'flex';
            inputWrapper.classList.add('input-locked');
            // If in modal, disable the submit there too
            if (modalSubmitBtn) modalSubmitBtn.disabled = true;
        } else {
            userInput.disabled = false;
            sendBtn.disabled = false;
            attachBtn.disabled = false;
            lockMessage.style.display = 'none';
            inputWrapper.classList.remove('input-locked');
        }

        if (stats.percentage > 100) {
            // Overflow state: show clear warning
            percentageLabel.textContent = `⚠ ${stats.percentage}% — Context overflow!`;
            tokenProgress.style.backgroundColor = 'var(--danger)';
            percentageLabel.style.color = 'var(--danger)';
        } else if (stats.percentage < 60) {
            percentageLabel.textContent = `${stats.percentage}% used`;
            tokenProgress.style.backgroundColor = 'var(--success)';
            percentageLabel.style.color = 'var(--success)';
        } else if (stats.percentage < 80) {
            percentageLabel.textContent = `${stats.percentage}% used`;
            tokenProgress.style.backgroundColor = 'var(--warning)';
            percentageLabel.style.color = 'var(--warning)';
        } else {
            percentageLabel.textContent = `${stats.percentage}% used`;
            tokenProgress.style.backgroundColor = 'var(--danger)';
            percentageLabel.style.color = 'var(--danger)';
        }

        // Update compact bar (mobile)
        if (compactProgress && compactPercentage) {
            compactProgress.style.width = `${cappedPct}%`;
            compactPercentage.textContent = `${Math.round(stats.percentage)}%`;
            
            if (stats.percentage > 100) {
                compactProgress.style.backgroundColor = 'var(--danger)';
            } else if (stats.percentage > 80) {
                compactProgress.style.backgroundColor = 'var(--warning)';
            } else {
                compactProgress.style.backgroundColor = 'var(--success)';
            }
        }
    }

    function setTyping(state) {
        if (isTyping === state) return;
        isTyping = state;
        
        if (state) {
            // Create typing bubble
            typingBubble = document.createElement('div');
            typingBubble.className = 'message assistant typing';
            typingBubble.innerHTML = `
                <div class="message-header">
                    <span class="role-label">Assistant</span>
                    <span class="status-thinking">Thinking...</span>
                </div>
                <div class="message-content">
                    <div class="typing-dots">
                        <span></span><span></span><span></span>
                    </div>
                </div>
            `;
            chatWindow.appendChild(typingBubble);
            scrollToBottom();
        } else {
            // Remove typing bubble
            if (typingBubble) {
                typingBubble.remove();
                typingBubble = null;
            }
        }
        
        sendBtn.disabled = state;
    }

    function showStatus(msg, type) {
        statusMessage.textContent = msg;
        statusMessage.className = `status-message text-${type}`;
        setTimeout(() => {
            if (statusMessage.textContent === msg) {
                statusMessage.textContent = '';
                statusMessage.className = 'status-message';
            }
        }, 5000);
    }

    function scrollToBottom() {
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // --- Event Listeners ---
    sendBtn.addEventListener('click', sendMessage);
    
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-grow textarea
    userInput.addEventListener('input', () => {
        userInput.style.height = 'auto';
        userInput.style.height = `${userInput.scrollHeight}px`;
    });

    summarizeBtn.addEventListener('click', summarizeContext);
    pruneBtn.addEventListener('click', pruneContext);
    resetBtn.addEventListener('click', resetChat);
    
    autoContextToggle.addEventListener('change', (e) => {
        autoContextEnabled = e.target.checked;
        showStatus(`Auto-management ${autoContextEnabled ? 'ON' : 'OFF'}`, 'success');
    });
});
