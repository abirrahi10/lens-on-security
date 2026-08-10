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
  const homeUrl = new URL('/', site).href;
  const feedUrl = new URL('/rss.xml', site).href;
  const lastBuildDate = posts.length > 0
    ? new Date(posts[0].data.date).toUTCString()
    : new Date().toUTCString();

  const items = posts.map((post) => {
    const postUrl = new URL(`/posts/${post.slug}/`, site).href;
    const categories = post.data.tags
      .map((tag) => `      <category>${escapeXml(tag)}</category>`)
      .join('\n');

    return `    <item>
      <title>${escapeXml(post.data.title)}</title>
      <link>${escapeXml(postUrl)}</link>
      <guid isPermaLink="true">${escapeXml(postUrl)}</guid>
      <description>${escapeXml(post.data.dek)}</description>
      <pubDate>${new Date(post.data.date).toUTCString()}</pubDate>
${categories}
    </item>`;
  }).join('\n');

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Lens on Security</title>
    <link>${escapeXml(homeUrl)}</link>
    <description>Security concepts, seen through photographs.</description>
    <language>en-us</language>
    <lastBuildDate>${lastBuildDate}</lastBuildDate>
    <atom:link href="${escapeXml(feedUrl)}" rel="self" type="application/rss+xml" />
${items}
  </channel>
</rss>
`;

  return new Response(body, {
    headers: { 'Content-Type': 'application/rss+xml; charset=utf-8' },
  });
}
