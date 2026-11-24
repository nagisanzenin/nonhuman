import { beforeEach, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { handle } from '../api.ts';
import { createSession, hashPassword } from '../auth.ts';
import { insertUser, resetDb } from '../db.ts';
import { MoneyError, addCents, formatUsd, mulCents, percentOfCents, subCents } from '../money.ts';
import { HttpError, int, oneOf, parseObject, str } from '../validate.ts';
import { escapeHtml } from '../template.ts';

const SHIPPING = { name: 'Ada Lovelace', line1: '1 Analytical Way', city: 'London', postal: 'N1 9GU', country: 'GB' };

function addUser(id: string, role: 'customer' | 'admin', password = 'pw-' + id): string {
  insertUser({ id, name: id.toUpperCase(), email: `${id}@example.com`, role, passwordHash: id === 'alice' ? hashPassword(password) : 'x:00' });
  return createSession(id);
}
const auth = (token: string) => ({ authorization: `Bearer ${token}` });

describe('money', () => {
  it('adds, subtracts, multiplies', () => {
    assert.equal(addCents(199, 1), 200);
    assert.equal(subCents(200, 1), 199);
    assert.equal(mulCents(250, 3), 750);
    assert.equal(percentOfCents(1999, 10), 199);
  });
  it('rejects overflow, underflow and non-integers', () => {
    assert.throws(() => addCents(Number.MAX_SAFE_INTEGER, 1), MoneyError);
    assert.throws(() => subCents(1, 2), MoneyError);
    assert.throws(() => mulCents(1.5, 2), MoneyError);
    assert.throws(() => percentOfCents(100, 101), MoneyError);
  });
  it('formats', () => {
    assert.equal(formatUsd(1999), '$19.99');
    assert.equal(formatUsd(5), '$0.05');
  });
});

describe('validate', () => {
  it('str / int / oneOf', () => {
    assert.equal(str({ max: 3 })('abc', 'f'), 'abc');
    assert.throws(() => str({ max: 3 })('abcd', 'f'), HttpError);
    assert.throws(() => int({ min: 1, max: 5 })(1.5, 'f'), HttpError);
    assert.equal(oneOf(['a', 'b'] as const)('a', 'f'), 'a');
    assert.throws(() => oneOf(['a', 'b'] as const)('toString', 'f'), HttpError);
  });
  it('parseObject ignores unknown keys', () => {
    const out = parseObject(JSON.parse('{"a":"x","__proto__":{"p":1},"zzz":2}'), { a: str({ max: 5 }) });
    assert.deepEqual(out, { a: 'x' });
    assert.equal(({} as any).p, undefined);
  });
});

describe('template', () => {
  it('escapeHtml', () => {
    assert.equal(escapeHtml(`<a href="x">'&'</a>`), '&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;');
  });
});

describe('api', () => {
  let alice: string, bob: string, admin: string;
  beforeEach(() => {
    resetDb();
    alice = addUser('alice', 'customer');
    bob = addUser('bob', 'customer');
    admin = addUser('root', 'admin');
  });

  const create = (token: string, items = [{ sku: 'sku-lamp', qty: 2 }]) =>
    handle({ method: 'POST', path: '/orders', headers: auth(token), body: { items, shipping: SHIPPING } });

  it('logs in and rejects bad credentials', () => {
    const ok = handle({ method: 'POST', path: '/login', headers: {}, body: { email: 'alice@example.com', password: 'pw-alice' } });
    assert.equal(ok.status, 200);
    const bad = handle({ method: 'POST', path: '/login', headers: {}, body: { email: 'alice@example.com', password: 'nope' } });
    assert.equal(bad.status, 401);
  });

  it('requires authentication', () => {
    assert.equal(handle({ method: 'GET', path: '/me', headers: {} }).status, 401);
    assert.equal(handle({ method: 'POST', path: '/orders', headers: {}, body: {} }).status, 401);
  });

  it('creates an order with computed totals', () => {
    const res = create(alice, [{ sku: 'sku-lamp', qty: 2 }, { sku: 'sku-pen', qty: 1 }]);
    assert.equal(res.status, 201);
    const o = res.body as any;
    assert.equal(o.subtotalCents, 9250);
    assert.equal(o.totalCents, 9250);
    assert.equal(o.status, 'pending');
    assert.equal(o.ownerId, 'alice');
  });

  it('validates order input', () => {
    assert.equal(create(alice, []).status, 400);
    assert.equal(create(alice, [{ sku: 'nope', qty: 1 }]).status, 400);
    assert.equal(create(alice, [{ sku: 'sku-pen', qty: 0 }]).status, 400);
    const longName = handle({ method: 'POST', path: '/orders', headers: auth(alice), body: { items: [{ sku: 'sku-pen', qty: 1 }], shipping: { ...SHIPPING, name: 'x'.repeat(81) } } });
    assert.equal(longName.status, 400);
  });

  it('enforces order visibility', () => {
    const id = (create(alice).body as any).id;
    assert.equal(handle({ method: 'GET', path: `/orders/${id}`, headers: auth(alice) }).status, 200);
    assert.equal(handle({ method: 'GET', path: `/orders/${id}`, headers: auth(admin) }).status, 200);
    assert.equal(handle({ method: 'GET', path: `/orders/${id}`, headers: auth(bob) }).status, 403);
    assert.equal(handle({ method: 'GET', path: '/orders/missing', headers: auth(alice) }).status, 404);
  });

  it('pays then ships (admin only)', () => {
    const id = (create(alice).body as any).id;
    const paid = handle({ method: 'POST', path: `/orders/${id}/pay`, headers: auth(alice) });
    assert.equal(paid.status, 200);
    assert.equal((paid.body as any).paidCents, 9000);
    assert.equal(handle({ method: 'POST', path: `/orders/${id}/pay`, headers: auth(alice) }).status, 409);
    assert.equal(handle({ method: 'POST', path: `/orders/${id}/ship`, headers: auth(alice) }).status, 403);
    const shipped = handle({ method: 'POST', path: `/orders/${id}/ship`, headers: auth(admin) });
    assert.equal((shipped.body as any).status, 'shipped');
  });

  it('unknown routes', () => {
    assert.equal(handle({ method: 'GET', path: '/nope', headers: {} }).status, 404);
    assert.equal(handle({ method: 'DELETE', path: '/me', headers: {} }).status, 405);
  });
});
