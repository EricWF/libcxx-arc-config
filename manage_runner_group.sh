#!/bin/bash
set -e
GROUP_NAME=$2
ACTION=$1

function do_act() {
  METHOD=$1
  gh api \
    --method "${METHOD}" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "${@:2}"
}

if [[ $ACTION == 'create' ]]; then
    do_act POST /orgs/llvm/actions/runner-groups \
      -f name="${GROUP_NAME}" \
      -f visibility='all'  \
      -F allows_public_repositories=true
elif [[ $ACTION == 'delete' ]]; then
    rgroup=$(do_act GET /orgs/llvm/actions/runner-groups | jq -r '.runner_groups[] | select(.name == "'${GROUP_NAME}'") | .id')
    do_act DELETE /orgs/llvm/actions/runner-groups/${rgroup}
elif [[ "$ACTION" == "list" ]]; then
    do_act GET /orgs/llvm/actions/runner-groups
elif [[ "$ACTION" == "get" ]]; then

  do_act GET /orgs/llvm/actions/runner-groups | jq -r '.runner_groups[] | select(.name == "'${GROUP_NAME}'") | .id'
fi
