/**
 * Read-only Home Assistant WebSocket protocol CONTRACT (no transport).
 *
 * Grounded in imported Home Assistant Core:
 *   websocket_api/const.py URL="/api/websocket"
 *   websocket_api/auth.py auth_required -> auth -> auth_ok/auth_invalid
 *   websocket_api/commands.py "get_states" -> result
 *
 * No WebSocket is opened here. No network, token persistence, telemetry, action
 * calls or real home data access. Synthetic test frames only until separately
 * reviewed consent, transport, privacy filtering and integration are available.
 */

export const HA_WS_PATH="/api/websocket";
export const MAX_FRAME_CHARS=262_144;
export const MAX_STATES=2048;
const ENTITY_ID=/^[a-z][a-z0-9_]*\.[a-z0-9_]+$/;

function requireEntityIds(value){
  if(!Array.isArray(value)||value.length<1||value.length>32){
    throw new TypeError("1-32 explicitly allowlisted entity IDs required");
  }
  const unique=new Set();
  for(const id of value){
    if(typeof id!=="string"||!ENTITY_ID.test(id)||id.length>100||unique.has(id)){
      throw new TypeError("invalid or duplicate entity allowlist entry");
    }
    unique.add(id);
  }
  return unique;
}

function decodeFrame(raw){
  if(typeof raw==="string"){
    if(raw.length>MAX_FRAME_CHARS)throw new Error("oversized protocol frame");
    try{raw=JSON.parse(raw);}catch{throw new Error("invalid protocol JSON");}
  }
  if(!raw||typeof raw!=="object"||Array.isArray(raw)){
    throw new Error("protocol frame must be an object");
  }
  return raw;
}

/** Validate and MINIMIZE the accepted local state projection.
 * This is NOT a server-side privacy filter. get_states fetches all authorized
 * entity states before client filtering, so real deployment remains blocked.
 */
export function projectAllowedStateSnapshot(states,allowedIds){
  const allow=requireEntityIds(allowedIds);
  if(!Array.isArray(states)||states.length>MAX_STATES){
    throw new Error("invalid or oversized states result");
  }
  const filtered=[];
  const seen=new Set();
  for(const state of states){
    if(!state||typeof state!=="object"||Array.isArray(state)){
      throw new Error("malformed state entry");
    }
    const id=state.entity_id;
    if(!allow.has(id))continue;
    if(seen.has(id)||typeof state.state!=="string"||state.state.length>120){
      throw new Error("duplicate or malformed allowlisted state");
    }
    if(/[\u0000-\u001f\u007f]/.test(state.state)){
      throw new Error("untrusted control character in state");
    }
    seen.add(id);
    // Intentionally drop attributes, timestamps, contexts, friendly names,
    // coordinates and any future backend fields.
    filtered.push(Object.freeze({entity_id:id,state:state.state}));
  }
  return Object.freeze(filtered);
}

export function createReadOnlyHassProtocol({
  sendFrame,
  onSnapshot,
  accessToken,
  permittedEntityIds
}){
  if(typeof sendFrame!=="function"||typeof onSnapshot!=="function"){
    throw new TypeError("explicit transport callbacks required");
  }
  const allowed=requireEntityIds(permittedEntityIds);
  if(typeof accessToken!=="string"||accessToken.length<1||accessToken.length>4096){
    throw new TypeError("nonempty in-memory token required");
  }
  let token=accessToken;
  let phase="awaiting_auth_required";
  let lastError=null;
  const requestId=1;

  function fail(reason){
    token=null;
    phase="failed";
    lastError=reason;
    throw new Error("Home Assistant read-only contract: "+reason);
  }
  return Object.freeze({
    receive(raw){
      if(phase==="failed"||phase==="closed"){
        throw new Error("read-only protocol is closed");
      }
      let msg;
      try{msg=decodeFrame(raw);}catch{fail("untrusted protocol frame");}
      if(phase==="awaiting_auth_required"){
        if(msg.type!=="auth_required")fail("unexpected initial frame");
        if(!token)fail("missing authentication token");
        const credential=token;
        token=null;
        phase="awaiting_auth_ok";
        // Only the auth frame can carry a credential; no logs or storage.
        sendFrame(Object.freeze({type:"auth",access_token:credential}));
        return "auth_sent";
      }
      if(phase==="awaiting_auth_ok"){
        if(msg.type==="auth_invalid")fail("authentication declined");
        if(msg.type!=="auth_ok")fail("unexpected authentication response");
        phase="awaiting_states";
        sendFrame(Object.freeze({id:requestId,type:"get_states"}));
        return "read_only_states_requested";
      }
      if(phase==="awaiting_states"){
        if(msg.type!=="result"||msg.id!==requestId||msg.success!==true){
          fail("unexpected read-only result");
        }
        let projected;
        try{
          projected=projectAllowedStateSnapshot(msg.result,[...allowed]);
        }catch{
          fail("state projection refused untrusted result");
        }
        phase="complete";
        onSnapshot(projected);
        return "read_only_snapshot_complete";
      }
      fail("unexpected additional protocol message");
    },
    close(){token=null;phase="closed";},
    get status(){return phase;},
    get error(){return lastError;},
    get permittedCount(){return allowed.size;}
  });
}
