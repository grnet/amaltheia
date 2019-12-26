# amaltheia: A system update tool for production servers

In ancient Greek mythology, Amaltheia was the goat that brought up Zeus,
protecting him from the wrath of his father Kronos.

On the cloud, `amaltheia` is a tool to automate and manage update tasks (e.g.
package updates, firmware upgrades) on production servers, taking care of
safely stopping and recovering any running services.

It is currently work-in-progress, and most definitely not a goat.

## Installation

`amaltheia` can be installed directly from GitHub:

```bash
$ pip3 install git+https://github.com/grnet/amaltheia.git
```

Or you can install as an egg, for development:

```
$ cd amaltheia/
$ pip3 install -r requirements.txt
$ pip3 install -e .
```

## Usage

See the `examples/` folder for example job files, or `jenkins/` for a complete
use-case.

```
$ ./amaltheia/amaltheia.py -s job.yaml -o config.log_level=info
```

## Docker

Alternatively, you can build a Docker image with your configuration:

```bash
$ docker build -t amaltheia:VERSION \
    --build-arg ssh_id_rsa=YOUR_SSH_KEY \
    --build-arg ssh_config=YOUR_SSH_CONFIG_FILE \
    --build-arg jobs=YOUR_JOB_FILE
```

And then execute amaltheia by spawning ephemeral containers:

```bash
$ docker run --rm amaltheia:VERSION -s /amaltheia/YOUR_JOB_FILE
```

## Documentation

Detailed documentation for `amaltheia` can be found [in the docs folder][1], or
the source code. We strive to keep the `amaltheia` source code simple to read
and well-documented.

Feel free to open a new issue if anything is missing.


## Concepts

`amaltheia` uses the following concepts:

- **`hosts`** are the machines on which the update actions will be performed.
- **`services`** are services running on machines (e.g. nova-compute). Each
  service has a dedicated class (in services.py) that knows how to evacuate and
  restore the service when running on a host.
- **`updaters`** do the actual updates (e.g. apt-get upgrades).
- **`jobs`** are defined as a list of hosts, services, updates and a strategy.
  We apply the updates on the hosts, taking care of enabling/disabling the
  running services, while following a specific strategy. Jobs are defined in
  a single YAML file and may have custom variables.
- **`discoverers`** are responsible for creating a list of hosts by querying
  other services (e.g. Patchman, NetBox, MaaS, Juju)
- **`strategies`** are followed by amaltheia when performing the update actions
  and describe the order in which the updates are applied (e.g. serial/parallel)


## Current Assumptions/limitations

- Currently designed to fit the update process of nova-compute nodes.
- Currently supports SSH and OpenStack commands only. Can be extended.


## Roadmap

- Extend to more openstack services (e.g. neutron)
- Extend with different update strategies (keep a ratio of servers/AZ up)

[1]: docs/configuration.md "Amaltheia configuration documentation"


Aggelos Kolaitis <akolaitis@admin.grnet.gr>
