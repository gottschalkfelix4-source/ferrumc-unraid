<script lang="ts">
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import { page } from '$app/state';
	import { telemetry } from '$lib/stores/telemetry.svelte.js';
	import { formatUptime } from '$lib/utils/format.js';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';

	const pageTitles: Record<string, string> = {
		'/': 'Overview',
		'/console': 'Server Console',
		'/players': 'Player Management',
		'/config': 'Configuration'
	};

	const uptime = $derived(formatUptime(telemetry.data.uptime));
	const pageTitle = $derived(pageTitles[page.url.pathname] ?? 'Overview');
</script>

<header class="h-20 border-b border-border flex items-center justify-between px-4 md:px-8 bg-background/50 backdrop-blur-sm z-10">
	<div class="flex items-center gap-2 text-sm text-muted-foreground">
		<Sidebar.Trigger class="-ml-2 mr-2" />
		<span class="hidden sm:inline">Dashboard</span>
		<ChevronRight class="w-4 h-4" />
		<span class="text-foreground font-medium">{pageTitle}</span>
	</div>
	<div class="flex items-center gap-4">
		<div class="text-right">
			<p class="text-xs text-muted-foreground">Uptime</p>
			<p class="text-sm font-mono text-foreground">{uptime}</p>
		</div>
	</div>
</header>
