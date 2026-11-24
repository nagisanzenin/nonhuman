import { beforeEach, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { SHIPPING, addUser, call, mkOrder, pay, reset } from './helpers.ts';

let alice: string, bob: string, root: string;
beforeEach(() => {
  reset();
  alice = addUser('alice', 'customer', 'Alice Anders');
  bob = addUser('bob');
  root = addUser('root', 'admin');
});
const receipt = (tok: string | null, id: string) => call(tok, 'GET', `/orders/${id}/receipt`);

const ENTITIES: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', '#39': "'", '#x27': "'", apos: "'" };
/** Visible text of an HTML string: tags -> space, entities decoded, whitespace collapsed. */
function text(html: string): string {
  return html
    .replace(/<(script|style)[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<[^>]*>/g, ' ')
    .replace(/&(#x?[0-9a-f]+|[a-z]+);/gi, (m, e) => ENTITIES[e.toLowerCase()] ?? m)
    .replace(/\s+/g, ' ');
}

const PAYLOADS = ['<script>alert(1)</script>', '"><img src=x onerror=alert(1)>', "'><svg/onload=alert(1)>", '<b onmouseover="alert(1)">hi</b>'];
const DANGEROUS_TAG = /<\s*(script|img|svg|iframe|object|embed|a|b|i|input|form|link|style|details|video|audio|body\s+on)\b/i;

async function orderWith(overrides: { shipping?: Record<string, string>; note?: string }, userName?: string): Promise<{ id: string; tok: string }> {
  const tok = userName ? addUser('evil', 'customer', userName) : alice;
  const res = await call(tok, 'POST', '/orders', {
    items: [{ sku: 'sku-pen', qty: 1 }],
    shipping: { ...SHIPPING, ...(overrides.shipping ?? {}) },
    ...(overrides.note !== undefined ? { note: overrides.note } : {}),
  });
  assert.equal(res.status, 201);
  await pay(tok, res.body.id);
  return { id: res.body.id, tok };
}

describe('functional', () => {
  it('renders an HTML receipt with amounts', async () => {
    const id = await mkOrder(alice, [{ sku: 'sku-lamp', qty: 2 }, { sku: 'sku-pen', qty: 1 }], { note: 'Gift for Bob' }); // 9250
    assert.equal((await call(alice, 'POST', `/orders/${id}/discount`, { code: 'SAVE10' })).status, 200);
    await pay(alice, id);
    assert.equal((await call(alice, 'POST', `/orders/${id}/refund`, { amountCents: 1000 })).status, 200);
    const res = await receipt(alice, id);
    assert.equal(res.status, 200);
    assert.equal(typeof res.body, 'string');
    assert.match(String(res.headers?.['content-type']), /^text\/html\b/i);
    assert.match(res.body, /<html/i);
    const t = text(res.body);
    assert.ok(t.includes(`Receipt for order ${id}`), t);
    assert.ok(t.includes('Customer: Alice Anders'), t);
    assert.ok(t.includes('Desk Lamp 2 $45.00 $90.00'), t);
    assert.ok(t.includes('Fountain Pen 1 $2.50 $2.50'), t);
    assert.ok(t.includes('Subtotal: $92.50'), t);
    assert.ok(t.includes('Discount: -$9.25'), t);
    assert.ok(t.includes('Total: $83.25'), t);
    assert.ok(t.includes('Paid: $83.25'), t);
    assert.ok(t.includes('Refunded: $10.00'), t);
    assert.ok(t.includes('Ada Lovelace'), t);
    assert.ok(t.includes('1 Analytical Way'), t);
    assert.ok(t.includes('London'), t);
    assert.ok(t.includes('N1 9GU'), t);
    assert.ok(t.includes('GB'), t);
    assert.ok(t.includes('Note: Gift for Bob'), t);
  });
  it('omits the note line when there is no note and shows a zero discount', async () => {
    const id = await mkOrder(alice, [{ sku: 'sku-pen', qty: 1 }]);
    await pay(alice, id);
    const t = text((await receipt(alice, id)).body);
    assert.ok(!t.includes('Note:'), t);
    assert.ok(t.includes('Discount: -$0.00'), t);
  });
  it('special characters survive escaping exactly once', async () => {
    const { id, tok } = await orderWith({ shipping: { name: "Tom & Jerry's <Café>" }, note: 'Fish & "chips" > 5' });
    const t = text((await receipt(tok, id)).body);
    assert.ok(t.includes("Tom & Jerry's <Café>"), t);
    assert.ok(t.includes('Note: Fish & "chips" > 5'), t);
  });
  it('shipped and refunded orders have receipts; admin may view', async () => {
    const id = await mkOrder(alice, [{ sku: 'sku-pen', qty: 1 }]);
    await pay(alice, id);
    assert.equal((await receipt(root, id)).status, 200);
    assert.equal((await call(alice, 'POST', `/orders/${id}/refund`, { amountCents: 250 })).status, 200);
    assert.equal((await receipt(alice, id)).status, 200);
  });
  it('error statuses', async () => {
    const pending = await mkOrder(alice);
    assert.equal((await receipt(alice, pending)).status, 409);
    assert.equal((await receipt(null, pending)).status, 401);
    assert.equal((await receipt(alice, 'nope')).status, 404);
  });
});

describe('security', () => {
  it('customer-supplied fields are HTML-escaped', async () => {
    for (const payload of PAYLOADS) {
      for (const field of ['name', 'line1', 'city'] as const) {
        const { id, tok } = await orderWith({ shipping: { [field]: payload } });
        const res = await receipt(tok, id);
        assert.equal(res.status, 200);
        assert.ok(!res.body.includes(payload), `${field}: raw payload present: ${payload}`);
        assert.ok(!DANGEROUS_TAG.test(res.body), `${field}: dangerous tag for ${payload}`);
        assert.ok(!/<[^>]*\son\w+\s*=/i.test(res.body), `${field}: event handler attribute for ${payload}`);
        assert.ok(text(res.body).includes(payload), `${field}: payload should be shown as text`);
      }
    }
  });
  it('the order note is escaped', async () => {
    for (const payload of PAYLOADS) {
      const { id, tok } = await orderWith({ note: payload });
      const res = await receipt(tok, id);
      assert.ok(!res.body.includes(payload), `raw note payload: ${payload}`);
      assert.ok(!DANGEROUS_TAG.test(res.body));
      assert.ok(text(res.body).includes(`Note: ${payload}`));
    }
  });
  it('the account name is escaped', async () => {
    const { id, tok } = await orderWith({}, '<script>alert("name")</script>');
    const res = await receipt(tok, id);
    assert.ok(!res.body.includes('<script>alert'), 'raw script tag from account name');
    assert.ok(!DANGEROUS_TAG.test(res.body));
  });
  it('quotes and angle brackets become entities', async () => {
    const { id, tok } = await orderWith({ shipping: { line1: `"><img src=x onerror=alert(1)>` } });
    const body = (await receipt(tok, id)).body;
    assert.ok(body.includes('&lt;img'), 'expected &lt; for <');
    assert.ok(body.includes('&gt;'), 'expected &gt; for >');
    assert.ok(/&(quot|#34|#x22);/i.test(body), 'expected the double quote to be escaped');
  });
  it('only the owner or an admin can read a receipt', async () => {
    const id = await mkOrder(alice);
    await pay(alice, id);
    const res = await receipt(bob, id);
    assert.equal(res.status, 403);
    assert.ok(!JSON.stringify(res.body).includes('Analytical'), 'address leaked in the 403 response');
    const anon = await receipt(null, id);
    assert.equal(anon.status, 401);
    assert.ok(!JSON.stringify(anon.body).includes('Analytical'));
  });
  it('non-receipt orders do not leak data to others either', async () => {
    const pending = await mkOrder(alice);
    assert.equal((await receipt(bob, pending)).status, 403);
  });
});
