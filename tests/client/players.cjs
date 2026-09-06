// Real Minecraft 1.21.8 clients exercise native player management.
const mc = require('minecraft-protocol');
const assert = require('node:assert/strict');
const [dashboardPort='9000', minecraftPort='25565', password] = process.argv.slice(2);
const base = `http://127.0.0.1:${dashboardPort}/api`;
let cookie = '';
const clients = [];
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function api(path, method='GET', body) {
  const res = await fetch(base+path, {method, headers: {'Content-Type':'application/json','X-FerrumC-Request':'dashboard',Cookie:cookie}, body:body ? JSON.stringify(body) : undefined});
  if(res.headers.get('set-cookie')) cookie=res.headers.get('set-cookie').split(';')[0];
  const data=await res.json();
  assert(res.ok, JSON.stringify(data)); return data;
}
async function wait(predicate, timeout=30000) {
  const end=Date.now()+timeout;
  while(Date.now()<end) {const value=await predicate(); if(value)return value; await sleep(250);}
  throw Error('Timed out waiting for player/server state');
}
async function restart() {
  await api('/power','POST',{action:'restart'});
  await wait(async()=>{const s=await api('/state');return s.fresh&&!s.operation;},60000);
}
function connect() {
  const client=mc.createClient({host:'127.0.0.1',port:Number(minecraftPort),username:'FerrumCTest',version:'1.21.8',auth:'offline',hideErrors:true});
  client.ended=false;client.reason='';
  client.on('position', packet => {
    client.write('teleport_confirm',{teleportId:packet.teleportId});
    client.write('position_look',{x:packet.x,y:packet.y,z:packet.z,yaw:packet.yaw,pitch:packet.pitch,flags:{onGround:true,hasHorizontalCollision:false}});
  });
  client.on('end',()=>client.ended=true);
  client.on('error',error=>client.reason=String(error));
  client.on('disconnect',packet=>client.reason=JSON.stringify(packet));
  client.on('kick_disconnect',packet=>client.reason=JSON.stringify(packet));
  clients.push(client); return client;
}
async function player() {return (await api('/state')).players.find(p=>p.name==='FerrumCTest');}
async function main() {
  await api('/login','POST',{password});
  const original=await api('/config');
  const set=async values=>{const c=await api('/config');await api('/config','PUT',{values,revision:c.revision});await restart();};
  try {
    await set({...original.values,online_mode:false,encryption_enabled:false,whitelist:false});
    const first=connect(); const p=await wait(player);
    await api(`/players/${p.uuid}/kick`,'POST',{reason:'Dashboard kick test'});
    await wait(()=>first.ended); await wait(async()=>!await player());
    const second=connect();await wait(player);
    await api('/lists/bans','POST',{action:'add',uuid:p.uuid});
    await wait(()=>second.ended);await wait(async()=>!await player());
    const denied=connect();await wait(()=>denied.ended);
    assert.match(denied.reason,/banned/i);
    await api('/lists/bans','POST',{action:'remove',uuid:p.uuid});
    const third=connect();await wait(player);third.end();await wait(async()=>!await player());
    await set({...original.values,online_mode:false,encryption_enabled:false,whitelist:true});
    const unlisted=connect();await wait(()=>unlisted.ended);assert.match(unlisted.reason,/whitelist/i);
    await api('/lists/whitelist','POST',{action:'add',uuid:p.uuid});
    const allowed=connect();await wait(player);allowed.end();await wait(async()=>!await player());
    await api('/lists/whitelist','POST',{action:'remove',uuid:p.uuid});
    const removed=connect();await wait(()=>removed.ended);assert.match(removed.reason,/whitelist/i);
    console.log('PASS: real player list, kick, ban/rejected login, unban, live whitelist add/remove');
  } finally {
    for(const client of clients)client.end();
    await set(original.values);
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{for(const client of clients)client.socket?.destroy();process.exit(process.exitCode||0);});
