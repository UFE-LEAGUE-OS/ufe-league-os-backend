# League OS Production Object Storage Deployment

## Architecture

The production frontend Nginx container is the only browser-facing gateway.

Browser media requests use:

    /storage/<bucket>/<object-key>

Nginx strips `/storage` and proxies the request to:

    http://object-storage:8333/<bucket>/<object-key>

SeaweedFS ports are not published on the Droplet.

## Public media

Public media URLs use:

    <public-origin>/storage/league-os-public/<object-key>

The public bucket policy grants anonymous `s3:GetObject` only.

## Private media

Django signs private URLs against the internal SeaweedFS endpoint. The private
storage backend rewrites the displayed URL to the public `/storage` proxy while
preserving the original object path and signed query parameters.

Nginx forwards the request with:

    Host: object-storage:8333

This preserves the host used to generate the S3 signature.

The private bucket does not receive an anonymous-read policy.

## Production Compose

Run the production deployment from `/opt/league-os` with:

    docker compose \
      --env-file .env.prod \
      -f docker-compose.prod.yml \
      -f ufe-league-os-backend/docker-compose.storage.prod.yml \
      config

The same two Compose files must be supplied to every production `up`, `ps`,
`logs`, `restart`, and `down` command.

## Rollback

Rollback must stop only the storage-enabled application services and restore
the previous Compose and environment files. The object-storage volume must not
be deleted during rollback.

Never run:

    docker compose down --volumes
