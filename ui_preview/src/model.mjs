/**
 * GoreeCloud Home Manager — synthetic, read-only UI design fixture.
 *
 * No actual household, device, person, location or network data is used here.
 * The production backend integration is not implemented in this preview.
 */
export const DEMO_DEVICES = Object.freeze([
  Object.freeze({id:"demo-light-01",name:"Ambient lights",room:"Living area",type:"Lighting",state:"On",category:"active"}),
  Object.freeze({id:"demo-climate-01",name:"Climate controller",room:"Living area",type:"Climate",state:"Comfort",category:"active"}),
  Object.freeze({id:"demo-sensor-01",name:"Window sensor",room:"Living area",type:"Sensor",state:"Closed",category:"normal"}),
  Object.freeze({id:"demo-light-02",name:"Reading light",room:"Studio",type:"Lighting",state:"Off",category:"idle"}),
  Object.freeze({id:"demo-audio-01",name:"Media speaker",room:"Studio",type:"Media",state:"Standby",category:"idle"}),
  Object.freeze({id:"demo-sensor-02",name:"Air quality",room:"Studio",type:"Sensor",state:"Good",category:"normal"})
]);

export const DEMO_ROOMS=Object.freeze(["All rooms","Living area","Studio"]);

/** Return only a new list of matching demo fixtures, never querying real systems. */
export function filterDemoDevices(query="",room="All rooms"){
  const normalized=String(query).trim().toLocaleLowerCase();
  return DEMO_DEVICES.filter((device)=>
    (room==="All rooms" || device.room===room) &&
    [device.name,device.room,device.type,device.state]
      .some((part)=>part.toLocaleLowerCase().includes(normalized))
  );
}

export function summarizeDemoDevices(devices=DEMO_DEVICES){
  return {
    total:devices.length,
    active:devices.filter((d)=>d.category==="active").length,
    normal:devices.filter((d)=>d.category==="normal").length,
    rooms:new Set(devices.map((d)=>d.room)).size
  };
}

export function clampDemoSection(section){
  const accepted=["overview","devices","automations","privacy"];
  return accepted.includes(section)?section:"overview";
}
