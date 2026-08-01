import { defineConfig } from 'astro/config';

const site = process.env.PUBLIC_SITE_URL ?? 'https://abirrahi10.github.io';
const base = process.env.PUBLIC_BASE_PATH ?? '/lens-on-security';

export default defineConfig({
  output: 'static',
  site,
  base,
});
