# Amaltheia configuration options

| Property      | Value            |
| ------------- | ---------------- |
| Software Name | Amaltheia        |
| Version       | 0.2              |
| Author        | Aggelos Kolaitis |
| Last Update   | 2020-01-23       |

All configuration for an amaltheia job is defined in a single YAML file. Some
configuration can be set when executing the job using either job variables or
configuration overrides. More on that below.

The skeleton of a job file looks like this:

```yaml
---
config:
  # configuration options
strategy:
  # strategy to follow for multiple hosts
hosts:
  # list of hosts to perform actions on
updates:
  # list of update actions
services:
  # list of services that need be stopped/evacuated/restarted
requires:
  # list of job variables that need to be passed as command-line arguments
```

And using it is as simple as:

```bash
$ python3 amaltheia/amaltheia.py -s job.yaml
```

Detailed documentation for each section can be found below. You can also
look in the `examples/` folder for a list of example job files, or the
`jenkins/` folder, for a complete use-case (a Jenkins job to update the
apt system packages of a huge number of machines. Monitoring which machines
need to be updated is delegated to [Patchman][1]. This job was developed
for the OpenStack@Louros deployment).

When developing new jobs, it is suggested that you follow the proposed
format for the jobs on the `examples/` folder, so that they be maintainable
and re-usable.

## Configuration block

This section contains general options for amaltheia.

| Name                                  | Required | Type       | Example           | Description                                                                                                                                         |
| ------------------------------------- | -------- | ---------- | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `config.color`                        | NO       | boolean    | `true`            | Use ANSI formatting sequences for making the output more readable. Disable if output is not a tty                                                   |
| `config.log-level`                    | NO       | int/string | `info`            | Log level to set. Translates to the python logging module levels. Can be either a number or one of `debug`, `info`, `warning`, `error`, `exception` |
| `config.openstack-rc`                 | YES*     | string     | `openstack.rc`    | Path to OpenStack RC file, if using OpenStack actions                                                                                               |
| `config.ssh-user`                     | YES**    | string     | `ubuntu`          | Username to use for ssh access on remote machines (if needed)                                                                                       |
| `config.ssh-id-rsa-file`              | YES**    | string     | `./ssh-id-rsa`    | Path to SSH identity to use for connections to remote machines (if needed)                                                                          |
| `config.ssh-id-rsa-password`          | YES**    | string     | `my-key-password` | Password to use for SSH identity (if needed)                                                                                                        |
| `config.ssh-config-file`              | YES**    | string     | `./ssh-config`    | Optional ssh config file to use for connecting to remote machines                                                                                   |
| `config.ssh-strict-host-key-checking` | YES**    | boolean    | `true`            | Whether to enable SSH strict host key checking                                                                                                      |


`*` Only when evacuating/restoring OpenStack services, e.g. `nova-compute`. See
services section below for more information.

`**` Only when performing updates that require SSH access on the target hosts.

Complete example for the configuration block:

```yaml
config:
  color: true
  ssh-user: ubuntu
  ssh-id-rsa-file: /path/to/ssh-id-rsa
  ssh-strict-host-key-checking: false
  log-level: info
```

## Hosts block

This section defines the hosts on which amaltheia will perform the requested
update actions. It is a list of host discoverers. Multiple host discoverers
of the same or different types can be used for a single job.

Currently, supported discoveres include `static`, `netbox` and `patchman`, and
their options are documented below.

A complete example for the hosts block can be seen below. This tells amaltheia
to perform any requested actions on:
* `myhost.domain.ext`, `myhost2.domain.ext`, `1.2.3.4`, which are passed as a
  a static list
* Any hosts that are reported from Patchman and whose names match the regular
  expression `lar04..` (using the regex format of the Python `re` module)

```yaml
hosts:
- static:
  - myhost.domain.ext
  - myhost2.domain.ext
  - 1.2.3.4
- patchman:
    patchman-url: https://patchman.domain.ext/patchman/api/host/
    host-name: '{{ host.hostname | lower }}'
    filter-name: 'lar04..'
    on-package-updates:
    - apt
```

### Static discoverer

The static discoverer accepts a static list of hosts to add to the inventory.
Each host can either be a string, or an object (which gives you the ability
to specify custom host arguments). A hostname can be either an IP address
or an FQDN.

Example:

```yaml
hosts:
- static:
  - host1.with.custom.ssh.config:
      ssh-user: ubuntu
      ssh-id-rsa-file: ssh-id-rsa
      ssh-id-rsa-password: my-safe-key-password
  - host2
  - 10.0.0.14
```

More on host arguments below.

### Patchman discoverer

The [Patchman][1] discoverer retrieves a list of hosts from Patchman, using
its Rest API. It automatically discovers which hosts have required updates and
which need to be rebooted, and allows for the addition of update actions on
each of these conditions. The complete format is:

| Name                          | Required | Type            | Example                                        | Description                                                                                                                                    |
| ----------------------------- | -------- | --------------- | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `patchman.patchman-url`       | YES      | String          | `"https://patchman.server/patchman/api/host/"` | Full Path to the Patchman API for retrieving the list of hosts                                                                                 |
| `patchman.host-name`          | NO       | String          | `"{{ host.hostname }}"`                        | Override host name returned by Patchman for each host. Can be a Jinja template. Access the patchman host information using the `host` variable |
| `patchman.filter-name`        | NO       | String          | `"lar04.*"`                                    | Filter out any machines whose name does not match the regular expression                                                                       |
| `patchman.on-package-updates` | NO       | List of actions | ``                                             | List of update actions to perform on the servers that have available package updates                                                           |
| `patchman.on-reboot-required` | NO       | List of actions | ``                                             | List of update actions to perform on the servers that require a reboot                                                                         |
| `patchman.skip-ok`            | NO       | Boolean         | `false`                                        | If `true`, then hosts that require no updates and/or reboot will not be added in the list                                                      |

Example 1: This example queries the Patchman server for hosts whose names match
the filter `lar04..` ("lar04" and two more characters). It adds an `apt` action
for the ones that have system package updates available, and a `reboot` action
for those that require a reboot.

```yaml
hosts:
- patchman:
    patchman-url: https://patchman.server/patchman/api/host/
    host-name: "{{ host.hostname }}.domain.gr"
    filter-name: "lar04.."
    on-package-updates:
    - apt
    on-reboot-required:
    - reboot
```

### NetBox discoverer

The [NetBox][2] discoverer retrieves a list of hosts from NetBox, using
its Rest API. The complete format of its arguments is:

| Name                 | Required | Type   | Example                                     | Description                                                                                                                               |
| -------------------- | -------- | ------ | ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `netbox.netbox-url`  | YES      | String | `"https://netbox.server/api/dcim/devices/"` | Full Path to the NetBox API endpoint for retrieving the list of hosts                                                                     |
| `netbox.host-name`   | NO       | String | `"{{ host.name|lower }}.domain.gr"`         | Jinja template for host name. NetBox data can be retrieved via the `host` variable                                                        |
| `netbox.host-args`   | NO       | Object | ` `                                         | Object for custom host arguments. Can use Jinja templates for either keys or values. NetBox data can be retrieved via the `host` variable |
| `netbox.filter-name` | NO       | String | `"lar04.."`                                 | Filter out machines whose name does not match the specified regular expression                                                            |

Example: The example below retrieves a list of hosts from NetBox. The API url
restricts the results using NetBox options: it will only return active hosts
(`status=1`), from a specific site (`site=myShinyDC`) and with specific device
type (`device_type_id=12`). Further filtering is performed by amaltheia so that
the hosts whose name does not match `lar04.*` be discarded. Also note the
`limit=0` parameter. The host names will have `.myShinyDC.gr` appended, and the
host argument `from_netbox` will be set to True.

```yaml
hosts:
- netbox:
    netbox-url: https://netbox.noc.grnet.gr/api/dcim/devices/?site=myShinyDC&limit=0&device_type_id=12&status=1
    filter-name: "lar04.*"
    host-name: "{{ host.name | lower }}.myShinyDC.gr"
    host-args:
      from-netbox: true
      ssh-user: ubuntu
      ssh-id-rsa-file: my-id-rsa
```


### HTTP discoverer

The HTTP discoverer retrieves a list of hosts from an HTTP url. The complete
format of its arguments is:

| Name                   | Required | Type            | Example                                                     | Description                                                                                                                                                 |
| ---------------------- | -------- | --------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `http.request.url`     | YES      | String          | `"https://netbox.server/api/dcim/devices/"`                 | Full path to the HTTP API url.                                                                                                                              |
| `http.request.method`  | NO       | String          | `"GET"`                                                     | HTTP method to use                                                                                                                                          |
| `http.request.headers` | NO       | Object          | `headers: {X-Auth-Token: aaaaa-bbbbbbb-cccccc}`             | HTTP request headers to send                                                                                                                                |
| `http.request.json`    | NO       | String          | `{data: test}`                                              | HTTP request parameters to be passed as a JSON body                                                                                                         |
| `http.results`         | YES      | String          | `{{ response.results }}`                                    | Jinja template for the JSON field to use for querying hosts. Result can be either a dictionary or a list                                                    |
| `http.next-url-field`  | YES      | String          | `{{ response.next }}`                                       | Jinja template for the JSON field to use as next URL, when API results use paging. If this value is a valid URL, then the discoverer will continue querying |
| `http.parse.host-name` | YES      | String          | `{{ item }}`                                                | For each item in the results, set discovered host name                                                                                                      |
| `http.parse.host-args` | NO       | Object          | `{custom-field: "{{ item.value }}"}`                        | Jinja template for extra host specific arguments to get                                                                                                     |
| `http.match`           | NO       | List of objects | `[{regex: "<some-regex>", value: "{{ item.value }}"}, ...]` | List of match rules for each host                                                                                                                           |

For the `http.parse` section, you can use Jinja with the `{{ item }}` variable.
If results are a list, then `{{ item }}` will be a list item. If results is a
dictionary, then you can use `{{ item.key }}` and `{{ item.value }}`.

A complete example can be found below:

```yaml
hosts:
- http:
    request:
      url: https://my.api.server/url
      method: GET
      headers:
        X-Auth: 18976319827369876d98f76asdfasdf
      json:
        parameter: value
    results-field: "{{ response.results }}"
    next-url-field: "{{ response.next }}"
    match:
    - regex: lar04..
      value: "{{ item.key }}"
    parse:
      host-name: "{{ item.key }}"
      host-args:
        IPMI: "{{ item.value.IPMI_address }}"
```

When paired with an API that returns a response like the following:

```json
GET https://my.api.server/url
{
  "next": "https://my.api.server/url?page=2",
  "results": {
    "host_1": {"IPMI_address": "10.0.0.1", "IP_address": "10.1.0.1"},
    "host_2": {"IPMI_address": "10.0.0.2", "IP_address": "10.1.0.2"},
  }
}

GET https://my.api.server/url?page=2
{
  "next": null,
  "results": {
    "host_3": {"IPMI_address": "10.0.0.3", "IP_address": "10.1.0.3"},
  }
}
```

Then the http discoverer will retrieve hosts `host_1`, `host_2` and `host_3`,
while also setting the `IPMI` host argument for each one of them.


## Host arguments

The following host arguments will be recognised by amaltheia:

| Name                  | Required | Type   | Example                        | Description                     |
| --------------------- | -------- | ------ | ------------------------------ | ------------------------------- |
| `ssh-user`            | NO       | String | `"ubuntu"`                     | Override default SSH username   |
| `ssh-id-rsa-file`     | NO       | String | `"my-id-rsa"`                  | Override default SSH key to use |
| `ssh-id-rsa-password` | NO       | String | `"my-id-rsa-password"`         | Override SSH key password       |
| `ssh-timeout`         | NO       | String | `10`                           | SSH connection timeout          |
| `ssh-proxycommand`    | NO       | String | `ssh -q -W ssh-gateway-server` | SSH Proxy command               |


## Updates Block

Updates are actions that will be performed on the hosts. These actions are
always performed in the order in which they are declared. Actions can be
either strings (for no arguments), or objects (and have custom arguments).

Currently, the following actions are supported: `dummy`, `apt`, `reboot`, and
`ssh` and `exec`. Update actions and their available options can be found below.

Example updates block:

```yaml
updates:
- apt
- ssh:
    command: touch .my.secret.file
- reboot
```


### Dummy update action

This action only prints a message. It is useful for debugging purposes.

### Apt update action

**Requires**: ssh access

The `apt` update action performs system package updates on a host. It makes
sure that the process will not be stuck on interactive prompts. The options
for this action are described below:

| Name               | Required | Type    | Example                | Description                                                                                              |
| ------------------ | -------- | ------- | ---------------------- | -------------------------------------------------------------------------------------------------------- |
| `apt.autoremove`   | NO       | Boolean | `true`                 | Run `apt-get autoremove` after performing upgrades                                                       |
| `apt.hold`         | NO       | List    | `[apt, vim]`           | `apt-mark hold` a list of packages **before** updating                                                   |
| `apt.unhold`       | NO       | List    | `[apt, vim]`           | `apt-mark unhold` a list of packages **after** updating                                                  |
| `apt.fix-hostname` | NO       | String  | `{{ host }}.my.domain` | Jinja template for configuring the host name to use (if any override is needed, e.g. adding domain name) |

Example: This action will perform any system updates available. It will also
autoremove old packages afterwards. However, it will hold the versions for the
Linux kernel.

```yaml
updates:
- apt:
    autoremove: true
    hold:
    - linux-image
    - linux-headers
```

### Reboot action

**Requires**: ssh access

The `reboot` update action will take care of rebooting a machine.

| Name                         | Required | Type    | Example                | Description                                                                                              |
| ---------------------------- | -------- | ------- | ---------------------- | -------------------------------------------------------------------------------------------------------- |
| `reboot.wait`                | NO       | Boolean | `true`                 | Wait for the machine to come back up after rebooting                                                     |
| `reboot.wait-timeout`        | NO       | Integer | `1000`                 | Timeout (in seconds) after which the machine reboot operation will be considered failed                  |
| `reboot.wait-check-interval` | NO       | List    | `10`                   | How often to check if the machine has rebooted successfully                                              |
| `reboot.fix-hostname`        | NO       | String  | `{{ host }}.my.domain` | Jinja template for configuring the host name to use (if any override is needed, e.g. adding domain name) |

Example 1: Reboot machines and wait for it to complete for a maximum of 10
minutes.

```yaml
updates:
- reboot:
    wait: true
    wait-timeout: 600
```

Example 2: Update apt packages and then reboot machines. Do not wait for them
to return so that amaltheia returns quickly.

```yaml
updates:
- apt
- reboot
```

### Jenkins action

**Requires**: Jenkins credentials (passed as parameters)

The `jenkins` update action can execute a Jenkins job.

| Name                          | Required | Type    | Example                      | Description                                                                                                   |
| ----------------------------- | -------- | ------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `jenkins.server`              | YES      | String  | `https://my-jenkins-server/` | Jenkins Server URL                                                                                            |
| `jenkins.username`            | YES      | String  | `username`                   | Jenkins username                                                                                              |
| `jenkins.password`            | YES      | String  | `password`                   | Jenkins password                                                                                              |
| `jenkins.job`                 | YES      | String  | `some-important-job`         | Jenkins job to execute                                                                                        |
| `jenkins.build-arguments`     | YES (*)  | Object  | `{key: value, bool: false}`  | Build jenkins job with parameters. Can be a Jinja template, with access to `{{ host }}` and `{{ host_args }}` |
| `jenkins.fix-hostname`        | NO       | String  | `{{ host }}.my.domain`       | Jinja template for configuring the host name to use (if any override is needed, e.g. adding domain name)      |
| `jenkins.wait`                | NO       | Boolean | `true`                       | Whether to wait for the Jenkins job to finish execution                                                       |
| `jenkins.wait-timeout`        | NO       | Integer | `1000`                       | Timeout after N seconds if Jenkins job has not finished executing                                             |
| `jenkins.wait-check-interval` | NO       | List    | `10`                         | Check if job has finished every N seconds, until timeout                                                      |

`*` Only when running a job with required parameters.

Example 1: Call a simple Jenkins job and do not wait for execution

```yaml
updates:
- jenkins:
    server: https://production.jenkins.server/
    username: 'jenkins-user'
    password: 'a-secure-password-i-just-thought-about'
    job: 'my-jenkins-job-name'
    wait: false
```

Example 2: Call a Jenkins Job with parameters. Wait for job to finish (max 5 minutes).

```yaml
updates:
- jenkins:
    server: https://production.jenkins.server/
    username: 'jenkins-user'
    password: 'a-secure-password-i-just-thought-about'
    job: 'my-jenkins-job-name'
    build-arguments:
      host: '{{ host }}'
    wait: true
    wait-timeout: 300
    wait-check-interval: 10
```

### SSH update action

**Requires**: ssh access

The `ssh` update action executes an arbitrary command on a remote machine.

| Name               | Required | Type   | Example                 | Description                                                                                              |
| ------------------ | -------- | ------ | ----------------------- | -------------------------------------------------------------------------------------------------------- |
| `ssh.command`      | YES      | String | `touch .my-secret-file` | Arbitrary SSH command to execute                                                                         |
| `ssh.fix-hostname` | NO       | String | `{{ host }}.my.domain`  | Jinja template for configuring the host name to use (if any override is needed, e.g. adding domain name) |
Example (Do not try this one):

```yaml
updates:
- ssh:
    command: sudo rm -rf /
```

### Execute command update action

**Requires**: nothing

The `exec` update action executes an arbitrary command from the host where
amaltheia is running, capturing its return code, stdout and stderr.

| Name                     | Required | Type    | Example                | Description                                                                                              |
| ------------------------ | -------- | ------- | ---------------------- | -------------------------------------------------------------------------------------------------------- |
| `exec.args`              | YES      | List    | `[echo, hi]`           | List of command and command line arguments                                                               |
| `exec.kwargs`            | NO       | Object  | `{shell: true}`        | Custom arguments to pass to [`subprocess.run()`][3] directly                                             |
| `exec.expect-stdout`     | NO       | String  | `OK`                   | If command output matches, then the update action is considered successful.                              |
| `exec.expect-returncode` | NO       | Integer | `0`                    | If command return code matches, then the update action is considered successful.                         |
| `exec.fix-hostname`      | NO       | String  | `{{ host }}.my.domain` | Jinja template for configuring the host name to use (if any override is needed, e.g. adding domain name) |

Example: This action will execute "echo hi" on the host where amaltheia is
running, using `/opt/mypath` as current working directory:

```yaml
updates:
- exec:
    args: [echo, hi]
    kwargs:
      cwd: /opt/mypath
```


## Services

This section defines services that are expected to be running on top of the
hosts where update actions will be performed. This is useful for updates where
downtime is required for the host, so it will have to be evacuated of any
running services, as well as have these services restored afterwards.

Like hosts and update actions, services can be either strings or objects, with
configuration options.

Currently, the following services are supported: `nova-compute`.

Example services block:

```yaml
services:
- nova-compute
```

### Nova Compute Service

**Requires: OpenStack credentials**

The `nova-compute` service is used to evacuate a nova-compute host before
rebooting or shutting it down for maintenance, as well as restore the service
afterwards. Uses the OpenStack APIs for all operations.

Evacuate Actions:
* Disable nova-compute service, so that no new VMs are scheduled on this host.
* Live-migrate any running VMs to other nova-compute hosts, to avoid impacting
  the users.
* Migrate non-running instances as well.
* Wait for all migrations to complete, before allowing the update actions to be
  executed.

Restore Actions:
* Re-enable the nova-compute service.

> NOTE: In the future, this service could be extended to fetch back user
> resources that were evacuated before the update actions.

The service parameters are defined below:

| Name                         | Required | Type    | Example                | Description                                                                                                                                                               |
| ---------------------------- | -------- | ------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `nova-compute.skip-evacuate` | NO       | Boolean | `false`                | Skip evacuation process (e.g. if user downtime is not an issue)                                                                                                           |
| `nova-compute.skip-restore`  | NO       | Boolean | `false`                | Skip restoring process (e.g. if planning to decommission node)                                                                                                            |
| `nova-compute.timeout`       | NO       | Integer | `120`                  | **Per VM** timeout before flagging the migration process as failed. For example, if a host has 5 VMs running, and timeout is set to 100, then timeout will be 500 seconds |
| `nova-compute.fix-hostname`  | NO       | String  | `{{ host }}.my.domain` | Jinja template for configuring the host name to use (if any override is needed, e.g. adding domain name)                                                                  |

Example: Move away running VMs for the hosts before performing any update
action. Wait for 100 seconds per VM for the process to complete. After running
the update actions, do not restore the service (e.g. so that an operator can
verify the host state))

```yaml
services:
- nova-compute:
    timeout: 100
    skip_restore: true
```

## Command-line arguments

Amaltheia job files are always a single file. However, amaltheia accepts
command-line arguments in order to either override configuration options
or specify variables for the running job.

### Override configuration

You can override configuration using the `--override/-o` flag. For example,
the following job sets the log level to `INFO` by default:

```yaml
config:
  log_level: info
hosts:
- static:
  - myhost.domain.ext
updates:
- apt
```

You can override the log level when executing the job with:

```bash
$ python3 amaltheia/amaltheia.py -s job.yaml -o config.log_level=debug
```

As can be seen from the example below, use dots (`.`) to access child names.

**NOTE**: The format for overriding configuration is `-o key=value` The `value`
will be tread as YAML input, which means that you can even use lists or
dictionaries. Consider the following example:

```yaml
config:
  log-level: info
hosts:
- static:
  - my.host.name
updates:
- dummy
```

You can then do:

```bash
$ python3 amaltheia/amaltheia.py -s job.yaml -o updates="[apt,reboot]"
```

This will override the original `dummy` update action with the actions `apt`
and `reboot`.

### Job variables

Job can be parametrized with variables. Variables can also be accessed where
needed using Jinja templates. For example, this is a job that updates the apt
packages on a single host:

```yaml
config:
  log-level: info
  ssh-id-rsa: path/to/ssh-id-rsa-key
hosts:
- static:
  - '{{ myhost }}'
updates:
- apt
```

Then, you can pass the value for `myhost` using the `--variables/-v` command
line argument:

```bash
$ python3 amaltheia/amaltheia.py -s job.yaml -v myhost=server1.domain.gr
$ python3 amaltheia/amaltheia.py -s job.yaml -v myhost=server2.domain.gr
```

The format is `-v key=value`. Again, the `value` part will be treated as YAML
input.

> NOTE: Jinja variables **are only supported** for host and update action
> arguments. For other usages, use an override instead.

#### Required Variables

Further, a job can have a list of "required" variables that need to be set
using command-line arguments. These are defined in the special `required`
section:

```yaml
requires:
- myhost
config:
  log-level: info
hosts:
- static:
  - '{{ myhost }}'
updates:
- apt
```

Attempting to execute the job without passing them will result in an error:

```bash
$ python3 amaltheia/amaltheia.py -s job.yaml
CRITICAL:root:[amaltheia] Missing required variable myhost for script a.yml
```

#### Multiple Variables

You can define multiple variables like this:

```bash
$ python3 amaltheia/amaltheia.py -s job.yaml -v key1=value1 key2=value2
```


## Strategies

Last but not least, amaltheia can be told to follow a specific strategy when
updating a list of hosts.

Strategies can be either strings or objects.

The following strategies are currently implemented: `serial`, `parallel`.

Example:

```yaml
strategy: serial
```

### Serial strategy

The `serial` strategy performs all update actions on a host-by-host basis. It
performs updates on one host at a time, and only moves on to the next when
finished.

The parameters for the serial strategy are:


| Name                   | Required | Type    | Example | Description                                                                               |
| ---------------------- | -------- | ------- | ------- | ----------------------------------------------------------------------------------------- |
| `serial.quit-on-error` | NO       | Boolean | `false` | If the update actions fail for a single host, then abort update for the rest of the hosts |

Example:

```yaml
strategy:
  serial:
    quit-on-error: true
```

### Parallel strategy

The `parallel` strategy works with up to N hosts in parallel at a time.

The parameters for the parallel strategy are:

| Name                 | Required | Type    | Example | Description                              |
| -------------------- | -------- | ------- | ------- | ---------------------------------------- |
| `parallel.nparallel` | YES      | Integer | `4`     | Number of hosts to work with in parallel |


[1]: https://github.com/furlongm/patchman "Patchman GitHub repository"
[2]: https://netbox.readthedocs.io/en/stable/ "NetBox ReadTheDocs page"
[3]: https://docs.python.org/3/library/subprocess.html "Python3 subprocess module documentation"
