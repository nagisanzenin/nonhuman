// Request router for ordersvc. handle() never throws: errors become
// {status, body: {error}} responses.

import { login, requireOwner, requireOwnerOrAdmin, requireRole, requireSession } from './auth.ts';
import { ORDER_STATUSES, allOrders, getCode, getOrder, getProduct, getUser, insertOrder } from './db.ts';
import type { Order, OrderItem } from './db.ts';
import { MoneyError, addCents, formatUsd, minCents, mulCents, percentOfCents, subCents } from './money.ts';
import { escapeHtml, layout } from './template.ts';
import { HttpError, arrayOf, int, oneOf, optional, parseObject, shippingFields, str } from './validate.ts';

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

// --- s1: discount codes -----------------------------------------------------
route('POST', `/orders/${ID}/discount`, ({ headers, params, body }) => {
  const session = requireSession(headers);
  const order = loadOrder(params[0]);
  requireOwner(session, order.ownerId);
  const { code } = parseObject(body, { code: str({ min: 1, max: 32 }) });
  if (order.status !== 'pending') throw new HttpError(409, 'order is not pending');
  if (order.discountCode !== null) throw new HttpError(409, 'a discount is already applied');
  const dc = getCode(code.trim().toUpperCase());
  if (!dc || !dc.active) throw new HttpError(404, 'discount code not found');
  if (dc.maxRedemptions !== null && dc.redeemed >= dc.maxRedemptions) {
    throw new HttpError(409, 'discount code has been fully redeemed');
  }
  const raw = dc.kind === 'percent' ? percentOfCents(order.subtotalCents, dc.value) : dc.value;
  const discount = minCents(raw, order.subtotalCents);
  order.discountCents = discount;
  order.totalCents = subCents(order.subtotalCents, discount);
  order.discountCode = dc.code;
  dc.redeemed += 1;
  return json(200, {
    id: order.id,
    subtotalCents: order.subtotalCents,
    discountCents: order.discountCents,
    totalCents: order.totalCents,
    discountCode: order.discountCode,
  });
});

// --- s2: partial refunds ----------------------------------------------------
route('POST', `/orders/${ID}/refund`, ({ headers, params, body }) => {
  const session = requireSession(headers);
  const order = loadOrder(params[0]);
  requireOwnerOrAdmin(session, order.ownerId);
  const { amountCents } = parseObject(body, { amountCents: int({ min: 1, max: Number.MAX_SAFE_INTEGER }) });
  if (order.status !== 'paid' && order.status !== 'shipped') throw new HttpError(409, 'order is not refundable');
  const refundable = subCents(order.paidCents, order.refundedCents);
  if (amountCents > refundable) throw new HttpError(422, 'amount exceeds refundable balance');
  order.refundedCents = addCents(order.refundedCents, amountCents);
  if (order.refundedCents === order.paidCents) order.status = 'refunded';
  return json(200, {
    id: order.id,
    refundedCents: order.refundedCents,
    refundableCents: subCents(order.paidCents, order.refundedCents),
    status: order.status,
  });
});

// --- s3: admin order listing ------------------------------------------------
/** Query values are strings: accept only plain decimal digits (up to 15 of them). */
function digits(value: unknown): number {
  return typeof value === 'string' && /^\d{1,15}$/.test(value) ? Number(value) : Number.NaN;
}

route('GET', '/admin/orders', ({ headers, query }) => {
  const session = requireSession(headers);
  requireRole(session, 'admin');
  const filters = parseObject(query, {
    status: optional(oneOf(ORDER_STATUSES)),
    customerId: optional(str({ min: 1, max: 64 })),
    limit: (v, f) => (v === undefined ? 20 : int({ min: 1, max: 100 })(digits(v), f)),
    offset: (v, f) => (v === undefined ? 0 : int({ min: 0, max: Number.MAX_SAFE_INTEGER })(digits(v), f)),
  }, 'query');
  const matching = allOrders()
    .filter((o) => (filters.status === undefined || o.status === filters.status))
    .filter((o) => (filters.customerId === undefined || o.ownerId === filters.customerId))
    .sort((a, b) => b.seq - a.seq);
  const page = matching.slice(filters.offset, filters.offset + filters.limit);
  return json(200, {
    total: matching.length,
    limit: filters.limit,
    offset: filters.offset,
    orders: page.map((o) => ({
      id: o.id,
      ownerId: o.ownerId,
      status: o.status,
      totalCents: o.totalCents,
      createdAt: o.createdAt,
    })),
  });
});

// --- s4: HTML receipt -------------------------------------------------------
route('GET', `/orders/${ID}/receipt`, ({ headers, params }) => {
  const session = requireSession(headers);
  const order = loadOrder(params[0]);
  requireOwnerOrAdmin(session, order.ownerId);
  if (order.status !== 'paid' && order.status !== 'shipped' && order.status !== 'refunded') {
    throw new HttpError(409, 'order has no receipt yet');
  }
  const owner = getUser(order.ownerId);
  const rows = order.items
    .map(
      (it) =>
        `<tr><td>${escapeHtml(it.name)}</td><td>${it.qty}</td><td>${formatUsd(it.unitCents)}</td>` +
        `<td>${formatUsd(mulCents(it.unitCents, it.qty))}</td></tr>`,
    )
    .join('\n');
  const s = order.shipping;
  const parts = [
    `<h1>Receipt for order ${escapeHtml(order.id)}</h1>`,
    `<p>Customer: ${escapeHtml(owner?.name ?? order.ownerId)}</p>`,
    `<table><thead><tr><th>Item</th><th>Qty</th><th>Unit</th><th>Line</th></tr></thead><tbody>`,
    rows,
    `</tbody></table>`,
    `<p>Subtotal: ${formatUsd(order.subtotalCents)}</p>`,
    `<p>Discount: -${formatUsd(order.discountCents)}</p>`,
    `<p>Total: ${formatUsd(order.totalCents)}</p>`,
    `<p>Paid: ${formatUsd(order.paidCents)}</p>`,
    `<p>Refunded: ${formatUsd(order.refundedCents)}</p>`,
    `<h2>Ship to</h2>`,
    `<p>${escapeHtml(s.name)}<br>${escapeHtml(s.line1)}<br>${escapeHtml(s.city)} ${escapeHtml(s.postal)}<br>${escapeHtml(s.country)}</p>`,
  ];
  if (order.note) parts.push(`<p>Note: ${escapeHtml(order.note)}</p>`);
  return {
    status: 200,
    body: layout(`Receipt ${order.id}`, parts.join('\n')),
    headers: { 'content-type': 'text/html; charset=utf-8' },
  };
});

// --- s5: update shipping address -------------------------------------------
route('PATCH', `/orders/${ID}/shipping`, ({ headers, params, body }) => {
  const session = requireSession(headers);
  const order = loadOrder(params[0]);
  requireOwnerOrAdmin(session, order.ownerId);
  const changes = parseObject(body, {
    name: optional(shippingFields.name),
    line1: optional(shippingFields.line1),
    city: optional(shippingFields.city),
    postal: optional(shippingFields.postal),
    country: optional(shippingFields.country),
  });
  if (Object.keys(changes).length === 0) throw new HttpError(400, 'no shipping fields supplied');
  if (order.status !== 'pending' && order.status !== 'paid') throw new HttpError(409, 'order can no longer be changed');
  order.shipping = { ...order.shipping, ...changes };
  return json(200, { id: order.id, shipping: { ...order.shipping } });
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
