import { XMLParser } from 'fast-xml-parser';
import sanitizeHtml from 'sanitize-html';

export interface FeedSource {
  title: string;
  feedUrl: string;
  siteUrl: string;
  category: string;
  visible: boolean;
}

export interface FeedArticle {
  title: string;
  url: string;
  published: string;
  timestamp: number;
  summary: string;
  content: string;
  sourceTitle: string;
  sourceUrl: string;
  category: string;
}

export interface FeedResult {
  source: FeedSource;
  articles: FeedArticle[];
  available: boolean;
}

const parser = new XMLParser({
  ignoreAttributes: false,
  attributeNamePrefix: '@_',
  cdataPropName: '#cdata',
  removeNSPrefix: true,
  trimValues: true,
});

const asArray = <T>(value: T | T[] | undefined): T[] => {
  if (value === undefined || value === null) return [];
  return Array.isArray(value) ? value : [value];
};

function textValue(value: unknown): string {
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  if (!value || typeof value !== 'object') return '';
  const object = value as Record<string, unknown>;
  return textValue(object['#cdata'] ?? object['#text'] ?? object.content ?? '');
}

function entryLink(entry: Record<string, unknown>): string {
  if (typeof entry.link === 'string') return entry.link;
  const links = asArray(entry.link as Record<string, unknown> | Record<string, unknown>[] | undefined);
  const alternate = links.find((link) => !link['@_rel'] || link['@_rel'] === 'alternate') ?? links[0];
  return alternate ? textValue(alternate['@_href'] ?? alternate['#text'] ?? alternate) : '';
}

function readableDate(value: string): { label: string; timestamp: number } {
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return { label: '', timestamp: 0 };
  return {
    label: new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(timestamp),
    timestamp,
  };
}

function plainText(value: string): string {
  return sanitizeHtml(value, { allowedTags: [], allowedAttributes: {} })
    .replace(/\s+/g, ' ')
    .trim();
}

function safeArticleHtml(value: string): string {
  return sanitizeHtml(value, {
    allowedTags: [
      'p', 'br', 'h2', 'h3', 'h4', 'strong', 'b', 'em', 'i', 'ul', 'ol', 'li',
      'blockquote', 'code', 'pre', 'a', 'hr', 'figure', 'figcaption',
    ],
    allowedSchemes: ['http', 'https', 'mailto'],
    disallowedTagsMode: 'discard',
    transformTags: {
      a: (_tagName, attributes) => ({
        tagName: 'a',
        attribs: { ...attributes, rel: 'noopener noreferrer' },
      }),
    },
    allowedAttributes: { a: ['href', 'title', 'rel'] },
  });
}

function parsedEntries(document: Record<string, unknown>): Record<string, unknown>[] {
  const rss = document.rss as Record<string, unknown> | undefined;
  const channel = rss?.channel as Record<string, unknown> | undefined;
  if (channel) return asArray(channel.item as Record<string, unknown> | Record<string, unknown>[] | undefined);
  const feed = document.feed as Record<string, unknown> | undefined;
  return asArray(feed?.entry as Record<string, unknown> | Record<string, unknown>[] | undefined);
}

function articleFromEntry(entry: Record<string, unknown>, source: FeedSource): FeedArticle | null {
  const title = textValue(entry.title).trim();
  const url = entryLink(entry).trim();
  if (!title || !url || !/^https?:\/\//i.test(url)) return null;

  const rawContent = textValue(entry.encoded ?? entry.content ?? entry.description ?? entry.summary);
  const rawSummary = textValue(entry.summary ?? entry.description ?? rawContent);
  const sanitizedContent = safeArticleHtml(rawContent);
  const summaryText = plainText(rawSummary || sanitizedContent);
  const date = readableDate(textValue(entry.pubDate ?? entry.published ?? entry.updated ?? entry.date));

  return {
    title,
    url,
    published: date.label,
    timestamp: date.timestamp,
    summary: summaryText.length > 260 ? `${summaryText.slice(0, 257).trimEnd()}…` : summaryText,
    content: sanitizedContent || `<p>${sanitizeHtml(summaryText, { allowedTags: [] })}</p>`,
    sourceTitle: source.title,
    sourceUrl: source.siteUrl || source.feedUrl,
    category: source.category || 'Uncategorized',
  };
}

export async function fetchFeed(source: FeedSource): Promise<FeedResult> {
  try {
    const response = await fetch(source.feedUrl, {
      headers: { 'User-Agent': 'LensOnSecurityReader/1.0 (+https://lensonsecurity.com/reading/)' },
      signal: AbortSignal.timeout(10_000),
    });
    if (!response.ok) throw new Error(`Feed returned ${response.status}`);
    const document = parser.parse(await response.text()) as Record<string, unknown>;
    const articles = parsedEntries(document)
      .map((entry) => articleFromEntry(entry, source))
      .filter((article): article is FeedArticle => article !== null)
      .sort((a, b) => b.timestamp - a.timestamp)
      .slice(0, 8);
    return { source, articles, available: true };
  } catch {
    return { source, articles: [], available: false };
  }
}

export async function fetchReadingFeeds(sources: FeedSource[]): Promise<FeedResult[]> {
  return Promise.all(sources.filter((source) => source.visible).map(fetchFeed));
}
