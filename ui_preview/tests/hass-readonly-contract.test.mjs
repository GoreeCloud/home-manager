import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";
import test from "node:test";
import {
  HA_WS_PATH,MAX_FRAME_CHARS,MAX_STATES,
  projectAllowedStateSnapshot,createReadOnlyHassProtocol
} from "../src/hass-readonly-contract.mjs";

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"../..");
const inherited=readFileSync(
  path.join(repo,"homeassistant/components/websocket_api/auth.py"),"utf8"
);
const commands=readFileSync(
  path.join(repo,"homeassistant/components/websocket_api/commands.py"),"utf8"
);
const constants=readFileSync(
  path.join(repo,"homeassistant/components/websocket_api/const.py"),"utf8"
);

function setup({allow=["light.demo_lamp"],token="synthetic-access-token"}={}){
  const frames=[],snapshots=[];
  const session=createReadOnlyHassProtocol({
    sendFrame:(frame)=>frames.push(frame),
    onSnapshot:(states)=>snapshots.push(states),
    permittedEntityIds:allow,accessToken:token
  });
  return {frames,snapshots,session};
}

test("contract accurately reflects imported HA authentication and read-only command names",()=>{
  assert.equal(HA_WS_PATH,"/api/websocket");
  for(const [source,pattern] of [
    [constants,/URL: Final = "\/api\/websocket"/],
    [inherited,/TYPE_AUTH_REQUIRED: Final = "auth_required"/],
    [inherited,/TYPE_AUTH_OK: Final = "auth_ok"/],
    [inherited,/TYPE_AUTH_INVALID: Final = "auth_invalid"/],
    [inherited,/probatio\.Exclusive\("access_token", "auth"\)/],
    [commands,/probatio\.Required\("type"\): "get_states"/]
  ])assert.match(source,pattern);
});

test("synthetic handshake sends only auth then get_states; projects requested minimal fields",()=>{
  const {frames,snapshots,session}=setup();
  assert.equal(session.status,"awaiting_auth_required");
  assert.equal(session.receive(JSON.stringify({type:"auth_required",ha_version:"synthetic"})),"auth_sent");
  assert.deepEqual(frames,[{type:"auth",access_token:"synthetic-access-token"}]);
  assert.equal(session.receive({type:"auth_ok",ha_version:"synthetic"}),"read_only_states_requested");
  assert.deepEqual(frames[1],{id:1,type:"get_states"});
  assert.equal(session.receive({id:1,type:"result",success:true,result:[
    {entity_id:"light.demo_lamp",state:"on",attributes:{lat:51,secret:"not output"},
      last_changed:"not output"},
    {entity_id:"person.demo_person",state:"home",attributes:{location:"never output"}}
  ]}),"read_only_snapshot_complete");
  assert.deepEqual(snapshots,[[{entity_id:"light.demo_lamp",state:"on"}]]);
  assert.equal(Object.isFrozen(snapshots[0]),true);
  assert.equal(Object.isFrozen(snapshots[0][0]),true);
  assert.equal(session.status,"complete");
  assert.equal(session.permittedCount,1);
  assert.equal(JSON.stringify(session).includes("synthetic-access-token"),false);
});

test("invalid authentication fails closed without requesting states",()=>{
  const {frames,session}=setup();
  session.receive({type:"auth_required"});
  assert.throws(()=>session.receive({type:"auth_invalid",message:"private server details"}),/authentication declined/);
  assert.equal(session.status,"failed");
  assert.deepEqual(frames.map(x=>x.type),["auth"]);
  assert.doesNotMatch(session.error,/private server details/);
});

test("unexpected pre-auth data and unsolicited server events fail closed",()=>{
  const a=setup();
  assert.throws(()=>a.session.receive({type:"event",event:{device:"demo"}}),/unexpected initial frame/);
  assert.equal(a.frames.length,0);
  const b=setup();
  b.session.receive({type:"auth_required"});
  assert.throws(()=>b.session.receive({type:"auth_required"}),/unexpected authentication response/);
});

test("unrelated command IDs, denied result and entity malformed fields never emit snapshots",()=>{
  for(const result of [
    {type:"result",id:2,success:true,result:[]},
    {type:"result",id:1,success:false,error:{message:"not granted"}},
    {type:"result",id:1,success:true,result:"invalid"},
    {type:"result",id:1,success:true,result:[{entity_id:"light.demo_lamp",state:42}]},
    {type:"result",id:1,success:true,result:[
      {entity_id:"light.demo_lamp",state:"on"},{entity_id:"light.demo_lamp",state:"off"}
    ]}
  ]){
    const {session,snapshots}=setup();
    session.receive({type:"auth_required"});
    session.receive({type:"auth_ok"});
    assert.throws(()=>session.receive(result),/read-only/);
    assert.equal(session.status,"failed");
    assert.deepEqual(snapshots,[]);
  }
});

test("invalid and duplicate permission lists are refused before any messages",()=>{
  for(const allow of [[],["../../admin"],["light.one","light.one"],
    ["light.with-dash"],["person.private",null],Array.from({length:33},(_,i)=>"light.demo"+i)]){
    assert.throws(()=>setup({allow}),/allowlist/);
  }
  for(const token of ["","x".repeat(4097),null]){
    assert.throws(()=>setup({token}),/token required/);
  }
});

test("state projection rejects control characters, invalid shapes and oversized result",()=>{
  for(const states of [
    null,{},Array.from({length:MAX_STATES+1},()=>({entity_id:"light.demo_lamp",state:"on"})),
    [{entity_id:"light.demo_lamp",state:"secret\nnewline"}],
    [{entity_id:"light.demo_lamp",state:"x".repeat(121)}],
    [null]
  ])assert.throws(()=>projectAllowedStateSnapshot(states,["light.demo_lamp"]));
});

test("frames beyond size bound, malformed JSON and unexpected late packets fail closed",()=>{
  assert.ok(MAX_FRAME_CHARS>=131072);
  for(const payload of ["{invalid","x".repeat(MAX_FRAME_CHARS+1)]){
    const {session}=setup();
    assert.throws(()=>session.receive(payload),/untrusted protocol frame/);
    assert.equal(session.status,"failed");
  }
  const b=setup();
  b.session.receive({type:"auth_required"});
  b.session.receive({type:"auth_ok"});
  b.session.receive({type:"result",id:1,success:true,result:[]});
  assert.throws(()=>b.session.receive({type:"result",id:1,success:true,result:[]}),/unexpected additional/);
});

test("closing intentionally erases pending auth and refuses subsequent frames",()=>{
  const {session,frames}=setup();
  session.close();
  assert.equal(session.status,"closed");
  assert.throws(()=>session.receive({type:"auth_required"}),/closed/);
  assert.deepEqual(frames,[]);
});

test("preview has no transport, token persistence, external connection or actual device controls",()=>{
  const script=readFileSync(path.join(repo,"ui_preview/src/hass-readonly-contract.mjs"),"utf8");
  const html=readFileSync(path.join(repo,"ui_preview/index.html"),"utf8");
  const preview=readFileSync(path.join(repo,"ui_preview/src/app.mjs"),"utf8");
  assert.match(script,/No WebSocket is opened/);
  assert.match(script,/get_states fetches all authorized/);
  assert.doesNotMatch(script,/\bnew WebSocket\s*\(|\bfetch\s*\(|\blocalStorage\b|\bsessionStorage\b|\bnavigator\.bluetooth\b/);
  assert.match(html,/connect-src 'none'/);
  assert.doesNotMatch(preview,/hass-readonly-contract\.mjs/);
});
