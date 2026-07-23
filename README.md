# Lens on Security

A static Astro learning blog. Posts are currently defined in `src/data/posts.ts`; replace the SVG concept images in `public/images/` with your own web-ready photographs when ready.

## Run locally

```powershell
npm install
npm run dev
```

Then open the local address Astro prints in the terminal. Build for deployment with `npm run build`; upload the generated `dist/` folder to the Raspberry Pi.

## GitHub Pages

This project is configured to publish at `https://abirrahi10.github.io/lens-on-security/`. Commit `package-lock.json` and `.github/workflows/deploy.yml`, then in the GitHub repository go to **Settings → Pages** and choose **GitHub Actions** as the publishing source. Every push to `main` will then rebuild and deploy the site.

## Sources

In `src/data/posts.ts`, add a `sources` list only to posts that use external material. In the body text, place a simple numbered marker such as `[1]` directly after the claim or quotation it supports. The matching source entry renders as a clean numbered list below the article.

```ts
sources: [
  'https://example.com/article'
]
```
