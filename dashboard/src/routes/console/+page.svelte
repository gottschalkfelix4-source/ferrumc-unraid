<script lang="ts">
	import { telemetry } from '$lib/stores/telemetry.svelte.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { tick } from 'svelte';
	let command=$state(''), error=$state(''), busy=$state(false), filter=$state(''), level=$state('ALL'), follow=$state(true);
	let scrollbox: HTMLDivElement;
	let history: string[]=[]; let position=0;
	const visible = $derived(telemetry.logs.filter(line => (level==='ALL'||line.level===level) && line.message.toLowerCase().includes(filter.toLowerCase())));
	$effect(() => { const count=visible.length; if(follow && count) tick().then(() => {if(scrollbox) scrollbox.scrollTop=scrollbox.scrollHeight;}); });
	const colors: Record<string,string>={INFO:'text-success',WARN:'text-warning',ERROR:'text-destructive',DEBUG:'text-purple-400',TRACE:'text-muted-foreground'};
	async function submit(event: SubmitEvent) {
		event.preventDefault();if(!command.trim())return;busy=true;error='';
		try {await telemetry.sendCommand(command);history=[...history.slice(-99),command];position=history.length;command='';}
		catch(e){error=(e as Error).message;}finally{busy=false;}
	}
	function keydown(event: KeyboardEvent) {
		if(event.key==='ArrowUp'){event.preventDefault();position=Math.max(0,position-1);command=history[position]??'';}
		if(event.key==='ArrowDown'){event.preventDefault();position=Math.min(history.length,position+1);command=history[position]??'';}
	}
</script>
<svelte:head><title>Console | FerrumC Dashboard</title></svelte:head>
<div class="max-w-7xl mx-auto h-[calc(100dvh-10rem)] min-h-110 flex flex-col">
	<div class="glass rounded-2xl border border-border flex-1 flex flex-col overflow-hidden">
		<div class="flex flex-wrap gap-3 items-center px-5 py-4 border-b border-border bg-secondary/30">
			<h2 class="font-semibold mr-auto">Server Console</h2><Input aria-label="Filter console logs" placeholder="Filter logs…" bind:value={filter} class="w-full sm:w-48 bg-black/20"/>
			<select aria-label="Log level" bind:value={level} class="rounded-md border border-border bg-secondary px-3 py-2 text-sm">{#each ['ALL','INFO','WARN','ERROR','DEBUG','TRACE'] as value}<option>{value}</option>{/each}</select>
			<Button variant="outline" size="sm" onclick={() => follow=!follow}>{follow?'Pause scrolling':'Follow logs'}</Button>
			<a href="/api/logs/download" class="text-sm text-primary hover:underline" download>Download</a>
		</div>
		<!-- svelte-ignore a11y_no_noninteractive_tabindex (The scrollable console must be keyboard accessible.) -->
		<div bind:this={scrollbox} class="flex-1 p-4 font-mono text-sm overflow-y-auto bg-black/40 min-h-0" role="log" aria-label="Server console output" aria-live="off" tabindex="0">
			{#each visible as log (log.id)}<div class="flex gap-3 py-0.5 break-all"><span class="text-muted-foreground shrink-0">{new Date(log.time).toLocaleTimeString('en-GB')}</span><span class="{colors[log.level]??'text-muted-foreground'} shrink-0 w-12">{log.level}</span><span class="whitespace-pre-wrap">{log.message}</span></div>{:else}<p class="text-muted-foreground p-4">{telemetry.logs.length?'No logs match your filter.':'Waiting for server output…'}</p>{/each}
		</div>
		<form onsubmit={submit} class="p-4 border-t border-border bg-secondary/20 space-y-3">
			<div class="flex gap-3 items-center"><span class="text-primary font-mono">&gt;</span><Input aria-label="Server command" bind:value={command} onkeydown={keydown} placeholder="Type a command, e.g. help" maxlength={1024} disabled={!telemetry.fresh||busy} class="font-mono bg-black/20"/><Button type="submit" disabled={!telemetry.fresh||busy||!command.trim()}>{busy?'Sending…':'Send'}</Button></div>
			{#if error}<p role="alert" class="text-sm text-destructive">{error}</p>{/if}
			<p class="text-xs text-muted-foreground">{telemetry.fresh?'Commands run as the server console. Use help for available commands; use Power Options to restart.':'Start the server from Power Options to send commands.'} Showing up to 2,000 recent lines.</p>
		</form>
	</div>
</div>
