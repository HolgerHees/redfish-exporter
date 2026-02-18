"""
Redfish Prometheus Exporter
"""
import argparse
import logging
import os
import warnings
import sys

from wsgiref.simple_server import make_server, WSGIServer, WSGIRequestHandler
from socketserver import ThreadingMixIn
import yaml

import falcon
import importlib

from helper.session import RedfishSession
from helper.metrics import Metrics

from prometheus_client.exposition import CONTENT_TYPE_LATEST


class _SilentHandler(WSGIRequestHandler):
    """WSGI handler that does not log requests."""

    def log_message(self, format, *args): # pylint: disable=redefined-builtin
        """Log nothing."""


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """Thread per request HTTP server."""

class Configuration:
    def __init__(self, cli_config):
        try:
            with open(cli_config.config, "r", encoding="utf8") as config_file:
                yaml_config = yaml.load(config_file.read(), Loader=yaml.FullLoader)
        except FileNotFoundError as err:
            print(f"Config File not found: {err}")
            sys.exit(1)

        self.listen_port = int(os.getenv("LISTEN_PORT", yaml_config.get('listen_port', 9200)))
        self.timeout = int(os.getenv("TIMEOUT", yaml_config.get('timeout', 10)))
        self.username = os.getenv("USERNAME", yaml_config.get('username'))
        self.password = os.getenv("PASSWORD", yaml_config.get('password'))

        self.job = cli_config.job if cli_config.job else os.getenv("JOB", yaml_config.get("job"))
        self.modules = cli_config.modules if cli_config.modules else os.getenv("MODULES", yaml_config.get("modules"))

        self.debug = cli_config.debug
        self.target = cli_config.target

        try:
            with open(cli_config.secrets, "r", encoding="utf8") as secrets_file:
                self.secret_configs = yaml.load(secrets_file.read(), Loader=yaml.FullLoader)
        except FileNotFoundError as err:
            self.secret_configs = {}
            logging.info("Password file not found")

    def getJobCredentials(self, job):
        usr_env_var = job.replace("-", "_").upper() + "_USERNAME"
        pwd_env_var = job.replace("-", "_").upper() + "_PASSWORD"
        _username = os.getenv(usr_env_var, self.secret_configs.get(usr_env_var, self.username))
        _password = os.getenv(pwd_env_var, self.secret_configs.get(pwd_env_var, self.password))
        return _username, _password

class Handler:
    def __init__(self, config):
        """
        Start the Falcon API or process cli
        """
        self.config = config

        if config.target:
            metrics = self._process(config.target, config.job, config.modules)
            if metrics  is not None:
                print(metrics.decode('utf-8'))
        else:
            port = int(os.getenv("LISTEN_PORT", config.listen_port))
            addr = "0.0.0.0"
            logging.info("Starting Redfish Prometheus Server ...")

            api = falcon.API()
            api.add_route("/metrics", self)
            api.add_route("/health", self)

            with make_server(addr, port, api, ThreadingWSGIServer, handler_class=_SilentHandler) as httpd:
                httpd.daemon = True # pylint: disable=attribute-defined-outside-init
                logging.info("Listening on Port %s", port)
                try:
                    httpd.serve_forever()
                except (KeyboardInterrupt, SystemExit):
                    logging.info("Stopping Redfish Prometheus Server")
                    sys.exit(0)

    def on_get(self, req, resp):
        """
        Define the GET method for the API.
        """
        if req.path == "/health":
            resp.text = b"ok"
            resp.status = falcon.HTTP_200
        else:
            target = req.get_param("target")
            if not target:
                logging.error("No target parameter provided!")
                raise falcon.HTTPMissingParam("target")

            job = req.get_param("job")
            if not job:
                job = self.config.job

            modules = req.get_param("modules")
            if not modules:
                modules = self.config.modules

            resp.set_header("Content-Type", CONTENT_TYPE_LATEST)

            metrics = self._process(target, job, modules)
            if metrics  is not None:
                resp.text = metrics
                resp.status = falcon.HTTP_200
            else:
                resp.status = falcon.HTTP_500

    def _process(self, target, job, modules):
        modules = modules.split(",") if modules else None
        metrics = Metrics()

        with RedfishSession(self.config, target, job, modules, metrics) as session:
            if not session.isConnected():
                return metrics.dump()

            sub_urls = session.getSubUrls()


            if not modules or "Certificate" in modules:
                collector = importlib.import_module("collectors.base_certificate")
                collector.Handler(session).process()

            if not modules or "Firmware" in modules:
                collector = importlib.import_module("collectors.base_firmware")
                collector.Handler(session).process()

            if modules:
                # ThermalSubsystem contains parts of Sensors
                if "Sensors" in modules and "Thermal" not in modules:
                    modules.append("Thermal")
                elif "Thermal" in modules and "Sensors" not in modules:
                    modules.append("Sensors")

            mappend_modules = {}
            if "ThermalSubsystem" in sub_urls:
                mappend_modules["Thermal"] = "ThermalSubsystem"
                sub_urls["Thermal"] = sub_urls["ThermalSubsystem"]
                del sub_urls["ThermalSubsystem"]
            if "PowerSubsystem" in sub_urls:
                mappend_modules["Power"] = "PowerSubsystem"
                sub_urls["Power"] = sub_urls["PowerSubsystem"]
                del sub_urls["PowerSubsystem"]
            known_types = []
            unkown_types = []
            success_types = []
            failed_types = []
            for name, data in sub_urls.items():
                identifier = "{} / {}".format(data["type"], name)

                try:
                    collector = importlib.import_module("collectors.{}".format("{}_{}".format(data["type"], name).lower()))
                    known_types.append(identifier)
                except ModuleNotFoundError:
                    unkown_types.append(identifier)
                    continue

                if modules and name not in modules:
                   continue

                is_success = collector.Handler(session).process(mappend_modules.get(name, name), data["url"])
                if is_success:
                    success_types.append(identifier)
                else:
                    failed_types.append(identifier)

            known_types.sort()
            unkown_types.sort()

            #print(sub_urls.keys())

            logging.debug("KNOWN TYPES: {}".format(known_types))
            logging.debug("UNKNOWN TYPES: {}".format(unkown_types))
            logging.debug("SUCCESS TYPES: {}".format(success_types))
            logging.debug("FAILED TYPES: {}".format(failed_types))

        return metrics.dump()

def get_args():
    """
    Get the command line arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        help="Specify config yaml file",
        metavar="FILE",
        required=False,
        default="config.yml"
    )
    parser.add_argument(
        "-s",
        "--secrets",
        help="Specify additional secrets yaml file",
        metavar="FILE",
        required=False,
        default="secrets.yml"
    )

    parser.add_argument(
        "-d", "--debug", 
        help="Debugging mode",
        action="store_true",
        required=False
    )

    parser.add_argument(
        "-t", "--target",
        help="Don't start as a service and use a target url instead",
        required=False
    )

    parser.add_argument(
        "-j", "--job",
        help="Job name",
        required=False
    )

    parser.add_argument(
        "-m", "--modules",
        help="Comma seperated module names",
        required=False
    )

    return parser.parse_args()


if __name__ == "__main__":

    config = Configuration(get_args())

    warnings.filterwarnings("ignore")
    logger = logging.getLogger()
    logger.setLevel("DEBUG" if config.debug else "INFO")

    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter('%(asctime)-15s %(process)d %(filename)24s:%(lineno)-4d %(levelname)-7s %(message)s'))
    logger.addHandler(sh)

    Handler(config)
