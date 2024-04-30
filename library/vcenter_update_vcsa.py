#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2024, Orcun Atakan <oatakan@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
module: vcenter_update_vcsa
short_description: Updates the vCenter Server Appliance (VCSA)
description:
  - This module updates the vCenter Service Appliance (VCSA) to the latest version available.
version_added: "2.10"
options:
  hostname:
    description:
      - The hostname or IP address of the vCenter server.
    required: true
  username:
    description:
      - The username to use to authenticate to vCenter.
    required: true
  password:
    description:
      - The password to use to authenticate to vCenter.
    required: true
  timeout:
    description:
      - Timeout value in seconds to wait for the update to finish.
    required: false
    default: 3600
  validate_certs:
    description:
      - Allows connection when SSL certificates are not valid. Set to false when certificates are not trusted.
      - If the value is not specified in the task, the value of environment variable VMWARE_VALIDATE_CERTS will be used instead.
    required: false
    default: true
notes:
  - This module requires connectivity to the vCenter server.
author:
  - "oatakan"
'''

from ansible.module_utils.basic import AnsibleModule, env_fallback  # Import env_fallback for environment variable fallback
import requests
import time
import json
import logging

# Configuration variable to control logging
ENABLE_LOGGING = False

def authenticate_vcsa(module, session, vcsa_url, username, password):
    """Authenticate with the VCSA and return the session token."""
    auth_url = f"{vcsa_url}/rest/com/vmware/cis/session"
    try:
        response = session.post(auth_url, auth=(username, password))
        response.raise_for_status()  # Raises an exception for HTTP error codes

        # Check if the authentication token was successfully retrieved
        auth_token = response.json().get('value')
        if not auth_token:
            module.fail_json(msg="Authentication failed: No token received.", **result)

        return auth_token  # Return the session token
    except requests.exceptions.RequestException as e:
        module.fail_json(msg=f"Failed to authenticate with VCSA: {e}")

def get_vcsa_version(session, vcsa_url, headers):
    """ Retrieve the current version of the vCSA appliance. """
    version_url = f"{vcsa_url}/api/appliance/system/version"
    response = session.get(version_url, headers=headers)
    if response.status_code == 200:
        return response.json()  # Return the whole JSON response which contains version info
    else:
        return {'error': 'Unable to fetch version information', 'status_code': response.status_code}

def wait_for_stage_complete(session, vcsa_url, timeout, headers, start_time):
    """ Polls the update status endpoint to check if the staging task is complete. """
    status_url = f"{vcsa_url}/api/appliance/update"
    stage_timeout = timeout / 6
    end_time = start_time + stage_timeout
    while time.time() < end_time:
        remaining_time = end_time - time.time()
        response = session.get(status_url, headers=headers)
        if response.status_code == 200:
            status = response.json()
            if status.get('state') == "UPDATES_PENDING":
                return True  # Staging completed successfully
        time.sleep(min(30, remaining_time))
    return False

def wait_for_install_complete(module, session, vcsa_url, timeout, headers, username, password, start_time):
    """ Polls the update status endpoint to check if the staging task is complete. """
    status_url = f"{vcsa_url}/api/appliance/update"
    end_time = start_time + timeout
    while time.time() < end_time:
        remaining_time = end_time - time.time()
        try:
            response = session.get(status_url, headers=headers)
            if response.status_code == 200:
                status = response.json()
                logging.info(f"Checking update status: {status}")
                if status.get('state') == "UP_TO_DATE":
                    return True  # Install completed successfully
            elif response.status_code == 401:
                logging.info("Session expired. Re-authenticating...")
                token = authenticate_vcsa(module, session, vcsa_url, username, password)
                session.headers.update({'vmware-api-session-id': token})
                headers = {'vmware-api-session-id': token}
                response = session.get(status_url, headers=headers)  # Retry the request
            else:
                logging.info(f"Unexpected status code {response.status_code}: {response.text}")
            response.raise_for_status()  # Handle other HTTP errors after potential re-authentication
        except requests.exceptions.HTTPError as e:
            # Log the error but continue the loop unless it's a critical error
            logging.info(f"HTTP Error encountered: {str(e)}. Retrying...")
        except requests.exceptions.ConnectionError as e:
            # Handle connection issues separately
            logging.info(f"Connection Error encountered: {str(e)}. Retrying...")
        except requests.exceptions.RequestException as e:
            # General request exceptions (timeouts, too many redirects, etc.)
            logging.info(f"Request Exception encountered: {str(e)}. Retrying...")
        except Exception as e:
            # Generic exception handler for any other unforeseen exceptions
            logging.info(f"An unexpected error encountered: {str(e)}. Retrying...")
        time.sleep(min(30, remaining_time))
    return False

def setup_logging():
    # Configure logging
    if ENABLE_LOGGING:
        logging.basicConfig(level=logging.DEBUG, filename='vcenter_update.log',
                            filemode='a', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    else:
        # Disable all logging
        logging.disable(logging.CRITICAL)

def run_module():
    module_args = dict(
        hostname=dict(type='str', required=True),
        username=dict(type='str', required=True),
        password=dict(type='str', required=True, no_log=True),
        timeout=dict(type='int', required=False, default=3600),  # Default timeout of 1 hour
        validate_certs=dict(type='bool', required=False, default=True,
                            fallback=(env_fallback, ['VMWARE_VALIDATE_CERTS']))  # Correctly closed parenthesis
    )

    result = dict(
        changed=False,
        original_message='',
        message='',
        update_details={}
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    setup_logging()
    logging.info(f"Starting module execution")

    hostname = module.params['hostname']
    username = module.params['username']
    password = module.params['password']
    timeout = module.params['timeout']
    validate_certs = module.params['validate_certs']

    vcsa_url = f"https://{hostname}"
    start_time = time.time()

    session = requests.Session()
    session.verify = validate_certs

    # Authenticate
    try:
        token = authenticate_vcsa(module, session, vcsa_url, username, password)
        session.headers.update({'vmware-api-session-id': token})

        headers = {'vmware-api-session-id': token}
        result['version_info_before'] = get_vcsa_version(session, vcsa_url, headers)

        pending_update_url = f"{vcsa_url}/api/appliance/update/pending?source_type=LOCAL_AND_ONLINE"
        pending_updates_response = session.get(pending_update_url, headers=headers)

        # Special handling for 404 status code
        if pending_updates_response.status_code == 404:
            response_data = pending_updates_response.json()
            if response_data.get('error_type') == 'NOT_FOUND' and \
                    any(msg.get('id') == 'com.vmware.appliance.update.no_updates_found' for msg in
                        response_data.get('messages', [])):
                result['message'] = 'No pending updates found.'
                result['update_details']['reboot_required'] = False
                result['version_info_after'] = result['version_info_before']
                module.exit_json(**result)
            else:
                module.fail_json(
                    msg="404 Error: The resource was not found, but the response was not recognized as 'no updates found.'",
                    response=response_data)

        pending_updates_response.raise_for_status()
        pending_updates = pending_updates_response.json()
        if not pending_updates:
            result['message'] = 'No updates available.'
            result['update_details']['reboot_required'] = False
            result['version_info_after'] = result['version_info_before']
        else:
            # Stage the update
            stage_url = f"{vcsa_url}/api/appliance/update/pending/{pending_updates[0]['version']}?action=stage"
            stage_response = session.post(stage_url, headers=headers)

            if wait_for_stage_complete(session, vcsa_url, timeout, headers, start_time):
                result['message'] = 'Staging complete. Proceeding with installation.'
                install_url = f"{vcsa_url}/api/appliance/update/pending/{pending_updates[0]['version']}?action=install"
                payload = json.dumps({
                    "user_data": {
                        "key": "id",
                        "value": pending_updates[0]['version']
                    }
                })
                headers['Content-Type'] = 'application/json'
                install_response = session.post(install_url, headers=headers, data=payload)
                # install_response.raise_for_status()
                if wait_for_install_complete(module, session, vcsa_url, timeout, headers, username, password, start_time):
                    result['changed'] = True
                    result['message'] = 'Update installed successfully.'
                    result['update_details'] = pending_updates[0]
                    result['version_info_after'] = get_vcsa_version(session, vcsa_url, headers)
                else:
                    module.fail_json(msg="Failed to verify update install completion within timeout.", **result)
            else:
                module.fail_json(msg="Failed to verify staging completion within timeout.", **result)

    except requests.exceptions.RequestException as e:
        module.fail_json(msg=str(e), **result)

    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()
