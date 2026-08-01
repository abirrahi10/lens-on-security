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

WireGuard is the authentication boundary. Do not expose this application through a public tunnel or router port-forward.
