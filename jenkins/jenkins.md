# Use Case: Perform system package updates on OpenStack@Louros

Toolset:

- `Jenkins`: Configure and manage jobs, automation, GUI
- `Patchman`: Daily reports by machines for their apt packages status
- `amaltheia`: Configurable job that automates the process of retrieving
  the list of hosts that have pending system package updates (using Patchman)
  and performing them.


## Requirements

- Jenkins (no extensions required)
- Jenkins worker with network access to all machines that need to be updated
- SSH identity for connecting to all machines.
- Docker


## Steps

-   Clone the repository

    ```bash
    $ git clone git@github.com:grnet/amaltheia
    $ cd amaltheia
    ```

-   Copy your SSH key to this folder

    ```bash
    $ cp YOUR_SSH_PRIVATE_KEY ./ssh_id_rsa
    ```

-   Edit the `jenkins/job.sample.yaml` file and set the URL of the Patchman
    server. Then:

    ```bash
    $ cp jenkins/job.sample.yaml job.yaml
    ```

-   Build the Docker image for amaltheia

    ```bash
    $ docker build -t amaltheia-jenkins-image --build-arg jobs=job.yaml
    ```

-   Create a new jenkins pipeline, using `jenkins/Jenkinsfile`. Add two
    parameters:

    - `filter` (String Parameter)
    - `autoremove` (Boolean Parameter)


## Done!

After completing the steps below, you should have a Jenkins job that can
upgrade your system packages.
