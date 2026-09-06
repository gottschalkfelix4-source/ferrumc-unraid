<script lang="ts">
	import { api, auth, telemetry } from '$lib/stores/telemetry.svelte.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	let password = $state(''), error = $state(''), busy = $state(false);
	async function login(event: SubmitEvent) {
		event.preventDefault(); busy = true; error = '';
		try { await api('/login', {method:'POST', body:JSON.stringify({password})}); password=''; auth.authenticated=true; telemetry.connect(); }
		catch (e) { error = (e as Error).message; }
		finally { busy = false; }
	}
</script>
<svelte:head><title>Sign in | FerrumC Dashboard</title></svelte:head>
<div class="min-h-dvh flex items-center justify-center p-6 bg-background">
	<div class="w-full max-w-md glass rounded-2xl p-8 space-y-7">
		<div class="flex items-center gap-4"><img src="/icon.png" alt="" class="size-12 rounded-xl"/><div><h1 class="text-2xl font-semibold text-white">FerrumC</h1><p class="text-sm text-muted-foreground">Server dashboard</p></div></div>
		<form onsubmit={login} class="space-y-5">
			<div class="space-y-2"><label for="password" class="text-sm">Dashboard password</label><Input id="password" type="password" bind:value={password} autocomplete="current-password" required class="bg-black/20"/></div>
			{#if error}<p class="text-sm text-destructive" role="alert">{error}</p>{/if}
			<Button type="submit" disabled={busy || !password} class="w-full">{busy ? 'Signing in…' : 'Sign in'}</Button>
		</form>
		<p class="text-sm text-muted-foreground leading-relaxed">Use the dashboard password from your Unraid container settings. If no password was set, find the generated password in <code class="text-foreground">dashboard-password.txt</code> in your FerrumC appdata folder.</p>
	</div>
</div>
