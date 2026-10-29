import {webkit} from '/work/node_modules/playwright/index.mjs';
const browser=await webkit.launch({headless:true});
try{const page=await browser.newPage();await page.goto('https://127.0.0.1:8443/pof.html');await page.waitForFunction(()=>!!window.havenPoF);
const result=await page.evaluate(()=>{const call=window.havenPoF.call;let a=call('',{op:'init',identity:'wk-a'}).state,b=call('',{op:'init',identity:'wk-b'}).state;const kp=call(b,{op:'package'});b=kp.state;a=call(a,{op:'create',group_id:'wk'}).state;const add=call(a,{op:'add',group_id:'wk',key_package:kp.result.key_package});a=add.state;b=call(b,{op:'join',group_id:'wk',welcome:add.result.welcome}).state;const msg=call(a,{op:'encrypt',group_id:'wk',plaintext:'WebKit MLS سلام'});return call(b,{op:'process',group_id:'wk',ciphertext:msg.result.ciphertext}).result.plaintext;});
if(result!=='WebKit MLS سلام')throw new Error('Unexpected plaintext');console.log('PASS WebKit trusted IP TLS + real OpenMLS WASM (isolated Linux container; NOT physical iOS Safari).');
}finally{await browser.close();}
