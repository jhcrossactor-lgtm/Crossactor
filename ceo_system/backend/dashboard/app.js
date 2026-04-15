/* === Crossactor AI CEO System - Dashboard App === */

const API_BASE = window.location.origin;

// --- DOM 参照 ---
const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const thinkingIndicator = document.getElementById('thinking-indicator');
const orgPanel = document.getElementById('orgPanel');
const orgOverlay = document.getElementById('orgOverlay');
const orgBody = document.getElementById('orgBody');
const extraAgentsCount = document.getElementById('extra-agents-count');
const extraCount = document.getElementById('extra-count');

// --- 状態管理 ---
let isProcessing = false;

// --- 初期化 ---
window.addEventListener('load', () => {
  messageInput.focus();
  refreshAgentCount();
});


// === メッセージ送信 ===

async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text || isProcessing) return;

  setProcessing(true);
  messageInput.value = '';
  autoResize(messageInput);

  // オーナーメッセージを表示
  appendMessage('owner', 'オーナー', text);

  try {
    const response = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'サーバーエラーが発生しました');
    }

    const data = await response.json();

    // BONEへの相談があった場合、そのプロセスを表示
    if (data.bone_request) {
      appendBoneConsultTag(data.bone_request);
    }

    // BONEの応答を表示（あれば）
    if (data.bone_response) {
      appendMessage('bone', 'BONE（参謀）', data.bone_response);
    }

    // Croの最終応答
    appendMessage('cro', 'Cro（CEO）', data.message);

    // 増員提案があった場合
    if (data.new_agent_proposal) {
      appendHireProposal(data.new_agent_proposal);
      await refreshAgentCount();
    }

  } catch (err) {
    appendSystemMessage(`エラー: ${err.message}`);
  } finally {
    setProcessing(false);
    messageInput.focus();
  }
}


// === メッセージ表示 ===

function appendMessage(type, speakerName, text) {
  const group = document.createElement('div');
  group.className = 'message-group';

  const bubble = document.createElement('div');
  bubble.className = `message-bubble ${type}-bubble`;

  const iconMap = { cro: 'C', bone: 'B', owner: 'O' };
  const iconClassMap = { cro: 'icon-cro', bone: 'icon-bone', owner: 'icon-owner' };

  bubble.innerHTML = `
    <div class="speaker-icon ${iconClassMap[type]}">${iconMap[type]}</div>
    <div class="message-content">
      <div class="speaker-name">${speakerName}</div>
      <div class="message-text">${escapeHtml(text)}</div>
    </div>
  `;

  group.appendChild(bubble);
  chatMessages.appendChild(group);
  scrollToBottom();
}


function appendBoneConsultTag(question) {
  const tag = document.createElement('div');
  tag.className = 'message-group';
  tag.innerHTML = `
    <div style="padding-left: 48px;">
      <div class="bone-consult-tag">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        BONEに情報収集依頼: ${escapeHtml(question.substring(0, 60))}${question.length > 60 ? '…' : ''}
      </div>
    </div>
  `;
  chatMessages.appendChild(tag);
  scrollToBottom();
}


function appendHireProposal(proposal) {
  const tag = document.createElement('div');
  tag.className = 'message-group';
  tag.innerHTML = `
    <div style="padding-left: 48px;">
      <div class="hire-proposal-tag">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path>
          <circle cx="9" cy="7" r="4"></circle>
          <line x1="19" y1="8" x2="19" y2="14"></line>
          <line x1="22" y1="11" x2="16" y2="11"></line>
        </svg>
        増員提案: ${escapeHtml(proposal.substring(0, 80))}${proposal.length > 80 ? '…' : ''}
      </div>
    </div>
  `;
  chatMessages.appendChild(tag);
  scrollToBottom();
}


function appendSystemMessage(text) {
  const msg = document.createElement('div');
  msg.className = 'message-group';
  msg.innerHTML = `
    <div style="text-align: center; padding: 8px;">
      <span style="font-size: 12px; color: #ff6b6b; background: rgba(255,107,107,0.1); padding: 6px 14px; border-radius: 20px;">${escapeHtml(text)}</span>
    </div>
  `;
  chatMessages.appendChild(msg);
  scrollToBottom();
}


// === 組織図パネル ===

function toggleOrgPanel() {
  const isOpen = orgPanel.classList.contains('open');
  if (isOpen) {
    orgPanel.classList.remove('open');
    orgOverlay.classList.remove('active');
  } else {
    orgPanel.classList.add('open');
    orgOverlay.classList.add('active');
    loadOrgChart();
  }
}


async function loadOrgChart() {
  orgBody.innerHTML = '<div class="org-loading">読み込み中...</div>';

  try {
    const response = await fetch(`${API_BASE}/api/org`);
    const data = await response.json();
    renderOrgChart(data);
  } catch (err) {
    orgBody.innerHTML = '<div class="org-loading">取得に失敗しました</div>';
  }
}


function renderOrgChart(data) {
  let html = '';

  // オーナー
  if (data.owner) {
    html += `
      <div class="org-section">
        <div class="org-section-title">最高権限</div>
        <div class="org-card">
          <div class="org-card-header">
            <div class="org-card-icon" style="background:rgba(245,166,35,0.15);border:1px solid rgba(245,166,35,0.4);color:#ffc04d;">O</div>
            <div>
              <div class="org-card-name">オーナー</div>
              <div class="org-card-title">${data.owner.title || '最高権限者'}</div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // Cro
  if (data.cro) {
    html += `
      <div class="org-section">
        <div class="org-section-title">CEO</div>
        <div class="org-card" style="border-left: 2px solid #7c5cfc;">
          <div class="org-card-header">
            <div class="org-card-icon" style="background:rgba(124,92,252,0.15);border:1px solid rgba(124,92,252,0.4);color:#a080ff;">C</div>
            <div>
              <div class="org-card-name">${data.cro.name}</div>
              <div class="org-card-title">${data.cro.title}</div>
            </div>
          </div>
          <div class="org-card-desc">${data.cro.description}</div>
          <div class="org-hired-date">就任: ${data.cro.hired_at}</div>
        </div>
      </div>
    `;
  }

  // BONE
  if (data.core_staff && data.core_staff.bone) {
    const bone = data.core_staff.bone;
    html += `
      <div class="org-section">
        <div class="org-section-title">参謀</div>
        <div class="org-card" style="border-left: 2px solid #00c9a7;">
          <div class="org-card-header">
            <div class="org-card-icon" style="background:rgba(0,201,167,0.15);border:1px solid rgba(0,201,167,0.4);color:#00e5c0;">B</div>
            <div>
              <div class="org-card-name">${bone.name}</div>
              <div class="org-card-title">${bone.title}</div>
            </div>
          </div>
          <div class="org-card-desc">${bone.description}</div>
          <div class="org-hired-date">就任: ${bone.hired_at}</div>
        </div>
      </div>
    `;
  }

  // 各部門のエージェント
  if (data.departments && Object.keys(data.departments).length > 0) {
    for (const [dept, agents] of Object.entries(data.departments)) {
      if (!agents || agents.length === 0) continue;
      html += `<div class="org-section"><div class="org-section-title">${escapeHtml(dept)}</div>`;
      for (const agent of agents) {
        const initial = (agent.name || '?')[0];
        html += `
          <div class="org-card">
            <div class="org-card-header">
              <div class="org-card-icon" style="background:rgba(150,150,200,0.15);border:1px solid rgba(150,150,200,0.3);color:#a0a0cc;">${escapeHtml(initial)}</div>
              <div>
                <div class="org-card-name">${escapeHtml(agent.name)}</div>
                <div class="org-card-title">${escapeHtml(agent.title)}</div>
              </div>
            </div>
            <div class="org-card-desc">${escapeHtml(agent.description || '')}</div>
          </div>
        `;
      }
      html += `</div>`;
    }
  }

  orgBody.innerHTML = html || '<div class="org-loading">データなし</div>';
}


// === セッションリセット ===

async function resetSession() {
  if (!confirm('会話セッションをリセットしますか？')) return;

  try {
    await fetch(`${API_BASE}/api/session/reset`, { method: 'POST' });
    chatMessages.innerHTML = '';
    appendSystemMessage('セッションをリセットしました。新しいセッションを開始します。');
  } catch (err) {
    appendSystemMessage('リセットに失敗しました');
  }
}


// === エージェント数更新 ===

async function refreshAgentCount() {
  try {
    const response = await fetch(`${API_BASE}/api/org/agents`);
    const data = await response.json();
    const agents = data.agents || [];
    // cro, bone を除いた追加エージェント数
    const extras = agents.filter(a => !['cro', 'bone'].includes(a.id));
    if (extras.length > 0) {
      extraAgentsCount.style.display = 'flex';
      extraCount.textContent = `+${extras.length}`;
    } else {
      extraAgentsCount.style.display = 'none';
    }
  } catch (_) {}
}


// === ユーティリティ ===

function setProcessing(processing) {
  isProcessing = processing;
  sendBtn.disabled = processing;
  thinkingIndicator.style.display = processing ? 'flex' : 'none';
}

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(text));
  return div.innerHTML;
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 160) + 'px';
}

function handleKeyDown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
}
