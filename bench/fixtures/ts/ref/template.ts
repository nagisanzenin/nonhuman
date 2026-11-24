// HTML helpers. Any value that did not come from this source file must go
// through escapeHtml before it is placed in markup.

const ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

/** Escapes text for use in HTML element content and quoted attribute values. */
export function escapeHtml(value: unknown): string {
  return String(value).replace(/[&<>"']/g, (ch) => ESCAPES[ch]);
}

/** Wraps already-safe body markup in a minimal document. The title is escaped. */
export function layout(title: string, bodyHtml: string): string {
  return [
    '<!doctype html>',
    '<html lang="en">',
    '<head><meta charset="utf-8"><title>' + escapeHtml(title) + '</title></head>',
    '<body>',
    bodyHtml,
    '</body>',
    '</html>',
  ].join('\n');
}
