import { beforeEach, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { SHIPPING, addUser, call, getOrder, mkOrder, pay, protoClean, reset, ship } from './helpers.ts';

let alice: string, bob: string, root: string;
beforeEach(() => {
  reset();
  alice = addUser('alice');
  bob = addUser('bob');
  root = addUser('root', 'admin');
});
const patch = (tok: string | null, id: string, body: unknown) => call(tok, 'PATCH', `/orders/${id}/shipping`, body);
const shippingOf = async (id: string) => (await getOrder(alice, id)).shipping;

describe('functional', () => {
  it('updates only the supplied fields', async () => {
    const id = await mkOrder(alice);
    const res = await patch(alice, id, { line1: '9 New Street', city: 'Leeds' });
    assert.equal(res.status, 200);
    assert.equal(res.body.id, id);
    assert.deepEqual(res.body.shipping, { ...SHIPPING, line1: '9 New Street', city: 'Leeds' });
    assert.deepEqual(await shippingOf(id), { ...SHIPPING, line1: '9 New Street', city: 'Leeds' });
  });
  it('updates every field at once', async () => {
    const id = await mkOrder(alice);
    const next = { name: 'Grace Hopper', line1: '2 Compiler Rd', city: 'Arlington', postal: '22201', country: 'US' };
    const res = await patch(alice, id, next);
    assert.equal(res.status, 200);
    assert.deepEqual(res.body.shipping, next);
  });
  it('works on paid orders and for admins', async () => {
    const id = await mkOrder(alice);
    await pay(alice, id);
    assert.equal((await patch(alice, id, { city: 'Bath' })).status, 200);
    assert.equal((await patch(root, id, { city: 'York' })).status, 200);
    assert.equal((await shippingOf(id)).city, 'York');
  });
  it('error statuses', async () => {
    const id = await mkOrder(alice);
    assert.equal((await patch(null, id, { city: 'X1' })).status, 401);
    assert.equal((await patch(alice, 'nope', { city: 'Bath' })).status, 404);
    assert.equal((await patch(alice, id, {})).status, 400);
    assert.equal((await patch(alice, id, { colour: 'red' })).status, 400);
    assert.equal((await patch(alice, id, { city: 123 })).status, 400);
    assert.equal((await patch(alice, id, { city: '' })).status, 400);
    assert.equal((await patch(alice, id, null)).status, 400);
    assert.equal((await patch(alice, id, [{ city: 'Bath' }])).status, 400);
  });
  it('shipped and refunded orders are locked', async () => {
    const shipped = await mkOrder(alice);
    await pay(alice, shipped);
    await ship(root, shipped);
    assert.equal((await patch(alice, shipped, { city: 'Bath' })).status, 409);
    const refunded = await mkOrder(alice, [{ sku: 'sku-pen', qty: 1 }]);
    await pay(alice, refunded);
    await call(alice, 'POST', `/orders/${refunded}/refund`, { amountCents: 250 });
    assert.equal((await patch(alice, refunded, { city: 'Bath' })).status, 409);
  });
});

describe('security', () => {
  it('other customers cannot edit an order', async () => {
    const id = await mkOrder(alice);
    const res = await patch(bob, id, { line1: 'Evil Lane 1' });
    assert.equal(res.status, 403);
    assert.deepEqual(await shippingOf(id), SHIPPING);
  });
  it('shipped orders are not changed', async () => {
    const id = await mkOrder(alice);
    await pay(alice, id);
    await ship(root, id);
    assert.equal((await patch(alice, id, { line1: 'Elsewhere 5' })).status, 409);
    assert.equal((await patch(root, id, { line1: 'Elsewhere 5' })).status, 409);
    assert.deepEqual(await shippingOf(id), SHIPPING);
  });
  it('field length limits match order creation', async () => {
    const id = await mkOrder(alice);
    const tooLong: Record<string, string> = { name: 'n'.repeat(81), line1: 'l'.repeat(121), city: 'c'.repeat(61), postal: 'p'.repeat(13), country: 'GBR' };
    for (const [k, v] of Object.entries(tooLong)) {
      assert.equal((await patch(alice, id, { [k]: v })).status, 400, `${k} too long`);
    }
    assert.equal((await patch(alice, id, { postal: 'ab' })).status, 400);
    assert.equal((await patch(alice, id, { country: 'G' })).status, 400);
    assert.deepEqual(await shippingOf(id), SHIPPING);
    const maxed = { name: 'n'.repeat(80), line1: 'l'.repeat(120), city: 'c'.repeat(60), postal: 'p'.repeat(12), country: 'FR' };
    assert.equal((await patch(alice, id, maxed)).status, 200);
  });
  it('non-string values are rejected', async () => {
    const id = await mkOrder(alice);
    for (const v of [123, true, null, ['Bath'], { $ne: 1 }, { toString: 'x' }]) {
      const res = await patch(alice, id, { city: v });
      assert.equal(res.status, 400, JSON.stringify(v));
    }
    assert.deepEqual(await shippingOf(id), SHIPPING);
  });
  it('an invalid field means nothing is applied', async () => {
    const id = await mkOrder(alice);
    const res = await patch(alice, id, { name: 'Changed Name', city: 'Paris', line1: 'x'.repeat(121) });
    assert.equal(res.status, 400);
    assert.deepEqual(await shippingOf(id), SHIPPING);
  });
  it('extra keys cannot change other parts of the order', async () => {
    const id = await mkOrder(alice);
    const before = await getOrder(alice, id);
    const res = await patch(alice, id, { city: 'Paris', ownerId: 'bob', status: 'shipped', totalCents: 1, paidCents: 9000, refundedCents: 0, items: [], id: 'o999', note: 'pwned' });
    assert.equal(res.status, 200);
    const after = await getOrder(alice, id);
    assert.deepEqual({ ...after, shipping: undefined }, { ...before, shipping: undefined });
    assert.deepEqual(Object.keys(after.shipping).sort(), Object.keys(SHIPPING).sort());
    assert.equal(after.shipping.city, 'Paris');
    assert.deepEqual(Object.keys(res.body.shipping).sort(), Object.keys(SHIPPING).sort());
  });
  it('prototype-pollution payloads are harmless', async () => {
    const id = await mkOrder(alice);
    const payloads = [
      '{"__proto__":{"polluted":1},"city":"Paris"}',
      '{"constructor":{"prototype":{"polluted":2}},"city":"Paris"}',
      '{"city":"Paris","__proto__":{"city":"Hacked","polluted":3}}',
      '{"shipping":{"__proto__":{"polluted":4}},"city":"Paris"}',
    ];
    for (const raw of payloads) {
      const res = await patch(alice, id, JSON.parse(raw));
      assert.ok(res.status === 200 || res.status === 400, `${raw} -> ${res.status}`);
      protoClean();
      const o = await getOrder(alice, id);
      assert.deepEqual(Object.keys(o.shipping).sort(), Object.keys(SHIPPING).sort());
      assert.equal(o.ownerId, 'alice');
      assert.equal(o.shipping.polluted, undefined);
    }
    const fresh = await mkOrder(bob);
    assert.deepEqual((await getOrder(bob, fresh)).shipping, SHIPPING);
  });
});
