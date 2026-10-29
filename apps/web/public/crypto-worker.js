import init, {execute} from '/crypto/haven_crypto.js';
const ready=init();
let chain=Promise.resolve();
self.onmessage=e=>{chain=chain.then(async()=>{const {id,state,command}=e.data;try{await ready;const value=JSON.parse(execute(state,JSON.stringify(command)));self.postMessage({id,value});}catch{self.postMessage({id,error:'CRYPTO_REJECTED'});}});};
