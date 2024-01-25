# actions-runner-controller Demo Setup

## Prerequisites

Before proceeding with the installation of the actions-runner-controller, you need to install the following tools:

- **Helm**: Helm is a package manager for Kubernetes, which facilitates the installation and management of applications on Kubernetes clusters.
- **kubectl**: The Kubernetes command-line tool, kubectl, allows you to run commands against Kubernetes clusters.
- **gcloud**: The gcloud command-line interface is a tool that provides the primary CLI to Google Cloud Platform. It is used to perform a host of operations on GCP resources.
- **Taskfile**: **OPTIONAL** This is a task runner/task automation tool that leverages a file called 'Taskfile.yml' to execute common development tasks.

The current configurations are stored in a private repository under the libcxx github organization.
(because none of this  needs to be public, and it seems like an easy way to leak a key).

https://github.com/libcxx/self-hosted-runners/tree/main

I sent out invites to the all attendees of the meeting so they would have access.

## Introduction

The libc++ runners are hosted on google cloud using kubernetes and githubs
Action runner controller Helm template.

For this handoff we're going to create a new cluster named `grover`.


### About the ARC Configs & Documentation
 :warning: **There is a lot of old documentation**: Be very careful to only reference documentation for the "ARC" or "actions runner controller" and its helm charts!
 if you see "summerwind" mentioned, you're in the wrong documentation.
 
The documentation for setting up ARC is very good, and almost entirely sufficient.
Please use it as your jumping off point.

All of the [relevant documentation can be found rooted here](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners-with-actions-runner-controller)


Please reference the [Quickstart Guide](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners-with-actions-runner-controller/quickstart-for-actions-runner-controller)
for instructions on deploying a manager and runner set.
 

### Setting up the cluster

The easiest way to do this is to clone an existing cluster in a new region,
but here are the settings I use for setting up a new cluster manually.

1. Create a cluster
    * Choose "Manual" and not autoscaling.
    * Configuration:
        * Name: `grover` # For this example
        * Location: `us-west1-b` # for this example
        * Node Pools:
          * `default node` pool:
            * Pool Section:
                * `Enable cluster Autoscaler`: `YES`
                * `Location policy`: `Any`
                * `Minimum Nodes`: `1`
          * `worker-pool` (Created by you):
              * Pool Section:
                * `Enable cluster autoscaler`: `YES`
                * `Location policy`: `Any`
                * `Minimum Nodes`: `0`
                * `Maximum Nodes`: `Your choice` It's 1 node per builder.
                * `Max Surge`: `0`
                * `Max Unavailable`: `1`
              * Nodes Section:
                * `Operation System`: Choose Ubuntu (I think COS has issues? Needs more testing)
                * `Machine Type`: `c2-standard-30` (is my goto, c2d and e2 are also OK)
                * `Boot Disk Size`: `25Gb`
                * `Enable Nodes on Spot VMs`: YES` (VERY VERY IMPORTART!!)
              * Metadata Section:
                * Add taint `NoSchedule` `"runner=true"`
                * [Optional] Add labels to describe the machine type, for example: "libcxx/cpu":  "30", which we can use later.
        * Cluster Section:
          * Automation Section:
            * `Autoscaling Profile`: `Optimize Utilization` (Maybe? Might cause preemption too often?)
          * Features Section:
            * Enable logging and monitoring on all components


### Setting up the cluster
    
After the cluster is created, we need to connect to it from the command line.

I will use these variables to make things simpler
```bash
export CLUSTER=grover
export ZONE=us-west1-b
```

Now connect to the cluster
```bash
gcloud container clusters get-credentials $CLUSTER --zone $ZONE --project libcxx-buildbots
```

Now we need to create the kuberenetes namespaces we will use:

```bash
kubectl create namespace $CLUSTER-runners
kubectl create namespace $CLUSTER-systems
```

Now we need to create the secrets we will use.








### Secrets

You'll need a private key file, github app id, and github app installation id
for the LLVM github runners app. The point of contact it Tom Stellard at AMD.
He is tsteller on discord, and I believe tstellar@amd.com.

The are currently two keys in use, and they can be found in the secrets
section of the kubernetes cluster. They are named `runner-github-app-secret-llvm` and ``runner-github-app-secret-llvm-2` and 
they can currently be accessed using commands like

```bash
gcloud container clusters get-credentials fozzie --zone us-east4-a --project libcxx-buildbots
kubectl get secret runner-github-app-secret-llvm --namespace fozzie-runners -o yaml

gcloud container clusters get-credentials rizzo --zone us-central1-f --project libcxx-buildbots
kubectl get secret runner-github-app-secret-llvm-2 --namespace rizzo-systems -o yaml
```
Note that the values printed here are base64 encoded and need to be decoded before reeuse.

These secrets should be accessed and stored in another location so they're
lifetime isn't tied to the cluster.

:warning: **DO NOT USE THE SAME KEY FOR TWO CLUSTERS OR INSTALLATIONS**: This will cause all of the installations to break and cause a very hard to recover from configuration  error, sometimes requiring nuking of all of the clusters using that key.


### About Failover, Rendundancy, and Machines




### On Machine times

I tested using many different machine shapes and CPU platforms. I found
that 32 or 64 threaded builders are most economical.

The 32 thread builders run a single configuration more than 4x faster than an 8 thread builder,
so fewer builders with more threads is best.

### On Preemption

The bots use preemptable machines, meaning they can be interrupted & shutdown at any time.
Depending on resourse availability, this can happen anywhere from 1 a week to 20 times a day.
When a build gets killed, it needs to be manually restarted. 

I had a script running to do this automatically, but it is no longer working.
We need to address this to prevent our nightly builds from never completing
and developers having to wait a day & multiple manual restarts before submitting code.


#### Erics Taskfile

Because I hate typing and remembering commands, I created a taskfile for myself.
It may be useful as a reference.

```yaml
version: '3'

env:
  PROJECT: libcxx-buildbots
  RUNNER_CHART: oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set
  CONTROLLER_CHART: oci://ghcr.io/actions/actions-runner-controller-charts/gha-runner-scale-set-controller


dotenv: ['./clusters/{{.CLUSTER}}/config.env', './secrets/{{.ORG}}-secrets.env']

x-deps: &deps
  - connect-cluster

tasks:
  list:
    requires:
      vars: [ 'CLUSTER' ]
    cmds:
      - helm list -n {{.CLUSTER}}-runners
      - helm list -n {{.CLUSTER}}-systems

  cloud-cmd:
    silent: true
    dir: '{{.TASKFILE_DIR}}'
    requires:
      vars: [ 'PARENT', 'LOCATION', 'CLUSTER' ]
    cmds:
        - cmd: |-
            curl -s -H "Content-Type: application/json" \
                        -H "Authorization: Bearer $(gcloud auth print-access-token)" \
                        -X GET https://container.googleapis.com/v1/projects/libcxx-buildbots/locations/{{.LOCATION}}/{{.PARENT}}?alt=json \
                        -o {{default "/dev/stdout" .OUTPUT}}

  get-pool:
    - task: cloud-cmd
      vars:
        PARENT: clusters/{{.CLUSTER}}/nodePools/{{.NAME}}

  new-create-pool:
    dir: '{{.TASKFILE_DIR}}'
    requires:
        vars: [ 'LOCATION', 'CLUSTER', 'KIND', 'CPU', 'MEMORY', 'LOCAL_SSD' ]
    vars:
      DRY_RUN: 0
    env:
        KIND: '{{.KIND}}'
        CPU: '{{.CPU}}'
        MEMORY: '{{.MEMORY}}'
        LOCAL_SSD: '{{.LOCAL_SSD}}'
        HAS_LOCAL_SSD: '{{if ne .LOCAL_SSD "0"}}true{{else}}false{{end}}'
    cmds:
        - cmd: |-
            cat ./pools/pool-template.json | envsubst > /tmp/pool.json
        - cmd: |-
            cat /tmp/pool.json
        - cmd: |-
            curl -X POST -H "Content-Type: application/json" \
            -H "Authorization: Bearer $(gcloud auth print-access-token)" \
            --data-binary @/tmp/pool.json \
            https://container.googleapis.com/v1/projects/libcxx-buildbots/zones/{{.LOCATION}}/clusters/{{.CLUSTER}}/nodePools?alt=json

  install-runner:
   - task: template-runner-cmd
     vars:
       CMD: install

  upgrade-runner:
    - task: template-runner-cmd
      vars:
        CMD: upgrade

  template-runner:
    - task: template-runner-cmd
      vars:
        CMD: template

  rest:
    requires:
      vars: [ 'INPUT' ]
    vars:
        ENDPOINT:
          sh: head -n 1 {{.INPUT}}
        DATA:
          sh: tail -n +2 {{.INPUT}}
        DATAFILE:
          sh:  mktemp --suffix .json
    cmds:
      - cmd: tail -n +2 {{.INPUT}} > {{.DATAFILE}}
      - cmd: |-
            curl -H "Content-Type: application/json" \
                        -H "Authorization: Bearer $(gcloud auth print-access-token)" \
                        --data-binary @{{.DATAFILE}} \
                        -X {{.ENDPOINT}}

  stage-runner:
    deps: *deps
    dir: '{{.TASKFILE_DIR}}'
    requires:
      vars: [ 'CLUSTER', 'SET' ]
    cmds:
      - cmd: cp ./runner-{{.SET}}.yaml ./live/{{.CLUSTER}}/runner-{{.SET}}.yaml

  template-runner-cmd:
    deps: *deps
    dir: '{{.TASKFILE_DIR}}'
    requires:
      vars: [ 'CMD', 'CLUSTER', 'SET', 'CHART_VERSION' ]
    vars:
      OSET: "{{default .SET .OSET}}"
      OVERRIDE: "{{if eq .OSET \"\"}}{{else}}-f ./clusters/{{.CLUSTER}}/runner-{{.OSET}}.yaml {{end}}"
    cmds:
      - cmd: |-
          helm {{.CMD}} libcxx-runners-{{.SET}}-set \
          --namespace {{.CLUSTER}}-runners \
          -f ./clusters/{{.CLUSTER}}/runner-values.yaml \
           -f ./clusters/{{.CLUSTER}}/runner-{{.SET}}.yaml \
           {{.OVERRIDE}} \
          --version "{{.CHART_VERSION}}" {{.RUNNER_CHART}} 

  uninstall-runner:
    deps: *deps
    dir: '{{.TASKFILE_DIR}}'
    requires:
      vars: [ 'CLUSTER', 'SET' ]
    cmds:
      - cmd: |-
          helm uninstall libcxx-runners-{{.SET}}-set \
          --namespace {{.CLUSTER}}-runners
        

  

  install-controller:
    deps: *deps
    dir: '{{.TASKFILE_DIR}}'
    requires:
      vars: [ 'CLUSTER' ]
    cmds:
      - cmd: |-
          helm install arc \
          --namespace {{.CLUSTER}}-systems \
          -f ./clusters/{{.CLUSTER}}/controller-values.yaml \
          --version "{{.CHART_VERSION}}" {{.CONTROLLER_CHART}}

  uninstall-controller:
    deps: *deps
    dir: '{{.TASKFILE_DIR}}'
    requires:
      vars: [ 'CLUSTER' ]
    cmds:
      - helm uninstall arc --namespace {{.CLUSTER }}-systems

  upgrade-controller:
    deps: *deps
    dir: '{{.TASKFILE_DIR}}'
    requires:
      vars: [ 'CLUSTER' ]
    cmds:
      - cmd: |- 
          helm upgrade arc --namespace {{.CLUSTER}}-systems \
          -f ./clusters/{{.CLUSTER}}/controller-values.yaml \
          --version "{{.CHART_VERSION}}" \
          {{.CONTROLLER_CHART}}


  create-pool:
    deps: *deps
    dir: '{{.TASKFILE_DIR}}'
    requires:
      vars: ['NAME', 'LOCATION', 'CLUSTER']
    cmds:
      - cmd: |- 
          curl -X POST -H "Content-Type: application/json" \
                    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
                    --data-binary @./pools/{{.NAME}}.json \
                    https://container.googleapis.com/v1/projects/libcxx-buildbots/zones/{{.LOCATION}}/clusters/{{.CLUSTER}}/nodePools?alt=json

  delete-pool:
    deps: *deps
    dir: '{{.TASKFILE_DIR}}'
    requires:
      vars: ['NAME', 'CLUSTER', 'LOCATION']
    cmds:
        - cmd: |- 
             gcloud container node-pools delete {{.NAME}} --cluster {{.CLUSTER}} --zone {{.LOCATION}}

  list-pools:
    dir: '{{.TASKFILE_DIR}}'
    requires:
      vars: ['LOCATION']
    cmds:
      - cmd: |- 
          gcloud container node-pools list --cluster {{.CLUSTER}} --zone {{.LOCATION}} 

  create-namespaces:
    deps: *deps
    dir: '{{.TASKFILE_DIR}}'
    requires:
      vars: [ 'CLUSTER' ]
    cmds:
      - |-
        kubectl get namespace {{.CLUSTER}}-runners || kubectl create namespace {{.CLUSTER}}-runners
      - |-
        kubectl get namespace {{.CLUSTER}}-systems || kubectl create namespace {{.CLUSTER}}-systems

  create-secrets:
    deps: *deps
    dir: '{{.TASKFILE_DIR}}'
    requires:
      vars: ['ORG', 'CLUSTER']
    dotenv: ['./secrets/{{.ORG}}-secrets.env']
    precondition:
      - cmd: |-
          test -f {{.GITHUB_APP_KEYFILE}}
          test -f ./secrets/{{.ORG}}-secrets.env
    cmds:
      - |-
        kubectl get secret/runner-github-app-secret-{{.ORG}} -n {{.CLUSTER}}-runners || kubectl create secret generic runner-github-app-secret-{{.ORG}} \
        --namespace={{.CLUSTER}}-runners \
        --from-literal=github_app_id=$GITHUB_APP_ID \
        --from-literal=github_app_installation_id=$GITHUB_INSTALLATION_ID \
        --from-file=github_app_private_key=$GITHUB_APP_KEYFILE
      - |-
        kubectl create secret generic runner-github-app-secret-{{.ORG}} \
        --namespace={{.CLUSTER}}-systems \
        --from-literal=github_app_id=$GITHUB_APP_ID \
        --from-literal=github_app_installation_id=$GITHUB_INSTALLATION_ID \
        --from-file=github_app_private_key=$GITHUB_APP_KEYFILE


  connect-cluster:
    run: when_changed
    dir: '{{.TASKFILE_DIR}}'

    precondition:
      - cmd: |-
          test -f ./clusters/{{.CLUSTER}}/config.env
    dotenv: ['./clusters/{{.CLUSTER}}/config.env']
    requires:
      vars: [ 'CLUSTER', 'LOCATION' ]
    cmds:
      - gcloud container clusters get-credentials {{.CLUSTER}} --zone {{.LOCATION}} --project libcxx-buildbots


  default:
    cmds:
      - echo "No task specified"
```

The secrets file format used by the taskfile is

```
# A github app private key & ID. Follow these instructions to create one:
# https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners-with-actions-runner-controller/authenticating-to-the-github-api#authenticating-arc-with-a-github-app
export GITHUB_APP_KEYFILE= # Path to the private key file
export GITHUB_APP_ID=
export GITHUB_INSTALLATION_ID=
```

The 

