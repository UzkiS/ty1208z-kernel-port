/* Run with the pinned LuCI source and jsdom 26.1.0 installed in a private prefix. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require(process.argv[3] || 'jsdom');
const source = fs.readFileSync(process.argv[4] || 'openwrt/system/reset/reset.js', 'utf8');
const runtime = fs.readFileSync(process.argv[2], 'utf8');
const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    url: 'http://router.example/cgi-bin/luci/admin/system/reset',
    runScripts: 'outside-only'
});
dom.window.eval(runtime);
const renderer = dom.window.LuCI.prototype.dom;
const E = renderer.create.bind(renderer);
const tick = () => new Promise(resolve => setImmediate(resolve));

async function check(fail) {
    let modal, result = { code: 0 }, writable = true;
    const calls = [], reconnect = [], notifications = [];
    const ui = {
        createHandlerFn: (ctx, fn) => fn.bind(ctx),
        showModal: (title, body) => { modal = { title, body }; },
        hideModal: () => { modal = null; },
        awaitReconnect: (...hosts) => reconnect.push(hosts),
        addNotification: (...args) => notifications.push(args)
    };
    const api = { exec: async (command, args) => { calls.push([command, args]); return result; } };
    const view = new dom.window.Function('view', 'fs', 'ui', 'E', 'L', 'window', source)(
        { extend: obj => obj }, api, ui, E, { hasViewPermission: () => writable }, dom.window);
    await view.load();
    assert.equal(JSON.stringify(calls), JSON.stringify([['/sbin/ty1208z-reset', ['--check']]]));
    calls.length = 0;
    const button = view.render({ code: 0 }).querySelector('button');
    assert.equal(button.hasAttribute('disabled'), false, 'successful preflight must omit disabled attribute');
    assert.equal(button.disabled, false, 'browser DOM must enable the reset button');
    button.click();
    assert.ok(modal, 'enabled button must open the confirmation');
    assert.equal(calls.length, 0, 'confirmation must precede the reset request');
    result = fail ? { code: 1, stderr: 'preflight failed' } : { code: 0 };
    modal.body[1].querySelectorAll('button')[1].click();
    await tick();
    assert.equal(JSON.stringify(calls), JSON.stringify([['/sbin/ty1208z-reset', ['-y', '-r']]]));
    assert.equal(reconnect.length, fail ? 0 : 1);
    assert.equal(notifications.length, fail ? 1 : 0);
    for (const [permission, code] of [[false, 0], [true, 1]]) {
        writable = permission;
        modal = null;
        const blocked = view.render({ code }).querySelector('button');
        assert.equal(blocked.disabled, true);
        blocked.click();
        assert.equal(modal, null, 'disabled button must ignore clicks');
    }
}

async function main() {
    await check(false);
    await check(true);
    const menu = JSON.parse(fs.readFileSync(path.join(__dirname, '../openwrt/system/reset/menu.json')));
    assert.equal(menu['admin/system/reset'].action.path, 'system/reset');
    assert.deepEqual(menu['admin/system/ty1208z-reset'].action, {
        type: 'alias', path: 'admin/system/reset'
    });
    console.log('RESET_REAL_LUCI_DOM_BUTTON_CONFIRMATION_RPC_ERRORS_READONLY_AND_ROUTE_ALIAS_PASS');
}
main().catch(error => { console.error(error); process.exitCode = 1; }).finally(() => dom.window.close());
