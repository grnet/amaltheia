# Commands for migrating nova-compute instances from running host

Disable service so that no new instances come: `openstack compute service set NOVA-COMPUTE-SERVER-NAME nova-compute --disable`

Check instances running: `nova hypervisor-servers NOVA-COMPUTE-SERVER-NAME`

Find information for a specific instance (Pass value of field `ID`): `openstack server show OPENSTACK-SERVER-UUID`

Live-migrate running instances: `nova host-evacuate-live NOVA-COMPUTE-SERVER-NAME`

Live-migrate fails for stopped instances, move them as well: `nova host-servers-migrate NOVA-COMPUTE-SERVER-NAME`
