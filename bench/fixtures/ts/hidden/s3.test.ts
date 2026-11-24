import { beforeEach, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { addUser, call, mkOrder, pay, protoClean, reset, ship } from './helpers.ts';

let alice: string, bob: string, root: string;
let ids: Record<string, string>;
beforeEach(async () => {
  reset();
  alice = addUser('alice');
  bob = addUser('bob');
  root = addUser('root', 'admin');
  // creation order: a1 pending, a2 paid, b1 paid, b2 shipped, a3 pending
  ids = {};
  ids.a1 = await mkOrder(alice, [{ sku: 'sku-pen', qty: 1 }]);
  ids.a2 = await mkOrder(alice, [{ sku: 'sku-book', qty: 1 }]);
  await pay(alice, ids.a2);
  ids.b1 = await mkOrder(bob, [{ sku: 'sku-lamp', qty: 1 }]);
  await pay(bob, ids.b1);
  ids.b2 = await mkOrder(bob, [{ sku: 'sku-desk', qty: 1 }]);
  await pay(bob, ids.b2);
  await ship(root, ids.b2);
  ids.a3 = await mkOrder(alice, [{ sku: 'sku-pen', qty: 2 }]);
});
const list = (tok: string | null, qs = '') => call(tok, 'GET', `/admin/orders${qs}`);
const idsOf = (res: any) => res.body.orders.map((o: any) => o.id);

describe('functional', () => {
  it('lists all orders newest first with the documented shape', async () => {
    const res = await list(root);
    assert.equal(res.status, 200);
    assert.equal(res.body.total, 5);
    assert.equal(res.body.limit, 20);
    assert.equal(res.body.offset, 0);
    assert.deepEqual(idsOf(res), [ids.a3, ids.b2, ids.b1, ids.a2, ids.a1]);
    const first = res.body.orders[0];
    assert.deepEqual(Object.keys(first).sort(), ['createdAt', 'id', 'ownerId', 'status', 'totalCents']);
    assert.equal(first.ownerId, 'alice');
    assert.equal(first.status, 'pending');
    assert.equal(first.totalCents, 500);
  });
  it('filters by status', async () => {
    const res = await list(root, '?status=paid');
    assert.deepEqual(idsOf(res), [ids.b1, ids.a2]);
    assert.equal(res.body.total, 2);
    assert.deepEqual(idsOf(await list(root, '?status=shipped')), [ids.b2]);
    assert.deepEqual(idsOf(await list(root, '?status=refunded')), []);
  });
  it('filters by customer', async () => {
    assert.deepEqual(idsOf(await list(root, '?customerId=bob')), [ids.b2, ids.b1]);
  });
  it('combines filters', async () => {
    assert.deepEqual(idsOf(await list(root, '?customerId=alice&status=pending')), [ids.a3, ids.a1]);
    assert.deepEqual(idsOf(await list(root, '?customerId=bob&status=pending')), []);
  });
  it('pages with limit and offset; total ignores paging', async () => {
    const res = await list(root, '?limit=2&offset=1');
    assert.deepEqual(idsOf(res), [ids.b2, ids.b1]);
    assert.equal(res.body.total, 5);
    assert.equal(res.body.limit, 2);
    assert.equal(res.body.offset, 1);
    assert.deepEqual(idsOf(await list(root, '?limit=2&offset=4')), [ids.a1]);
    assert.deepEqual(idsOf(await list(root, '?offset=50')), []);
  });
  it('unknown customer matches nothing; unknown params are ignored', async () => {
    const res = await list(root, '?customerId=nobody');
    assert.equal(res.status, 200);
    assert.equal(res.body.total, 0);
    const res2 = await list(root, '?color=red&status=paid');
    assert.equal(res2.status, 200);
    assert.equal(res2.body.total, 2);
  });
  it('error statuses', async () => {
    assert.equal((await list(null)).status, 401);
    assert.equal((await list(root, '?status=bogus')).status, 400);
    for (const qs of ['?limit=0', '?limit=101', '?limit=abc', '?limit=1.5', '?limit=', '?offset=-1', '?offset=x', '?offset=']) {
      assert.equal((await list(root, qs)).status, 400, qs);
    }
    assert.equal((await list(root, '?limit=100')).status, 200);
  });
});

describe('security', () => {
  it('customers are forbidden and see no data', async () => {
    const res = await list(alice);
    assert.equal(res.status, 403);
    assert.equal(res.body.orders, undefined);
    assert.equal((await list(bob, '?customerId=bob')).status, 403);
    assert.equal((await list(null)).body.orders, undefined);
  });
  it('status is validated against the enum, including inherited property names', async () => {
    for (const v of ['__proto__', 'constructor', 'toString', 'hasOwnProperty', 'valueOf', 'PAID', 'paid,shipped', ' paid', 'paid ', '%00', "paid'--"]) {
      const res = await list(root, `?status=${encodeURIComponent(v)}`);
      assert.equal(res.status, 400, `status=${v} -> ${res.status}`);
    }
    protoClean();
  });
  it('customerId lookups do not hit inherited properties', async () => {
    for (const v of ['__proto__', 'constructor', 'toString', 'hasOwnProperty']) {
      const res = await list(root, `?customerId=${v}`);
      assert.ok(res.status === 200 || res.status === 400, `customerId=${v} -> ${res.status}`);
      if (res.status === 200) assert.equal(res.body.total, 0);
    }
    assert.equal((await list(root, `?customerId=${'x'.repeat(65)}`)).status, 400);
    assert.equal((await list(root, '?customerId=')).status, 400);
  });
  it('prototype-pollution style query keys are harmless', async () => {
    const qs = [
      '?__proto__[polluted]=1',
      '?__proto__.polluted=1',
      '?constructor[prototype][polluted]=1',
      '?constructor.prototype.polluted=1',
      '?__proto__=x&status=paid',
      '?status=paid&__proto__[status]=pending',
      '?limit=__proto__',
    ];
    for (const q of qs) {
      const res = await list(root, q);
      assert.ok(res.status === 200 || res.status === 400, `${q} -> ${res.status}`);
      protoClean();
    }
    const res = await list(root, '?status=paid&__proto__[status]=pending&constructor[prototype][status]=pending');
    assert.equal(res.status, 200);
    assert.deepEqual(idsOf(res), [ids.b1, ids.a2]);
  });
  it('results are not widened by the filters', async () => {
    const res = await list(root, '?status=paid&customerId=alice');
    assert.deepEqual(idsOf(res), [ids.a2]);
    for (const o of res.body.orders) {
      assert.equal(o.status, 'paid');
      assert.equal(o.ownerId, 'alice');
      assert.equal(o.shipping, undefined);
      assert.equal(o.items, undefined);
    }
  });
});
