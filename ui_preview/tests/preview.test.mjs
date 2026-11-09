import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {fileURLToPath} from "node:url";
import path from "node:path";
import test from "node:test";
import {
  DEMO_DEVICES,
  DEMO_ROOMS,
  filterDemoDevices,
  summarizeDemoDevices,
  clampDemoSection
} from "../src/model.mjs";

const dir=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(dir,"..");
const html=readFileSync(path.join(root,"index.html"),"utf8");
const css=readFileSync(path.join(root,"styles.css"),"utf8");
const app=readFileSync(path.join(root,"src/app.mjs"),"utf8");

test("demo fixtures contain no account identifiers, network endpoints or duplicated device ids",()=>{
  assert.equal(DEMO_DEVICES.length,6);
  assert.equal(new Set(DEMO_DEVICES.map(d=>d.id)).size,DEMO_DEVICES.length);
  assert.equal(new Set(DEMO_DEVICES.map(d=>d.room)).size,2);
  for(const device of DEMO_DEVICES){
    assert.match(device.id,/^demo-[a-z-]+-\d{2}$/);
    assert.match(device.name,/^[A-Za-z0-9 ]+$/);
    assert.equal(typeof device.state,"string");
    assert.equal(Object.isFrozen(device),true);
  }
});

test("search is local, case insensitive, and filters on both room and type",()=>{
  assert.equal(filterDemoDevices("light").length,2);
  assert.equal(filterDemoDevices(" LiGhT ","Studio").length,1);
  assert.equal(filterDemoDevices("sensor").length,2);
  assert.equal(filterDemoDevices("closed","Studio").length,0);
  assert.equal(filterDemoDevices("nonexistent").length,0);
  assert.equal(filterDemoDevices("","All rooms").length,6);
});

test("summary is deterministic and does not modify source fixtures",()=>{
  const before=JSON.stringify(DEMO_DEVICES);
  assert.deepEqual(summarizeDemoDevices(),{total:6,active:2,normal:2,rooms:2});
  assert.equal(JSON.stringify(DEMO_DEVICES),before);
  assert.deepEqual(DEMO_ROOMS,["All rooms","Living area","Studio"]);
});

test("navigation clamps unknown section names without interpreting user strings",()=>{
  for(const section of ["overview","devices","automations","privacy"]){
    assert.equal(clampDemoSection(section),section);
  }
  assert.equal(clampDemoSection("../../../admin"),"overview");
  assert.equal(clampDemoSection("real-devices"),"overview");
});

test("preview HTML exposes accessibility landmarks, live disclosure and four page states",()=>{
  assert.match(html,/<html lang="en">/);
  assert.match(html,/href="#content"/);
  assert.match(html,/<main id="content" tabindex="-1" aria-labelledby="overview-title">/);
  assert.match(html,/aria-label="Mobile navigation"/);
  assert.match(html,/class="mobile-brand"/);
  assert.match(css,/\.mobile-brand \{display:flex/);
  assert.match(html,/aria-label="Main navigation"/);
  for(const section of ["overview","devices","automations","privacy"]){
    assert.match(html,new RegExp('id="page-'+section+'"'));
    assert.match(html,new RegExp('<h1 id="'+section+'-title" tabindex="-1">'));
    assert.equal(html.split('data-section="'+section+'"').length-1,2);
  }
  assert.match(html,/No account, device, sensor, or home system is connected/);
  assert.match(html,/No triggers connected/);
  assert.match(html,/id="device-count" role="status" aria-live="polite" aria-atomic="true"/);
  assert.match(html,/id="device-results" class="device-list"><\/div>/);
  assert.match(app,/main\.setAttribute\("aria-labelledby",safe\+"-title"\)/);
});

test("no external domain, telemetry endpoint, iframe, inline execution or live controls",()=>{
  assert.match(html,/connect-src 'none'/);
  assert.match(html,/default-src 'none'/);
  assert.match(html,/script-src 'self'/);
  assert.doesNotMatch(html,/<iframe\b/i);
  assert.doesNotMatch(html,/<script(?![^>]*src=)/i);
  assert.doesNotMatch(html,/https?:\/\/|onload=|onclick=/i);
  assert.doesNotMatch(app,/\bfetch\s*\(|\bWebSocket\s*\(|\bXMLHttpRequest\s*\(|\bnavigator\.bluetooth\b/);
  assert.match(app,/createThemeController\(\{storage:null/);
  assert.match(app,/replaceChildren\(\)/);
  assert.match(app,/textContent=/);
});

test("GC UI Foundations semantic token imports are used without a brand color mandate",()=>{
  assert.match(html,/vendor\/gc-ui\/styles\/gc\.v1\.generated\.css/);
  assert.match(app,/vendor\/gc-ui\/src\/index\.mjs/);
  assert.match(css,/var\(--gc-v1-color-canvas\)/);
  assert.match(css,/var\(--gc-v1-color-primary\)/);
  assert.match(css,/var\(--gc-v1-foundation-radius-lg\)/);
  assert.match(app,/seed:"#46647A"/);
  assert.match(app,/not a mandated GoreeCloud/);
});

test("responsive, forced-color, reduced-motion and mobile safe-area states are authored",()=>{
  assert.match(css,/@media \(max-width:780px\)/);
  assert.match(css,/env\(safe-area-inset-bottom\)/);
  assert.match(css,/@media \(forced-colors:active\)/);
  assert.match(css,/@media \(prefers-reduced-motion:reduce\)/);
  assert.match(css,/:focus-visible/);
  assert.match(css,/min-height:51px/);
});

test("view actions and appearance control are local and reversible",()=>{
  assert.match(app,/navigateTo\(button\.dataset\.section\)/);
  assert.match(app,/navigateTo\(button\.dataset\.openSection\)/);
  assert.match(app,/removeAttribute\("aria-current"\)/);
  assert.match(app,/room\.addEventListener\("change",renderDevices\)/);
  assert.match(app,/theme\.set\(\{mode:event\.currentTarget\.value\}\)/);
  assert.match(app,/theme\.destroy\(\)/);
  assert.match(app,/gc-preview-test/);
  assert.match(app,/import\("\.\.\/tests\/browser-interactions\.mjs"\)/);
});

test("all device rows are created using DOM text nodes, not HTML injection",()=>{
  assert.doesNotMatch(app,/\.innerHTML\b|\.outerHTML\b|insertAdjacentHTML/);
  assert.match(app,/document\.createElement\("article"\)/);
  assert.match(app,/row\.append\(icon,body,state\)/);
});
