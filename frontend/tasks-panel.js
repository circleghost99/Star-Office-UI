/**
 * Tasks Panel — task list UI + SSE listener for task flow animations.
 * Loaded by index.html, integrates with Phaser game via window.animateTaskFlow().
 */

(function () {
  'use strict';

  const TASKS_POLL_INTERVAL = 10000; // 10s
  let _tasks = [];

  // ---- DOM Rendering ----

  function renderTasksPanel(tasks) {
    const panel = document.getElementById('tasks-panel-list');
    if (!panel) return;

    if (!tasks.length) {
      panel.innerHTML = '<div class="task-empty">暂无任务</div>';
      return;
    }

    panel.innerHTML = tasks.map(t => {
      const statusClass = `task-status-${t.status}`;
      const statusLabel = { pending: '待处理', working: '进行中', complete: '已完成' }[t.status] || t.status;
      const agent = t.assigned_agent_id ? `<span class="task-agent">${escapeHtml(t.assigned_agent_id)}</span>` : '';
      return `
        <div class="task-card ${statusClass}">
          <div class="task-title">${escapeHtml(t.title)}</div>
          <div class="task-meta">
            <span class="task-badge ${statusClass}">${statusLabel}</span>
            ${agent}
          </div>
        </div>`;
    }).join('');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ---- Data Fetching ----

  async function fetchTasks() {
    try {
      const resp = await fetch('/api/tasks?flows=true');
      if (!resp.ok) return;
      _tasks = await resp.json();
      renderTasksPanel(_tasks);
    } catch (e) {
      // silent
    }
  }

  // ---- SSE Integration ----

  function setupTaskSSE() {
    // Listen for task events from the existing SSE stream
    // The main game.js already connects to /events; we just need to handle task-specific events
    // We'll add a global handler that game.js can call
    window._onTaskSSEEvent = function (eventType, data) {
      if (eventType === 'task_created' || eventType === 'task_updated') {
        fetchTasks(); // refresh list
      }
      if (eventType === 'task_flow') {
        // Trigger Phaser animation
        if (typeof window.animateTaskFlow === 'function') {
          window.animateTaskFlow(data.from_agent_id, data.to_agent_id);
        }
      }
    };
  }

  // ---- Init ----

  function init() {
    fetchTasks();
    setInterval(fetchTasks, TASKS_POLL_INTERVAL);
    setupTaskSSE();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
