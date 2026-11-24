// In-memory store. Replace with a real database in production; callers only
// use the functions exported here.

export type Role = 'customer' | 'admin';

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  passwordHash: string;
}

export const ORDER_STATUSES = ['pending', 'paid', 'shipped', 'cancelled', 'refunded'] as const;
export type OrderStatus = (typeof ORDER_STATUSES)[number];

export interface Shipping {
  name: string;
  line1: string;
  city: string;
  postal: string;
  country: string;
}

export interface OrderItem {
  sku: string;
  name: string;
  qty: number;
  unitCents: number;
}

export interface Order {
  id: string;
  seq: number;
  ownerId: string;
  items: OrderItem[];
  status: OrderStatus;
  shipping: Shipping;
  note: string;
  subtotalCents: number;
  discountCents: number;
  totalCents: number;
  discountCode: string | null;
  paidCents: number;
  refundedCents: number;
  createdAt: string;
}

export interface Product {
  sku: string;
  name: string;
  priceCents: number;
}

export interface DiscountCode {
  code: string;
  kind: 'percent' | 'fixed';
  /** percent: 1..100; fixed: cents */
  value: number;
  active: boolean;
  /** null = unlimited */
  maxRedemptions: number | null;
  redeemed: number;
}

const users = new Map<string, User>();
const orders = new Map<string, Order>();
const products = new Map<string, Product>();
const codes = new Map<string, DiscountCode>();
let orderSeq = 0;

/** Clears all data and reloads the built-in catalog and discount codes. */
export function resetDb(): void {
  users.clear();
  orders.clear();
  products.clear();
  codes.clear();
  orderSeq = 0;
  const catalog: Product[] = [
    { sku: 'sku-pen', name: 'Fountain Pen', priceCents: 250 },
    { sku: 'sku-book', name: 'Notebook', priceCents: 1999 },
    { sku: 'sku-lamp', name: 'Desk Lamp', priceCents: 4500 },
    { sku: 'sku-desk', name: 'Standing Desk', priceCents: 25000 },
  ];
  for (const p of catalog) products.set(p.sku, p);
  const seedCodes: DiscountCode[] = [
    { code: 'SAVE10', kind: 'percent', value: 10, active: true, maxRedemptions: null, redeemed: 0 },
    { code: 'HALF', kind: 'percent', value: 50, active: true, maxRedemptions: null, redeemed: 0 },
    { code: 'FLAT500', kind: 'fixed', value: 500, active: true, maxRedemptions: null, redeemed: 0 },
    { code: 'FLAT100K', kind: 'fixed', value: 100000, active: true, maxRedemptions: null, redeemed: 0 },
    { code: 'ONCE100', kind: 'fixed', value: 100, active: true, maxRedemptions: 1, redeemed: 0 },
    { code: 'OLD20', kind: 'percent', value: 20, active: false, maxRedemptions: null, redeemed: 0 },
  ];
  for (const c of seedCodes) codes.set(c.code, c);
}

resetDb();

export function insertUser(user: User): void {
  users.set(user.id, user);
}

export function getUser(id: string): User | undefined {
  return users.get(id);
}

export function findUserByEmail(email: string): User | undefined {
  for (const u of users.values()) {
    if (u.email === email) return u;
  }
  return undefined;
}

export function getProduct(sku: string): Product | undefined {
  return products.get(sku);
}

export function getCode(code: string): DiscountCode | undefined {
  return codes.get(code);
}

/** Assigns id, seq and createdAt, stores the order and returns it. */
export function insertOrder(draft: Omit<Order, 'id' | 'seq' | 'createdAt'>): Order {
  orderSeq += 1;
  const order: Order = {
    ...draft,
    id: `o${orderSeq}`,
    seq: orderSeq,
    createdAt: new Date().toISOString(),
  };
  orders.set(order.id, order);
  return order;
}

export function getOrder(id: string): Order | undefined {
  return orders.get(id);
}

/** All orders in creation order. */
export function allOrders(): Order[] {
  return [...orders.values()];
}
