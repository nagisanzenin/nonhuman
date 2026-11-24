// Custom node:test reporter: prints one "R <suite> <pass|fail>" line per leaf test.
export default async function* reporter(source) {
  let suite = '?';
  for await (const ev of source) {
    const d = ev.data;
    if (ev.type === 'test:start' && d.nesting === 0 && d.name) suite = d.name;
    if ((ev.type === 'test:pass' || ev.type === 'test:fail') && d.nesting >= 1 && d.details?.type !== 'suite') {
      yield `R ${suite} ${ev.type === 'test:pass' ? 'pass' : 'fail'}\n`;
    }
  }
}
