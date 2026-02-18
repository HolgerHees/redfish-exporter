import logging
import os
import time
import requests
import re
import socket

from collectors._collector import POWER_STATES, HEALTH_STATES

class RedfishSession:
    def __init__(self, config, target, job, modules, metric):
        self.config = config
        self.target = target
        self.job = job
        self.modules = modules
        self.metric = metric

        self.ipaddress = None
        self.hostname = None

        self._timeout = config.timeout

        self._username = None
        self._password = None

        self._session = ""
        self._last_http_code = 0

        self._session_url = None
        self._redfish_up = False

        # Label
        self.redfish_version = None
        self.vendor = None
        self.product = None
        self.uuid = None
        self.manufacturer = None
        self.model = None
        self.serial = None

        # Values
        self.powerstate = None
        self.server_health = None

        self.root_urls = {}
        self.sub_urls = {}

        self.ip_re = re.compile(
            r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}"
            r"([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$"
        )

    def __enter__(self):

        self._open()

        labels = {"hostname": self.target}
        self.metric.createMetricFamily("up", "Redfish Server Monitoring availability", labels=labels).addMetricSample(value=self._redfish_up, labels=labels)

        return self

    def _open(self):
        logging.debug("Received Target %s with job '%s' and modules '%s'", self.target, self.job, ", ".join(self.modules) if self.modules is not None else 'all')

        self._username, self._password = self.config.getJobCredentials(self.job)

        if not self._username or not self._password:
            logging.error("Target %s: Unknown job '%s' provided or no user/password found in environment and config file", self.target, self.job)
            return

        logging.debug("Target %s: Using user '%s'", self.target, self._username)

        if self.ip_re.match(self.target):
            self.host = self.target
            #try:
            #    socket.gethostbyaddr(self.target)[0]
            #except socket.herror as err:
            #    logging.warning("Target %s: Reverse DNS lookup failed: %s. Using IP address as host.", self.target, err)
            #    self.hostname = self.target
        else:
            try:
                self.host = socket.gethostbyname(self.target)
            except socket.gaierror as err:
                logging.error("Target %s: DNS lookup failed with error '%s'", self.target, err)
                return

        """Get the url for the server info and messure the response time"""
        server_response = self.fetch("/redfish/v1", auth=None)
        if server_response is None:
            return

        if "RedfishVersion" in server_response:
            self.redfish_version = server_response['RedfishVersion']

        if "Vendor" in server_response:
            self.vendor = server_response['Vendor']

        if "Product" in server_response:
            self.product = server_response['Product']

        if "UUID" in server_response:
            self.uuid = server_response['UUID']

        for key in ["Systems", "SessionService", "Chassis"]:
            if key in server_response:
                self.root_urls[key] = server_response[key]['@odata.id']
            else:
                logging.warning("Target %s: No '%s' URL found on server '%s'", self.target, key, self.hostname)
                return

        session_service = self.fetch( self.root_urls['SessionService'], auth=False)
        if not session_service:
            return

        sessions_url = "https://{}{}".format(self.target, session_service['Sessions']['@odata.id'])
        session_data = {"UserName": self._username, "Password": self._password}
        self._session.auth = None

        try:
            result = self._session.post(
                sessions_url, json=session_data, verify=False, timeout=self._timeout
            )
            result.raise_for_status()

            if result and result.status_code in [200, 201, 202, 204]:
                self._auth_token = result.headers['X-Auth-Token']
                session_url = result.headers.get('Location')

            if not self._auth_token:
                logging.warning("Target %s: No X-Auth-Token in headers", self.target)
                return

            if not session_url:
                try:
                    json_body = result.json()
                    session_url = json_body.get('@odata.id')
                except (ValueError, requests.exceptions.JSONDecodeError) as e:
                    logging.warning("Invalid or empty JSON body. Exception: %s", e)

            if not session_url:
                logging.warning("Session URL not found in either JSON body or Location header.")
                return

            logging.info("Target %s: Got an auth token from server '%s'", self.target, self.host)

            self._session_url = "https://{}{}".format(self.target, session_url)
            self._redfish_up = True
        except requests.exceptions.ConnectionError:
            logging.warning("Target %s: Failed to get an auth token from server %s.", self.target, self.host)
        except requests.exceptions.HTTPError as err:
            logging.warning("Target %s: No session received from server %s: %s", self.target, self.host, err)
        except requests.exceptions.ReadTimeout as err:
            logging.warning("Target %s: No session received from server %s: %s", self.target, self.host, err)

    def __exit__(self, exc_type, exc_value, traceback):
        if self._session_url is None:
            return

        try:
            self._session.auth = None
            self._session.headers.update({"X-Auth-Token": self._auth_token})
            result = self._session.delete(self._session_url, verify=False, timeout=self._timeout)
            result.raise_for_status()
            self._session_url = None
            self._redfish_up = False
        except requests.exceptions.ConnectionError:
            logging.warning("Target %s: Failed to release session on server '%s'", self.target, self.host)
        except requests.exceptions.ReadTimeout:
            logging.warning("Target %s: Timeout during release session on server '%s'", self.target, self.host)

    def getTarget(self):
        return self.target

    def getHost(self):
        return self.host

    def getPort(self):
        return 443

    def getManufactor(self):
        return self.manufacturer

    def getMetricBuilder(self):
        return self.metric

    def isConnected(self):
        return self._redfish_up

    def getSubUrls(self):
        systems = self.fetch(self.root_urls['Systems'])
        if not systems:
            return {}

        server_info = {}
        for member in systems['Members']:
            info = self.fetch(member['@odata.id'])
            if info:
                server_info.update(info)

        if not server_info:
            return {}

        self.manufacturer = server_info.get('Manufacturer')
        if not self.manufacturer and self.vendor:
            self.manufacturer = self.vendor

        self.model = server_info.get('Model')
        if not self.model and self.product:
            self.model = self.product

        power_state = server_info.get('PowerState')
        self.powerstate = POWER_STATES[power_state.lower()] if power_state else 0

        # Dell has the Serial# in the SKU field, others in the SerialNumber field.
        if "SKU" in server_info and re.match(r'^[Dd]ell.*', server_info['Manufacturer']):
            self.serial = server_info['SKU']
        else:
            self.serial = server_info['SerialNumber']

        self.server_health = HEALTH_STATES[server_info['Status']['Health'].lower()]

        labels = {
            "hostname": self.target,
            "server_manufacturer": self.manufacturer,
            "server_model": self.model,
            "server_serial": self.serial
        }

        self.metric.initBaseLabel(labels)

        self.metric.createMetricFamily("server_up", "Redfish Server Powerstate").addMetricSample(self.powerstate)
        self.metric.createMetricFamily("server_health", "Redfish Server Health").addMetricSample(self.server_health)

        if "Links" in server_info and "Chassis" in server_info['Links']:
            self.root_urls['Chassis'] = server_info['Links']['Chassis'][0] if isinstance(server_info['Links']['Chassis'][0], str) else server_info['Links']['Chassis'][0]['@odata.id']

        for k, v in server_info.items():
            if isinstance(v, dict) and "@odata.id" in v:
                self.sub_urls[k] = { "type": "System", "url": v['@odata.id'] }

        chassis = self.fetch( self.root_urls['Chassis'])
        if chassis:
            for k, v in chassis.items():
                if isinstance(v, dict) and "@odata.id" in v:
                    self.sub_urls[k] = { "type": "Chassis", "url": v['@odata.id'] }
            #for key in ['PowerSubsystem', 'Power', 'ThermalSubsystem', 'Thermal', 'Sensors']:
            #    if key in chassis:
            #        self.sub_urls[key] = chassis[key]['@odata.id']

        return self.sub_urls

    def fetch(self, command, auth=True):
        """Connect to the server and get the data."""
        server_response = None

        url = "https://{}{}".format(self.target, command)

        # check if we already established a session with the server
        if not self._session:
            session_type = "new"
            self._session = requests.Session()
        else:
            session_type = "reuse"

        self._session.verify = False
        self._session.headers.update({"charset": "utf-8"})
        self._session.headers.update({"content-type": "application/json"})

        if auth is None:
            auth_type = "no auth"
            self._session.auth = None
        elif auth == False:
            auth_type = "basic auth for user '{}'".format(self._username)
            self._session.auth = (self._username, self._password)
        else:
            auth_type = "auth token"
            self._session.auth = None
            self._session.headers.update({"X-Auth-Token": self._auth_token})

        logging.debug("Target %s: Url: %s, Auth: %s, Session: %s", self.target, url, auth_type, session_type)

        try:
            req = self._session.get(url, stream=True, timeout=self._timeout)
            req.raise_for_status()
            self._last_http_code = req.status_code
            try:
                data = req.json()
                if 'error' in data:
                    self._last_http_code = 500
                    logging.error("Target %s: '%s'", self.target, data['error'])
                else:
                    server_response = data
            except requests.JSONDecodeError:
                self._last_http_code = 500
                logging.error("Target %s: No json data received.", self.target)
        except requests.exceptions.HTTPError as err:
            self._last_http_code = err.response.status_code
            if err.response.status_code in [401,403]:
                logging.error("Target %s: Authorization Error: Wrong job provided or user/password set wrong on server '%s' - %s", self.target, self.host, err)
            else:
                logging.error("Target %s: HTTP Error on server '%s' - '%s'", self.target, self.host, err)

        except requests.exceptions.ConnectTimeout:
            self._last_http_code = 408
            logging.error("Target %s: Timeout while connecting to '%s'", self.target, self.host)
        except requests.exceptions.ReadTimeout:
            self._last_http_code = 408
            logging.error("Target %s: Timeout while reading data from '%s'", self.target, self.host)
        except requests.exceptions.ConnectionError as err:
            self._last_http_code = 444
            logging.error("Target %s: Unable to connect to '%s' - '%s'", self.target, self.host, err)
        except requests.exceptions.RequestException:
            self._last_http_code = 500
            logging.error("Target %s: Unexpected error '%s'", self.target, sys.exc_info()[0])

        return server_response
