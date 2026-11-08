/** Standalone first-party preview controller. It never contacts a backend. */
import {createThemeController} from "../vendor/gc-ui/src/index.mjs";
import {
  DEMO_DEVICES,
  filterDemoDevices,
  summarizeDemoDevices,
  clampDemoSection
} from "./model.mjs";

const deviceResults=document.getElementById("device-results");
const deviceEmpty=document.getElementById("device-empty");
const search=document.getElementById("device-search");
const room=document.getElementById("room-filter");
const sectionButtons=[...document.querySelectorAll("[data-section]")];
const openButtons=[...document.querySelectorAll("[data-open-section]")];

const headings={
  overview:"Overview",
  devices:"Devices",
  automations:"Automations",
  privacy:"Privacy"
};
const icons=Object.freeze({
  Lighting:"✧",
  Climate:"◈",
  Sensor:"◉",
  Media:"♫"
});

/* The example seed is an optional demo preference, not a mandated GoreeCloud
 * product or ecosystem color. Disable persistence for privacy by design. */
const theme=createThemeController({storage:null,key:"home-manager-preview-ephemeral:"});
theme.set({mode:"auto",accent:"custom",seed:"#46647A",material:"solid"});

function renderDevices(){
  const matches=filterDemoDevices(search.value,room.value);
  deviceResults.replaceChildren();
  for(const device of matches){
    const row=document.createElement("article");
    row.className="device-row";
    row.setAttribute("aria-label",device.name+" — "+device.room+", "+device.state);
    const icon=document.createElement("span");
    icon.className="device-icon";
    icon.setAttribute("aria-hidden","true");
    icon.textContent=icons[device.type]??"◇";
    const body=document.createElement("div");
    body.className="device-body";
    const label=document.createElement("strong");
    label.textContent=device.name;
    const details=document.createElement("small");
    details.textContent=device.type+" · "+device.room;
    body.append(label,details);
    const state=document.createElement("span");
    state.className="device-state";
    state.dataset.kind=device.category;
    state.textContent=device.state;
    row.append(icon,body,state);
    deviceResults.append(row);
  }
  deviceEmpty.hidden=matches.length>0;
  const label=matches.length===1?"sample device":"sample devices";
  document.getElementById("device-count").textContent=String(matches.length)+" "+label;
}

function navigateTo(section,{focus=true}={}){
  const safe=clampDemoSection(section);
  for(const name of Object.keys(headings)){
    const view=document.getElementById("page-"+name);
    view.hidden=name!==safe;
  }
  for(const button of sectionButtons){
    if(button.dataset.section===safe)button.setAttribute("aria-current","page");
    else button.removeAttribute("aria-current");
  }
  document.getElementById("breadcrumb-current").textContent=headings[safe];
  document.title=headings[safe]+" · GoreeCloud Home Manager — Interface Preview";
  if(focus){
    const main=document.getElementById("content");
    main.focus({preventScroll:true});
    main.scrollIntoView({block:"start",behavior:"auto"});
  }
}

for(const button of sectionButtons) {
  button.addEventListener("click",()=>navigateTo(button.dataset.section));
}
for(const button of openButtons) {
  button.addEventListener("click",()=>navigateTo(button.dataset.openSection));
}
search.addEventListener("input",renderDevices);
room.addEventListener("change",renderDevices);

document.getElementById("theme-mode").addEventListener("change",(event)=>{
  theme.set({mode:event.currentTarget.value});
});
document.getElementById("accent-seed").addEventListener("input",(event)=>{
  theme.set({accent:"custom",seed:event.currentTarget.value});
});

const summary=summarizeDemoDevices(DEMO_DEVICES);
document.getElementById("metric-devices").textContent=String(summary.total);
document.getElementById("metric-rooms").textContent=String(summary.rooms);
document.getElementById("metric-active").textContent=String(summary.active);

renderDevices();
navigateTo("overview",{focus:false});
window.addEventListener("pagehide",()=>theme.destroy(),{once:true});

/* Test hook is inert outside the explicit localhost CI test query. The
 * imported module contains only synthetic DOM interaction checks. */
if(new URL(window.location.href).searchParams.get("gc-preview-test")==="1"){
  import("../tests/browser-interactions.mjs").catch((error)=>{
    document.documentElement.dataset.gcUiTest="fail";
    const message=document.createElement("output");
    message.id="gc-preview-test-output";
    message.textContent="BROWSER INTERACTION FAIL: "+String(error?.message??"unknown").slice(0,180);
    document.getElementById("content").append(message);
  });
}
