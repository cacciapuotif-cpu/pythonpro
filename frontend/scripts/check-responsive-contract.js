#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const frontendRoot = path.resolve(__dirname, '..');
const sourceRoot = path.join(frontendRoot, 'src');
const breakpointRegistry = path.join(sourceRoot, 'styles', '_breakpoints.scss');
const failures = [];

const walk = (directory) => fs.readdirSync(directory, { withFileTypes: true })
  .flatMap((entry) => {
    const absolutePath = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(absolutePath) : [absolutePath];
  });

const registry = fs.readFileSync(breakpointRegistry, 'utf8');
for (const expected of ['$phone-max: 30rem', '$mobile-max: 48rem', '$tablet-max: 64rem']) {
  if (!registry.includes(expected)) {
    failures.push(`Registro breakpoint incompleto: manca "${expected}"`);
  }
}

for (const file of walk(sourceRoot).filter((candidate) => /\.(css|scss)$/.test(candidate))) {
  if (file === breakpointRegistry) continue;
  const contents = fs.readFileSync(file, 'utf8');
  if (/@media[^{]*(?:min|max)-width\s*:/.test(contents)) {
    failures.push(`${path.relative(frontendRoot, file)} contiene un breakpoint locale`);
  }
}

const indexHtml = fs.readFileSync(path.join(frontendRoot, 'public', 'index.html'), 'utf8');
const viewport = indexHtml.match(/<meta\s+name="viewport"\s+content="([^"]+)"/)?.[1] || '';
for (const requiredValue of ['width=device-width', 'initial-scale=1', 'viewport-fit=cover']) {
  if (!viewport.split(',').map((value) => value.trim()).includes(requiredValue)) {
    failures.push(`Meta viewport: manca "${requiredValue}"`);
  }
}

const globalStyles = fs.readFileSync(path.join(sourceRoot, 'index.scss'), 'utf8');
for (const requiredValue of [
  'box-sizing: border-box',
  'font-size: 16px',
  'env(safe-area-inset-top, 0px)',
  'env(safe-area-inset-bottom, 0px)',
  '@include bp.mobile',
]) {
  if (!globalStyles.includes(requiredValue)) {
    failures.push(`Fondamenta globali: manca "${requiredValue}"`);
  }
}

if (failures.length > 0) {
  console.error('Contratto responsive NON rispettato:');
  failures.forEach((failure) => console.error(`- ${failure}`));
  process.exit(1);
}

console.log('Contratto responsive rispettato: viewport, breakpoint, safe area e tipografia.');
