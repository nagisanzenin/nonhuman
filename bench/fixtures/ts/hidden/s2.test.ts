import { beforeEach, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { addUser, call, getOrder, mkOrder, pay, reset, ship } from './helpers.ts';

let alice: string, bob: string, root: string;
beforeEach(() => {
  reset();
  alice = addUser('alice');
  bob = addUser('bob');
  root = addUser('root', 'admin');
});
const refund = (tok: string | null, id: string, amountCents: unknown) => call(tok, 'POST', `/orders/${id}/refund`, { amountCents });
async function paidOrder(): Promise<string> {
  const id = await mkOrder(alice); // 9000
  await pay(alice, id);
  return id;
}

describe('functional', () => {
  it('partial refund updates balances', async () => {
    const id = await paidOrder();
    const res = await refund(alice, id, 1000);
    assert.equal(res.status, 200);
    assert.deepEqual(res.body, { id, refundedCents: 1000, refundableCents: 8000, status: 'paid' });
    assert.equal((await getOrder(alice, id)).refundedCents, 1000);
  });
  it('refunds accumulate', async () => {
    const id = await paidOrder();
    await refund(alice, id, 1000);
    const res = await refund(alice, id, 2000);
    assert.equal(res.body.refundedCents, 3000);
    assert.equal(res.body.refundableCents, 6000);
  });
  it('full refund sets status refunded and blocks further refunds', async () => {
    const id = await paidOrder();
    await refund(alice, id, 4000);
    const res = await refund(alice, id, 5000);
    assert.equal(res.status, 200);
    assert.equal(res.body.status, 'refunded');
    assert.equal(res.body.refundableCents, 0);
    assert.equal((await refund(alice, id, 1)).status, 409);
  });
  it('shipped orders can be refunded and stay shipped', async () => {
    const id = await paidOrder();
    await ship(root, id);
    const res = await refund(alice, id, 100);
    assert.equal(res.status, 200);
    assert.equal(res.body.status, 'shipped');
  });
  it('admin can refund', async () => {
    const id = await paidOrder();
    assert.equal((await refund(root, id, 500)).status, 200);
  });
  it('error statuses', async () => {
    const id = await paidOrder();
    const pending = await mkOrder(alice);
    assert.equal((await refund(null, id, 100)).status, 401);
    assert.equal((await refund(alice, 'nope', 100)).status, 404);
    assert.equal((await refund(alice, pending, 100)).status, 409);
    assert.equal((await refund(alice, id, 9001)).status, 422);
    assert.equal((await call(alice, 'POST', `/orders/${id}/refund`, {})).status, 400);
    assert.equal((await refund(alice, id, 0)).status, 400);
    assert.equal((await refund(alice, id, -5)).status, 400);
  });
});

describe('security', () => {
  it('only the owner or an admin may refund', async () => {
    const id = await paidOrder();
    assert.equal((await refund(bob, id, 100)).status, 403);
    assert.equal((await getOrder(alice, id)).refundedCents, 0);
  });
  it('cannot refund more than was paid across several refunds', async () => {
    const id = await paidOrder();
    assert.equal((await refund(alice, id, 5000)).status, 200);
    assert.equal((await refund(alice, id, 4001)).status, 422);
    assert.equal((await getOrder(alice, id)).refundedCents, 5000);
    assert.equal((await refund(alice, id, 4000)).status, 200);
    assert.equal((await refund(alice, id, 1)).status, 409);
    assert.equal((await getOrder(alice, id)).refundedCents, 9000);
  });
  it('refund is bounded by the amount paid, not the pre-discount subtotal', async () => {
    const id = await mkOrder(alice);
    assert.equal((await call(alice, 'POST', `/orders/${id}/discount`, { code: 'FLAT500' })).status, 200);
    await pay(alice, id);
    assert.equal((await refund(alice, id, 8501)).status, 422);
    assert.equal((await refund(alice, id, 8500)).status, 200);
    assert.equal((await getOrder(alice, id)).refundedCents, 8500);
  });
  it('rejects non-integer amounts', async () => {
    const id = await paidOrder();
    for (const bad of [10.5, 0.1, '100', '1e2', null, true, [100], { v: 100 }, NaN, Infinity]) {
      const res = await refund(alice, id, bad);
      assert.equal(res.status, 400, `amount ${JSON.stringify(bad)} -> ${res.status}`);
    }
    assert.equal((await getOrder(alice, id)).refundedCents, 0);
  });
  it('rejects unsafe or huge integers', async () => {
    const id = await paidOrder();
    assert.equal((await call(alice, 'POST', `/orders/${id}/refund`, JSON.parse('{"amountCents": 1e21}'))).status, 400);
    assert.equal((await call(alice, 'POST', `/orders/${id}/refund`, JSON.parse('{"amountCents": 9007199254740993}'))).status, 400);
    assert.equal((await refund(alice, id, Number.MAX_SAFE_INTEGER)).status, 422);
    assert.equal((await getOrder(alice, id)).refundedCents, 0);
  });
  it('malformed bodies are 400, not 500', async () => {
    const id = await paidOrder();
    for (const body of [null, 'x', 5, [], [{ amountCents: 1 }]]) {
      const res = await call(alice, 'POST', `/orders/${id}/refund`, body);
      assert.equal(res.status, 400);
    }
  });
  it('a pending order cannot be refunded even with a valid amount', async () => {
    const pending = await mkOrder(alice);
    assert.equal((await refund(alice, pending, 100)).status, 409);
    assert.equal((await getOrder(alice, pending)).refundedCents, 0);
  });
});
