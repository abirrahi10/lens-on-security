import { getCollection } from 'astro:content';

const escapeXml = (value: string) => value
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&apos;');

export async function GET({ site }: { site: URL }) {
  const posts = (await getCollection('blog', ({ data }) => !data.draft))
    .sort((a, b) => Date.parse(b.data.date) - Date.parse(a.data.date));
  const staticPaths = ['/', '/about/', '/architecture/', '/reading/', '/resume/', '/resume/view/', '/sitemap/'];

  const staticUrls = staticPaths.map((path) => `  <url>
    <loc>${escapeXml(new URL(path, site).href)}</loc>
  </url>`);
  const postUrls = posts.map((post) => `  <url>
    <loc>${escapeXml(new URL(`/posts/${post.slug}/`, site).href)}</loc>
    <lastmod>${new Date(post.data.date).toISOString().slice(0, 10)}</lastmod>
  </url>`);
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${[...staticUrls, ...postUrls].join('\n')}
</urlset>
`;

  return new Response(body, {
    headers: { 'Content-Type': 'application/xml; charset=utf-8' },
  });
}
