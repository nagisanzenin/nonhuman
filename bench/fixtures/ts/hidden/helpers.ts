// Shared helpers for hidden tests. The app under test is chosen by APP_DIR.
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';

if (!process.env.APP_DIR) throw new Error('APP_DIR is not set');
const dir = resolve(process.env.APP_DIR);
const load = (file: string): Promise<any> => import(pathToFileURL(join(dir, file)).href);

export const db = await load('db.ts');
export const auth = await load('auth.ts');
export const api = await load('api.ts');

export const SHIPPING = { name: 'Ada Lovelace', line1: '1 Analytical Way', city: 'London', postal: 'N1 9GU', country: 'GB' };

export type Tok = string | null;

export function reset(): void {
  db.resetDb();
}

/** Inserts a user and returns a session token for them. */
export function addUser(id: string, role: 'customer' | 'admin' = 'customer', name = `User ${id}`): string {
  db.insertUser({ id, name, email: `${id}@example.com`, role, passwordHash: 'x:00' });
  return auth.createSession(id);
}

export async function call(token: Tok, method: string, path: string, body?: unknown): Promise<{ status: number; body: any; headers?: Record<string, string> }> {
  const headers: Record<string, string> = token ? { authorization: `Bearer ${token}` } : {};
  return await api.handle({ method, path, headers, body });
}

/** Creates an order via the API and returns its id. */
export async function mkOrder(
  token: string,
  items: Array<{ sku: string; qty: number }> = [{ sku: 'sku-lamp', qty: 2 }],
  extra: Record<string, unknown> = {},
): Promise<string> {
  const res = await call(token, 'POST', '/orders', { items, shipping: { ...SHIPPING }, ...extra });
  assert.equal(res.status, 201, `order creation failed: ${JSON.stringify(res.body)}`);
  return res.body.id;
}

export async function pay(token: string, id: string): Promise<void> {
  const res = await call(token, 'POST', `/orders/${id}/pay`);
  assert.equal(res.status, 200, `pay failed: ${JSON.stringify(res.body)}`);
}

export async function ship(adminToken: string, id: string): Promise<void> {
  const res = await call(adminToken, 'POST', `/orders/${id}/ship`);
  assert.equal(res.status, 200, `ship failed: ${JSON.stringify(res.body)}`);
}

export async function getOrder(token: string, id: string): Promise<any> {
  const res = await call(token, 'GET', `/orders/${id}`);
  assert.equal(res.status, 200);
  return res.body;
}

export function protoClean(): void {
  assert.equal(({} as any).polluted, undefined, 'Object.prototype was polluted');
  assert.equal(Object.prototype.hasOwnProperty.call(Object.prototype, 'polluted'), false);
}
