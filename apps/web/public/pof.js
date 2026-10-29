import init,{execute} from '/crypto/haven_crypto.js';
await init();
window.havenPoF={call:(state,command)=>JSON.parse(execute(state,JSON.stringify(command)))};
document.getElementById('result').textContent='WASM initialized; no security qualification implied.';
