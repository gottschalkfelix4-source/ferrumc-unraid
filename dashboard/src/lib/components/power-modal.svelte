<script lang="ts">
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';
	import Square from '@lucide/svelte/icons/square';
	import Play from '@lucide/svelte/icons/play';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { api, telemetry } from '$lib/stores/telemetry.svelte.js';
	let {open=$bindable(false)}: {open?:boolean}=$props();
	let selected=$state(''), busy=$state(false), error=$state('');
	$effect(() => { if (!open) {selected='';error='';} });
	async function execute() {
		busy=true;error='';
		try {await api('/power',{method:'POST',body:JSON.stringify({action:selected})});open=false;}
		catch(e) {error=(e as Error).message;} finally {busy=false;}
	}
</script>
<Dialog.Root bind:open><Dialog.Content class="sm:max-w-md">
	<Dialog.Header><Dialog.Title>{selected ? `${selected[0].toUpperCase()+selected.slice(1)} server?` : 'Power Options'}</Dialog.Title><Dialog.Description>{selected==='stop'?'Players will disconnect and the world will be saved. This dashboard stays available.':selected==='restart'?'Players will disconnect, the world will be saved and configuration changes will be applied.':selected==='start'?'Start Minecraft with the saved server configuration.':'Manage the Minecraft server. Your dashboard stays online.'}</Dialog.Description></Dialog.Header>
	{#if !selected}<div class="space-y-3 py-3">
		{#each [{action:'start',title:'Start Server',description:'Bring your Minecraft world online',icon:Play},{action:'restart',title:'Restart Server',description:'Save the world and apply configuration',icon:RefreshCw},{action:'stop',title:'Stop Server',description:'Save the world and disconnect players',icon:Square}] as item}
			<button disabled={!!telemetry.operation || !telemetry.connected || (item.action==='start' ? !['Stopped','Failed'].includes(telemetry.data.status) : telemetry.data.status!=='Running')} onclick={() => selected=item.action} class="w-full flex items-center gap-4 p-4 rounded-xl border border-border bg-secondary hover:bg-secondary/80 text-left disabled:opacity-40 disabled:cursor-not-allowed"><div class="size-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center"><item.icon class="size-5"/></div><div><h3 class="font-medium">{item.title}</h3><p class="text-sm text-muted-foreground">{item.description}</p></div></button>
		{/each}
	</div>{:else}<div class="flex gap-3 pt-4"><Button variant="outline" class="flex-1" disabled={busy} onclick={() => selected=''}>Cancel</Button><Button class="flex-1" variant={selected==='stop'?'destructive':'default'} disabled={busy} onclick={execute}>{busy?'Working…':`Confirm ${selected}`}</Button></div>{/if}
	{#if error}<p class="text-sm text-destructive" role="alert">{error}</p>{/if}
</Dialog.Content></Dialog.Root>
