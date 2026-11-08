import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";
import test from "node:test";
import {
  ENTITY_STATE_PATH,MAX_ENTITY_RESPONSE_CHARS,
  describeRestrictedEntityGet,projectRestrictedEntityResponse
} from "../src/ha-entity-rest-contract.mjs";

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"../..");
const coreApi=readFileSync(path.join(repo,"homeassistant/components/api/__init__.py"),"utf8");
const coreAuth=readFileSync(path.join(repo,"homeassistant/components/http/auth.py"),"utf8");
const allow=["light.demo_lamp","sensor.demo_temperature"];
const entity="light.demo_lamp";
const fakeState={
  entity_id:entity,state:"on",attributes:{
    friendly_name:"should not escape",coordinates:[0,0],user_id:"not included"
  },last_updated:"not exported",context:{id:"private"}
};

test("targeted entity GET and backend entity permissions verified against imported source",()=>{
  assert.equal(ENTITY_STATE_PATH,"/api/states/");
  assert.match(coreApi,/class APIEntityStateView\(HomeAssistantView\)/);
  assert.match(coreApi,/url = "\/api\/states\/\{entity_id\}"/);
  assert.match(coreApi,/def get\(self, request: web.Request, entity_id: str\)/);
  assert.match(coreApi,/user\.permissions\.check_entity\(entity_id, POLICY_READ\)/);
  assert.match(coreApi,/raise Unauthorized\(entity_id=entity_id\)/);
  assert.match(coreAuth,/auth_type != "Bearer"/);
  assert.match(coreAuth,/async_validate_access_token\(auth_val\)/);
});

test("only explicitly consent-listed IDs yield a single GET request description",()=>{
  const plan=describeRestrictedEntityGet(entity,allow);
  assert.deepEqual(plan,{
    method:"GET",path:"/api/states/light.demo_lamp",
    redirect:"error",credentials:"omit",cache:"no-store",
    headers:{Accept:"application/json"}
  });
  assert.equal(Object.isFrozen(plan),true);
  assert.equal(Object.isFrozen(plan.headers),true);
  assert.equal(JSON.stringify(plan).includes("token"),false);
});

test("path traversal, injection and unknown entity IDs are rejected before any I/O",()=>{
  for(const name of [
    "", "light.demo_lamp/../../admin", "../config",
    "light.demo%2Ffoo", "light.demo-lamp", "light..",
    "http://private.example/api", "light.demo?admin=1",
    "person.private_home", "light.demo_lamp\nX-Header:evil"
  ])assert.throws(()=>describeRestrictedEntityGet(name,allow),/allowlist/);
});

test("allowlist cannot contain duplicates, malformed names or excessive entries",()=>{
  for(const ids of [[],["light.a","light.a"],["../../config"],
    Array.from({length:33},(_,i)=>"sensor.demo"+i),["person.demo",null]]){
    assert.throws(()=>describeRestrictedEntityGet("light.a",ids),/allowlist/);
  }
});

test("authorized single-entity response drops all attributes and contextual metadata",()=>{
  const projected=projectRestrictedEntityResponse(entity,allow,{status:200,body:JSON.stringify(fakeState)});
  assert.deepEqual(projected,{entity_id:entity,state:"on"});
  assert.equal(Object.isFrozen(projected),true);
  assert.doesNotMatch(JSON.stringify(projected),/coordinates|user_id|friendly_name|context|last_updated/);
});

test("both JSON object and string responses validate the exact requested ID",()=>{
  assert.deepEqual(projectRestrictedEntityResponse(entity,allow,{status:200,body:fakeState}),
    {entity_id:entity,state:"on"});
  const wrong={...fakeState,entity_id:"sensor.demo_temperature"};
  assert.throws(()=>projectRestrictedEntityResponse(entity,allow,{status:200,body:wrong}),/unexpected entity/);
});

test("403, 401, 404 and 5xx fail without exposing server error response content",()=>{
  for(const status of [401,403,404,429,500,302]){
    assert.throws(()=>projectRestrictedEntityResponse(entity,allow,{
      status,body:{message:"sensitive backend diagnostic"}
    }),/entity/);
  }
});

test("unexpected JSON, control chars and too-large body fail closed",()=>{
  const bad=[
    {status:200,body:"{bad json"},
    {status:200,body:"x".repeat(MAX_ENTITY_RESPONSE_CHARS+1)},
    {status:200,body:{entity_id:entity,state:"unknown\ninject"}},
    {status:200,body:{entity_id:entity,state:42}},
    {status:200,body:[fakeState]},
    {status:200,body:{...fakeState,state:"x".repeat(121)}}
  ];
  for(const result of bad)assert.throws(()=>projectRestrictedEntityResponse(entity,allow,result));
});

test("unauthorized ID refuses even a synthetic response before parsing data",()=>{
  assert.throws(()=>projectRestrictedEntityResponse("person.private_home",allow,{
    status:200,body:fakeState
  }),/allowlist/);
});

test("module is transportless and current demo remains disconnected",()=>{
  const js=readFileSync(path.join(repo,"ui_preview/src/ha-entity-rest-contract.mjs"),"utf8");
  const html=readFileSync(path.join(repo,"ui_preview/index.html"),"utf8");
  const app=readFileSync(path.join(repo,"ui_preview/src/app.mjs"),"utf8");
  assert.match(js,/This module has NO HTTP client/);
  assert.doesNotMatch(js,/\bfetch\s*\(|\bXMLHttpRequest\b|\bnew WebSocket\s*\(|\bhttp\.request\s*\(|\blocalStorage\b/);
  assert.match(html,/connect-src 'none'/);
  assert.doesNotMatch(app,/ha-entity-rest-contract\.mjs/);
});
