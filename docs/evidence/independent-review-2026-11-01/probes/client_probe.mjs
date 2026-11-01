import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
import init,{execute} from '../../apps/web/public/crypto/haven_crypto.js';
globalThis.window=globalThis; globalThis.self=globalThis;
const {Messenger,digest}=await import('./messenger.mjs');
await init({module_or_path:fs.readFileSync('apps/web/public/crypto/haven_crypto_bg.wasm')});
const run=(s,c)=>JSON.parse(execute(s,JSON.stringify(c)));
globalThis.reviewCrypto=run;
const aid=crypto.randomUUID(),bid=crypto.randomUUID(),au=crypto.randomUUID(),bu=crypto.randomUUID(),cid=crypto.randomUUID(),gid='review-'+cid;
let a=run('',{op:'init',identity:`${au}:${aid}`}), b=run('',{op:'init',identity:`${bu}:${bid}`});
const ac={id:aid,user_id:au,identity:a.result.identity,public_key:a.result.public_key,role:'owner'},bc={id:bid,user_id:bu,identity:b.result.identity,public_key:b.result.public_key,role:'member'};
a=run(a.state,{op:'create',group_id:gid});
b=run(b.state,{op:'package'});
a=run(a.state,{op:'add',group_id:gid,key_package:b.result.key_package});
b=run(b.state,{op:'join',group_id:gid,welcome:a.result.welcome});
const canonical=(v)=>JSON.stringify(v,Object.keys(v).sort());
// Use the same canonicalizer as the implementation, including nested fields.
const {default:canon}=await import('../../apps/web/node_modules/canonicalize/lib/canonicalize.js');
const sign=(s,v)=>run(s,{op:'sign',payload:Buffer.from(canon(v)).toString('base64')}).result.signature;
const genesis={domain:'haven/genesis/v1',id:cid,kind:'group',group_id:gid,members:[ac]},gs=sign(a.state,genesis);
const genesisHash=await digest(canon({header:genesis,signature:gs}));
const head={seq:1,hash:'a'.repeat(64),epoch:1,group_id:gid,genesis_hash:genesisHash,kind:'group',members:[ac,bc],epoch_start_seq:1};
const state={v:1,profile:'haven-delivery-v2',device_id:bid,device:{label:'bob',identity:bc.identity,public_key:bc.public_key},crypto:b.state,revision:1,pins:{[aid]:ac.public_key,[bid]:bc.public_key},heads:{[cid]:head},cursor:{[cid]:1},events:[],outbox:{},drafts:{}};
let prev=head.hash;
const envelopes=[];
for (const [i,plain] of ['{',JSON.stringify({id:crypto.randomUUID(),conversation_id:cid,sender:aid,time:new Date().toISOString(),type:'text',text:'After malformed event'})].entries()) {
 a=run(a.state,{op:'encrypt',group_id:gid,plaintext:plain});
 const id=i===0?crypto.randomUUID():JSON.parse(plain).id;
 const header={domain:'haven/envelope/v1',v:1,conversation_id:cid,group_id:gid,sender_device:aid,client_message_id:id,epoch:1,seq:i+2,previous_hash:prev,ciphertext_hash:await digest(Buffer.from(a.result.ciphertext,'base64')),transition:null};
 const signature=sign(a.state,header);prev=await digest(canon({header,signature}));
 envelopes.push({id:crypto.randomUUID(),client_message_id:id,sender_device:aid,v:1,seq:i+2,epoch:1,kind:'application',ciphertext:a.result.ciphertext,header,signature,chain_hash:prev});
}
const detail={id:cid,kind:'group',group_id:gid,epoch:1,last_seq:3,status:'active',head_hash:prev,genesis,genesis_signature:gs,members:[]};
let calls=[],writes=0;
globalThis.reviewAPI=async(path,method='GET')=>{calls.push([path,method]);if(path.endsWith('/acks'))return method==='POST'?{}:{cursors:[]};if(path.includes('/proofs'))return {proofs:envelopes};if(path.includes('/messages'))return {messages:envelopes};return detail;};
globalThis.reviewSave=async()=>{writes++};
const client=new Messenger(bu,'synthetic-secret-for-review',state);
const errors=[];
for(let n=0;n<2;n++)try{await client.sync(detail)}catch(e){errors.push(e.message)}
const wire=JSON.parse(execFileSync('packages/crypto-core/bin/haven-public-verify-x86_64-linux',{input:JSON.stringify({op:'wire',ciphertext:envelopes[0].ciphertext})}));
console.log(JSON.stringify({check:'malformed_authenticated_message',real_MLS_wire_verified:wire.group_id===gid,attempts:2,errors,cursor:client.state.cursor[cid],later_valid_message_received:client.state.events.length>0,persistence_writes:writes}));
// With no pending messages, the production sync implementation still posts an ACK.
const idleDetail={...detail,last_seq:1,head_hash:head.hash};
globalThis.reviewAPI=async(path,method='GET')=>{calls.push([path,method]);return path.endsWith('/acks')?(method==='POST'?{}:{cursors:[]}):idleDetail;};
calls=[];await client.sync(idleDetail);
console.log(JSON.stringify({check:'idle_sync',http_requests:calls.length,requests:calls}));
