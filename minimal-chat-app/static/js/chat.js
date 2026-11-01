// Minimalist Chat App — Real-Time Core Script

// State
let currentUser = null;
let currentToken = null;
let activeConversation = null;
let activeWebSocket = null;
let conversations = [];
let typingTimeout = null;
let isUserTyping = false;

// DOM Elements
const sidebarEl = document.getElementById("sidebar");
const chatAppEl = document.getElementById("chat-app");
const chatPlaceholderEl = document.getElementById("chat-placeholder");
const chatActiveViewEl = document.getElementById("chat-active-view");
const conversationsListEl = document.getElementById("conversations-list");
const conversationsLoadingEl = document.getElementById("conversations-loading");
const noConversationsEl = document.getElementById("no-conversations");
const chatCountEl = document.getElementById("chat-count");
const messagesContainerEl = document.getElementById("messages-container");
const messagesListEl = document.getElementById("messages-list");
const messageInputEl = document.getElementById("message-input");
const btnSendEl = document.getElementById("btn-send-message");
const userSearchInputEl = document.getElementById("user-search-input");
const searchResultsEl = document.getElementById("search-results");
const searchResultsListEl = document.getElementById("search-results-list");
const btnClearSearchEl = document.getElementById("btn-clear-search");
const emojiPickerEl = document.getElementById("emoji-picker");
const typingIndicatorEl = document.getElementById("typing-indicator");
const typingTextEl = document.getElementById("typing-text");
const btnScrollBottomEl = document.getElementById("btn-scroll-bottom");
const partnerAvatarEl = document.getElementById("partner-avatar");
const partnerStatusDotEl = document.getElementById("partner-status-dot");
const partnerUsernameEl = document.getElementById("partner-username");
const partnerStatusLabelEl = document.getElementById("partner-status-label");
const myAvatarEl = document.getElementById("my-avatar");
const myUsernameEl = document.getElementById("my-username");

// Initialize on load
document.addEventListener("DOMContentLoaded", async () => {
    currentToken = localStorage.getItem("access_token");
    const storedUser = localStorage.getItem("current_user");

    if (storedUser) {
        try {
            currentUser = JSON.parse(storedUser);
        } catch (e) {
            currentUser = null;
        }
    }

    // Verify authentication with backend
    await verifyAuth();
    await loadConversations();

    // Auto focus
    if (userSearchInputEl) {
        userSearchInputEl.focus();
    }
});

// --- Authentication & User Hydration ---

async function verifyAuth() {
    try {
        const response = await fetch("/api/users/me", {
            headers: currentToken ? { "Authorization": `Bearer ${currentToken}` } : {}
        });

        if (!response.ok) {
            // Not authenticated, redirect to login
            localStorage.clear();
            window.location.href = "/login";
            return;
        }

        currentUser = await response.json();
        localStorage.setItem("current_user", JSON.stringify(currentUser));

        // Render current user profile in sidebar footer
        if (myUsernameEl) myUsernameEl.textContent = currentUser.username;
        if (myAvatarEl) {
            myAvatarEl.src = currentUser.profile_picture || `https://api.dicebear.com/7.x/initials/svg?seed=${currentUser.username}&backgroundColor=f1f5f9&textColor=0f172a`;
        }
    } catch (err) {
        console.error("Auth verification failed:", err);
    }
}

async function handleLogout() {
    try {
        await fetch("/api/logout", {
            method: "POST",
            headers: currentToken ? { "Authorization": `Bearer ${currentToken}` } : {}
        });
    } catch (e) {
        // Ignore network errors on logout
    }
    localStorage.clear();
    window.location.href = "/login";
}

// --- Conversations Management ---

async function loadConversations() {
    try {
        const response = await fetch("/api/conversations", {
            headers: currentToken ? { "Authorization": `Bearer ${currentToken}` } : {}
        });

        if (!response.ok) {
            throw new Error("Failed to load conversations");
        }

        conversations = await response.json();
        renderConversationsList(conversations);
    } catch (err) {
        console.error("Error loading conversations:", err);
    } finally {
        if (conversationsLoadingEl) {
            conversationsLoadingEl.classList.add("hidden");
        }
    }
}

function renderConversationsList(convList) {
    if (!conversationsListEl) return;
    conversationsListEl.innerHTML = "";

    if (!convList || convList.length === 0) {
        if (noConversationsEl) noConversationsEl.classList.remove("hidden");
        if (chatCountEl) chatCountEl.textContent = "0";
        return;
    }

    if (noConversationsEl) noConversationsEl.classList.add("hidden");
    if (chatCountEl) chatCountEl.textContent = convList.length;

    convList.forEach(conv => {
        const otherUser = conv.other_user;
        const lastMsg = conv.last_message;
        const isActive = activeConversation && activeConversation.id === conv.id;

        const item = document.createElement("div");
        item.className = `conversation-item ${isActive ? "active" : ""}`;
        item.dataset.convId = conv.id;
        item.onclick = () => selectConversation(conv.id);

        const avatarUrl = otherUser.profile_picture || `https://api.dicebear.com/7.x/initials/svg?seed=${otherUser.username}&backgroundColor=f1f5f9&textColor=0f172a`;
        const timeFormatted = lastMsg ? formatMessageTimestamp(lastMsg.created_at, true) : "";
        
        let previewText = "No messages yet";
        if (lastMsg) {
            if (lastMsg.message_type === "instagram_reel") {
                previewText = "📹 Instagram Reel";
            } else if (lastMsg.message_type === "youtube") {
                previewText = "▶️ YouTube Video";
            } else if (lastMsg.message_type === "link") {
                previewText = "🔗 Link shared";
            } else {
                previewText = escapeHtml(lastMsg.content);
            }
        }

        item.innerHTML = `
            <div class="avatar-container">
                <img src="${avatarUrl}" alt="${escapeHtml(otherUser.username)}" class="avatar-img">
                <span class="status-indicator ${otherUser.is_online ? "online" : ""}" id="conv-status-dot-${otherUser.id}"></span>
            </div>
            <div class="conv-meta">
                <div class="conv-top-row">
                    <span class="conv-username">${escapeHtml(otherUser.username)}</span>
                    <span class="conv-time">${timeFormatted}</span>
                </div>
                <div class="conv-bottom-row">
                    <span class="conv-preview ${conv.unread_count > 0 ? "unread" : ""}" id="conv-preview-${conv.id}">${previewText}</span>
                    ${conv.unread_count > 0 ? `<span class="conv-unread-badge" id="conv-badge-${conv.id}">${conv.unread_count}</span>` : ""}
                </div>
            </div>
        `;
        conversationsListEl.appendChild(item);
    });

    if (window.lucide) lucide.createIcons();
}

// --- User Search & Start Conversation ---

let searchDebounceTimer = null;

function handleUserSearch(query) {
    clearTimeout(searchDebounceTimer);
    const q = query.trim();

    if (btnClearSearchEl) {
        btnClearSearchEl.classList.toggle("hidden", q.length === 0);
    }

    if (!q) {
        if (searchResultsEl) searchResultsEl.classList.add("hidden");
        return;
    }

    searchDebounceTimer = setTimeout(async () => {
        try {
            const resp = await fetch(`/api/users/search?q=${encodeURIComponent(q)}`, {
                headers: currentToken ? { "Authorization": `Bearer ${currentToken}` } : {}
            });
            if (resp.ok) {
                const users = await resp.json();
                renderSearchResults(users);
            }
        } catch (e) {
            console.error("Search failed:", e);
        }
    }, 250);
}

function clearSearch() {
    if (userSearchInputEl) {
        userSearchInputEl.value = "";
        handleUserSearch("");
        userSearchInputEl.focus();
    }
}

function focusSearch() {
    if (userSearchInputEl) {
        userSearchInputEl.focus();
    }
}

function renderSearchResults(users) {
    if (!searchResultsEl || !searchResultsListEl) return;
    searchResultsListEl.innerHTML = "";

    if (!users || users.length === 0) {
        searchResultsListEl.innerHTML = `<div style="padding: 12px; font-size: 13px; color: var(--text-muted); text-align: center;">No users found with that username</div>`;
        searchResultsEl.classList.remove("hidden");
        return;
    }

    users.forEach(u => {
        const item = document.createElement("div");
        item.className = "search-result-item";
        const avatarUrl = u.profile_picture || `https://api.dicebear.com/7.x/initials/svg?seed=${u.username}&backgroundColor=f1f5f9&textColor=0f172a`;

        item.innerHTML = `
            <div class="search-user-info">
                <div class="avatar-container" style="width: 32px; height: 32px;">
                    <img src="${avatarUrl}" alt="${escapeHtml(u.username)}" class="avatar-img">
                    <span class="status-indicator ${u.is_online ? "online" : ""}" style="width: 8px; height: 8px;"></span>
                </div>
                <span class="search-username">${escapeHtml(u.username)}</span>
            </div>
            <button class="btn-start-chat" onclick="startConversationWithUser(${u.id})">Message</button>
        `;
        searchResultsListEl.appendChild(item);
    });

    searchResultsEl.classList.remove("hidden");
}

async function startConversationWithUser(recipientUserId) {
    try {
        const resp = await fetch("/api/conversations", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...(currentToken ? { "Authorization": `Bearer ${currentToken}` } : {})
            },
            body: JSON.stringify({ recipient_user_id: recipientUserId })
        });

        if (!resp.ok) {
            const errData = await resp.json();
            throw new Error(errData.detail || "Could not start conversation");
        }

        const conv = await resp.json();
        // Clear search
        clearSearch();
        if (searchResultsEl) searchResultsEl.classList.add("hidden");

        // Reload conversations and select this one
        await loadConversations();
        await selectConversation(conv.id);
    } catch (err) {
        showToast(err.message || "Failed to start conversation");
    }
}

// --- Select & Open Active Conversation ---

async function selectConversation(conversationId) {
    // Highlight in sidebar
    document.querySelectorAll(".conversation-item").forEach(item => {
        item.classList.toggle("active", item.dataset.convId == conversationId);
    });

    // Clear unread badge
    const badge = document.getElementById(`conv-badge-${conversationId}`);
    if (badge) badge.remove();

    try {
        const resp = await fetch(`/api/conversations/${conversationId}`, {
            headers: currentToken ? { "Authorization": `Bearer ${currentToken}` } : {}
        });

        if (!resp.ok) {
            throw new Error("Unable to open conversation");
        }

        activeConversation = await resp.json();

        // Switch UI to active chat
        if (chatPlaceholderEl) chatPlaceholderEl.classList.add("hidden");
        if (chatActiveViewEl) chatActiveViewEl.classList.remove("hidden");
        if (chatAppEl) chatAppEl.classList.add("in-chat"); // For mobile full-screen

        // Update Header
        const partner = activeConversation.other_user;
        if (partnerUsernameEl) partnerUsernameEl.textContent = partner.username;
        if (partnerAvatarEl) {
            partnerAvatarEl.src = partner.profile_picture || `https://api.dicebear.com/7.x/initials/svg?seed=${partner.username}&backgroundColor=f1f5f9&textColor=0f172a`;
        }
        updatePartnerStatusUI(partner.is_online);

        // Load Messages
        await loadMessageHistory(conversationId);

        // Connect WebSocket
        connectWebSocket(conversationId);

        // Focus composer
        if (messageInputEl) messageInputEl.focus();

    } catch (err) {
        showToast(err.message || "Could not load conversation");
    }
}

function closeActiveChatOnMobile() {
    if (chatAppEl) chatAppEl.classList.remove("in-chat");
}

function updatePartnerStatusUI(isOnline, isTyping = false) {
    if (!partnerStatusDotEl || !partnerStatusLabelEl) return;

    if (isTyping) {
        partnerStatusLabelEl.textContent = "typing...";
        partnerStatusLabelEl.className = "partner-status online";
        partnerStatusDotEl.className = "status-indicator online";
        return;
    }

    if (isOnline) {
        partnerStatusLabelEl.textContent = "Online";
        partnerStatusLabelEl.className = "partner-status online";
        partnerStatusDotEl.className = "status-indicator online";
    } else {
        partnerStatusLabelEl.textContent = "Offline";
        partnerStatusLabelEl.className = "partner-status";
        partnerStatusDotEl.className = "status-indicator";
    }
}

// --- Message History & Rendering ---

async function loadMessageHistory(conversationId) {
    if (!messagesListEl) return;
    messagesListEl.innerHTML = "";

    try {
        const resp = await fetch(`/api/messages/${conversationId}`, {
            headers: currentToken ? { "Authorization": `Bearer ${currentToken}` } : {}
        });

        if (!resp.ok) {
            throw new Error("Failed to load messages");
        }

        const messages = await resp.json();

        let lastDateString = "";
        messages.forEach(msg => {
            const msgDate = new Date(msg.created_at).toDateString();
            if (msgDate !== lastDateString) {
                renderDateDivider(msg.created_at);
                lastDateString = msgDate;
            }
            renderMessageBubble(msg);
        });

        scrollToBottom(false);
    } catch (err) {
        console.error("Error loading messages:", err);
    }
}

function renderDateDivider(isoString) {
    const divider = document.createElement("div");
    divider.className = "date-divider";
    const date = new Date(isoString);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    let label = date.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });
    if (date.toDateString() === today.toDateString()) {
        label = "Today";
    } else if (date.toDateString() === yesterday.toDateString()) {
        label = "Yesterday";
    }

    divider.innerHTML = `<span>${label}</span>`;
    messagesListEl.appendChild(divider);
}

function renderMessageBubble(msg) {
    if (!messagesListEl) return;

    const isSent = currentUser && msg.sender_id === currentUser.id;
    const row = document.createElement("div");
    row.className = `message-row ${isSent ? "sent" : "received"}`;
    row.dataset.msgId = msg.id;

    const avatarUrl = msg.sender_profile_picture || `https://api.dicebear.com/7.x/initials/svg?seed=${msg.sender_username || "user"}&backgroundColor=f1f5f9&textColor=0f172a`;
    const timeFormatted = formatMessageTimestamp(msg.created_at);

    // Build Link Card (Instagram Reel, YouTube, or General Web Link)
    let linkCardHtml = "";
    if (msg.link_preview) {
        linkCardHtml = buildLinkPreviewCard(msg.link_preview, msg.message_type);
    }

    // Auto-link any plain URLs in text
    const linkedContent = linkifyText(escapeHtml(msg.content));

    row.innerHTML = `
        ${!isSent ? `<img src="${avatarUrl}" alt="${escapeHtml(msg.sender_username || "")}" class="message-sender-avatar" title="${escapeHtml(msg.sender_username || "")}">` : ""}
        <div class="message-content-wrapper">
            <div class="message-bubble">
                <div class="message-text">${linkedContent}</div>
                ${linkCardHtml}
                <div class="message-meta">
                    <span>${timeFormatted}</span>
                    ${isSent ? `
                        <i data-lucide="${msg.is_read ? "check-check" : "check"}" class="status-icon ${msg.is_read ? "read" : ""}"></i>
                    ` : ""}
                </div>
            </div>
            <!-- Hover Copy Action -->
            <div class="message-actions-overlay">
                <button type="button" class="btn-copy-msg" onclick="copyMessageText('${escapeForAttr(msg.content)}')">
                    <i data-lucide="copy"></i>
                    <span>Copy</span>
                </button>
            </div>
        </div>
    `;

    messagesListEl.appendChild(row);
    if (window.lucide) lucide.createIcons();
}

// --- Instagram & Link Cards Builder ---

function buildLinkPreviewCard(preview, messageType) {
    if (!preview) return "";

    const platform = preview.platform || "general";
    const originalUrl = preview.original_url || "#";
    const title = preview.title || (platform === "instagram" ? "Instagram Reel" : "Shared Link");
    const description = preview.description || "";
    const imageUrl = preview.image_url;
    const isReel = preview.is_reel || messageType === "instagram_reel";

    // A. Instagram Reel / Post Card
    if (platform === "instagram") {
        return `
            <a href="${escapeHtml(originalUrl)}" target="_blank" rel="noopener noreferrer" class="link-card instagram-card">
                <div class="card-platform-header">
                    <div class="platform-badge instagram">
                        <i data-lucide="camera"></i>
                        <span>Instagram</span>
                    </div>
                    ${isReel ? `<span class="reel-tag">Reel</span>` : ""}
                </div>
                ${imageUrl ? `
                    <div class="card-media-wrapper">
                        <img src="${escapeHtml(imageUrl)}" alt="Reel Preview" loading="lazy" onerror="this.parentElement.style.display='none'">
                        <div class="media-play-overlay">
                            <i data-lucide="play"></i>
                        </div>
                    </div>
                ` : `
                    <div class="card-media-wrapper" style="height: 120px; background: linear-gradient(135deg, #405de6, #5851db, #833ab4, #c13584, #e1306c, #fd1d1d);">
                        <div class="media-play-overlay">
                            <i data-lucide="instagram"></i>
                        </div>
                    </div>
                `}
                <div class="card-body">
                    <h4 class="card-title">${escapeHtml(title)}</h4>
                    ${description ? `<p class="card-description">${escapeHtml(description)}</p>` : ""}
                    <div class="card-footer">
                        <span class="btn-open-link">
                            <span>Open Instagram</span>
                            <i data-lucide="external-link"></i>
                        </span>
                        <span class="card-domain">instagram.com</span>
                    </div>
                </div>
            </a>
        `;
    }

    // B. YouTube Card
    if (platform === "youtube") {
        return `
            <a href="${escapeHtml(originalUrl)}" target="_blank" rel="noopener noreferrer" class="link-card youtube-card">
                <div class="card-platform-header">
                    <div class="platform-badge youtube">
                        <i data-lucide="video"></i>
                        <span>YouTube</span>
                    </div>
                    ${isReel ? `<span class="reel-tag">Short</span>` : ""}
                </div>
                ${imageUrl ? `
                    <div class="card-media-wrapper">
                        <img src="${escapeHtml(imageUrl)}" alt="Video Preview" loading="lazy">
                        <div class="media-play-overlay">
                            <i data-lucide="play"></i>
                        </div>
                    </div>
                ` : ""}
                <div class="card-body">
                    <h4 class="card-title">${escapeHtml(title)}</h4>
                    ${description ? `<p class="card-description">${escapeHtml(description)}</p>` : ""}
                    <div class="card-footer">
                        <span class="btn-open-link">
                            <span>Watch on YouTube</span>
                            <i data-lucide="external-link"></i>
                        </span>
                        <span class="card-domain">youtube.com</span>
                    </div>
                </div>
            </a>
        `;
    }

    // C. General Website Card
    return `
        <a href="${escapeHtml(originalUrl)}" target="_blank" rel="noopener noreferrer" class="link-card general-card">
            <div class="card-platform-header">
                <div class="platform-badge general">
                    <i data-lucide="globe"></i>
                    <span>${escapeHtml(preview.site_name || "Website")}</span>
                </div>
            </div>
            ${imageUrl ? `
                <div class="card-media-wrapper" style="max-height: 160px;">
                    <img src="${escapeHtml(imageUrl)}" alt="Link Preview" loading="lazy" onerror="this.parentElement.style.display='none'">
                </div>
            ` : ""}
            <div class="card-body">
                <h4 class="card-title">${escapeHtml(title)}</h4>
                ${description ? `<p class="card-description">${escapeHtml(description)}</p>` : ""}
                <div class="card-footer">
                    <span class="btn-open-link">
                        <span>Visit page</span>
                        <i data-lucide="external-link"></i>
                    </span>
                    <span class="card-domain">${escapeHtml(preview.site_name || "link")}</span>
                </div>
            </div>
        </a>
    `;
}

// --- WebSocket Connection & Real-time Events ---

function connectWebSocket(conversationId) {
    if (activeWebSocket) {
        try {
            activeWebSocket.close();
        } catch (e) {}
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/${conversationId}?token=${encodeURIComponent(currentToken || "")}`;

    activeWebSocket = new WebSocket(wsUrl);

    activeWebSocket.onopen = () => {
        console.log("WebSocket connected to conversation", conversationId);
        // Mark existing messages as read
        if (activeWebSocket.readyState === WebSocket.OPEN) {
            activeWebSocket.send(JSON.stringify({ type: "mark_read" }));
        }
    };

    activeWebSocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleIncomingRealtimeEvent(data);
        } catch (e) {
            console.error("Error parsing WS message:", e);
        }
    };

    activeWebSocket.onclose = () => {
        console.log("WebSocket disconnected from conversation", conversationId);
    };

    activeWebSocket.onerror = (err) => {
        console.warn("WebSocket error:", err);
    };
}

function handleIncomingRealtimeEvent(data) {
    const eventType = data.type;

    // 1. New Chat Message
    if (eventType === "new_message") {
        const msg = data.message;
        if (activeConversation && msg.conversation_id === activeConversation.id) {
            renderMessageBubble(msg);
            scrollToBottom(true);

            // If partner sent it, mark as read
            if (currentUser && msg.sender_id !== currentUser.id && activeWebSocket && activeWebSocket.readyState === WebSocket.OPEN) {
                activeWebSocket.send(JSON.stringify({ type: "mark_read" }));
            }
        }

        // Update sidebar preview
        updateSidebarConversation(msg.conversation_id, msg);
    }

    // 2. Typing Indicator
    else if (eventType === "typing") {
        if (activeConversation && data.conversation_id === activeConversation.id && currentUser && data.user_id !== currentUser.id) {
            showTypingIndicator(data.username, data.is_typing);
            updatePartnerStatusUI(true, data.is_typing);
        }
    }

    // 3. Messages Read Receipt
    else if (eventType === "messages_read") {
        if (activeConversation && data.conversation_id === activeConversation.id) {
            // Update sent message icons to read checkmarks
            document.querySelectorAll(".message-row.sent .status-icon").forEach(icon => {
                icon.className = "status-icon read";
                icon.setAttribute("data-lucide", "check-check");
            });
            if (window.lucide) lucide.createIcons();
        }
    }

    // 4. Real-time User Online/Offline Status
    else if (eventType === "user_status") {
        const userId = data.user_id;
        const isOnline = data.is_online;

        // Update dot in sidebar
        const dot = document.getElementById(`conv-status-dot-${userId}`);
        if (dot) {
            dot.className = `status-indicator ${isOnline ? "online" : ""}`;
        }

        // Update active chat header if this is the active partner
        if (activeConversation && activeConversation.other_user.id === userId) {
            activeConversation.other_user.is_online = isOnline;
            updatePartnerStatusUI(isOnline);
        }
    }

    // 5. Sidebar Update for other conversations
    else if (eventType === "sidebar_update") {
        updateSidebarConversation(data.conversation_id, data.last_message);
    }
}

function updateSidebarConversation(convId, lastMsg) {
    const previewEl = document.getElementById(`conv-preview-${convId}`);
    if (previewEl && lastMsg) {
        let text = lastMsg.content;
        if (lastMsg.message_type === "instagram_reel") text = "📹 Instagram Reel";
        else if (lastMsg.message_type === "youtube") text = "▶️ YouTube Video";
        else if (lastMsg.message_type === "link") text = "🔗 Link shared";
        previewEl.textContent = text;
    }
}

function showTypingIndicator(username, isTyping) {
    if (!typingIndicatorEl || !typingTextEl) return;
    if (isTyping) {
        typingTextEl.textContent = `${username} is typing...`;
        typingIndicatorEl.classList.remove("hidden");
        scrollToBottom(false);
    } else {
        typingIndicatorEl.classList.add("hidden");
    }
}

// --- Sending Messages ---

async function sendMessage() {
    if (!messageInputEl || !activeConversation) return;

    const content = messageInputEl.value.trim();
    if (!content) return;

    // Clear input & reset height
    messageInputEl.value = "";
    messageInputEl.style.height = "auto";
    sendTypingEvent(false);

    // Prefer sending via WebSocket for instant latency
    if (activeWebSocket && activeWebSocket.readyState === WebSocket.OPEN) {
        activeWebSocket.send(JSON.stringify({
            type: "message",
            content: content
        }));
    } else {
        // Fallback to REST endpoint
        try {
            await fetch("/api/messages", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...(currentToken ? { "Authorization": `Bearer ${currentToken}` } : {})
                },
                body: JSON.stringify({
                    conversation_id: activeConversation.id,
                    content: content
                })
            });
        } catch (err) {
            showToast("Failed to send message. Please retry.");
        }
    }
}

function handleInputKeyDown(event) {
    // Enter to send, Shift + Enter for newline
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function handleInputTyping(event) {
    // Auto-grow textarea
    const textarea = event.target;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 140)}px`;

    // Emit typing indicator
    if (!isUserTyping) {
        isUserTyping = true;
        sendTypingEvent(true);
    }

    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => {
        isUserTyping = false;
        sendTypingEvent(false);
    }, 2000);
}

function sendTypingEvent(typingState) {
    if (activeWebSocket && activeWebSocket.readyState === WebSocket.OPEN) {
        activeWebSocket.send(JSON.stringify({
            type: "typing",
            is_typing: typingState
        }));
    }
}

// --- Emoji Picker ---

function toggleEmojiPicker() {
    if (!emojiPickerEl) return;
    emojiPickerEl.classList.toggle("hidden");
}

function insertEmoji(emoji) {
    if (!messageInputEl) return;
    messageInputEl.value += emoji;
    messageInputEl.focus();
    if (emojiPickerEl) emojiPickerEl.classList.add("hidden");
}

// Close emoji picker when clicking outside
document.addEventListener("click", (e) => {
    if (emojiPickerEl && !emojiPickerEl.classList.contains("hidden")) {
        const toggleBtn = document.getElementById("btn-toggle-emoji");
        if (!emojiPickerEl.contains(e.target) && (!toggleBtn || !toggleBtn.contains(e.target))) {
            emojiPickerEl.classList.add("hidden");
        }
    }
});

// --- Scroll Helpers ---

function scrollToBottom(smooth = true) {
    if (!messagesContainerEl) return;
    messagesContainerEl.scrollTo({
        top: messagesContainerEl.scrollHeight,
        behavior: smooth ? "smooth" : "auto"
    });
}

function handleChatScroll() {
    if (!messagesContainerEl || !btnScrollBottomEl) return;
    const scrollDiff = messagesContainerEl.scrollHeight - messagesContainerEl.scrollTop - messagesContainerEl.clientHeight;
    // Show scroll button if user scrolled up more than 150px
    btnScrollBottomEl.classList.toggle("hidden", scrollDiff < 150);
}

// --- Copy & Toast Helpers ---

async function copyMessageText(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast("Message copied to clipboard");
    } catch (e) {
        showToast("Could not copy message");
    }
}

function showToast(message) {
    const toast = document.getElementById("toast-notification");
    if (!toast) return;
    toast.textContent = message;
    toast.classList.remove("hidden");
    clearTimeout(toast.timeoutId);
    toast.timeoutId = setTimeout(() => {
        toast.classList.add("hidden");
    }, 2500);
}

// --- Utilities ---

function escapeHtml(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function escapeForAttr(str) {
    if (!str) return "";
    return str
        .replace(/'/g, "\\'")
        .replace(/"/g, "&quot;")
        .replace(/\n/g, "\\n");
}

function linkifyText(text) {
    if (!text) return "";
    const urlPattern = /(https?:\/\/[^\s]+)/g;
    return text.replace(urlPattern, (url) => {
        return `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`;
    });
}

function formatMessageTimestamp(isoString, short = false) {
    if (!isoString) return "";
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return "";

    if (short) {
        const now = new Date();
        if (date.toDateString() === now.toDateString()) {
            return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
        }
        return date.toLocaleDateString([], { month: "short", day: "numeric" });
    }

    return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}
