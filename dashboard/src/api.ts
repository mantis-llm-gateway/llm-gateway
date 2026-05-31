import type { Config, ConfigResponse } from './types';

export async function fetchConfig(): Promise<ConfigResponse> {
  const res = await fetch('/config');
  if (!res.ok) throw new Error(`Failed to load config: ${res.status}`);
  return res.json();
}

export async function submitConfig(config: Config): Promise<ConfigResponse> {
  const res = await fetch('/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Submission failed: ${res.status}`);
  }
  return res.json();
}
