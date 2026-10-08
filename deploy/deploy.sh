#!/usr/bin/env bash
set -euo pipefail

# Run from /opt/eplpred after loading the image built and tested in CI.
commit=${1:?Pass the full commit SHA}
port=${2:-8000}
[[ "$commit" =~ ^[a-f0-9]{40}$ ]] || { echo 'Invalid commit SHA' >&2; exit 1; }
[[ "$port" =~ ^[0-9]+$ ]] && (( port >= 1024 && port <= 65535 )) || {
  echo 'APP_PORT must be between 1024 and 65535' >&2; exit 1;
}
cd /opt/eplpred
exec 9>deploy.lock
flock -n 9 || { echo 'Another deployment is running' >&2; exit 1; }

export APP_IMAGE="eplpred:$commit" APP_PORT="$port"
docker image inspect "$APP_IMAGE" >/dev/null
compose=(docker compose --project-name eplpred --file compose.yaml)
previous_container=$("${compose[@]}" ps --all --quiet app)
previous_image=''
previous_port="$port"
if [[ -n "$previous_container" ]]; then
  previous_image=$(docker inspect --format '{{.Config.Image}}' "$previous_container")
  previous_port=$(docker inspect --format '{{(index (index .HostConfig.PortBindings "8000/tcp") 0).HostPort}}' "$previous_container")
fi

if ! "${compose[@]}" up --detach --wait --wait-timeout 180; then
  "${compose[@]}" logs --tail 100 app >&2
  if [[ -n "$previous_image" ]]; then
    echo "Restoring previous image: $previous_image" >&2
    APP_IMAGE="$previous_image" APP_PORT="$previous_port" "${compose[@]}" up --detach --wait --wait-timeout 180
  fi
  exit 1
fi

# Record the running version only after it passes its health check.
printf 'APP_IMAGE=%s\nAPP_PORT=%s\n' "$APP_IMAGE" "$APP_PORT" > .env.next
mv .env.next .env
echo "Deployed $commit on port $port"
