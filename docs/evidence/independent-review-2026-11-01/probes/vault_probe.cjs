const fs=require('node:fs'),vm=require('node:vm');
globalThis.self=globalThis;globalThis.window=globalThis;globalThis.require=require;
let resolve;self.postMessage=v=>resolve(v);
require('./vault-worker.cjs');
const base={v:1,device_id:crypto.randomUUID(),profile:'haven-delivery-v2',device:{label:'review'},crypto:'',revision:1,pins:{},heads:{},cursor:{},events:[],outbox:{},drafts:{}};
(async()=>{for(const count of [100,500,800]){
 const value={...base,events:Array.from({length:count},()=>({id:crypto.randomUUID(),conversation_id:crypto.randomUUID(),sender:crypto.randomUUID(),time:new Date().toISOString(),type:'text',text:'x'.repeat(20000),state:'recipient_synced'}))};
 const bytes=Buffer.byteLength(JSON.stringify(value));
 const start=performance.now();
 const response=awaitMessage({id:count,op:'seal',secret:'synthetic-review-passphrase',scope:'review',value});
 function awaitMessage(data){return new Promise(r=>{resolve=r;self.onmessage({data})})}
 const r=await response;console.log(JSON.stringify({check:'vault_snapshot_capacity',events:count,serialized_bytes:bytes,result:r.error||'sealed',milliseconds:Math.round(performance.now()-start)}));
}
})().catch(e=>{console.error(e);process.exitCode=1});
