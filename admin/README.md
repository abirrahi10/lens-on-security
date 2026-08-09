# Lens Publisher

Lens Publisher is a VPN-only publishing application for the Lens on Security Astro site. Drafts and original working data remain on the Raspberry Pi NAS. Publishing creates validated Markdown and optimized photographs in a Git checkout, commits them, and pushes to GitHub.

The dashboard also includes an About-page editor. It manages the public profile text, certifications, labeled profile links, the “Why this exists” section, résumé card title, headshot, and résumé PDF. New headshots can be dragged and zoomed into the same 4:5 frame used by the public site before publishing.

Article drafts use a rich Markdown editor with formatting controls for headings, emphasis, quotations, lists, links, code, dividers, highlights, and a small set of accessible site colors. The editor offers Write, Split, and Preview modes while preserving portable Markdown in Git.

## Security model

- The production service is reachable only through the home LAN and WireGuard; no router port is opened.
- Requests are accepted only from explicitly configured private subnets or loopback.
- Every write operation requires a session CSRF token.
- Session cookies are HTTP-only and SameSite Strict.
- Uploaded photographs are decoded, resized, converted to JPEG, and written without EXIF metadata.
- About-page headshots use the same protected image pipeline and are cropped to a consistent 4:5 frame.
- Résumé replacements are size-limited and validated as PDF files before they enter the publishing repository.
- Git commands use fixed argument arrays and a dedicated repository deploy key.
- Drafts never leave the Pi until Publish is explicitly selected.
- The dashboard also reads published Markdown from the Pi's Git checkout. Unpublishing removes the public Markdown and images in a new Git commit, then restores the article as a private editable draft.
- Permanent deletion is available only for private drafts. Unpublish a live article first, then delete the restored draft.

WireGuard is the authentication boundary. Do not expose this application through a public tunnel or router port-forward.
