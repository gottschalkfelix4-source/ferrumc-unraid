<script lang="ts">
	import { onMount } from 'svelte';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { api } from '$lib/stores/telemetry.svelte.js';
	type Values={motd:string[];max_players:number;chunk_render_distance:number;online_mode:boolean;whitelist:boolean;default_gamemode:string;tps:number;network_compression_threshold:number;encryption_enabled:boolean};
	let values=$state<Values|null>(null), motd=$state(''), revision=$state(''), baseline=$state('');
	let busy=$state(false), error=$state(''), notice=$state(''), managed=$state(false);
	const dirty=$derived(values ? JSON.stringify({...values,motd:motd.split('\n')})!==baseline : false);
	async function load() {busy=true;error='';try {const result=await api('/config');values=result.values;motd=result.values.motd.join('\n');revision=result.revision;baseline=JSON.stringify(values);managed=result.managed;}catch(e){error=(e as Error).message;}finally{busy=false;}}
	onMount(load);
	async function save(event:SubmitEvent){event.preventDefault();if(!values)return;busy=true;error='';notice='';try{const result=await api('/config',{method:'PUT',body:JSON.stringify({values:{...values,motd:motd.split('\n')},revision})});values=result.values;baseline=JSON.stringify(values);revision=result.revision;managed=true;notice='Configuration saved. Restart the server to apply your changes.';}catch(e){error=(e as Error).message;}finally{busy=false;}}
</script>
<svelte:head><title>Configuration | FerrumC Dashboard</title></svelte:head>
<div class="max-w-7xl mx-auto space-y-5">
	<div class="glass rounded-2xl border border-border p-6 md:p-8">
		<div class="mb-7"><h2 class="text-lg font-semibold text-white">Server Configuration</h2><p class="text-sm text-muted-foreground mt-2">Save settings here, then restart to apply them. Saved dashboard settings take precedence over container defaults.</p></div>
		{#if error}<div class="mb-5 text-sm text-destructive" role="alert">{error} <button class="underline ml-2" onclick={load}>Reload configuration</button></div>{/if}
		{#if notice}<p class="mb-5 rounded-lg bg-success/10 p-4 text-sm text-success" role="status">{notice}</p>{/if}
		{#if values}<form onsubmit={save} class="space-y-7">
			<div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
				<div class="space-y-2 md:col-span-2"><label for="motd" class="text-sm">Server list messages</label><textarea id="motd" bind:value={motd} rows="3" maxlength="10240" required class="w-full rounded-lg border border-border bg-black/20 px-3 py-2 text-sm"></textarea><p class="text-xs text-muted-foreground">One message per line. FerrumC chooses a message from this list.</p></div>
				<div class="space-y-2"><label for="players" class="text-sm">Maximum players</label><Input id="players" type="number" min={1} max={10000} step={1} required bind:value={values.max_players} class="bg-black/20"/></div>
				<div class="space-y-2"><label for="view" class="text-sm">View distance (chunks)</label><Input id="view" type="number" min={2} max={32} step={1} required bind:value={values.chunk_render_distance} class="bg-black/20"/></div>
				<div class="space-y-2"><label for="gamemode" class="text-sm">Default game mode</label><select id="gamemode" bind:value={values.default_gamemode} class="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm">{#each ['creative','survival','adventure','spectator'] as mode}<option value={mode}>{mode[0].toUpperCase()+mode.slice(1)}</option>{/each}</select><p class="text-xs text-muted-foreground">Creative is recommended for this experimental server.</p></div>
				<div class="space-y-2"><label for="tps" class="text-sm">Target ticks per second</label><Input id="tps" type="number" min={1} max={100} step={1} required bind:value={values.tps} class="bg-black/20"/></div>
				<div class="space-y-2"><label for="compression" class="text-sm">Compression threshold (bytes)</label><Input id="compression" type="number" min={-1} max={1048576} step={1} required bind:value={values.network_compression_threshold} class="bg-black/20"/><p class="text-xs text-muted-foreground">Use -1 to disable network compression.</p></div>
				<div class="space-y-4 rounded-xl bg-secondary/40 p-4">
					<label class="flex items-center justify-between gap-4 text-sm" for="online">Authenticate Minecraft accounts<input id="online" type="checkbox" bind:checked={values.online_mode} class="accent-orange-600 size-4"/></label>
					<label class="flex items-center justify-between gap-4 text-sm" for="whitelist">Require whitelist membership<input id="whitelist" type="checkbox" bind:checked={values.whitelist} class="accent-orange-600 size-4"/></label>
					<label class="flex items-center justify-between gap-4 text-sm" for="encryption">Encrypt player connections<input id="encryption" type="checkbox" bind:checked={values.encryption_enabled} class="accent-orange-600 size-4"/></label>
					<p class="text-xs text-muted-foreground">Account authentication always enables encryption. Manage the whitelist on the Players page.</p>
				</div>
			</div>
			<div class="pt-5 border-t border-border flex items-center justify-between gap-4"><p class="text-sm text-muted-foreground">{dirty?'Unsaved changes':managed?'Using saved dashboard settings':'Using container defaults'}</p><div class="flex gap-3"><Button type="button" variant="outline" disabled={busy||!dirty} onclick={load}>Discard</Button><Button type="submit" disabled={busy||!dirty} class="shadow-lg shadow-primary/20">{busy?'Saving…':'Save Changes'}</Button></div></div>
		</form>{:else if !error}<p class="text-muted-foreground">Loading configuration…</p>{/if}
	</div>
</div>
