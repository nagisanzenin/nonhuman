// Sessions and authorization helpers.

import { randomBytes, scryptSync, timingSafeEqual } from 'node:crypto';
import { findUserByEmail, getUser } from './db.ts';
import type { Role, User } from './db.ts';
import { HttpError } from './validate.ts';

const SESSION_TTL_MS = 60 * 60 * 1000;

interface SessionRecord {
  userId: string;
  expiresAt: number;
}

export interface Session {
  token: string;
  user: User;
}

const sessions = new Map<string, SessionRecord>();

export function hashPassword(password: string): string {
  const salt = randomBytes(16);
  const hash = scryptSync(password, salt, 32);
  return `${salt.toString('hex')}:${hash.toString('hex')}`;
}

function verifyPassword(password: string, stored: string): boolean {
  const [saltHex, hashHex] = stored.split(':');
  const expected = Buffer.from(hashHex, 'hex');
  const actual = scryptSync(password, Buffer.from(saltHex, 'hex'), expected.length);
  return timingSafeEqual(actual, expected);
}

export function createSession(userId: string, now = Date.now()): string {
  const token = randomBytes(24).toString('hex');
  sessions.set(token, { userId, expiresAt: now + SESSION_TTL_MS });
  return token;
}

/** Returns a new session token or throws 401 with a deliberately generic message. */
export function login(email: string, password: string): string {
  const user = findUserByEmail(email);
  if (!user || !verifyPassword(password, user.passwordHash)) {
    throw new HttpError(401, 'invalid credentials');
  }
  return createSession(user.id);
}

/** Looks up the session for an `authorization: Bearer <token>` header (lower-case keys). */
export function getSession(headers: Record<string, string>): Session | null {
  const header = headers['authorization'];
  if (typeof header !== 'string' || !header.startsWith('Bearer ')) return null;
  const token = header.slice('Bearer '.length).trim();
  const record = sessions.get(token);
  if (!record) return null;
  if (record.expiresAt <= Date.now()) {
    sessions.delete(token);
    return null;
  }
  const user = getUser(record.userId);
  return user ? { token, user } : null;
}

export function requireSession(headers: Record<string, string>): Session {
  const session = getSession(headers);
  if (!session) throw new HttpError(401, 'authentication required');
  return session;
}

/** Throws 403 unless the session user has one of the given roles. */
export function requireRole(session: Session, ...roles: Role[]): void {
  if (!roles.includes(session.user.role)) throw new HttpError(403, 'forbidden');
}

/** Throws 403 unless the session user IS the owner (admins are not exempt). */
export function requireOwner(session: Session, ownerId: string): void {
  if (session.user.id !== ownerId) throw new HttpError(403, 'forbidden');
}

/** Throws 403 unless the session user is the owner or an admin. */
export function requireOwnerOrAdmin(session: Session, ownerId: string): void {
  if (session.user.role !== 'admin' && session.user.id !== ownerId) {
    throw new HttpError(403, 'forbidden');
  }
}
