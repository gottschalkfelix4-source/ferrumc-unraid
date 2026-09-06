<script lang="ts">
	import LayoutGrid from '@lucide/svelte/icons/layout-grid';
	import Terminal from '@lucide/svelte/icons/terminal';
	import Users from '@lucide/svelte/icons/users';
	import Settings from '@lucide/svelte/icons/settings';
	import Zap from '@lucide/svelte/icons/zap';
	import LogOut from '@lucide/svelte/icons/log-out';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import { page } from '$app/state';
	import { afterNavigate } from '$app/navigation';
	import { api, auth, telemetry } from '$lib/stores/telemetry.svelte.js';
	const sidebar = Sidebar.useSidebar();
	afterNavigate(() => sidebar.setOpenMobile(false));
	const navItems = [{href:'/',label:'Overview',icon:LayoutGrid},{href:'/console',label:'Console',icon:Terminal},{href:'/players',label:'Players',icon:Users},{href:'/config',label:'Config',icon:Settings}];
	let {onPowerClick, open=$bindable()}: {onPowerClick?:()=>void;open?:boolean}=$props();
	let logoutError = $state('');
	async function logout() { try { await api('/logout',{method:'POST',body:'{}'}); telemetry.disconnect(); auth.authenticated=false; } catch { logoutError='Sign out failed. Try again.'; } }
</script>
<Sidebar.Root collapsible="icon" class="border-r border-border">
	<Sidebar.Header class="h-20 border-b border-border justify-center">
		<div class="flex items-center gap-3 {open?'px-2':''}"><img src="/icon.png" alt="FerrumC" class="size-8 rounded-lg shadow-lg shadow-primary/20"/><div class="group-data-[collapsible=icon]:hidden"><h1 class="font-bold text-white tracking-tight text-lg">FerrumC</h1><div class="flex items-center gap-1.5"><span class="size-2 rounded-full {telemetry.fresh?'bg-success':'bg-warning'}"></span><span class="text-xs uppercase tracking-wider text-muted-foreground font-mono">{telemetry.connected ? telemetry.data.status : 'Offline'}</span></div></div></div>
	</Sidebar.Header>
	<Sidebar.Content><Sidebar.Group><Sidebar.GroupContent><Sidebar.Menu>
		{#each navItems as item (item.href)}<Sidebar.MenuItem><Sidebar.MenuButton isActive={page.url.pathname===item.href} class="h-12">{#snippet child({props})}<a href={item.href} {...props}><item.icon class="size-5"/><span class="font-medium">{item.label}</span></a>{/snippet}</Sidebar.MenuButton></Sidebar.MenuItem>{/each}
	</Sidebar.Menu></Sidebar.GroupContent></Sidebar.Group></Sidebar.Content>
	<Sidebar.Footer class="border-t border-border"><Sidebar.Menu>
		<Sidebar.MenuItem><Sidebar.MenuButton class="h-12 text-primary" onclick={onPowerClick}><Zap class="size-5"/><span class="font-medium">Power Options</span></Sidebar.MenuButton></Sidebar.MenuItem>
		<Sidebar.MenuItem><Sidebar.MenuButton class="h-11" onclick={logout}><LogOut class="size-5"/><span>Sign out</span></Sidebar.MenuButton></Sidebar.MenuItem>
		{#if logoutError}<p role="alert" class="text-sm text-destructive">{logoutError}</p>{/if}
	</Sidebar.Menu></Sidebar.Footer>
</Sidebar.Root>
