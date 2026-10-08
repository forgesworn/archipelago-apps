# shellcheck shell=bash disable=SC2034  # APP_TAG and APP_REF are for the caller
# The image tag and upstream ref each app is built and published under, derived
# from PINS. Sourced by scripts/image-plan.sh (CI) and scripts/validate.sh, so
# the version prefix lives in one place. Expects PINS already sourced.
#
# app_image <app-id>: sets APP_TAG and APP_REF, or returns 2 for an unknown app.
app_image() {
  case "$1" in
    wildbloom-node)
      APP_REF=${WILDBLOOM_NODE_REF:?}
      APP_TAG="ghcr.io/forgesworn/wildbloom-node:0.3.5-${APP_REF:0:7}-${WILDBLOOM_NODE_PKG_REV:?}" ;;
    wildbloom)
      APP_REF=${WILDBLOOM_REF:?}
      APP_TAG="ghcr.io/forgesworn/wildbloom:0.0.1-${APP_REF:0:7}-${WILDBLOOM_PKG_REV:?}" ;;
    *) echo "unknown app: $1" >&2; return 2 ;;
  esac
}
