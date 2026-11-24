// Integer-cents money arithmetic. All amounts in this service are non-negative
// integer cents; every operation verifies the result is still a safe integer.

export class MoneyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'MoneyError';
  }
}

/** Returns `value` if it is a non-negative safe integer number of cents, else throws. */
export function assertCents(value: unknown, field = 'amount'): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value)) {
    throw new MoneyError(`${field} must be an integer number of cents`);
  }
  if (value < 0) {
    throw new MoneyError(`${field} must not be negative`);
  }
  return value;
}

export function addCents(a: number, b: number): number {
  assertCents(a, 'a');
  assertCents(b, 'b');
  const sum = a + b;
  if (!Number.isSafeInteger(sum)) {
    throw new MoneyError('amount overflow');
  }
  return sum;
}

/** a - b; throws if the result would be negative. */
export function subCents(a: number, b: number): number {
  assertCents(a, 'a');
  assertCents(b, 'b');
  if (b > a) {
    throw new MoneyError('amount underflow');
  }
  return a - b;
}

export function mulCents(cents: number, qty: number): number {
  assertCents(cents, 'cents');
  assertCents(qty, 'qty');
  const product = cents * qty;
  if (!Number.isSafeInteger(product)) {
    throw new MoneyError('amount overflow');
  }
  return product;
}

/** floor(cents * percent / 100) for an integer percent in 0..100. */
export function percentOfCents(cents: number, percent: number): number {
  assertCents(cents, 'cents');
  if (!Number.isInteger(percent) || percent < 0 || percent > 100) {
    throw new MoneyError('percent must be an integer between 0 and 100');
  }
  const scaled = cents * percent;
  if (!Number.isSafeInteger(scaled)) {
    throw new MoneyError('amount overflow');
  }
  return Math.floor(scaled / 100);
}

export function minCents(a: number, b: number): number {
  return Math.min(assertCents(a, 'a'), assertCents(b, 'b'));
}

/** 1999 -> "19.99" */
export function formatCents(cents: number): string {
  assertCents(cents);
  const whole = Math.floor(cents / 100);
  const frac = String(cents % 100).padStart(2, '0');
  return `${whole}.${frac}`;
}

/** 1999 -> "$19.99" */
export function formatUsd(cents: number): string {
  return `$${formatCents(cents)}`;
}
