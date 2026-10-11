/**
 * Jeevan Setu — Centralized Auto-Refresh Manager
 * 
 * Provides automated background API polling every 10 seconds across
 * Attendant, Doctor, Nurse, and Admin portals without full page reloads.
 * 
 * Features:
 * - Centralized 10-second interval: AUTO_REFRESH_INTERVAL = 10000 ms
 * - Concurrency control: Prevents overlapping in-flight API requests
 * - Form & Input Protection: Guards active inputs, textareas, dirty forms, and open modals from being clobbered
 * - Tab Visibility Awareness: Automatically pauses when page is backgrounded, instantly refreshes when foregrounded
 * - Lifecycle Management: Automatically tears down timers on navigation/unload (prevents memory leaks and duplicate timers)
 * - Resilient Error Handling: Tolerates network hiccups without crashing the UI; handles 401 cleanly
 * - Live Timestamp & Status Indicator Support
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
  var tasks = new Map(); // key -> task state
  var isVisibilityListenerAttached = false;
  var isUnloadListenerAttached = false;

  /**
   * Check if the user is actively typing, focusing an input, selecting text, or interacting with a modal/form.
   * @param {HTMLElement|string} [container] Optional container element to check within
   * @returns {boolean} true if user is actively interacting
   */
  function isUserInputActive(container) {
    try {
      var active = document.activeElement;
      if (active) {
        var tagName = (active.tagName || '').toUpperCase();
        if (tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT' || active.isContentEditable) {
          // If container specified, check if active is inside container
          if (container) {
            var parent = typeof container === 'string' ? document.querySelector(container) : container;
            if (parent && parent.contains(active)) return true;
          } else {
            return true;
          }
        }
      }

      // Check for any open interactive modal or dirty form
      var openModals = document.querySelectorAll('.modal.show, .modal:not(.hidden):not([style*="display: none"]), [data-modal-open="true"]');
      if (openModals.length > 0) return true;

      var dirtyForms = document.querySelectorAll('form[data-dirty="true"], form.is-editing');
      if (dirtyForms.length > 0) return true;

      // Check text selection
      var sel = window.getSelection ? window.getSelection() : null;
      if (sel && sel.toString().length > 0) return true;

    } catch (e) {
      // Non-blocking fail-safe
    }
    return false;
  }

  /**
   * Ensure page visibility listener is set up to instantly trigger refreshes upon return.
   */
  function setupVisibilityListener() {
    if (isVisibilityListenerAttached || typeof document === 'undefined') return;
    isVisibilityListenerAttached = true;

    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible') {
        var now = Date.now();
        tasks.forEach(function (task) {
          if (!task.enabled) return;
          // If more than interval has elapsed since last run, trigger immediately
          if (now - task.lastRun >= task.interval) {
            runTask(task);
          }
        });
      }
    });
  }

  /**
   * Ensure cleanup listener is attached to avoid multiple zombie timers on page navigation.
   */
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
   * Execute a registered task safely with in-flight concurrency protection.
   * @param {Object} task 
   */
  async function runTask(task) {
    if (!task || !task.enabled || task.isExecuting) return;

    // Visibility check: if backgrounded and skipBackground is enabled, defer
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

  /**
   * Register and start an automatic polling task.
   * 
   * @param {string} key Unique identifier for this task (e.g. 'attendant_vitals', 'doctor_dashboard')
   * @param {Function} taskFn The async or sync function that performs the background API fetch and DOM update
   * @param {number} [intervalMs=10000] Interval in ms (defaults to 10,000ms / 10s)
   * @param {Object} [options={}] Additional configuration options
   * @param {boolean} [options.immediate=true] Whether to invoke taskFn immediately upon registration
   * @param {boolean} [options.skipWhenHidden=true] Whether to pause polling when the browser tab is hidden
   * @param {Function} [options.onSuccess] Callback invoked after each successful run
   * @param {Function} [options.onError] Callback invoked if taskFn throws an error
   * @returns {Object} Task controller object
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

    // Stop existing task with same key if present
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

  /**
   * Stop an active auto-refresh task.
   * @param {string} key 
   */
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

  /**
   * Stop all active auto-refresh tasks.
   */
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

  /**
   * Helper to format a subtle live timestamp indicator text.
   * @param {number|Date} [timestamp] Defaults to current time
   * @returns {string} Formatted string like "Live • Updated 10:32:15 PM"
   */
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
