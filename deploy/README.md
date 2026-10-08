# VPS deployment

This deploys the Python web app to your VPS without a domain.
The URL is `http://<VPS_IP>:8000` (or the port configured below).

The server is provisioned with the `eplpred-deploy` SSH account and `/opt/eplpred`.
This repository's Actions secrets and variables are configured for that account,
SSH port 22, and app port 8000. The instructions below describe reproducing setup.

## Server preparation (once)

The VPS needs Linux, Docker Engine, the Docker Compose plugin (v2 with `--wait`),
SSH, Bash, gzip, and `flock`. Install Docker using the
[official instructions](https://docs.docker.com/engine/install/).
Choose an SSH user that can run Docker and owns `/opt/eplpred`:

```bash
sudo install -d -o <ssh-user> -g <ssh-user> /opt/eplpred
sudo usermod -aG docker <ssh-user>
# Log out and reconnect after changing group membership.
docker compose version
```

Allow inbound TCP to the app port in the VPS firewall and provider firewall.
Check existing listeners before choosing the port. This application uses its own
Compose project (`eplpred`) and does not modify other projects or their ports.

Create a dedicated, passwordless Ed25519 deployment key. Add the public key to
the chosen user's `~/.ssh/authorized_keys`. Verify the server's SSH host key
through an existing trusted connection before saving it as `VPS_KNOWN_HOSTS`.
Docker access grants control of the host, so keep this key limited to this repo.

## GitHub configuration

Set these repository Actions secrets (Settings → Secrets and variables → Actions):

| Secret | Value |
| --- | --- |
| `VPS_HOST` | VPS IP address or hostname |
| `VPS_USER` | SSH username with Docker access and write access to `/opt/eplpred` |
| `VPS_SSH_KEY` | Dedicated deployment private key (complete OpenSSH text) |
| `VPS_KNOWN_HOSTS` | Verified OpenSSH known-hosts entry; use `[IP]:PORT` for a nonstandard SSH port |

Optional repository Actions variables:

| Variable | Default |
| --- | --- |
| `VPS_SSH_PORT` | `22` |
| `APP_PORT` | `8000` (must be between 1024 and 65535) |

Merge the deployment pull request into `main` to install the workflow. Every push
to `main` then runs pytest, builds an image from `uv.lock`, and tests the container
with the same read-only filesystem and restricted privileges used on the VPS.
Only after these checks pass does Actions load the tested image onto the server
and run `deploy/deploy.sh`. No container registry or registry credential is needed.
The workflow can also be run manually from the Actions tab on `main`.

The server's `.env` records the last healthy image and app port. Containers restart
after a reboot. If a new image fails its health check, the deployment fails and
the script restores the previous image and port. Deployment briefly interrupts
requests while the model loads. CI does not delete old Docker images on the VPS.

## Check or roll back

```bash
cd /opt/eplpred
docker compose --project-name eplpred ps
docker compose --project-name eplpred logs --tail 100 app
curl --fail http://127.0.0.1:8000/healthz

# Roll back to a previous commit whose image is still present:
bash deploy.sh <previous-full-commit-sha> 8000
```

The container generates features during image creation. At start-up the server
answers at once (the page shows a loading screen) while it loads the data and
trains the model; `/healthz` returns 503 with the loading progress until that is
done, then 200. It therefore checks readiness, not merely whether a process exists. The container runs Waitress as a non-root
user and publishes port 8000 through Docker.

For a local preview, run `uv run python app.py --no-browser`.
