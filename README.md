# ansible-vmware-esxi

Ansible playbooks and roles for managing VMware ESXi and vCenter environments, including:

- Deploying VCSA (vCenter Server Appliance)
- Configuring vCenter (clusters, DRS, folders, pools, license)
- Adding ESXi hosts to vCenter
- Deploying/importing OVA-based VMs/templates
- Updating ESXi and VCSA

## Repository Layout

- `add_esxi_host_to_vcenter.yml` - add an ESXi host using the `vcenter-add-host` role
- `configure_vcenter_appliance.yml` - configure vCenter using the `vcenter-configure` role
- `deploy_vcenter_appliance.yml` - deploy VCSA from OVA/ISO via datastore path
- `deploy_vcenter_appliance_via_linux_host.yml` - deploy VCSA from a Linux host with mounted NFS share
- `deploy_vm_from_ova.yml` - deploy OVA to ESXi using `ovftool`
- `deploy_vm_from_ova_local.yml` - deploy OVA from local file using Ansible module
- `import_templates_to_vcenter.yml` - import OVA templates to vCenter
- `update_esxi.yml` - update ESXi hosts using the `esxi-update` role
- `update_vcsa.yml` - update vCenter appliance via custom module in `library/vcenter_update_vcsa.py`

Main roles are under `roles/` and collection dependencies are defined in `collections/requirements.yml`.

## Requirements

- Python 3
- Ansible (tested in this project with `ansible-core 2.16.x`)
- Required collections:
	- `community.vmware`
	- `vmware.vmware`
- Access to vCenter/ESXi API endpoints from the machine running Ansible
- For OVA workflows:
	- `ovftool` available at the configured path, or
	- local OVA file for `deploy_vm_from_ova_local.yml`

## Install Dependencies

```bash
# (optional) activate your virtualenv
source ~/projects/ansible-latest/bin/activate

# install required collections
ansible-galaxy collection install -r collections/requirements.yml
```

## Authentication and Environment Variables

Most playbooks/roles use these environment variables:

- `VMWARE_HOST` - vCenter hostname or IP
- `VMWARE_USER` - vCenter username
- `VMWARE_PASSWORD` - vCenter password
- `VMWARE_VALIDATE_CERTS` (optional) - set to `false` in lab/self-signed environments

Example:

```bash
export VMWARE_HOST='vcenter.example.local'
export VMWARE_USER='administrator@vsphere.local'
export VMWARE_PASSWORD='your-password'
export VMWARE_VALIDATE_CERTS='false'
```

## Inventory

You can run against a target ESXi host inventory (for host-focused operations) or localhost (for vCenter-only operations).

Example `inventory.ini`:

```ini
[esxi]
esxi01 ansible_host=192.168.1.10 ansible_user=root ansible_password='esxi-root-password'
```

## Common Usage

```bash
# Add ESXi host to vCenter (role-based)
ansible-playbook -i inventory.ini add_esxi_host_to_vcenter.yml

# Configure vCenter objects (runs on localhost)
ansible-playbook -i inventory.ini configure_vcenter_appliance.yml

# Deploy VCSA (datastore/NFS path based workflow)
ansible-playbook -i inventory.ini deploy_vcenter_appliance.yml

# Deploy VCSA via Linux host mounted share
ansible-playbook -i inventory.ini deploy_vcenter_appliance_via_linux_host.yml

# Deploy VM from OVA using ovftool path on datastore
ansible-playbook -i inventory.ini deploy_vm_from_ova.yml

# Deploy VM from a local OVA file
ansible-playbook -i inventory.ini deploy_vm_from_ova_local.yml

# Import multiple templates to vCenter
ansible-playbook -i inventory.ini import_templates_to_vcenter.yml

# Update ESXi
ansible-playbook -i inventory.ini update_esxi.yml

# Update VCSA (custom module)
ansible-playbook -i inventory.ini update_vcsa.yml
```

## Role Defaults You’ll Likely Override

Common variables are defined in each role’s `defaults/main.yml`.

- `roles/vcenter-add-host/defaults/main.yml`
	- `vcenter_datacenter`, `vcenter_cluster`, `target_esx_datastore`
- `roles/vcenter-configure/defaults/main.yml`
	- `vcenter_datacenter`, `vcenter_cluster`, `enable_drs`, `enable_vsan`, `vcenter_resource_pools`, `vcenter_vm_folders`, `vcenter_license`
- `roles/vcsa-deploy/defaults/main.yml`
	- `vcsa_iso`, `network_host`, `network_path`, `vcenter_appliance_name`, networking values
- `roles/vcsa-deploy-via-linux-host/defaults/main.yml`
	- `network_mount_dir`, `vcsa_iso`, `vcenter_appliance_name`, networking values
- `roles/vcenter-deploy-ova/defaults/main.yml`
	- `ova_files`, `network_mount_dir`, `ovftool`, `target_esx_datastore`, `target_esx_portgroup`
- `roles/vcenter-deploy-ova-template/defaults/main.yml`
	- `ova_files`, `vcenter_datacenter`, `vcenter_cluster`
- `roles/esxi-update/defaults/main.yml`
	- `esxi_cli_mem_default`, `esxi_cli_mem_max`

Prefer overriding values in inventory/group vars or with `-e` as needed.

## Notes on Collections

This repository currently uses a mixed approach:

- `vmware.vmware` where a direct equivalent is available and validated
- `community.vmware` where no safe drop-in equivalent is currently used in this codebase

Both collections are intentionally kept in `collections/requirements.yml`.

## Custom Module (`update_vcsa.yml`)

`update_vcsa.yml` uses the local custom module `library/vcenter_update_vcsa.py`.

- It talks to VCSA REST endpoints directly
- It requires Python `requests` in the Ansible Python environment

If needed:

```bash
pip install requests
```

## Troubleshooting

- Verify environment variables are exported before running playbooks.
- If module resolution fails, reinstall collections:
	- `ansible-galaxy collection install -r collections/requirements.yml --force`
- Use syntax check first:
	- `ansible-playbook -i inventory.ini <playbook>.yml --syntax-check`
- In lab setups with self-signed certs, set `VMWARE_VALIDATE_CERTS=false`.
