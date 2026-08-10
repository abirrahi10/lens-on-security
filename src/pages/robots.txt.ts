export function GET({ site }: { site: URL }) {
  const sitemapUrl = new URL('/sitemap.xml', site).href;
  const body = `User-agent: *
Allow: /

Sitemap: ${sitemapUrl}
`;

  return new Response(body, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
}
