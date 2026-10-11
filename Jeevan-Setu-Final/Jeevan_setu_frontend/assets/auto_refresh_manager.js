/**
 * Jeevan Setu — Centralized Auto-Refresh Manager (Assets Directory Mirror)
 */
(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define([], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.AutoRefreshManager = factory();
    root.AUTO_REFRESH_INTERVAL = root.AutoRefreshManager.DEFAULT_INTERVAL;
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var DEFAULT_INTERVAL = 10000; // 10 seconds in milliseconds
  var tasks = new Map();
  var isVisibilityListenerAttached = false;
  var isUnloadListenerAttached = false;

  function isUserInputActive(container) {
    try {
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

      var openModals = document.querySelectorAll('.modal.show, .modal:not(.hidden):not([style*="display: none"]), [data-modal-open="true"]');
      if (openModals.length > 0) return true;

      var dirtyForms = document.querySelectorAll('form[data-dirty="true"], form.is-editing');
      if (dirtyForms.length > 0) return true;

      var sel = window.getSelection ? window.getSelection() : null;
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

  async function runTask(task) {
    if (!task || !task.enabled || task.isExecuting) return;
    if (document.visibilityState === 'hidden' && task.skipWhenHidden) return;

    task.isExecuting = true;
    task.lastRun = Date.now();

    try {
      var result = task.fn();
      if (result && typeof result.then === 'function') {
        await result;
      }
      task.errorCount = 0;
      task.lastSuccess = Date.now();
      if (task.onSuccess) task.onSuccess();
    } catch (err) {
      task.errorCount = (task.errorCount || 0) + 1;
      console.warn('[AutoRefreshManager] Task "' + task.key + '" refresh error (attempt #' + task.errorCount + '):', err);
      if (task.onError) task.onError(err);
    } finally {
      task.isExecuting = false;
    }
  }

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

  function formatLiveTimestamp(timestamp) {
    var date = timestamp ? (timestamp instanceof Date ? timestamp : new Date(timestamp)) : new Date();
    return 'Live • ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  return {
    DEFAULT_INTERVAL: DEFAULT_INTERVAL,
    start: start,
    stop: stop,
    stopAll: stopAll,
    isUserInputActive: isUserInputActive,
    formatLiveTimestamp: formatLiveTimestamp
  };
});
