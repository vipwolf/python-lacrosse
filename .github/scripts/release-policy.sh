set -euo pipefail

if [[ "$GITHUB_EVENT_NAME" != push || "$GITHUB_REPOSITORY" != vipwolf/python-lacrosse ]]; then
    printf '%s\n' 'Publication is restricted to pushes in vipwolf/python-lacrosse.' >&2
    exit 1
fi

if [[ "$(git rev-parse HEAD)" != "$GITHUB_SHA" ]]; then
    printf '%s\n' 'Checkout does not match the triggering commit.' >&2
    exit 1
fi

case "$GITHUB_REF_TYPE:$GITHUB_REF_NAME" in
    branch:main|branch:develop)
        [[ "$GITHUB_RUN_ID" =~ ^[1-9][0-9]*$ ]]
        [[ "$GITHUB_RUN_ATTEMPT" =~ ^[1-9][0-9]*$ ]]
        tags=$(git tag --merged HEAD --sort=-version:refname)
        version=''
        while IFS= read -r tag; do
            if [[ "$tag" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
                version="${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.$((10#${BASH_REMATCH[3]} + 1)).dev${GITHUB_RUN_ID}"
                break
            fi
        done <<< "$tags"
        if [[ -z "$version" ]]; then
            printf '%s\n' 'Branch builds require a reachable canonical X.Y.Z release tag.' >&2
            exit 1
        fi
        ;;
    tag:*)
        if [[ ! "$GITHUB_REF_NAME" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)((a|b|rc)(0|[1-9][0-9]*))?$ ]]; then
            printf '%s\n' 'Release tags must be canonical X.Y.Z versions with an optional aN, bN, or rcN suffix.' >&2
            exit 1
        fi
        [[ "$(git rev-parse --verify "refs/tags/${GITHUB_REF_NAME}^{commit}")" == "$GITHUB_SHA" ]]
        git fetch --no-tags origin +refs/heads/main:refs/remotes/origin/main
        if ! git merge-base --is-ancestor HEAD refs/remotes/origin/main; then
            printf '%s\n' 'Release commit is not in main history.' >&2
            exit 1
        fi
        version="$GITHUB_REF_NAME"
        ;;
    *)
        printf '%s\n' 'Only main, develop, and validated release tags may publish.' >&2
        exit 1
        ;;
esac

git diff --exit-code HEAD --
printf 'version=%s\n' "$version" >> "$GITHUB_OUTPUT"
