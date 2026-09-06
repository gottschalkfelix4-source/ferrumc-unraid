<script lang="ts">
	import Activity from "@lucide/svelte/icons/activity";
	import Check from "@lucide/svelte/icons/check";
	import Users from "@lucide/svelte/icons/users";
	import Server from "@lucide/svelte/icons/server";
	import Cpu from "@lucide/svelte/icons/cpu";
	import HardDrive from "@lucide/svelte/icons/hard-drive";
	import ArrowUp from "@lucide/svelte/icons/arrow-up";
	import ArrowDown from "@lucide/svelte/icons/arrow-down";
	import { telemetry } from "$lib/stores/telemetry.svelte.js";
	import { formatBytes } from "$lib/utils/format.js";
	import { onMount } from "svelte";
	import { Button } from "$lib/components/ui/button/index.js";
	import * as Chart from "$lib/components/ui/chart/index.js";
	import { AreaChart, Area, LinearGradient } from "layerchart";
	import { scaleUtc } from "d3-scale";
	import { curveNatural } from "d3-shape";

	let range = $state('1h');
    let chartError = $state('');
    async function loadHistory(next = range) { range = next; try { await telemetry.history(range); chartError = ''; } catch { chartError = 'Could not load metric history.'; } }
    onMount(() => { loadHistory(); const timer = setInterval(() => loadHistory(), 10000); return () => clearInterval(timer); });
    // Chart config for TPS
	const chartConfig = {
		tps: {
			label: "TPS",
			color: "#10b981", // emerald-500 / success color
		},
	mspt: { label: "MSPT (ms)", color: "#ea580c" },
	} satisfies Chart.ChartConfig;

	// Derived values
	const ramFormatted = $derived(telemetry.fresh ? formatBytes(telemetry.data.ramUsage) : "—");
	const totalRamFormatted = $derived(formatBytes(telemetry.data.totalRam));
	const ramPercent = $derived(
		telemetry.data.totalRam > 0
			? (
					(telemetry.data.ramUsage / telemetry.data.totalRam) *
					100
				).toFixed(1)
			: "0",
	);
	const cpuPercent = $derived(telemetry.fresh ? telemetry.data.cpuUsage.toFixed(0) : "—");
	const playersPercent = $derived(
		telemetry.data.maxPlayers > 0
			? (telemetry.data.onlinePlayers / telemetry.data.maxPlayers) * 100
			: 0,
	);
	const storageUsedFormatted = $derived(
		formatBytes(telemetry.data.storageUsed ?? 0),
	);

	// TPS chart data
	const tpsData = $derived(telemetry.data.tpsHistory);
</script>

<svelte:head>
	<title>Overview | FerrumC Dashboard</title>
</svelte:head>

<div class="max-w-7xl mx-auto space-y-6 transition-opacity duration-300">
	<!-- KPI Grid -->
	<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
		<!-- Status Card -->
		<div class="glass p-5 rounded-2xl">
			<div class="flex justify-between items-start mb-4">
				<div>
					<p
						class="text-xs text-muted-foreground uppercase tracking-wider font-medium"
					>
						Status
					</p>
					<h3 class="text-2xl font-bold text-foreground mt-1">
						{telemetry.data.status}
					</h3>
				</div>
				<div class="p-2 rounded-lg {telemetry.fresh ? 'bg-success/10 text-success' : 'bg-secondary text-muted-foreground'}">
					{#if telemetry.fresh}<Check class="w-5 h-5" />{:else}<Activity class="w-5 h-5" />{/if}
				</div>
			</div>
			<div class="w-full bg-border h-1 rounded-full overflow-hidden">
				<div class="{telemetry.fresh ? 'bg-success' : 'bg-muted-foreground'} h-full w-full rounded-full"></div>
			</div>
		</div>

		<!-- Players Card -->
		<div class="glass p-5 rounded-2xl">
			<div class="flex justify-between items-start mb-4">
				<div>
					<p
						class="text-xs text-muted-foreground uppercase tracking-wider font-medium"
					>
						Players
					</p>
					<h3 class="text-2xl font-bold text-foreground mt-1">
						<span>{telemetry.data.onlinePlayers}</span>
						<span class="text-sm text-muted-foreground font-normal"
							>/ {telemetry.data.maxPlayers}</span
						>
					</h3>
				</div>
				<div class="p-2 rounded-lg bg-blue-500/10 text-blue-500">
					<Users class="w-5 h-5" />
				</div>
			</div>
			<div class="w-full bg-border h-1 rounded-full overflow-hidden">
				<div
					class="bg-blue-500 h-full rounded-full transition-all duration-300"
					style="width: {playersPercent}%"
				></div>
			</div>
		</div>

		<!-- Memory Card -->
		<div class="glass p-5 rounded-2xl">
			<div class="flex justify-between items-start mb-4">
				<div>
					<p
						class="text-xs text-muted-foreground uppercase tracking-wider font-medium"
					>
						Memory
					</p>
					<h3 class="text-2xl font-bold text-foreground mt-1">
						{ramFormatted}
					</h3>
				</div>
				<div class="p-2 rounded-lg bg-primary/10 text-primary">
					<Server class="w-5 h-5" />
				</div>
			</div>
			<div class="w-full bg-border h-1 rounded-full overflow-hidden">
				<div
					class="bg-primary h-full rounded-full transition-all duration-300"
					style="width: {ramPercent}%"
				></div>
			</div>
		</div>

		<!-- CPU Card -->
		<div class="glass p-5 rounded-2xl">
			<div class="flex justify-between items-start mb-4">
				<div>
					<p
						class="text-xs text-muted-foreground uppercase tracking-wider font-medium"
					>
						CPU Load
					</p>
					<h3 class="text-2xl font-bold text-foreground mt-1">
						{cpuPercent}%
					</h3>
				</div>
				<div class="p-2 rounded-lg bg-purple-500/10 text-purple-500">
					<Cpu class="w-5 h-5" />
				</div>
			</div>
			<div class="w-full bg-border h-1 rounded-full overflow-hidden">
				<div
					class="bg-purple-500 h-full rounded-full transition-all duration-300"
					style="width: {Math.min(100,telemetry.data.cpuUsage)}%"
				></div>
			</div>
		</div>
	</div>

	<!-- Main Chart Section -->
	<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
		<!-- TPS Chart -->
		<div class="lg:col-span-2 glass rounded-2xl p-6 border border-border">
			<div class="flex items-center justify-between mb-6">
				<div>
					<h3 class="text-lg font-semibold text-foreground">
						Performance Metrics
					</h3>
					<p class="text-sm text-muted-foreground">
						TPS {telemetry.fresh ? telemetry.data.tps.toFixed(1) : "—"} · Tick duration {telemetry.fresh ? telemetry.data.mspt.toFixed(2) : "—"} ms
					</p>
				</div>
                <div class="flex gap-1">{#each ['1h','6h','24h'] as value}<Button variant={range===value?'secondary':'ghost'} size="sm" onclick={() => loadHistory(value)}>{value.toUpperCase()}</Button>{/each}</div>
			</div>
			{#if chartError}<p class="text-sm text-destructive" role="alert">{chartError}</p>{/if}
            {#if !tpsData.length}<p class="py-24 text-center text-sm text-muted-foreground">Waiting for measured tick data. History is retained for 24 hours.</p>{:else}
            <Chart.Container config={chartConfig} class="h-87.5 w-full">
				<AreaChart
					data={tpsData}
					x="time"
					xScale={scaleUtc()}
					yDomain={[0, Math.max(22,...tpsData.map(p => p.mspt + 5),...tpsData.map(p => p.tps + 2))]}
					series={[
						{
							key: "tps",
							label: "TPS",
							color: chartConfig.tps.color,
						},
                        {key:"mspt",label:"MSPT (ms)",color:chartConfig.mspt.color},
					]}
					props={{
						area: {
							curve: curveNatural,
							"fill-opacity": 0.4,
							line: { class: "stroke-2" },
							motion: "tween",
						},
						xAxis: {
							format: (v: Date) =>
								v.toLocaleTimeString("en-US", {
									hour: "2-digit",
									minute: "2-digit",
								}),
							ticks: 5,
						},
						yAxis: {
							ticks: 5,
						},
					}}
				>
					{#snippet marks({ series, getAreaProps })}
						{#each series as s, i (s.key)}
							<LinearGradient
								stops={[
									s.color ?? "",
									"color-mix(in lch, " +
										s.color +
										" 10%, transparent)",
								]}
								vertical
							>
								{#snippet children({
									gradient,
								}: {
									gradient: string;
								})}
									<Area
										{...getAreaProps(s, i)}
										fill={gradient}
									/>
								{/snippet}
							</LinearGradient>
						{/each}
					{/snippet}
					{#snippet tooltip()}
						<Chart.Tooltip
							labelFormatter={(v: Date) =>
								v.toLocaleTimeString("en-US", {
									hour: "2-digit",
									minute: "2-digit",
									second: "2-digit",
								})}
							hideLabel={false}
						/>
					{/snippet}
				</AreaChart>
			</Chart.Container>{/if}
		</div>

		<!-- Resource Distribution -->
		<div class="glass rounded-2xl p-6 border border-border flex flex-col">
			<h3 class="text-lg font-semibold text-foreground mb-6">
				System Resources
			</h3>

			<div class="flex-1 flex flex-col gap-6">
				<!-- CPU Detail -->
				<div class="space-y-2">
					<div class="flex justify-between items-end">
						<span
							class="text-sm text-muted-foreground flex items-center gap-2"
						>
							<Cpu class="w-4 h-4" />
							CPU Usage
						</span>
						<span class="text-foreground font-mono font-bold"
							>{cpuPercent}%</span
						>
					</div>
					<div
						class="w-full bg-secondary h-2 rounded-full overflow-hidden"
					>
						<div
							class="bg-purple-500 h-full transition-all duration-300"
							style="width: {Math.min(100,telemetry.data.cpuUsage)}%"
						></div>
					</div>
					<p class="text-xs text-muted-foreground truncate" title={telemetry.data.cpuModel}>
						{telemetry.data.cpuModel}
					</p>
					<p class="text-xs text-muted-foreground/70">
						{telemetry.data.cpuCores} cores / {telemetry.data.cpuThreads} threads
					</p>
				</div>

				<!-- RAM Detail -->
				<div class="space-y-2">
					<div class="flex justify-between items-end">
						<span
							class="text-sm text-muted-foreground flex items-center gap-2"
						>
							<Server class="w-4 h-4" />
							Memory
						</span>
						<span class="text-foreground font-mono font-bold"
							>{ramPercent}%</span
						>
					</div>
					<div
						class="w-full bg-secondary h-2 rounded-full overflow-hidden"
					>
						<div
							class="bg-primary h-full transition-all duration-300"
							style="width: {ramPercent}%"
						></div>
					</div>
					<p class="text-xs text-muted-foreground">
						{ramFormatted} / {totalRamFormatted} Allocated
					</p>
				</div>

				<!-- Storage Detail -->
				<div class="space-y-2">
					<div class="flex justify-between items-end">
						<span class="text-sm text-muted-foreground flex items-center gap-2">
							<HardDrive class="w-4 h-4" />
							World Size
						</span>
						<span class="text-foreground font-mono font-bold" id="resource-world-size">
							{storageUsedFormatted}
						</span>
					</div>

					<div class="w-full bg-secondary h-2 rounded-full overflow-hidden">
						<div
								class="bg-success h-full transition-all duration-300"
								style="width: 100%"
						></div>
					</div>

					<p class="text-xs text-muted-foreground" id="resource-world-detail">
						Current disk usage for world directory
					</p>
				</div>

				<!-- Container Network -->
				<div class="p-4 rounded-xl bg-secondary border border-border">
					<div class="flex justify-between items-center mb-2">
						<span class="text-sm text-muted-foreground"
							>Container Network</span
						>
					</div>
					<div class="flex justify-between items-center">
						<div class="flex items-center gap-2">
							<ArrowUp class="w-4 h-4 text-success" />
							<div>
								<p class="text-xs text-muted-foreground">
									Upload
								</p>
								<p class="text-sm font-mono text-foreground">
                                    {telemetry.data.networkTx === null ? "—" : formatBytes(telemetry.data.networkTx) + "/s"}
								</p>
							</div>
						</div>
						<div class="w-px h-8 bg-border"></div>
						<div class="flex items-center gap-2">
							<ArrowDown class="w-4 h-4 text-primary" />
							<div>
								<p class="text-xs text-muted-foreground">
									Download
								</p>
								<p class="text-sm font-mono text-foreground">
                                    {telemetry.data.networkRx === null ? "—" : formatBytes(telemetry.data.networkRx) + "/s"}
								</p>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>

    <div class="glass rounded-2xl border border-border overflow-hidden">
        <div class="px-6 py-4 border-b border-border flex justify-between items-center bg-secondary/50"><h3 class="text-sm font-semibold">Recent Console Activity</h3><a href="/console" class="text-sm text-primary hover:underline">View Full Console →</a></div>
        <div class="p-5 font-mono text-sm space-y-2">{#each telemetry.logs.slice(-5) as log (log.id)}<div class="flex gap-3"><span class="text-muted-foreground shrink-0">{new Date(log.time).toLocaleTimeString('en-GB')}</span><span class="break-all {log.level==='ERROR'?'text-destructive':log.level==='WARN'?'text-warning':'text-muted-foreground'}">{log.message}</span></div>{:else}<p class="text-muted-foreground">No server output yet.</p>{/each}</div>
    </div>
</div>
