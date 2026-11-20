/**
 * Jeevan Setu — Universal Automatic 5-Second Data Refresh & Synchronization Manager
 * 
 * Provides centralized, non-overlapping, tab-aware 5-second automatic data refresh
 * across all four Jeevan Setu portals (Admin, Doctor, Nurse, Attendant).
 * 
 * Key Guarantees:
 * 1. 5-Second Interval: Authoritative 5000ms cadence.
 * 2. In-Flight Protection: Ensures prior requests complete before launching another.
 * 3. Response Sequencing: Discards stale out-of-order responses.
 * 4. Tab Visibility Awareness: Pauses background polling when tab is hidden, immediately refreshes on return.
 * 5. Lifecycle Safety: Cleans up all intervals on page unload / component destroy.
 * 6. User Interaction Protection: Avoids rewriting active inputs, open dropdowns, or modals.
 * 7. Live Synchronization Indicator: Renders and maintains real-time sync state (Live, Syncing, Delayed, Offline).
 */
(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    var instance = factory();
    root.AutoRefreshManager = instance;
    root.AUTO_REFRESH_INTERVAL = instance.DEFAULT_INTERVAL;
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var DEFAULT_INTERVAL = 5000; // Authoritative 5-second interval
  var tasks = new Map();
  var isVisibilityListenerAttached = false;
  var isUnloadListenerAttached = false;
  var globalLastSuccessTime = Date.now();
  var globalSyncState = 'live'; // 'live' | 'syncing' | 'delayed' | 'offline'
  var indicatorElements = new Set();

  /**
   * Check if user is currently interacting with an input, modal, or form.
   */
  function isUserInputActive(container) {
    try {
      if (typeof document === 'undefined') return false;

      var active = document.activeElement;
      if (active) {
        var tagName = (active.tagName || '').toUpperCase();
        if (tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT' || active.isContentEditable) {
          if (container) {
            var parent = typeof container === 'string' ? document.querySelector(container) : container;
            if (parent && parent.contains(active)) return true;
          } else {
            return true;
          }
        }
      }

      // Check open modals
      var openModals = document.querySelectorAll(
        '.modal.show, .modal:not(.hidden):not([style*="display: none"]), [data-modal-open="true"], .swal2-container'
      );
      if (openModals.length > 0) return true;

      // Check dirty forms
      var dirtyForms = document.querySelectorAll('form[data-dirty="true"], form.is-editing');
      if (dirtyForms.length > 0) return true;

      // Check text selection
      var sel = (typeof window !== 'undefined' && window.getSelection) ? window.getSelection() : null;
      if (sel && sel.toString().length > 0) return true;
    } catch (e) {}
    return false;
  }

  function setupVisibilityListener() {
    if (isVisibilityListenerAttached || typeof document === 'undefined') return;
    isVisibilityListenerAttached = true;

    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible') {
        var now = Date.now();
        tasks.forEach(function (task) {
          if (!task.enabled) return;
          // Catch up immediately if the interval has elapsed while hidden
          if (now - task.lastRun >= task.interval) {
            runTask(task);
          }
        });
      }
    });
  }

  function setupUnloadListener() {
    if (isUnloadListenerAttached || typeof window === 'undefined') return;
    isUnloadListenerAttached = true;

    var cleanup = function () {
      stopAll();
    };

    window.addEventListener('beforeunload', cleanup);
    window.addEventListener('pagehide', cleanup);
  }

  /**
   * Run a registered auto-refresh task with in-flight and stale response guards.
   */
  async function runTask(task) {
    if (!task || !task.enabled || task.isExecuting) return;
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden' && task.skipWhenHidden) return;

    task.isExecuting = true;
    task.lastRun = Date.now();
    var currentSeq = ++task.seq;

    updateGlobalSyncState('syncing');

    // Delayed detection watchdog
    var delayedTimer = setTimeout(function () {
      if (task.isExecuting) {
        updateGlobalSyncState('delayed');
      }
    }, 8000);

    try {
      var result = task.fn();
      if (result && typeof result.then === 'function') {
        await result;
      }

      clearTimeout(delayedTimer);

      // Discard stale out-of-order response if another newer run completed
      if (currentSeq < task.latestCompletedSeq) {
        return;
      }

      task.latestCompletedSeq = currentSeq;
      task.errorCount = 0;
      task.lastSuccess = Date.now();
      globalLastSuccessTime = task.lastSuccess;

      updateGlobalSyncState('live');

      if (task.onSuccess) task.onSuccess();
    } catch (err) {
      clearTimeout(delayedTimer);
      task.errorCount = (task.errorCount || 0) + 1;
      console.warn('[AutoRefreshManager] Task "' + task.key + '" refresh error (attempt #' + task.errorCount + '):', err);

      updateGlobalSyncState('offline', err.message || 'Connection unavailable');

      if (task.onError) task.onError(err);
    } finally {
      task.isExecuting = false;
    }
  }

  /**
   * Register and start a periodic 5-second auto-refresh task.
   */
  function start(key, taskFn, intervalMs, options) {
    if (typeof key === 'function') {
      options = intervalMs;
      intervalMs = taskFn;
      taskFn = key;
      key = 'default_task_' + Math.random().toString(36).substring(2, 9);
    }

    options = options || {};
    var interval = typeof intervalMs === 'number' && intervalMs > 0 ? intervalMs : DEFAULT_INTERVAL;

    stop(key);
    setupVisibilityListener();
    setupUnloadListener();

    var task = {
      key: key,
      fn: taskFn,
      interval: interval,
      immediate: options.immediate !== false,
      skipWhenHidden: options.skipWhenHidden !== false,
      onSuccess: options.onSuccess || null,
      onError: options.onError || null,
      enabled: true,
      isExecuting: false,
      lastRun: 0,
      lastSuccess: 0,
      errorCount: 0,
      seq: 0,
      latestCompletedSeq: 0,
      timerId: null
    };

    task.timerId = setInterval(function () {
      runTask(task);
    }, task.interval);

    tasks.set(key, task);

    if (task.immediate) {
      runTask(task);
    }

    return {
      key: key,
      stop: function () { stop(key); },
      trigger: function () { runTask(task); },
      getStats: function () {
        return {
          key: task.key,
          interval: task.interval,
          lastSuccess: task.lastSuccess,
          errorCount: task.errorCount,
          isExecuting: task.isExecuting
        };
      }
    };
  }

  function stop(key) {
    var task = tasks.get(key);
    if (task) {
      task.enabled = false;
      if (task.timerId) {
        clearInterval(task.timerId);
        task.timerId = null;
      }
      tasks.delete(key);
    }
  }

  function stopAll() {
    tasks.forEach(function (task) {
      task.enabled = false;
      if (task.timerId) {
        clearInterval(task.timerId);
        task.timerId = null;
      }
    });
    tasks.clear();
  }

  function trigger(key) {
    var task = tasks.get(key);
    if (task) {
      runTask(task);
    }
  }

  function refreshAll() {
    tasks.forEach(function (task) {
      if (task.enabled) {
        runTask(task);
      }
    });
  }

  function formatTimestamp(d) {
    if (!d) return '--:--:--';
    var date = d instanceof Date ? d : new Date(d);
    if (isNaN(date.getTime())) return '--:--:--';
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  /**
   * Update the global sync state and reflect immediately across all attached indicators.
   */
  function updateGlobalSyncState(state, message) {
    globalSyncState = state;
    var timeStr = formatTimestamp(globalLastSuccessTime);

    indicatorElements.forEach(function (el) {
      if (!el || !document.body.contains(el)) {
        indicatorElements.delete(el);
        return;
      }

      var dot = el.querySelector('[data-sync-dot]');
      var text = el.querySelector('[data-sync-text]');
      if (!dot || !text) return;

      if (state === 'live') {
        el.className = 'js-sync-indicator inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 cursor-pointer select-none transition-all shadow-xs hover:bg-emerald-500/20';
        dot.className = 'w-2 h-2 rounded-full bg-emerald-400 animate-pulse';
        text.textContent = 'Live • ' + timeStr;
        el.title = 'Data automatically refreshing every 5s • Last successful sync: ' + timeStr + ' • Click to sync now';
      } else if (state === 'syncing') {
        el.className = 'js-sync-indicator inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-500/10 border border-blue-500/25 text-blue-400 cursor-wait select-none transition-all shadow-xs';
        dot.className = 'w-2 h-2 rounded-full bg-blue-400 animate-ping';
        text.textContent = 'Syncing...';
        el.title = 'Refreshing live hospital data...';
      } else if (state === 'delayed') {
        el.className = 'js-sync-indicator inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 border border-amber-500/25 text-amber-400 cursor-pointer select-none transition-all shadow-xs hover:bg-amber-500/20';
        dot.className = 'w-2 h-2 rounded-full bg-amber-400 animate-pulse';
        text.textContent = 'Delayed • ' + timeStr;
        el.title = 'Refresh is taking longer than expected. Retrying... • Click to sync now';
      } else if (state === 'offline') {
        el.className = 'js-sync-indicator inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 border border-rose-500/25 text-rose-400 cursor-pointer select-none transition-all shadow-xs hover:bg-rose-500/20';
        dot.className = 'w-2 h-2 rounded-full bg-rose-400';
        text.textContent = 'Offline • Retrying';
        el.title = 'Server connection temporarily unavailable (' + (message || 'network') + '). Click to retry.';
      }
    });
  }

  /**
   * Attach or render a live Data Freshness Indicator inside target container.
   */
  function attachIndicator(target, options) {
    if (typeof document === 'undefined') return null;

    options = options || {};
    var container = typeof target === 'string' ? document.querySelector(target) : target;
    if (!container) return null;

    var existing = container.querySelector('.js-sync-indicator');
    if (existing) {
      indicatorElements.add(existing);
      updateGlobalSyncState(globalSyncState);
      return existing;
    }

    var indicator = document.createElement('div');
    indicator.className = 'js-sync-indicator inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 cursor-pointer select-none transition-all shadow-xs hover:bg-emerald-500/20';
    indicator.setAttribute('data-purpose', 'live-data-freshness-indicator');
    indicator.innerHTML = '<span data-sync-dot class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span><span data-sync-text>Live • ' + formatTimestamp(globalLastSuccessTime) + '</span>';
    indicator.title = 'Data automatically refreshing every 5s • Click to sync now';

    indicator.addEventListener('click', function () {
      refreshAll();
    });

    if (options.prepend) {
      container.insertBefore(indicator, container.firstChild);
    } else {
      container.appendChild(indicator);
    }

    indicatorElements.add(indicator);
    updateGlobalSyncState(globalSyncState);
    return indicator;
  }

  return {
    DEFAULT_INTERVAL: DEFAULT_INTERVAL,
    start: start,
    stop: stop,
    stopAll: stopAll,
    trigger: trigger,
    refreshAll: refreshAll,
    isUserInputActive: isUserInputActive,
    attachIndicator: attachIndicator,
    updateGlobalSyncState: updateGlobalSyncState,
    getGlobalSyncState: function () { return globalSyncState; },
    getLastSuccessTime: function () { return globalLastSuccessTime; },
    formatTimestamp: formatTimestamp
  };
});
