<script lang="ts">
	import './layout.css';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import AppSidebar from '$lib/components/app-sidebar.svelte';
	import Header from '$lib/components/header.svelte';
	import PowerModal from '$lib/components/power-modal.svelte';
	import Login from '$lib/components/login.svelte';
	import { auth, telemetry } from '$lib/stores/telemetry.svelte.js';
	import { onMount } from 'svelte';
	let { children } = $props();
	let powerModalOpen = $state(false), open = $state(true), error = $state('');
	onMount(() => { telemetry.bootstrap().catch(() => error = 'Dashboard connection failed. Reload to try again.'); return () => telemetry.disconnect(); });
</script>
{#if auth.loading}
	<div class="min-h-dvh grid place-items-center"><p class="text-muted-foreground">Connecting to FerrumC…</p></div>
{:else if error}
	<div class="min-h-dvh grid place-items-center"><p role="alert">{error}</p></div>
{:else if !auth.authenticated}
	<Login />
{:else}
	<Sidebar.Provider bind:open>
		<AppSidebar bind:open onPowerClick={() => powerModalOpen = true} />
		<Sidebar.Inset class="flex flex-col h-dvh overflow-hidden min-w-0">
			<div class="absolute inset-0 pointer-events-none z-0 overflow-hidden"><div class="absolute top-[-20%] left-[20%] w-150 h-150 bg-primary/5 rounded-full blur-[120px]"></div></div>
			<Header />
			<main class="flex-1 overflow-y-auto p-4 md:p-8 z-10 relative min-w-0">
				{#if !telemetry.connected}<div class="mb-5 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm" role="status">Connection lost. Reconnecting to the dashboard…</div>{/if}
				{#if telemetry.pendingConfig}<div class="mb-5 flex items-center justify-between gap-4 rounded-xl border border-primary/30 bg-primary/10 p-4 text-sm"><span>Configuration saved. Restart the server to apply it.</span><button class="text-primary font-semibold" onclick={() => powerModalOpen = true}>Power Options</button></div>{/if}
				{@render children()}
			</main>
		</Sidebar.Inset>
	</Sidebar.Provider>
	<PowerModal bind:open={powerModalOpen}/>
{/if}
