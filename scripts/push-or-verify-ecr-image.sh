#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <ecr-image-reference>" >&2
  exit 2
fi

image_ref="$1"
repository_uri="${image_ref%:*}"
image_tag="${image_ref##*:}"
repository_name="${repository_uri#*/}"

remote_manifest=$(aws ecr batch-get-image \
  --repository-name "$repository_name" \
  --image-ids "imageTag=$image_tag" \
  --accepted-media-types \
    application/vnd.docker.distribution.manifest.v2+json \
    application/vnd.oci.image.manifest.v1+json \
  --query 'images[0].imageManifest' \
  --output text)

if [ -z "$remote_manifest" ] || [ "$remote_manifest" = "None" ]; then
  docker push "$image_ref"
  exit 0
fi

local_config_digest=$(docker image inspect "$image_ref" --format '{{.Id}}')
remote_config_digest=$(jq -r '.config.digest // empty' <<<"$remote_manifest")

if [ -z "$remote_config_digest" ] || [ "$local_config_digest" != "$remote_config_digest" ]; then
  echo "::error::Immutable ECR tag exists but does not match the rebuilt image config digest: $repository_name:$image_tag" >&2
  exit 1
fi

echo "Existing immutable ECR image matches the rebuilt image; push is not required: $repository_name:$image_tag"
