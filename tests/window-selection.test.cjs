const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');

// Execute the actual QML helper so the ordering regression cannot silently
// diverge from a test-only copy of the implementation.
const qml = fs.readFileSync(path.join(__dirname, '..', 'Border.qml'), 'utf8');
const source = qml.slice(qml.indexOf('  function fullWindow('), qml.indexOf("  // Quickshell's cached"));
const context = {};
vm.createContext(context);
vm.runInContext(source, context);
const app = {lastIpcObject: {class: 'ordinary.app', fullscreen: 2, mapped: true, hidden: false}};
const saver = {lastIpcObject: {class: 'org.omarchy.screensaver', fullscreen: 2, mapped: true, hidden: false}};
const check = (windows, special = 0) => context.fullWindow({
  lastIpcObject: {specialWorkspace: {id: special}},
  activeWorkspace: {toplevels: {values: windows}},
});
assert.equal(check([app]), app);
assert.equal(check([saver]), null);
assert.equal(check([app, saver]), null);
assert.equal(check([saver, app]), null);
assert.equal(check([app, {lastIpcObject: {...saver.lastIpcObject, hidden: true}}]), app);
assert.equal(check([app, {lastIpcObject: {...saver.lastIpcObject, mapped: false}}]), app);
assert.equal(check([{lastIpcObject: {class: 'ordinary.app', fullscreen: 0}}]), null);
assert.equal(check([{lastIpcObject: {class: 'ordinary.app', fullscreen: 1}}]), null);
assert.equal(check([app], -99), null);
assert.equal(context.fullWindow(null), null);
assert.equal(check([app, {lastIpcObject: {class: 'renamed', initialClass: 'org.omarchy.screensaver'}}]), null);
console.log('11 window-selection checks passed.');
