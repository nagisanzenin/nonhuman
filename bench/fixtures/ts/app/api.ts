// Request router for ordersvc. handle() never throws: errors become
// {status, body: {error}} responses.

import { login, requireOwnerOrAdmin, requireRole, requireSession } from './auth.ts';
import { getOrder, getProduct, insertOrder } from './db.ts';
import type { Order, OrderItem } from './db.ts';
import { MoneyError, addCents, mulCents } from './money.ts';
import { HttpError, arrayOf, int, parseObject, shippingFields, str, optional } from './validate.ts';

export interface Request {
  method: string;
  /** Path including an optional query string, e.g. "/admin/orders?status=paid". */
  path: string;
  headers: Record<string, string>;
  /** Already-parsed JSON body (any shape; validate before use). */
  body?: unknown;
}

export interface Response {
  status: number;
  body: unknown;
  headers?: Record<string, string>;
}

interface Ctx {
  params: string[];
  query: Record<string, string>;
  headers: Record<string, string>;
  body: unknown;
}

type Handler = (ctx: Ctx) => Response;

const ID = '([A-Za-z0-9_-]{1,32})';
const routes: Array<{ method: string; pattern: RegExp; handler: Handler }> = [];

function route(method: string, pattern: string, handler: Handler): void {
  routes.push({ method, pattern: new RegExp(`^${pattern}$`), handler });
}

function json(status: number, body: unknown): Response {
  return { status, body };
}

/** Parses a query string into a prototype-less map; later duplicates win. */
export function parseQuery(search: string): Record<string, string> {
  const out: Record<string, string> = Object.create(null);
  for (const [k, v] of new URLSearchParams(search)) out[k] = v;
  return out;
}

/** Loads an order or throws 404. */
export function loadOrder(id: string): Order {
  const order = getOrder(id);
  if (!order) throw new HttpError(404, 'order not found');
  return order;
}

function viewOrder(order: Order): Order {
  return structuredClone(order);
}

route('POST', '/login', ({ body }) => {
  const { email, password } = parseObject(body, {
    email: str({ min: 3, max: 120 }),
    password: str({ min: 1, max: 200 }),
  });
  return json(200, { token: login(email, password) });
});

route('GET', '/me', ({ headers }) => {
  const { user } = requireSession(headers);
  return json(200, { id: user.id, name: user.name, email: user.email, role: user.role });
});

const itemSchema = (value: unknown, field: string) =>
  parseObject(value, { sku: str({ min: 1, max: 40 }), qty: int({ min: 1, max: 100 }) }, field);

route('POST', '/orders', ({ headers, body }) => {
  const session = requireSession(headers);
  const input = parseObject(body, {
    items: arrayOf(itemSchema, { min: 1, max: 20 }),
    shipping: (v, f) => parseObject(v, shippingFields, f),
    note: optional(str({ min: 0, max: 200 })),
  });
  const items: OrderItem[] = input.items.map((line) => {
    const product = getProduct(line.sku);
    if (!product) throw new HttpError(400, `unknown sku: ${line.sku.slice(0, 40)}`);
    return { sku: product.sku, name: product.name, qty: line.qty, unitCents: product.priceCents };
  });
  const subtotal = items.reduce((sum, it) => addCents(sum, mulCents(it.unitCents, it.qty)), 0);
  const order = insertOrder({
    ownerId: session.user.id,
    items,
    status: 'pending',
    shipping: input.shipping as Order['shipping'],
    note: input.note ?? '',
    subtotalCents: subtotal,
    discountCents: 0,
    totalCents: subtotal,
    discountCode: null,
    paidCents: 0,
    refundedCents: 0,
  });
  return json(201, viewOrder(order));
});

route('GET', `/orders/${ID}`, ({ headers, params }) => {
  const session = requireSession(headers);
  const order = loadOrder(params[0]);
  requireOwnerOrAdmin(session, order.ownerId);
  return json(200, viewOrder(order));
});

route('POST', `/orders/${ID}/pay`, ({ headers, params }) => {
  const session = requireSession(headers);
  const order = loadOrder(params[0]);
  requireOwnerOrAdmin(session, order.ownerId);
  if (order.status !== 'pending') throw new HttpError(409, 'order is not pending');
  order.status = 'paid';
  order.paidCents = order.totalCents;
  return json(200, viewOrder(order));
});

route('POST', `/orders/${ID}/ship`, ({ headers, params }) => {
  const session = requireSession(headers);
  requireRole(session, 'admin');
  const order = loadOrder(params[0]);
  if (order.status !== 'paid') throw new HttpError(409, 'order is not paid');
  order.status = 'shipped';
  return json(200, viewOrder(order));
});

export function handle(req: Request): Response {
  try {
    const headers: Record<string, string> = Object.create(null);
    for (const [k, v] of Object.entries(req.headers ?? {})) headers[k.toLowerCase()] = String(v);
    const qIndex = req.path.indexOf('?');
    const pathname = qIndex === -1 ? req.path : req.path.slice(0, qIndex);
    const query = parseQuery(qIndex === -1 ? '' : req.path.slice(qIndex + 1));
    let pathMatched = false;
    for (const r of routes) {
      const m = r.pattern.exec(pathname);
      if (!m) continue;
      pathMatched = true;
      if (r.method !== req.method.toUpperCase()) continue;
      return r.handler({ params: m.slice(1), query, headers, body: req.body });
    }
    return json(pathMatched ? 405 : 404, { error: pathMatched ? 'method not allowed' : 'not found' });
  } catch (err) {
    if (err instanceof HttpError) return json(err.status, { error: err.message });
    if (err instanceof MoneyError) return json(400, { error: err.message });
    return json(500, { error: 'internal error' });
  }
}
