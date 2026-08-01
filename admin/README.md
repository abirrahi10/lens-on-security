# Lens Publisher

Lens Publisher is a VPN-only publishing application for the Lens on Security Astro site. Drafts and original working data remain on the Raspberry Pi NAS. Publishing creates validated Markdown and optimized photographs in a Git checkout, commits them, and pushes to GitHub.

## Security model

- The production service is reachable only through the home LAN and WireGuard; no router port is opened.
- Requests are accepted only from explicitly configured private subnets or loopback.
- Every write operation requires a session CSRF token.
- Session cookies are HTTP-only and SameSite Strict.
- Uploaded photographs are decoded, resized, converted to JPEG, and written without EXIF metadata.
- Git commands use fixed argument arrays and a dedicated repository deploy key.
- Drafts never leave the Pi until Publish is explicitly selected.
- The dashboard also reads published Markdown from the Pi's Git checkout. Unpublishing removes the public Markdown and images in a new Git commit, then restores the article as a private editable draft.
- Permanent deletion is available only for private drafts. Unpublish a live article first, then delete the restored draft.

WireGuard is the authentication boundary. Do not expose this application through a public tunnel or router port-forward.
