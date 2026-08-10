import { getCollection } from 'astro:content';
import { marked } from 'marked';
import sanitizeHtml from 'sanitize-html';

const escapeXml = (value: string) => value
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&apos;');

const cdata = (value: string) => value.replaceAll(']]>', ']]]]><![CDATA[>');

const sanitizeArticle = (value: string) => sanitizeHtml(value, {
  allowedTags: [
    'p', 'br', 'h2', 'h3', 'h4', 'strong', 'b', 'em', 'i', 'ul', 'ol', 'li',
    'blockquote', 'code', 'pre', 'a', 'hr', 'figure', 'figcaption', 'img', 'span', 'mark',
  ],
  allowedAttributes: {
    a: ['href', 'title', 'rel'],
    img: ['src', 'alt'],
    span: ['class'],
  },
  allowedClasses: { span: ['text-accent', 'text-muted', 'text-warm'] },
  allowedSchemes: ['http', 'https', 'mailto'],
  disallowedTagsMode: 'discard',
  transformTags: {
    a: (_tagName, attributes) => ({
      tagName: 'a',
      attribs: { ...attributes, rel: 'noopener noreferrer' },
    }),
  },
});

export async function GET({ site }: { site: URL }) {
  const posts = (await getCollection('blog', ({ data }) => !data.draft))
    .sort((a, b) => Date.parse(b.data.date) - Date.parse(a.data.date));
  const homeUrl = new URL('/', site).href;
  const feedUrl = new URL('/rss.xml', site).href;
  const lastBuildDate = posts.length > 0
    ? new Date(posts[0].data.date).toUTCString()
    : new Date().toUTCString();

  const itemList: string[] = [];
  for (const post of posts) {
    const postUrl = new URL(`/posts/${post.slug}/`, site).href;
    const primaryImage = post.data.images[0];
    const imageUrl = new URL(primaryImage.src, site).href;
    const categories = post.data.tags
      .map((tag) => `      <category>${escapeXml(tag)}</category>`)
      .join('\n');
    const sources = post.data.sources?.length
      ? `<h2>Sources</h2><ol>${post.data.sources.map((url) => `<li><a href="${escapeXml(url)}">${escapeXml(url)}</a></li>`).join('')}</ol>`
      : '';
    const renderedBody = await marked.parse(post.body, { gfm: true });
    const articleHtml = sanitizeArticle(
      `<figure><img src="${escapeXml(imageUrl)}" alt="${escapeXml(primaryImage.alt)}"></figure>${renderedBody}${sources}<p><a href="${escapeXml(postUrl)}">View the original article on Lens on Security</a></p>`,
    );

    itemList.push(`    <item>
      <title>${escapeXml(post.data.title)}</title>
      <link>${escapeXml(postUrl)}</link>
      <guid isPermaLink="true">${escapeXml(postUrl)}</guid>
      <description>${escapeXml(post.data.dek)}</description>
      <content:encoded><![CDATA[${cdata(articleHtml)}]]></content:encoded>
      <media:content url="${escapeXml(imageUrl)}" medium="image" type="image/jpeg">
        <media:description type="plain">${escapeXml(primaryImage.alt)}</media:description>
      </media:content>
      <pubDate>${new Date(post.data.date).toUTCString()}</pubDate>
${categories}
    </item>`);
  }
  const items = itemList.join('\n');

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/">
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
