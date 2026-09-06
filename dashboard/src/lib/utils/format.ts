/**
 * Formats a number of bytes into a human-readable string.
 * @param bytes - The number of bytes.
 * @param decimals - The number of decimal places (default 1).
 * @returns The formatted string (e.g., "1.5 GB").
 */
export function formatBytes(bytes: number, decimals = 1): string {
	if (bytes === 0) return '0 B';

	const k = 1024;
	const dm = decimals < 0 ? 0 : decimals;
	const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];

	const i = Math.floor(Math.log(bytes) / Math.log(k));

	return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Formats a duration in seconds into a human-readable string.
 * @param seconds - The duration in seconds.
 * @returns The formatted string (e.g., "14h 23m 12s").
 */
export function formatUptime(seconds: number): string {
	const h = Math.floor(seconds / 3600);
	const m = Math.floor((seconds % 3600) / 60);
	const s = Math.floor(seconds % 60);
	return `${h}h ${m}m ${s}s`;
}
