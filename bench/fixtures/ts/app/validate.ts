// Small schema-style validators. Each validator takes (value, fieldName) and
// returns the cleaned value or throws HttpError(400).

export class HttpError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'HttpError';
    this.status = status;
  }
}

export type Validator<T> = (value: unknown, field: string) => T;

function bad(field: string, problem: string): never {
  throw new HttpError(400, `${field} ${problem}`);
}

export function str(opts: { min?: number; max: number }): Validator<string> {
  const min = opts.min ?? 1;
  return (value, field) => {
    if (typeof value !== 'string') bad(field, 'must be a string');
    if (value.length < min) bad(field, `must be at least ${min} characters`);
    if (value.length > opts.max) bad(field, `must be at most ${opts.max} characters`);
    return value;
  };
}

export function int(opts: { min: number; max: number }): Validator<number> {
  return (value, field) => {
    if (typeof value !== 'number' || !Number.isSafeInteger(value)) bad(field, 'must be an integer');
    if (value < opts.min || value > opts.max) bad(field, `must be between ${opts.min} and ${opts.max}`);
    return value;
  };
}

export function oneOf<T extends string>(allowed: readonly T[]): Validator<T> {
  return (value, field) => {
    if (typeof value !== 'string' || !allowed.includes(value as T)) {
      bad(field, `must be one of: ${allowed.join(', ')}`);
    }
    return value as T;
  };
}

export function optional<T>(inner: Validator<T>): Validator<T | undefined> {
  return (value, field) => (value === undefined ? undefined : inner(value, field));
}

export function arrayOf<T>(inner: Validator<T>, opts: { min: number; max: number }): Validator<T[]> {
  return (value, field) => {
    if (!Array.isArray(value)) bad(field, 'must be an array');
    if (value.length < opts.min || value.length > opts.max) {
      bad(field, `must contain between ${opts.min} and ${opts.max} entries`);
    }
    return value.map((entry, i) => inner(entry, `${field}[${i}]`));
  };
}

export function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

type Schema = Record<string, Validator<unknown>>;
type Parsed<S extends Schema> = { [K in keyof S]: ReturnType<S[K]> };

/**
 * Validates `input` against `schema`. Only keys named in the schema are read
 * (as own properties) and only those keys appear in the result, so unknown or
 * hostile keys such as "__proto__" are ignored. Keys whose validator returned
 * undefined are omitted.
 */
export function parseObject<S extends Schema>(input: unknown, schema: S, what = 'body'): Parsed<S> {
  if (!isPlainObject(input)) bad(what, 'must be a JSON object');
  const out: Record<string, unknown> = {};
  for (const key of Object.keys(schema)) {
    const raw = Object.hasOwn(input, key) ? input[key] : undefined;
    const value = schema[key](raw, key);
    if (value !== undefined) out[key] = value;
  }
  return out as Parsed<S>;
}

/** Shipping address fields and their limits; shared by order creation. */
export const shippingFields = {
  name: str({ min: 1, max: 80 }),
  line1: str({ min: 1, max: 120 }),
  city: str({ min: 1, max: 60 }),
  postal: str({ min: 3, max: 12 }),
  country: str({ min: 2, max: 2 }),
};
