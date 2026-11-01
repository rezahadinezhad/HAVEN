import {build} from '../../apps/web/node_modules/esbuild/lib/main.js';
await build({entryPoints:['apps/web/src/lib/messenger.ts'],outfile:'.local/independent-review/messenger.mjs',bundle:true,banner:{js:"import {createRequire} from 'node:module'; const require=createRequire(import.meta.url); const __dirname=process.cwd();"},platform:'node',format:'esm',plugins:[{name:'review-boundaries',setup(b){b.onLoad({filter:/\/lib\/(api|vault|crypto|media|device-unlock)\.ts$/},a=>{const n=a.path.split('/').at(-1);const sources={
'api.ts':'export const api=(...a)=>globalThis.reviewAPI(...a);',
'vault.ts':'export const saveVault=async(...a)=>globalThis.reviewSave(...a); export const loadVault=async()=>undefined; export const unseal=async()=>{}; export const stopVaultWorker=()=>{};',
'crypto.ts':'export const cryptoCall=async(s,c)=>globalThis.reviewCrypto(s,c); export const lockCrypto=()=>{};',
'media.ts':'export const prepareUpload=()=>{};export const resumeUpload=()=>{};export const discardUpload=()=>{};',
'device-unlock.ts':'export const enrollDeviceUnlock=()=>{};export const removeDeviceUnlock=()=>{};export const unlockWithDevice=()=>{};'};return {contents:sources[n],loader:'ts'};});}}]});
