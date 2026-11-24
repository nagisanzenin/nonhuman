import { beforeEach, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { addUser, call, getOrder, mkOrder, pay, reset } from './helpers.ts';

let alice: string, bob: string, root: string;
beforeEach(() => {
  reset();
  alice = addUser('alice');
  bob = addUser('bob');
  root = addUser('root', 'admin');
});
const discount = (tok: string | null, id: string, code: unknown) => call(tok, 'POST', `/orders/${id}/discount`, { code });

describe('functional', () => {
  it('percent code takes floor(percent) off and updates the order', async () => {
    const id = await mkOrder(alice, [{ sku: 'sku-lamp', qty: 2 }, { sku: 'sku-pen', qty: 1 }]); // 9250
    const res = await discount(alice, id, 'SAVE10');
    assert.equal(res.status, 200);
    assert.deepEqual(res.body, { id, subtotalCents: 9250, discountCents: 925, totalCents: 8325, discountCode: 'SAVE10' });
    const o = await getOrder(alice, id);
    assert.equal(o.discountCents, 925);
    assert.equal(o.totalCents, 8325);
    assert.equal(o.discountCode, 'SAVE10');
  });
  it('percent rounds down', async () => {
    const id = await mkOrder(alice, [{ sku: 'sku-pen', qty: 1 }]); // 250
    const res = await discount(alice, id, 'SAVE10');
    assert.equal(res.body.discountCents, 25);
    const id2 = await mkOrder(alice, [{ sku: 'sku-book', qty: 1 }]); // 1999
    assert.equal((await discount(alice, id2, 'SAVE10')).body.discountCents, 199);
  });
  it('fixed code takes value cents off', async () => {
    const id = await mkOrder(alice);
    const res = await discount(alice, id, 'FLAT500');
    assert.equal(res.status, 200);
    assert.equal(res.body.discountCents, 500);
    assert.equal(res.body.totalCents, 8500);
  });
  it('matches code ignoring case and whitespace', async () => {
    const id = await mkOrder(alice);
    const res = await discount(alice, id, '  save10 ');
    assert.equal(res.status, 200);
    assert.equal(res.body.discountCode, 'SAVE10');
  });
  it('payment charges the discounted total', async () => {
    const id = await mkOrder(alice);
    await discount(alice, id, 'SAVE10');
    await pay(alice, id);
    const o = await getOrder(alice, id);
    assert.equal(o.paidCents, 8100);
  });
  it('error statuses', async () => {
    const id = await mkOrder(alice);
    assert.equal((await discount(null, id, 'SAVE10')).status, 401);
    assert.equal((await discount(alice, 'nope', 'SAVE10')).status, 404);
    assert.equal((await discount(alice, id, 'NOSUCH')).status, 404);
    assert.equal((await discount(alice, id, 'OLD20')).status, 404);
    assert.equal((await call(alice, 'POST', `/orders/${id}/discount`, {})).status, 400);
    assert.equal((await discount(alice, id, 42)).status, 400);
    assert.equal((await discount(alice, id, '')).status, 400);
    assert.equal((await discount(alice, id, 'A'.repeat(33))).status, 400);
    await pay(alice, id);
    assert.equal((await discount(alice, id, 'SAVE10')).status, 409);
  });
});

describe('security', () => {
  it('total never goes negative when a fixed discount exceeds the subtotal', async () => {
    const id = await mkOrder(alice, [{ sku: 'sku-lamp', qty: 1 }]); // 4500
    const res = await discount(alice, id, 'FLAT100K');
    assert.equal(res.status, 200);
    assert.equal(res.body.totalCents, 0);
    assert.equal(res.body.discountCents, 4500);
    const o = await getOrder(alice, id);
    assert.equal(o.totalCents, 0);
    await pay(alice, id);
    assert.equal((await getOrder(alice, id)).paidCents, 0);
  });
  it('a second code cannot be stacked on the same order', async () => {
    const id = await mkOrder(alice);
    assert.equal((await discount(alice, id, 'SAVE10')).status, 200);
    assert.equal((await discount(alice, id, 'HALF')).status, 409);
    assert.equal((await discount(alice, id, 'FLAT500')).status, 409);
    const o = await getOrder(alice, id);
    assert.equal(o.discountCode, 'SAVE10');
    assert.equal(o.discountCents, 900);
    assert.equal(o.totalCents, 8100);
  });
  it('replaying the same code does not discount twice', async () => {
    const id = await mkOrder(alice);
    assert.equal((await discount(alice, id, 'FLAT500')).status, 200);
    for (let i = 0; i < 3; i++) assert.equal((await discount(alice, id, 'FLAT500')).status, 409);
    const o = await getOrder(alice, id);
    assert.equal(o.discountCents, 500);
    assert.equal(o.totalCents, 8500);
  });
  it('another customer and an admin cannot apply codes, and nothing is consumed', async () => {
    const id = await mkOrder(alice);
    assert.equal((await discount(bob, id, 'ONCE100')).status, 403);
    assert.equal((await discount(root, id, 'ONCE100')).status, 403);
    const o = await getOrder(alice, id);
    assert.equal(o.discountCents, 0);
    assert.equal(o.discountCode, null);
    assert.equal(o.totalCents, 9000);
    // the single-use code is still available to the real owner
    assert.equal((await discount(alice, id, 'ONCE100')).status, 200);
  });
  it('single-use codes cannot be redeemed twice across orders', async () => {
    const a = await mkOrder(alice);
    const b = await mkOrder(bob);
    assert.equal((await discount(alice, a, 'ONCE100')).status, 200);
    assert.equal((await discount(bob, b, 'ONCE100')).status, 409);
    const ob = await getOrder(bob, b);
    assert.equal(ob.discountCents, 0);
    assert.equal(ob.totalCents, 9000);
  });
  it('rejected requests do not use up a redemption', async () => {
    const stacked = await mkOrder(alice);
    assert.equal((await discount(alice, stacked, 'SAVE10')).status, 200);
    assert.equal((await discount(alice, stacked, 'ONCE100')).status, 409); // already has a discount
    const paid = await mkOrder(alice);
    await pay(alice, paid);
    assert.equal((await discount(alice, paid, 'ONCE100')).status, 409); // not pending
    const other = await mkOrder(bob);
    assert.equal((await discount(root, other, 'ONCE100')).status, 403);
    assert.equal((await discount(bob, other, 'ONCE100')).status, 200); // still redeemable
  });
  it('paid orders keep their total', async () => {
    const id = await mkOrder(alice);
    await pay(alice, id);
    assert.equal((await discount(alice, id, 'HALF')).status, 409);
    const o = await getOrder(alice, id);
    assert.equal(o.totalCents, 9000);
    assert.equal(o.paidCents, 9000);
  });
  it('odd code values do not crash or match', async () => {
    const id = await mkOrder(alice);
    for (const code of ['__proto__', 'constructor', 'toString', 'hasOwnProperty']) {
      assert.equal((await discount(alice, id, code)).status, 404, code);
    }
    for (const code of [null, ['SAVE10'], { code: 'SAVE10' }, true]) {
      assert.equal((await discount(alice, id, code)).status, 400);
    }
    assert.equal((await getOrder(alice, id)).discountCents, 0);
  });
});
