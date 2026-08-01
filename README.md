# Lens on Security

A static Astro learning blog. Each published article is a Markdown file in `src/content/blog/`. Set `draft: true` in a post's frontmatter to keep it out of production builds.

## Run locally

```powershell
npm install
npm run dev
```

Then open the local address Astro prints in the terminal. Build for deployment with `npm run build`.

The production build defaults to `https://lensonsecurity.com/`. `PUBLIC_SITE_URL` and `PUBLIC_BASE_PATH` can override that configuration when testing another deployment target. Raspberry Pi deployment assets and rollback instructions are in `deploy/pi/`.

## GitHub Pages

This project publishes to `https://lensonsecurity.com/` through GitHub Pages. In the GitHub repository, choose **Settings > Pages > GitHub Actions** as the publishing source and set the custom domain to `lensonsecurity.com`. Every push to `main` will rebuild and deploy the site.

## Sources

In a post's Markdown frontmatter, add a `sources` list only when the article uses external material. In the body text, place a simple numbered marker such as `[1]` directly after the claim or quotation it supports. The matching source entry renders as a numbered list below the article.

```yaml
sources:
  - https://example.com/article
```
