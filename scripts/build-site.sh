#!/bin/bash
# Copies the paths listed in site-files.txt into the directory given as the
# only argument, which must not exist yet. pages.yml publishes that directory
# and tests/e2e serves it, so both test and deploy the same file set.
# Plain bash 3.2 (macOS) compatible.
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: build-site.sh OUTPUT_DIR" >&2
  exit 2
fi

case "$1" in
  /*) out="$1" ;;
  *) out="$PWD/$1" ;;
esac
cd "$(dirname "$0")/.."

mkdir "$out"
while IFS= read -r line || [ -n "$line" ]; do
  path="${line%%#*}"
  path="${path#"${path%%[![:space:]]*}"}"
  path="${path%"${path##*[![:space:]]}"}"
  [ -n "$path" ] || continue
  case "$path" in
    /* | .* | */.*)
      echo "::error::site-files.txt: absolute, hidden or '..' path: $path"
      exit 1
      ;;
  esac
  path="${path%/}"
  if [ -L "$path" ] || [ ! -e "$path" ]; then
    echo "::error::site-files.txt: missing path or symlink: $path"
    exit 1
  fi
  dest="$out/$(dirname "$path")"
  mkdir -p "$dest"
  cp -R "$path" "$dest/"
done < site-files.txt
if [ -n "$(find "$out" -type l)" ]; then
  echo "::error::$out contains a symlink"
  exit 1
fi
find "$out" -type f | sort
