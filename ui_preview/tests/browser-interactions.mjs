/**
 * Browser-only interaction acceptance for the synthetic preview.
 * Imported only when the explicit ?gc-preview-test=1 CI query is present.
 * Never requests network, hardware permissions, real state, or credentials.
 */
let assertions=0;
function check(condition,message){
  assertions++;
  if(!condition)throw new Error("synthetic browser interaction: "+message);
}
function button(section,scope="nav"){
  const selector=scope==="mobile"?".mobile-dock button[data-section]":".side-navigation button[data-section]";
  const found=[...document.querySelectorAll(selector)].find(x=>x.dataset.section===section);
  check(Boolean(found),"navigation control exists: "+section);
  return found;
}
function active(section){
  for(const item of document.querySelectorAll("[data-section]")){
    const expected=item.dataset.section===section;
    check((item.getAttribute("aria-current")==="page")===expected,
      "all desktop/mobile aria-current values agree for "+section);
  }
  for(const name of ["overview","devices","automations","privacy"]){
    const panel=document.getElementById("page-"+name);
    check(panel.hidden===(name!==section),"only correct view is visible: "+name);
  }
}

button("devices").click();
active("devices");
check(document.getElementById("device-results").children.length===6,
  "all six synthetic sample devices render");
check(document.activeElement===document.getElementById("content"),
  "navigation focus moves into the main landmark");

const search=document.getElementById("device-search");
search.value="reading";
search.dispatchEvent(new Event("input",{bubbles:true}));
check(document.getElementById("device-results").children.length===1,
  "search narrows to the correct fictional device");

const room=document.getElementById("room-filter");
room.value="Living area";
room.dispatchEvent(new Event("change",{bubbles:true}));
check(document.getElementById("device-results").children.length===0,
  "room filter and text query intersect correctly");
check(document.getElementById("device-empty").hidden===false,
  "no-results accessible feedback becomes visible");

room.value="All rooms";
room.dispatchEvent(new Event("change",{bubbles:true}));
search.value="";
search.dispatchEvent(new Event("input",{bubbles:true}));
check(document.getElementById("device-results").children.length===6,
  "filters restore synthetic inventory");
check(document.getElementById("device-empty").hidden===true,
  "empty-state disappears when matches exist");

button("automations","mobile").click();
active("automations");
check(document.getElementById("page-automations").textContent.includes("No triggers connected"),
  "routines remain explicitly non-executable");

button("privacy").click();
active("privacy");
check(document.getElementById("page-privacy").textContent.includes("No live connections"),
  "privacy disclosure remains visible");

const theme=document.getElementById("theme-mode");
theme.value="dark";
theme.dispatchEvent(new Event("change",{bubbles:true}));
check(document.documentElement.dataset.gcMode==="dark",
  "GC UI Foundations controller sets dark browser theme");
theme.value="light";
theme.dispatchEvent(new Event("change",{bubbles:true}));
check(document.documentElement.dataset.gcMode==="light",
  "GC UI Foundations controller switches to light browser theme");

const accent=document.getElementById("accent-seed");
accent.value="#467a6c";
accent.dispatchEvent(new Event("input",{bubbles:true}));
check(document.documentElement.dataset.gcAccent==="custom",
  "only example custom accent is applied");
check(document.documentElement.style.getPropertyValue("--gc-v1-color-primary")!=="",
  "verified Foundations color engine generated a CSS primary role");

button("overview").click();
active("overview");
const output=document.createElement("output");
output.id="gc-preview-test-output";
output.setAttribute("aria-label","Synthetic browser interaction test result");
output.textContent="BROWSER INTERACTION PASS: "+assertions+" local assertions; no real systems";
document.getElementById("content").append(output);
document.documentElement.dataset.gcUiTest="pass";
