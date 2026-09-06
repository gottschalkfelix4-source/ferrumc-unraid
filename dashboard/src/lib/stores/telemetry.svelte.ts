import { browser } from '$app/environment';

export interface LogEntry { id: number; time: number; level: string; message: string }
export interface Player { name: string; uuid: string }
export interface TpsDataPoint { time: Date; tps: number; mspt: number }
export const auth = $state({ loading: true, authenticated: false });
export async function api<T = any>(path: string, options: RequestInit = {}): Promise<T> {
	const response = await fetch('/api' + path, { credentials: 'same-origin', ...options,
		headers: { 'Content-Type': 'application/json', 'X-FerrumC-Request': 'dashboard', ...options.headers } });
	const body = await response.json();
	if (!response.ok) {
		if (response.status === 401 && path !== '/login') { auth.authenticated = false; telemetry.disconnect(); }
		throw new Error(body.error || `Request failed (${response.status})`);
	}
	return body;
}

function createTelemetryStore() {
	let socket: WebSocket | null = null;
	let retry: ReturnType<typeof setTimeout> | undefined;
	let active = false;
	let instance = "";
	let connected = $state(false);
	let logs = $state<LogEntry[]>([]);
	let players = $state<Player[]>([]);
	let pendingConfig = $state(false);
	let operation = $state<string | null>(null);
	let fresh = $state(false);
	let data = $state({ status: 'Connecting', ramUsage: 0, totalRam: 0, cpuUsage: 0,
		cpuModel: '—', cpuCores: 0, cpuThreads: 0, uptime: 0, onlinePlayers: 0, maxPlayers: 0,
		tps: 0, mspt: 0, storageUsed: 0, networkRx: null as number | null,
		networkTx: null as number | null, tpsHistory: [] as TpsDataPoint[] });

	function apply(state: any) {
		if (state.instance !== instance) { logs = []; instance = state.instance; }
		data.status = state.status;
		fresh = state.fresh;
		pendingConfig = state.pending_config;
		operation = state.operation;
		players = state.players ?? [];
		const m = state.metrics ?? {}, s = state.system ?? {};
		Object.assign(data, { ramUsage: m.ram_usage ?? 0, totalRam: m.total_ram ?? 0,
			cpuUsage: m.cpu_usage ?? 0, uptime: m.uptime ?? 0, onlinePlayers: players.length,
			maxPlayers: state.config?.max_players ?? 0, tps: m.tps ?? 0, mspt: m.mspt ?? 0,
			storageUsed: m.storage_used ?? 0, cpuModel: s.cpu_model ?? '—', cpuCores: s.cpu_cores ?? 0,
			cpuThreads: s.cpu_threads ?? 0, networkRx: m.network_rx ?? null, networkTx: m.network_tx ?? null });
	}
	function connect() {
		if (!browser || !auth.authenticated) return;
		active = true;
		if (socket) return;
		const url = new URL('/ws', window.location.href);
		url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
		const ws = new WebSocket(url);
		socket = ws;
		ws.onopen = () => { connected = true; };
		ws.onmessage = (event) => {
			try {
				const payload = JSON.parse(event.data);
				if (payload.type !== 'State') return;
				apply(payload.data);
				const batch: LogEntry[] = payload.logs ?? [];
				if (batch.length) {
					const last = logs.at(-1)?.id ?? 0;
					if (batch.at(-1)!.id < last) logs = []; // manager was restarted
					const seen = logs.at(-1)?.id ?? 0;
					logs = [...logs, ...batch.filter(line => line.id > seen)].slice(-2000);
				}
			} catch { data.status = 'Connection error'; }
		};
		ws.onclose = () => {
			if (socket !== ws) return;
			socket = null; connected = false; fresh = false;
			if (active) {
				data.status = 'Reconnecting';
				retry = setTimeout(async () => {
					try { auth.authenticated = (await api('/session')).authenticated; }
					catch { /* retry the connection after temporary network failure */ }
					if (active && auth.authenticated) connect();
				}, 2000);
			}
		};
		ws.onerror = () => ws.close();
	}
	function disconnect() {
		active = false; clearTimeout(retry);
		const current = socket; socket = null; current?.close(); connected = false; fresh = false; logs = []; players = [];
	}
	async function bootstrap() {
		try { auth.authenticated = (await api('/session')).authenticated; if (auth.authenticated) connect(); }
		finally { auth.loading = false; }
	}
	async function history(range: string) {
		const points = await api<Array<{time:number;tps:number;mspt:number}>>('/history?range=' + range);
		data.tpsHistory = points.map(point => ({ ...point, time: new Date(point.time) }));
	}
	return { get connected() { return connected; }, get data() { return data; }, get logs() { return logs; },
		get players() { return players; }, get pendingConfig() { return pendingConfig; },
		get operation() { return operation; }, get fresh() { return fresh; },
		connect, disconnect, bootstrap, history,
		sendCommand: (command: string) => api('/command', { method:'POST', body:JSON.stringify({command}) }) };
}
export const telemetry = createTelemetryStore();
