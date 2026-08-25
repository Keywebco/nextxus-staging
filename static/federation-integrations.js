/**
 * Federation Integration Pack v1
 * NextXus Federation — Gemini AI Chat + Google Sign-In + Media Library
 * Gold (#c9a84c) on Black (#0a0a0a), monospace, truth-first
 * 
 * Pre-rendered semantic HTML injected server-side; JS enhances interactivity.
 * GEMINI_API_KEY is NEVER exposed client-side — all AI calls proxy through /api/gemini
 */

(function() {
  'use strict';

  // ============================================================
  // CONFIG
  // ============================================================
  const FED_CONFIG = {
    geminiEndpoint: '/api/gemini',
    googleClientId: null, // Set via FED_GOOGLE_CLIENT_ID global or data attribute
    isThrone: false,      // Set true on nextxus.tech admin pages
    siteName: document.title || 'NextXus',
  };

  // Detect config from page
  if (window.FED_GOOGLE_CLIENT_ID) FED_CONFIG.googleClientId = window.FED_GOOGLE_CLIENT_ID;
  if (document.body.dataset.fedThrone === 'true') FED_CONFIG.isThrone = true;
  if (window.location.hostname.includes('nextxus.tech')) FED_CONFIG.isThrone = true;

  // ============================================================
  // UTILITY
  // ============================================================
  function el(tag, attrs, children) {
    const e = document.createElement(tag);
    if (attrs) Object.entries(attrs).forEach(([k,v]) => {
      if (k === 'className') e.className = v;
      else if (k === 'innerHTML') e.innerHTML = v;
      else if (k.startsWith('on')) e.addEventListener(k.slice(2).toLowerCase(), v);
      else e.setAttribute(k, v);
    });
    if (children) {
      if (typeof children === 'string') e.textContent = children;
      else if (Array.isArray(children)) children.forEach(c => { if(c) e.appendChild(c); });
      else e.appendChild(children);
    }
    return e;
  }

  // ============================================================
  // A. GEMINI AI CHAT WIDGET
  // ============================================================
  function initGeminiChat() {
    // Chat trigger button
    const trigger = el('button', {
      className: 'fed-chat-trigger',
      'aria-label': 'Open Federation AI Chat',
      title: 'Federation AI Assistant',
      innerHTML: '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/><path d="M7 9h2v2H7zm4 0h2v2h-2zm4 0h2v2h-2z"/></svg>'
    });

    // Chat panel
    const panel = el('div', { className: 'fed-chat-panel' });
    panel.innerHTML = `
      <div class="fed-chat-header">
        <h3>⟡ FEDERATION AI</h3>
        <button class="fed-chat-close" aria-label="Close chat">&times;</button>
      </div>
      <div class="fed-chat-messages" role="log" aria-live="polite">
        <div class="fed-msg system">Federation AI Assistant — Ask anything about NextXus</div>
      </div>
      <div class="fed-chat-input-area">
        <input class="fed-chat-input" type="text" placeholder="Type your question..." aria-label="Chat message" autocomplete="off">
        <button class="fed-chat-send" aria-label="Send message">SEND</button>
      </div>
    `;

    document.body.appendChild(trigger);
    document.body.appendChild(panel);

    const messages = panel.querySelector('.fed-chat-messages');
    const input = panel.querySelector('.fed-chat-input');
    const sendBtn = panel.querySelector('.fed-chat-send');
    const closeBtn = panel.querySelector('.fed-chat-close');

    let isOpen = false;

    function toggleChat() {
      isOpen = !isOpen;
      panel.classList.toggle('active', isOpen);
      if (isOpen) input.focus();
    }

    trigger.addEventListener('click', toggleChat);
    closeBtn.addEventListener('click', toggleChat);

    // Close on outside click
    document.addEventListener('click', function(e) {
      if (isOpen && !panel.contains(e.target) && !trigger.contains(e.target)) {
        isOpen = false;
        panel.classList.remove('active');
      }
    });

    function addMessage(text, role) {
      const msg = el('div', { className: 'fed-msg ' + role }, text);
      messages.appendChild(msg);
      messages.scrollTop = messages.scrollHeight;
      return msg;
    }

    function showTyping() {
      const typing = el('div', { className: 'fed-msg assistant' });
      typing.innerHTML = '<div class="fed-typing"><span></span><span></span><span></span></div>';
      messages.appendChild(typing);
      messages.scrollTop = messages.scrollHeight;
      return typing;
    }

    async function sendMessage() {
      const text = input.value.trim();
      if (!text) return;

      input.value = '';
      sendBtn.disabled = true;
      addMessage(text, 'user');

      const typing = showTyping();

      try {
        const resp = await fetch(FED_CONFIG.geminiEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text })
        });

        if (!resp.ok) throw new Error('Network error: ' + resp.status);

        const data = await resp.json();
        typing.remove();

        if (data.reply) {
          addMessage(data.reply, 'assistant');
        } else if (data.error) {
          addMessage('Error: ' + data.error, 'system');
        } else {
          addMessage('No response received.', 'system');
        }
      } catch (err) {
        typing.remove();
        addMessage('Connection error. Please try again.', 'system');
        console.error('[Federation AI]', err);
      }

      sendBtn.disabled = false;
      input.focus();
    }

    sendBtn.addEventListener('click', sendMessage);
    input.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  // ============================================================
  // B. GOOGLE SIGN-IN
  // ============================================================
  function initGoogleSignIn() {
    // Check for existing session
    const stored = localStorage.getItem('fed_user');
    if (stored) {
      try {
        const user = JSON.parse(stored);
        showWelcome(user);
        return;
      } catch(e) {
        localStorage.removeItem('fed_user');
      }
    }

    // If no Google Client ID configured, show placeholder button
    if (!FED_CONFIG.googleClientId) {
      injectSignInButton(null);
      return;
    }

    // Load Google Identity Services
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = function() {
      google.accounts.id.initialize({
        client_id: FED_CONFIG.googleClientId,
        callback: handleGoogleSignIn,
        auto_select: false,
      });
      injectSignInButton(true);
    };
    document.head.appendChild(script);
  }

  function injectSignInButton(gsiReady) {
    // Find nav or header to inject into
    const nav = document.querySelector('nav, header, [role="navigation"], .nav, .header, .navbar');
    if (!nav) return;

    const container = el('div', { className: 'fed-auth-bar' });

    if (gsiReady) {
      const btn = el('button', {
        className: 'fed-google-signin',
        innerHTML: '<svg viewBox="0 0 24 24"><path fill="#c9a84c" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#c9a84c" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#c9a84c" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#c9a84c" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg> Sign in with Google'
      });
      btn.addEventListener('click', function() {
        google.accounts.id.prompt();
      });
      container.appendChild(btn);
    } else {
      // No client ID — show inactive placeholder
      const btn = el('button', {
        className: 'fed-google-signin',
        innerHTML: '<svg viewBox="0 0 24 24"><path fill="#666" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/></svg> Sign in (config pending)',
        title: 'Google Sign-In requires OAuth Client ID configuration'
      });
      btn.disabled = true;
      btn.style.opacity = '0.5';
      container.appendChild(btn);
    }

    nav.appendChild(container);
  }

  function handleGoogleSignIn(response) {
    // Decode JWT payload
    const payload = JSON.parse(atob(response.credential.split('.')[1]));
    const user = {
      name: payload.name || payload.email,
      email: payload.email,
      picture: payload.picture || '',
      sub: payload.sub
    };
    localStorage.setItem('fed_user', JSON.stringify(user));
    showWelcome(user);
  }

  function showWelcome(user) {
    // Remove any existing sign-in buttons
    document.querySelectorAll('.fed-auth-bar').forEach(e => e.remove());

    const nav = document.querySelector('nav, header, [role="navigation"], .nav, .header, .navbar');
    if (!nav) return;

    const container = el('div', { className: 'fed-auth-bar' });
    const welcome = el('div', { className: 'fed-user-welcome' });

    if (user.picture) {
      const img = el('img', { className: 'fed-user-avatar', src: user.picture, alt: user.name });
      welcome.appendChild(img);
    }
    welcome.appendChild(el('span', {}, 'Welcome, ' + user.name.split(' ')[0]));

    const signout = el('button', { className: 'fed-user-signout' }, 'Sign out');
    signout.addEventListener('click', function() {
      localStorage.removeItem('fed_user');
      location.reload();
    });

    container.appendChild(welcome);
    container.appendChild(signout);
    nav.appendChild(container);
  }

  // ============================================================
  // C. MEDIA LIBRARY (Throne only)
  // ============================================================
  function initMediaLibrary() {
    if (!FED_CONFIG.isThrone) return;

    // Create overlay + panel
    const overlay = el('div', { className: 'fed-media-overlay' });
    const panel = el('div', { className: 'fed-media-panel' });
    panel.innerHTML = `
      <div class="fed-media-header">
        <h3>⟡ MEDIA LIBRARY — Google Drive</h3>
        <button class="fed-chat-close" aria-label="Close media library">&times;</button>
      </div>
      <div class="fed-media-body">
        <div class="fed-media-upload">
          <p>📁 Drop files here or click to upload to Google Drive</p>
          <input type="file" multiple style="display:none" id="fed-media-file-input">
        </div>
        <div class="fed-msg system" style="grid-column:1/-1;text-align:center;padding:24px;">
          Google Drive integration requires OAuth authentication.<br>
          Connect your Google account to browse and upload files.
        </div>
      </div>
    `;

    document.body.appendChild(overlay);
    document.body.appendChild(panel);

    // Find admin nav / sidebar to inject trigger
    const adminArea = document.querySelector('.admin-nav, .sidebar, nav, header');
    if (adminArea) {
      const trigger = el('button', {
        className: 'fed-media-trigger',
        innerHTML: '📁 Media Library'
      });
      trigger.addEventListener('click', function() {
        overlay.classList.add('active');
        panel.classList.add('active');
      });
      adminArea.appendChild(trigger);
    }

    const closeBtn = panel.querySelector('.fed-chat-close');
    closeBtn.addEventListener('click', function() {
      overlay.classList.remove('active');
      panel.classList.remove('active');
    });
    overlay.addEventListener('click', function() {
      overlay.classList.remove('active');
      panel.classList.remove('active');
    });

    // File upload placeholder
    const uploadZone = panel.querySelector('.fed-media-upload');
    const fileInput = panel.querySelector('#fed-media-file-input');
    uploadZone.addEventListener('click', function() { fileInput.click(); });
    fileInput.addEventListener('change', function() {
      // In production, this would use Google Drive API v3
      alert('Google Drive upload requires OAuth connection. Files selected: ' + fileInput.files.length);
    });
  }

  // ============================================================
  // INITIALIZATION
  // ============================================================
  function init() {
    // Wait for DOM
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', boot);
    } else {
      boot();
    }
  }

  function boot() {
    initGeminiChat();
    initGoogleSignIn();
    initMediaLibrary();
    console.log('[Federation Integration Pack v1] Loaded — ' + FED_CONFIG.siteName);
  }

  init();
})();
