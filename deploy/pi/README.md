# Raspberry Pi deployment

This deployment keeps the website away from ports used by Pi-hole. The included system service listens only on `127.0.0.1:8088`, and Cloudflare Tunnel connects to it locally. No router port-forward is required.

## Before installing

Record the Pi username, OS version and architecture, free SSD space, active listeners, and service health. Confirm that Pi-hole DNS, WireGuard, and NAS access work before and after each phase.

## Layout

- Repository: `~/apps/lens-on-security`
- Versioned builds: `/mnt/nas/websites/lens-on-security/releases`
- Live symlink: `/mnt/nas/websites/lens-on-security/current`
- Local website: `http://127.0.0.1:8088`

## Publishing

Set `SITE_URL` to the final HTTPS domain and run `deploy.sh`. It fast-forwards from `origin/main`, installs the locked dependencies, builds the site at the domain root, switches the live symlink atomically, and retains five releases.

Use `rollback.sh` to switch back to the prior retained release.

## Updating the private publisher

After new publisher code reaches `main`, update the Pi checkout and run the guarded updater:

```bash
git -C /mnt/nas/websites/lens-on-security/repository pull --ff-only origin main
bash /mnt/nas/websites/lens-on-security/repository/deploy/pi/update-publisher.sh
```

The updater copies only the private application code, refreshes its existing virtual environment, and restarts `lens-publisher.service`. Drafts and published content are not removed.

## Website service

`lens-on-security.service` uses Python's static file server behind Cloudflare Tunnel. It runs without root privileges, can only read the published files, starts after the NAS mount is available, and restarts automatically after a failure or reboot.

## Cloudflare Tunnel

The remotely managed tunnel flow is preferred. Point the public hostname to `http://127.0.0.1:8088`. The example configuration is included only for a locally managed tunnel.
