import { defineConfig } from 'astro/config';

const site = process.env.PUBLIC_SITE_URL ?? 'https://lensonsecurity.com';
const base = process.env.PUBLIC_BASE_PATH ?? '/';

export default defineConfig({
  output: 'static',
  site,
  base,
});
