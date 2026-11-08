/**
 * Home Assistant targeted entity GET — inert read-only request/response contract.
 *
 * Imported Core: homeassistant/components/api/__init__.py:
 *   APIEntityStateView.url="/api/states/{entity_id}"
 *   GET requires user.permissions.check_entity(entity_id, POLICY_READ).
 * Imported http/auth.py requires Authorization: Bearer for token auth.
 *
 * This module has NO HTTP client, credentials, real devices, subscriptions,
 * sockets, UI wiring or persistence. It never issues a request. A future
 * trusted adapter must independently approve origin, TLS, token custody,
 * consent and authorization. Synthetic validation only.
 */
export const ENTITY_STATE_PATH="/api/states/";
export const MAX_ENTITY_RESPONSE_CHARS=16_384;
const ENTITY_ID=/^[a-z][a-z0-9_]*\.[a-z0-9_]+$/;

function allowlist(ids){
  if(!Array.isArray(ids)||ids.length<1||ids.length>32){
    throw new TypeError("explicit entity allowlist must contain 1-32 IDs");
  }
  const allowed=new Set();
  for(const value of ids){
    if(typeof value!=="string"||value.length>100||!ENTITY_ID.test(value)||allowed.has(value)){
      throw new TypeError("invalid or repeated entity allowlist ID");
    }
    allowed.add(value);
  }
  return allowed;
}

/** Construct only the request description; credentials and origin excluded. */
export function describeRestrictedEntityGet(entityId,permittedEntityIds){
  const allowed=allowlist(permittedEntityIds);
  if(!allowed.has(entityId)){
    throw new Error("entity read forbidden by explicit allowlist");
  }
  return Object.freeze({
    method:"GET",
    path:ENTITY_STATE_PATH+entityId,
    redirect:"error",
    credentials:"omit",
    cache:"no-store",
    headers:Object.freeze({Accept:"application/json"})
  });
}

/**
 * Project the single result into a bounded entity_id/state pair.
 * This does not prove transport or backend data minimization: the upstream
 * individual-entity response includes other attributes, before projection.
 */
export function projectRestrictedEntityResponse(entityId,permittedEntityIds,response){
  // Do not even process response content for entities outside consent scope.
  describeRestrictedEntityGet(entityId,permittedEntityIds);
  if(!response||typeof response!=="object"||Array.isArray(response)){
    throw new Error("invalid entity response envelope");
  }
  if(response.status===401||response.status===403){
    throw new Error("entity read authentication or permission refused");
  }
  if(response.status===404){
    throw new Error("requested entity not available");
  }
  if(response.status!==200){
    throw new Error("unexpected entity HTTP status");
  }

  let value=response.body;
  if(typeof value==="string"){
    if(value.length>MAX_ENTITY_RESPONSE_CHARS){
      throw new Error("oversized entity response body");
    }
    try{value=JSON.parse(value);}catch{throw new Error("malformed entity JSON");}
  }else{
    let serialized;
    try{serialized=JSON.stringify(value);}catch{
      throw new Error("unserializable entity body");
    }
    if(typeof serialized!=="string"||serialized.length>MAX_ENTITY_RESPONSE_CHARS){
      throw new Error("oversized or invalid entity body");
    }
  }
  if(!value||typeof value!=="object"||Array.isArray(value)||
      value.entity_id!==entityId||typeof value.state!=="string"||
      value.state.length>120||/[\u0000-\u001f\u007f]/.test(value.state)){
    throw new Error("unexpected entity state payload");
  }
  // Never propagate HA attributes, location, friendly names, last_seen,
  // context/user IDs, linkability or timestamp-bearing metadata.
  return Object.freeze({entity_id:entityId,state:value.state});
}
