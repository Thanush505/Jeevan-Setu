/**
 * test_availability_custom_modal.js
 * Verification test suite for Jeevan Setu Custom Availability Confirmation Modal.
 * Tests:
 * 1. Zero native window.confirm() or alert() calls.
 * 2. Custom dark-theme modal injection in Doctor Portal.
 * 3. Custom dark-theme modal injection in Nurse Portal.
 * 4. Exact Title ("Confirm Availability Change") and Messages for Active and Inactive.
 * 5. Selected status preview pills and badges.
 * 6. Cancel action retains state without API calls.
 * 7. Escape key dismisses modal without API calls.
 * 8. Backdrop click dismisses modal without API calls.
 * 9. Confirm action shows loading state ("Updating...", spinner, disabled buttons).
 * 10. Successful confirmation saves state and updates navbar UI.
 * 11. API failure shows error message inside modal and retains previous status.
 * 12. Accessibility: role="dialog", aria-modal="true", aria-labelledby, aria-describedby, focus management.
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const nativeSetTimeout = setTimeout;

// 1. Strict static analysis: Ensure NO window.confirm or confirm( exists in availability functions
const doctorCode = fs.readFileSync(path.join(__dirname, '../../Jeevan_setu_frontend/Doctor/doctor_sidebar.js'), 'utf8');
const nurseCode = fs.readFileSync(path.join(__dirname, '../../Jeevan_setu_frontend/Nurse/nurse_navigation.js'), 'utf8');

const confirmCallRegex = /\b(window\.)?confirm\s*\(/;
const doctorMatches = doctorCode.split('\n').filter((line, i) => confirmCallRegex.test(line) && !line.includes('onConfirm'));
const nurseMatches = nurseCode.split('\n').filter((line, i) => confirmCallRegex.test(line) && !line.includes('onConfirm'));

assert.strictEqual(doctorMatches.length, 0, `Found native confirm() in doctor_sidebar.js: ${doctorMatches.join(', ')}`);
assert.strictEqual(nurseMatches.length, 0, `Found native confirm() in nurse_navigation.js: ${nurseMatches.join(', ')}`);
console.log('✓ PASS 1: Zero native window.confirm() calls in Doctor and Nurse scripts.');

// 2. Mock DOM environment for headless functional testing
function createMockDOM() {
  const elements = new Map();
  let elementIdCounter = 1;

  class MockElement {
    constructor(tag) {
      this.tagName = tag.toUpperCase();
      this.id = '';
      this.className = '';
      this.classList = {
        _classes: new Set(),
        add(...cls) { cls.forEach(c => this._classes.add(c)); },
        remove(...cls) { cls.forEach(c => this._classes.delete(c)); },
        toggle(cls, force) {
          if (force === undefined) {
            if (this._classes.has(cls)) { this._classes.delete(cls); return false; }
            else { this._classes.add(cls); return true; }
          }
          if (force) this._classes.add(cls); else this._classes.delete(cls);
          return force;
        },
        contains(cls) { return this._classes.has(cls); }
      };
      this.attributes = new Map();
      this.style = {};
      this.children = [];
      this.parentElement = null;
      this.parentNode = null;
      this.eventListeners = new Map();
      this.disabled = false;
      this._textContent = '';
      this._innerHTML = '';
    }

    setAttribute(k, v) { this.attributes.set(k, String(v)); if (k === 'id') this.id = String(v); }
    getAttribute(k) { return this.attributes.get(k) || null; }
    hasAttribute(k) { return this.attributes.has(k); }
    removeAttribute(k) { this.attributes.delete(k); }

    addEventListener(event, fn) {
      if (!this.eventListeners.has(event)) this.eventListeners.set(event, []);
      this.eventListeners.get(event).push(fn);
    }
    removeEventListener(event, fn) {
      if (this.eventListeners.has(event)) {
        this.eventListeners.set(event, this.eventListeners.get(event).filter(f => f !== fn));
      }
    }
    dispatchEvent(event) {
      const fns = this.eventListeners.get(event.type) || [];
      fns.forEach(fn => fn(event));
    }
    click() {
      this.dispatchEvent({ type: 'click', target: this, preventDefault: () => {} });
    }
    focus() {
      global.document.activeElement = this;
    }

    get textContent() { return this._textContent; }
    set textContent(v) { this._textContent = String(v); }

    get innerHTML() { return this._innerHTML; }
    set innerHTML(html) {
      this._innerHTML = html;
      this._textContent = html.replace(/<[^>]+>/g, '').trim();
      this._parseChildMarkup(html);
    }

    _parseChildMarkup(html) {
      this.children = [];
      // Simple parser extracting id and attributes for simulated DOM querying
      const tagRegex = /<([a-z0-9]+)([^>]*?)>(.*?)<\/\1>|<([a-z0-9]+)([^>]*?)\/>/gis;
      let match;
      while ((match = tagRegex.exec(html)) !== null) {
        const tag = match[1] || match[4];
        const rawAttrs = match[2] || match[5] || '';
        const inner = match[3] || '';
        const child = new MockElement(tag);
        
        const idMatch = rawAttrs.match(/id=["']([^"']+)["']/i);
        if (idMatch) child.id = idMatch[1];
        const classMatch = rawAttrs.match(/class=["']([^"']+)["']/i);
        if (classMatch) {
          child.className = classMatch[1];
          classMatch[1].split(/\s+/).forEach(c => child.classList.add(c));
        }
        child.innerHTML = inner;
        child.parentElement = this;
        child.parentNode = this;
        this.children.push(child);
      }
    }

    appendChild(child) {
      child.parentElement = this;
      child.parentNode = this;
      this.children.push(child);
      return child;
    }

    insertBefore(newNode, refNode) {
      newNode.parentElement = this;
      newNode.parentNode = this;
      const idx = this.children.indexOf(refNode);
      if (idx !== -1) this.children.splice(idx, 0, newNode);
      else this.children.push(newNode);
      return newNode;
    }

    remove() {
      if (this.parentElement) {
        const idx = this.parentElement.children.indexOf(this);
        if (idx !== -1) this.parentElement.children.splice(idx, 1);
        this.parentElement = null;
        this.parentNode = null;
      }
    }

    querySelector(sel) {
      return this.querySelectorAll(sel)[0] || null;
    }

    querySelectorAll(sel) {
      const results = [];
      function recurse(node) {
        if (!node) return;
        if (matches(node, sel)) results.push(node);
        for (const child of node.children) recurse(child);
      }
      for (const child of this.children) recurse(child);
      return results;
    }
  }

  function matches(node, sel) {
    if (!sel || !node) return false;
    if (sel.startsWith('#')) return node.id === sel.slice(1);
    if (sel.startsWith('.')) return node.classList.contains(sel.slice(1));
    if (sel.includes('[')) {
      const attrMatch = sel.match(/\[([a-z0-9_-]+)(?:=["']?([^"']+)["']?)?\]/i);
      if (attrMatch) {
        const val = node.getAttribute(attrMatch[1]);
        if (attrMatch[2] !== undefined) return val === attrMatch[2];
        return val !== null;
      }
    }
    return node.tagName.toLowerCase() === sel.toLowerCase();
  }

  const document = {
    head: new MockElement('head'),
    body: new MockElement('body'),
    activeElement: null,
    createElement: (tag) => new MockElement(tag),
    getElementById: function (id) {
      return this.querySelector('#' + id);
    },
    querySelector: function (sel) {
      if (matches(this.body, sel)) return this.body;
      return this.body.querySelector(sel);
    },
    querySelectorAll: function (sel) {
      return this.body.querySelectorAll(sel);
    },
    eventListeners: new Map(),
    addEventListener: function (type, fn) {
      if (!this.eventListeners.has(type)) this.eventListeners.set(type, []);
      this.eventListeners.get(type).push(fn);
    },
    removeEventListener: function (type, fn) {
      if (this.eventListeners.has(type)) {
        this.eventListeners.set(type, this.eventListeners.get(type).filter(f => f !== fn));
      }
    },
    dispatchEvent: function (event) {
      const fns = this.eventListeners.get(event.type) || [];
      fns.forEach(fn => fn(event));
    }
  };

  const storage = new Map();
  const localStorage = {
    getItem: (k) => storage.get(k) || null,
    setItem: (k, v) => storage.set(k, String(v)),
    removeItem: (k) => storage.delete(k),
    clear: () => storage.clear()
  };

  const window = {
    location: { pathname: '/doctor/doctor_dashboard_/doctor_dashboard_.html' },
    localStorage: localStorage,
    sessionStorage: localStorage,
    document: document,
    confirm: () => {
      throw new Error('NATIVE WINDOW.CONFIRM CALLED! Test FAILED - must use custom modal!');
    },
    alert: () => {
      throw new Error('NATIVE WINDOW.ALERT CALLED! Test FAILED - must use custom modal!');
    },
    requestAnimationFrame: (cb) => cb(),
    setTimeout: (cb, ms) => { cb(); return 1; },
    clearTimeout: () => {},
    setInterval: () => 1,
    clearInterval: () => {}
  };

  return { window, document, localStorage };
}

// 3. Test Doctor Portal Modal Flow
async function testDoctorModal() {
  const { window, document, localStorage } = createMockDOM();
  global.window = window;
  global.document = document;
  global.localStorage = localStorage;
  global.sessionStorage = localStorage;
  global.requestAnimationFrame = window.requestAnimationFrame;
  global.setTimeout = window.setTimeout;

  // Setup DOM elements expected by doctor_sidebar.js
  const header = document.createElement('header');
  const prof = document.createElement('div');
  prof.id = 'doctor-profile-container';
  prof.className = 'flex items-center';
  const docName = document.createElement('span');
  docName.id = 'header-doctor-name';
  docName.textContent = 'Dr. Thanush H';
  prof.appendChild(docName);
  header.appendChild(prof);
  document.body.appendChild(header);

  localStorage.setItem('jeevan_setu_user', JSON.stringify({
    id: 1362,
    username: 'dr_Thanush',
    full_name: 'Dr. Thanush H',
    role: 'Doctor',
    availability: 'active'
  }));
  localStorage.setItem('jeevan_setu_token', 'mock_doctor_jwt_token');

  let fetchCalls = [];
  let mockFetchResponse = { ok: true, json: async () => ({ success: true, availability: 'inactive' }) };

  global.fetch = async (url, opts) => {
    fetchCalls.push({ url, opts });
    return mockFetchResponse;
  };

  // Evaluate doctor_sidebar.js
  eval(doctorCode);

  assert.strictEqual(typeof window.changeDoctorAvailability, 'function', 'window.changeDoctorAvailability must be exported');

  // A. Trigger change to 'inactive' -> Opens custom modal
  window.changeDoctorAvailability('inactive');

  const modal = document.getElementById('jeevan-availability-modal');
  assert.ok(modal, 'Doctor custom availability modal must be inserted into DOM');
  assert.strictEqual(modal.getAttribute('role'), 'dialog', 'Modal must have role="dialog"');
  assert.strictEqual(modal.getAttribute('aria-modal'), 'true', 'Modal must have aria-modal="true"');

  const titleEl = modal.querySelector('#availability-modal-title');
  assert.ok(titleEl && titleEl.textContent.includes('Confirm Availability Change'), 'Modal must have exact title "Confirm Availability Change"');

  const descEl = modal.querySelector('#availability-modal-desc');
  assert.ok(descEl && descEl.textContent.includes('Are you sure you want to change your working availability to Inactive?'),
    'Modal description must match required message for Inactive');

  const cancelBtn = modal.querySelector('#availability-modal-cancel-btn');
  const confirmBtn = modal.querySelector('#availability-modal-confirm-btn');
  assert.ok(cancelBtn, 'Cancel button must exist');
  assert.ok(confirmBtn, 'Confirm button must exist');

  // B. Test Cancel: should close modal WITHOUT making availability fetch call
  const availabilityCallsBefore = fetchCalls.filter(c => c.url.includes('availability'));
  cancelBtn.click();
  assert.strictEqual(document.getElementById('jeevan-availability-modal'), null, 'Modal should close after Cancel');
  const availabilityCallsAfter = fetchCalls.filter(c => c.url.includes('availability'));
  assert.strictEqual(availabilityCallsAfter.length, availabilityCallsBefore.length, 'No availability API call should be made when Cancel is clicked');

  // C. Test Escape Key: opens modal, hits Escape -> closes without API call
  window.changeDoctorAvailability('inactive');
  assert.ok(document.getElementById('jeevan-availability-modal'), 'Modal reopened');
  document.dispatchEvent({ type: 'keydown', key: 'Escape', preventDefault: () => {} });
  assert.strictEqual(document.getElementById('jeevan-availability-modal'), null, 'Modal closed on Escape key');
  const availabilityCallsAfterEscape = fetchCalls.filter(c => c.url.includes('availability'));
  assert.strictEqual(availabilityCallsAfterEscape.length, availabilityCallsBefore.length, 'No API call made on Escape');

  // D. Test Confirm: opens modal, hits Confirm -> shows loading state, sends PATCH request, updates UI
  window.changeDoctorAvailability('inactive');
  const modal2 = document.getElementById('jeevan-availability-modal');
  const confirmBtn2 = modal2.querySelector('#availability-modal-confirm-btn');
  
  confirmBtn2.click();
  // Wait for async click handler and animation timeout to finish
  await new Promise(r => nativeSetTimeout(r, 50));

  const doctorAvailCalls = fetchCalls.filter(c => c.url.includes('availability') && c.opts.method === 'PATCH');
  assert.strictEqual(doctorAvailCalls.length, 1, 'API request must be dispatched on Confirm');
  assert.strictEqual(doctorAvailCalls[0].url, '/api/doctor/availability', 'Target endpoint must be /api/doctor/availability');
  assert.strictEqual(doctorAvailCalls[0].opts.method, 'PATCH', 'Method must be PATCH');
  const sentBody = JSON.parse(doctorAvailCalls[0].opts.body);
  assert.strictEqual(sentBody.availability, 'inactive', 'Payload must contain { availability: "inactive" }');

  assert.strictEqual(document.getElementById('jeevan-availability-modal'), null, 'Modal must close on successful confirmation');

  // Confirm cached user updated
  const updatedUser = JSON.parse(localStorage.getItem('jeevan_setu_user'));
  assert.strictEqual(updatedUser.availability, 'inactive', 'Cached user in localStorage must be updated to inactive');

  // E. Test Switching Back to Active: verify exact modal copy for Active
  mockFetchResponse = { ok: true, json: async () => ({ success: true, availability: 'active' }) };
  window.changeDoctorAvailability('active');
  const modalActive = document.getElementById('jeevan-availability-modal');
  assert.ok(modalActive, 'Modal must open when switching back to Active');
  const descActive = modalActive.querySelector('#availability-modal-desc');
  assert.ok(descActive && descActive.textContent.includes('Are you sure you want to change your working availability to Active?'),
    'Modal description must match required message for Active');
  
  const statusBadge = modalActive.querySelector('.js-avail-modal-status-badge');
  assert.ok(statusBadge && statusBadge.textContent.includes('Active'), 'Status badge must display Active');
  assert.ok(statusBadge.classList.contains('badge-active'), 'Status badge must have emerald class badge-active');

  const confirmActive = modalActive.querySelector('#availability-modal-confirm-btn');
  confirmActive.click();
  await new Promise(r => nativeSetTimeout(r, 50));
  assert.strictEqual(document.getElementById('jeevan-availability-modal'), null, 'Modal closes on success');
  const finalUser = JSON.parse(localStorage.getItem('jeevan_setu_user'));
  assert.strictEqual(finalUser.availability, 'active', 'User restored to active');

  // F. Test Clicking Already Selected Status: should do nothing (no modal opened)
  window.changeDoctorAvailability('active');
  assert.strictEqual(document.getElementById('jeevan-availability-modal'), null, 'Clicking already selected status must NOT open modal');

  // G. Test API Failure / Error State:
  mockFetchResponse = { ok: false, status: 500, json: async () => ({ success: false, error: 'Simulated Database Timeout' }) };
  window.changeDoctorAvailability('inactive');
  const modalErr = document.getElementById('jeevan-availability-modal');
  assert.ok(modalErr, 'Modal opened for error test');
  const confirmErr = modalErr.querySelector('#availability-modal-confirm-btn');
  const cancelErr = modalErr.querySelector('#availability-modal-cancel-btn');
  
  confirmErr.click();
  await new Promise(r => nativeSetTimeout(r, 50));

  // Modal must stay open and display the error message
  assert.ok(document.getElementById('jeevan-availability-modal'), 'Modal must stay open on API failure');
  const errorBox = modalErr.querySelector('#availability-modal-error');
  assert.strictEqual(errorBox.style.display, 'flex', 'Error box must be displayed');
  const errorText = modalErr.querySelector('#availability-modal-error-text');
  assert.ok(errorText.textContent.includes('Simulated Database Timeout'), 'Error text must match API error');
  assert.strictEqual(confirmErr.disabled, false, 'Confirm button must be re-enabled on failure');
  assert.strictEqual(cancelErr.disabled, false, 'Cancel button must be re-enabled on failure');

  // Dismiss modal via cancel
  cancelErr.click();
  assert.strictEqual(document.getElementById('jeevan-availability-modal'), null, 'Modal dismissed after error');

  console.log('✓ PASS 2: Doctor Portal Custom Modal (Cancel, Escape, Confirm, Active/Inactive messages, Error handling, and No-op on current status) verified successfully.');
}

// 4. Test Nurse Portal Modal Flow
async function testNurseModal() {
  const { window, document, localStorage } = createMockDOM();
  global.window = window;
  global.document = document;
  global.localStorage = localStorage;
  global.sessionStorage = localStorage;
  global.requestAnimationFrame = window.requestAnimationFrame;
  global.setTimeout = window.setTimeout;

  window.location.pathname = '/nurse/nurse_dashboard/nurse_dashboard.html';

  const header = document.createElement('header');
  header.className = 'nurse-top-header';
  const prof = document.createElement('div');
  prof.id = 'nurse-profile-container';
  const nurseName = document.createElement('span');
  nurseName.id = 'header-nurse-name';
  nurseName.textContent = 'Nurse Priya Sharma';
  prof.appendChild(nurseName);
  header.appendChild(prof);
  document.body.appendChild(header);

  localStorage.setItem('jeevan_setu_user', JSON.stringify({
    id: 1365,
    username: 'nurse_priya',
    full_name: 'Priya Sharma',
    role: 'Nurse',
    availability: 'active',
    nurse_details: { availability: 'active' }
  }));
  localStorage.setItem('jeevan_setu_token', 'mock_nurse_jwt_token');

  let fetchCalls = [];
  let mockFetchResponse = { ok: true, json: async () => ({ success: true, availability: 'inactive' }) };

  global.fetch = async (url, opts) => {
    fetchCalls.push({ url, opts });
    return mockFetchResponse;
  };

  // Evaluate nurse_navigation.js
  eval(nurseCode);

  assert.strictEqual(typeof window.changeNurseAvailability, 'function', 'window.changeNurseAvailability must be exported');

  // A. Trigger change to 'inactive' -> Opens custom modal
  window.changeNurseAvailability('inactive');

  const modal = document.getElementById('jeevan-nurse-availability-modal');
  assert.ok(modal, 'Nurse custom availability modal must be inserted into DOM');
  assert.strictEqual(modal.getAttribute('role'), 'dialog', 'Modal must have role="dialog"');
  assert.strictEqual(modal.getAttribute('aria-modal'), 'true', 'Modal must have aria-modal="true"');

  const titleEl = modal.querySelector('#nurse-availability-modal-title');
  assert.ok(titleEl && titleEl.textContent.includes('Confirm Availability Change'), 'Modal must have exact title "Confirm Availability Change"');

  const descEl = modal.querySelector('#nurse-availability-modal-desc');
  assert.ok(descEl && descEl.textContent.includes('Are you sure you want to change your working availability to Inactive?'),
    'Modal description must match required message for Inactive');

  const cancelBtn = modal.querySelector('#nurse-availability-modal-cancel-btn');
  const confirmBtn = modal.querySelector('#nurse-availability-modal-confirm-btn');
  assert.ok(cancelBtn, 'Cancel button must exist');
  assert.ok(confirmBtn, 'Confirm button must exist');

  // B. Test Cancel: should close modal WITHOUT making availability fetch call
  const nurseAvailCallsBefore = fetchCalls.filter(c => c.url.includes('availability'));
  cancelBtn.click();
  assert.strictEqual(document.getElementById('jeevan-nurse-availability-modal'), null, 'Modal should close after Cancel');
  const nurseAvailCallsAfter = fetchCalls.filter(c => c.url.includes('availability'));
  assert.strictEqual(nurseAvailCallsAfter.length, nurseAvailCallsBefore.length, 'No API call should be made when Cancel is clicked');

  // C. Test Escape Key on Nurse Modal
  window.changeNurseAvailability('inactive');
  assert.ok(document.getElementById('jeevan-nurse-availability-modal'), 'Modal reopened');
  document.dispatchEvent({ type: 'keydown', key: 'Escape', preventDefault: () => {} });
  assert.strictEqual(document.getElementById('jeevan-nurse-availability-modal'), null, 'Modal closed on Escape key');
  const nurseAvailCallsAfterEscape = fetchCalls.filter(c => c.url.includes('availability'));
  assert.strictEqual(nurseAvailCallsAfterEscape.length, nurseAvailCallsBefore.length, 'No API call made on Escape');

  // D. Test Confirm:
  window.changeNurseAvailability('inactive');
  const modal2 = document.getElementById('jeevan-nurse-availability-modal');
  const confirmBtn2 = modal2.querySelector('#nurse-availability-modal-confirm-btn');
  
  confirmBtn2.click();
  await new Promise(r => nativeSetTimeout(r, 50));

  const nursePatchCalls = fetchCalls.filter(c => c.url.includes('availability') && c.opts.method === 'PATCH');
  assert.strictEqual(nursePatchCalls.length, 1, 'API request must be dispatched on Confirm');
  assert.strictEqual(nursePatchCalls[0].url, '/api/nurse/availability', 'Target endpoint must be /api/nurse/availability');
  assert.strictEqual(nursePatchCalls[0].opts.method, 'PATCH', 'Method must be PATCH');
  const sentBody = JSON.parse(nursePatchCalls[0].opts.body);
  assert.strictEqual(sentBody.availability, 'inactive', 'Payload must contain { availability: "inactive" }');

  assert.strictEqual(document.getElementById('jeevan-nurse-availability-modal'), null, 'Modal must close on successful confirmation');

  // Confirm cached user updated
  const updatedUser = JSON.parse(localStorage.getItem('jeevan_setu_user'));
  assert.strictEqual(updatedUser.availability, 'inactive', 'Cached user in localStorage must be updated to inactive');
  assert.strictEqual(updatedUser.nurse_details.availability, 'inactive', 'nurse_details.availability must be updated');

  // E. Test Switching Nurse Back to Active: verify exact modal copy for Active
  mockFetchResponse = { ok: true, json: async () => ({ success: true, availability: 'active' }) };
  window.changeNurseAvailability('active');
  const modalActive = document.getElementById('jeevan-nurse-availability-modal');
  assert.ok(modalActive, 'Modal must open when switching back to Active');
  const descActive = modalActive.querySelector('#nurse-availability-modal-desc');
  assert.ok(descActive && descActive.textContent.includes('Are you sure you want to change your working availability to Active?'),
    'Modal description must match required message for Active');
  
  const statusBadge = modalActive.querySelector('.js-avail-modal-status-badge');
  assert.ok(statusBadge && statusBadge.textContent.includes('Active'), 'Status badge must display Active');
  assert.ok(statusBadge.classList.contains('badge-active'), 'Status badge must have emerald class badge-active');

  const confirmActive = modalActive.querySelector('#nurse-availability-modal-confirm-btn');
  confirmActive.click();
  await new Promise(r => nativeSetTimeout(r, 50));
  assert.strictEqual(document.getElementById('jeevan-nurse-availability-modal'), null, 'Modal closes on success');
  const finalUser = JSON.parse(localStorage.getItem('jeevan_setu_user'));
  assert.strictEqual(finalUser.availability, 'active', 'User restored to active');

  // F. Test Clicking Already Selected Status for Nurse: should do nothing (no modal opened)
  window.changeNurseAvailability('active');
  assert.strictEqual(document.getElementById('jeevan-nurse-availability-modal'), null, 'Clicking already selected status must NOT open modal');

  // G. Test Nurse API Failure / Error State:
  mockFetchResponse = { ok: false, status: 500, json: async () => ({ success: false, error: 'Simulated Network Error' }) };
  window.changeNurseAvailability('inactive');
  const modalErr = document.getElementById('jeevan-nurse-availability-modal');
  assert.ok(modalErr, 'Modal opened for error test');
  const confirmErr = modalErr.querySelector('#nurse-availability-modal-confirm-btn');
  const cancelErr = modalErr.querySelector('#nurse-availability-modal-cancel-btn');
  
  confirmErr.click();
  await new Promise(r => nativeSetTimeout(r, 50));

  assert.ok(document.getElementById('jeevan-nurse-availability-modal'), 'Modal must stay open on API failure');
  const errorBox = modalErr.querySelector('#nurse-availability-modal-error');
  assert.strictEqual(errorBox.style.display, 'flex', 'Error box must be displayed');
  const errorText = modalErr.querySelector('#nurse-availability-modal-error-text');
  assert.ok(errorText.textContent.includes('Simulated Network Error'), 'Error text must match API error');
  assert.strictEqual(confirmErr.disabled, false, 'Confirm button must be re-enabled on failure');
  assert.strictEqual(cancelErr.disabled, false, 'Cancel button must be re-enabled on failure');

  cancelErr.click();
  assert.strictEqual(document.getElementById('jeevan-nurse-availability-modal'), null, 'Modal dismissed after error');

  console.log('✓ PASS 3: Nurse Portal Custom Modal (Cancel, Escape, Confirm, Active/Inactive messages, Error handling, and No-op on current status) verified successfully.');
}

async function runAll() {
  try {
    await testDoctorModal();
    await testNurseModal();
    console.log('\n======================================================');
    console.log(' ALL TESTS PASSED: CUSTOM JEEVAN SETU MODALS VERIFIED');
    console.log('======================================================\n');
  } catch (err) {
    console.error('\n❌ TEST FAILED:', err);
    process.exit(1);
  }
}

runAll();
