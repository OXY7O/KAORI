#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

strict_semver() {
  local version="${1:?version required}"
  [[ "$version" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]
}

app_version() {
  awk -F= '$1 == "APP_VERSION" {print $2; exit}' .env.production.example | tr -d '[:space:]'
}

production_image() {
  awk -F= '$1 == "KAORI_IMAGE" {print $2; exit}' .env.production.example | tr -d '[:space:]'
}

release_doc_path() {
  local version="${1:?version required}"
  printf 'docs/releases/KAORI_%s.md\n' "${version//./_}"
}

ensure_release_preflight() {
  local version="${1:?version required}"
  local sha="${2:?sha required}"
  local image="${3:?Docker Hub image required}"

  strict_semver "$version" || {
    printf 'Release version must be strict MAJOR.MINOR.PATCH: %s\n' "$version" >&2
    return 1
  }

  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || {
    printf 'Release SHA must be a full 40-character commit SHA\n' >&2
    return 1
  }

  local canonical
  canonical="$(app_version)"
  [[ "$canonical" == "$version" ]] || {
    printf 'APP_VERSION mismatch: expected %s, repository has %s\n' "$version" "$canonical" >&2
    return 1
  }

  local configured_image expected_image
  configured_image="$(production_image)"
  expected_image="${image}:v${version}"
  [[ "$configured_image" == "$expected_image" ]] || {
    printf 'KAORI_IMAGE mismatch: expected %s, repository has %s\n' "$expected_image" "$configured_image" >&2
    return 1
  }

  grep -Eq "^## \\[${version//./\\.}\\] - [0-9]{4}-[0-9]{2}-[0-9]{2}$" CHANGELOG.md || {
    printf 'CHANGELOG.md has no dated release heading for %s\n' "$version" >&2
    return 1
  }

  local release_doc
  release_doc="$(release_doc_path "$version")"
  [[ -f "$release_doc" ]] || {
    printf 'Missing release evidence: %s\n' "$release_doc" >&2
    return 1
  }

  grep -Fq "# KAORI $version Release Notes" "$release_doc" || {
    printf 'Release note title does not match version %s\n' "$version" >&2
    return 1
  }
  grep -Fq "\`v$version\`" "$release_doc" || {
    printf 'Release notes do not contain tag v%s\n' "$version" >&2
    return 1
  }

  if git show-ref --tags --verify --quiet "refs/tags/v$version"; then
    local existing
    existing="$(git rev-list -n 1 "v$version")"
    [[ "$existing" == "$sha" ]] || {
      printf 'Tag v%s already points to %s instead of %s\n' "$version" "$existing" "$sha" >&2
      return 1
    }
  fi

  python scripts/verify_release_governance.py
}

registry_digest() {
  local ref="${1:?image reference required}"
  local raw digest
  raw="$(mktemp)"
  docker buildx imagetools inspect "$ref" --raw > "$raw"
  digest="$(sha256sum "$raw" | awk '{print $1}')"
  rm -f "$raw"
  printf 'sha256:%s\n' "$digest"
}

ensure_registry_tag_identity() {
  local ref="${1:?image tag required}"
  local expected="${2:?expected digest required}"

  if ! docker buildx imagetools inspect "$ref" >/dev/null 2>&1; then
    return 0
  fi

  local actual
  actual="$(registry_digest "$ref")"
  [[ "$actual" == "$expected" ]] || {
    printf 'Refusing to move existing registry tag %s from %s to %s\n' "$ref" "$actual" "$expected" >&2
    return 1
  }
  printf 'Registry tag %s already resolves to the approved digest\n' "$ref"
}

verify_image_labels() {
  local ref="${1:?digest reference required}"
  local version="${2:?version required}"
  local sha="${3:?sha required}"

  docker pull "$ref" >/dev/null
  local actual_version actual_sha
  actual_version="$(docker image inspect "$ref" --format '{{ index .Config.Labels "org.opencontainers.image.version" }}')"
  actual_sha="$(docker image inspect "$ref" --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}')"
  [[ "$actual_version" == "$version" ]] || {
    printf 'Candidate version label mismatch: %s\n' "$actual_version" >&2
    return 1
  }
  [[ "$actual_sha" == "$sha" ]] || {
    printf 'Candidate revision label mismatch: %s\n' "$actual_sha" >&2
    return 1
  }
}

candidate_build_date() {
  local ref="${1:?digest reference required}"
  docker pull "$ref" >/dev/null
  docker image inspect "$ref" --format '{{ index .Config.Labels "org.opencontainers.image.created" }}'
}

ensure_annotated_tag() {
  local version="${1:?version required}"
  local sha="${2:?sha required}"

  : "${GITHUB_TOKEN:?GITHUB_TOKEN is required}"
  : "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"

  local api auth_header ref_response ref_status ref_type ref_sha existing
  api="https://api.github.com/repos/${GITHUB_REPOSITORY}"
  auth_header="Authorization: Bearer ${GITHUB_TOKEN}"
  ref_response="$(mktemp)"
  ref_status="$(curl --silent --show-error \
    --output "$ref_response" \
    --write-out '%{http_code}' \
    --header "$auth_header" \
    --header 'Accept: application/vnd.github+json' \
    --header 'X-GitHub-Api-Version: 2022-11-28' \
    "$api/git/ref/tags/v$version")"

  if [[ "$ref_status" == "200" ]]; then
    ref_type="$(jq -r '.object.type // empty' "$ref_response")"
    ref_sha="$(jq -r '.object.sha // empty' "$ref_response")"
    rm -f "$ref_response"

    case "$ref_type" in
      commit)
        existing="$ref_sha"
        ;;
      tag)
        existing="$(curl --fail-with-body --silent --show-error \
          --header "$auth_header" \
          --header 'Accept: application/vnd.github+json' \
          --header 'X-GitHub-Api-Version: 2022-11-28' \
          "$api/git/tags/$ref_sha" | jq -r '.object.sha // empty')"
        ;;
      *)
        printf 'Unsupported Git tag ref object type for v%s: %s\n' "$version" "$ref_type" >&2
        return 1
        ;;
    esac

    [[ "$existing" == "$sha" ]] || {
      printf 'Refusing to move v%s from %s to %s\n' "$version" "$existing" "$sha" >&2
      return 1
    }
    printf 'Release tag v%s already exists at the approved SHA\n' "$version"
    return 0
  fi

  if [[ "$ref_status" != "404" ]]; then
    cat "$ref_response" >&2
    rm -f "$ref_response"
    printf 'GitHub tag lookup failed for v%s with HTTP %s\n' "$version" "$ref_status" >&2
    return 1
  fi
  rm -f "$ref_response"

  local tag_payload tag_response tag_object_sha ref_payload
  tag_payload="$(jq -nc \
    --arg tag "v$version" \
    --arg message "KAORI $version" \
    --arg object "$sha" \
    '{tag: $tag, message: $message, object: $object, type: "commit", tagger: {name: "KAORI Release Automation", email: "actions@users.noreply.github.com"}}')"
  tag_response="$(curl --fail-with-body --silent --show-error \
    --request POST \
    --header "$auth_header" \
    --header 'Accept: application/vnd.github+json' \
    --header 'X-GitHub-Api-Version: 2022-11-28' \
    --header 'Content-Type: application/json' \
    --data "$tag_payload" \
    "$api/git/tags")"
  tag_object_sha="$(jq -r '.sha // empty' <<<"$tag_response")"
  [[ "$tag_object_sha" =~ ^[0-9a-f]{40}$ ]] || {
    printf 'GitHub did not return a valid annotated tag object SHA for v%s\n' "$version" >&2
    return 1
  }

  ref_payload="$(jq -nc \
    --arg ref "refs/tags/v$version" \
    --arg sha "$tag_object_sha" \
    '{ref: $ref, sha: $sha}')"
  curl --fail-with-body --silent --show-error \
    --request POST \
    --header "$auth_header" \
    --header 'Accept: application/vnd.github+json' \
    --header 'X-GitHub-Api-Version: 2022-11-28' \
    --header 'Content-Type: application/json' \
    --data "$ref_payload" \
    "$api/git/refs" >/dev/null

  printf 'Created release tag v%s at approved SHA %s\n' "$version" "$sha"
}

generate_release_manifest() {
  local version="${1:?version required}"
  local sha="${2:?sha required}"
  local image="${3:?image required}"
  local digest="${4:?digest required}"
  local build_date="${5:?build date required}"
  local output="${6:-kaori-release-manifest.json}"
  local short_sha="${sha:0:12}"
  local minor="${version%.*}"

  mkdir -p "$(dirname "$output")"
  jq -n \
    --arg version "$version" \
    --arg tag "v$version" \
    --arg sha "$sha" \
    --arg image "$image:v$version" \
    --arg immutable_image "$image@$digest" \
    --arg digest "$digest" \
    --arg build_date "$build_date" \
    --arg version_tag "v$version" \
    --arg minor_tag "v$minor" \
    --arg sha_tag "sha-$short_sha" \
    '{
      version: $version,
      git_tag: $tag,
      git_sha: $sha,
      image: $image,
      immutable_image: $immutable_image,
      digest: $digest,
      promoted_tags: [$version_tag, $minor_tag, $sha_tag],
      build_date: $build_date,
      sbom: true,
      provenance: true,
      signed: true
    }' > "$output"
}

publish_github_release() {
  local version="${1:?version required}"
  local manifest="${2:?manifest required}"
  local release_doc
  release_doc="$(release_doc_path "$version")"

  : "${GITHUB_TOKEN:?GITHUB_TOKEN is required}"
  : "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"

  local api="https://api.github.com/repos/${GITHUB_REPOSITORY}"
  local response
  response="$(mktemp)"
  local auth_header="Authorization: Bearer ${GITHUB_TOKEN}"

  if curl -fsS -H "$auth_header" -H 'X-GitHub-Api-Version: 2022-11-28' \
    "$api/releases/tags/v$version" > "$response" 2>/dev/null; then
    printf 'GitHub Release v%s already exists; validating asset identity\n' "$version"
  else
    jq -n \
      --arg tag "v$version" \
      --arg name "KAORI $version" \
      --rawfile body "$release_doc" \
      '{tag_name: $tag, name: $name, body: $body, draft: false, prerelease: false}' \
      | curl -fsS -X POST \
          -H "$auth_header" \
          -H 'X-GitHub-Api-Version: 2022-11-28' \
          -H 'Content-Type: application/json' \
          --data-binary @- "$api/releases" > "$response"
  fi

  local release_id existing_digest local_digest
  release_id="$(jq -r '.id' "$response")"
  existing_digest="$(jq -r '.assets[]? | select(.name == "kaori-release-manifest.json") | .digest // empty' "$response" | head -n1)"
  local_digest="sha256:$(sha256sum "$manifest" | awk '{print $1}')"

  if [[ -n "$existing_digest" ]]; then
    rm -f "$response"
    [[ "$existing_digest" == "$local_digest" ]] || {
      printf 'Existing GitHub Release manifest digest conflicts with local manifest\n' >&2
      return 1
    }
    printf 'GitHub Release manifest already matches %s\n' "$local_digest"
    return 0
  fi

  if jq -e '.assets[]? | select(.name == "kaori-release-manifest.json")' "$response" >/dev/null; then
    rm -f "$response"
    printf 'Existing release manifest asset does not expose a digest; refusing mutation\n' >&2
    return 1
  fi

  curl -fsS -X POST \
    -H "$auth_header" \
    -H 'X-GitHub-Api-Version: 2022-11-28' \
    -H 'Content-Type: application/json' \
    --data-binary @"$manifest" \
    "https://uploads.github.com/repos/${GITHUB_REPOSITORY}/releases/${release_id}/assets?name=kaori-release-manifest.json" \
    >/dev/null
  rm -f "$response"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  case "${1:-}" in
    preflight)
      shift
      ensure_release_preflight "$@"
      ;;
    digest)
      shift
      registry_digest "$@"
      ;;
    registry-tag)
      shift
      ensure_registry_tag_identity "$@"
      ;;
    verify-labels)
      shift
      verify_image_labels "$@"
      ;;
    build-date)
      shift
      candidate_build_date "$@"
      ;;
    tag)
      shift
      ensure_annotated_tag "$@"
      ;;
    manifest)
      shift
      generate_release_manifest "$@"
      ;;
    github-release)
      shift
      publish_github_release "$@"
      ;;
    *)
      printf 'Usage: %s {preflight|digest|registry-tag|verify-labels|build-date|tag|manifest|github-release} ...\n' "$0" >&2
      exit 2
      ;;
  esac
fi
