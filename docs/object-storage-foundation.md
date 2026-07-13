# League OS Object Storage Foundation

## Purpose

League OS uses an S3-compatible object-storage service for application media.

The initial deployment uses SeaweedFS in single-node mode. This provides a
small S3-compatible foundation suitable for the current League OS Droplet
while retaining an upgrade path to additional volume servers later.

## Buckets

The storage foundation uses two buckets:

- `league-os-public`
- `league-os-private`

Django integration is intentionally handled in a separate feature so that
the storage service can first be tested independently.

## Local endpoints

From the host machine:

    http://127.0.0.1:8333

From containers on the Compose network:

    http://object-storage:8333

Django and boto3 must use path-style S3 addressing.

## Security boundaries

- Credentials are loaded from `.env.storage`.
- `.env.storage` must never be committed.
- The S3 host port binds only to `127.0.0.1`.
- SeaweedFS administration ports are not published.
- Production credentials must be generated separately.
- Public browser access is not enabled by this feature.
- Off-server backup is required before production media is enabled.

## Persistent data

The Compose file declares this persistent Docker volume:

    league_os_object_storage_data

Docker Compose adds the project prefix to the actual volume name.

Removing the storage container does not remove stored objects. Do not run
`docker compose down --volumes` unless the storage data is intentionally
being destroyed and a verified backup exists.

## Start locally

    docker compose \
      --env-file .env.storage \
      -f docker-compose.storage.yml \
      up -d

## Stop locally

    docker compose \
      --env-file .env.storage \
      -f docker-compose.storage.yml \
      down

Do not add `--volumes` when stopping the service.

## Future features

The following work is implemented separately:

1. Public Django media storage.
2. Private Django media storage and signed URLs.
3. Production reverse proxy and TLS.
4. Existing-media migration.
5. Off-server backup.
6. Restore verification.
