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
- The local S3 host port remains bound to `127.0.0.1`; production exposure requires TLS and reverse-proxy configuration.
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
      -f docker-compose.yml \
      -f docker-compose.storage.yml \
      up -d

## Stop locally

    docker compose \
      --env-file .env.storage \
      -f docker-compose.yml \
      -f docker-compose.storage.yml \
      down

Do not add `--volumes` when stopping the service.


## Django storage aliases

When `USE_S3_MEDIA=True`, Django provides these storage aliases:

- `default`: public media in `league-os-public`
- `private`: signed private media in `league-os-private`
- `staticfiles`: local collected static files

Existing avatars, logos, banners, and sport-variant icons use the public
`default` storage.

Restricted future fields such as identity documents, contracts,
certificates, receipts, and compliance files must use the `private`
storage alias.

Public objects use unsigned URLs. SeaweedFS public downloads are enabled by
an explicit bucket policy granting anonymous `s3:GetObject` access only to the
public bucket. The bootstrap runs when `S3_MANAGE_BUCKET_POLICIES=True`.

Private URLs are signed and expire after the configured
`S3_PRIVATE_URL_EXPIRY` period. The private bucket receives no anonymous-read
policy.

Local filesystem development uses separate `media` and `private_media`
directories. Django only exposes the public media directory during debug
development.
## Remaining features

The following work is implemented separately:

1. Production reverse proxy and TLS.
2. Existing-media migration.
3. Off-server backup.
4. Restore verification.
