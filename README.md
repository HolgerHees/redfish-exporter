# Redfish-Exporter

This is a Prometheus Exporter for extracting metrics from a server using the Redfish API.

It has been tested with the following server models:

- Dell PowerEdge R640 
- Supermicro AS -2024US-TRT
- XFusion 2258 V7
- Gigabyte G492-Z50

## Using as a cli command

Redfish export can be used as a command line tool, to debug redfish data.

```
python main.py
usage: main.py [-h] [-c FILE] [-p FILE] [-d] [-t TARGET] [-j JOB] [-m MODULES]

options:
  -h, --help            show this help message and exit
  -c, --config FILE     Specify config yaml file
  -s, --secrets FILE    Specify additional secrets yaml file
  -d, --debug           Debugging mode
  -t, --target TARGET   Don't start as a service and use a target host instead
  -j, --job JOB         Job name
  -m, --modules MODULES Comma seperated module names
```

to run it, just call

```
python main.py --target myredfishinterface.mydomain.de --job redfish-job1
```

This call will fetch all available redfish metrics from your server

To limit the processed modules, just specify like `--module "Processors,Memory,Storage"`

## Using as a service

to start the service, just run it without a target parameter

```
python3 main.py
2026-02-17 09:47:19,155 24108                  main.py:79   INFO    Starting Redfish Prometheus Server ...
2026-02-17 09:47:19,158 24108                  main.py:86   INFO    Listening on Port 9220
```

to trigger a redfish service check, just call

```
curl "http://localhost:9220/?job=redfish-job1&target=myredfishinterface.mydomain.de"

```

To limit the processed modules, just specify like `&module=Processors,Memory,Storage`

## Configuration

### The config.yml file

```
listen_port: 9220
timeout: 30
#job: 'redfish-job1'
#modules: 'Processors,Memory'
#username: admin
#password: admin
```

- `listen_port` is the default service port if you start redfish exporter in service mode
- `timeout` is the default timeout for any redfish connection
- `job` is the default fallback, if not specified as a cli argument or a query parameter
- `modules` is the default fallback, if not specified as a cli argument or a query parameter
- `username` and `password` is the default fallback, if not specified in job.yml or ENV vars

All of these parameters can also be defined as a environment variable like `LISTEN_PORT`, `TIMEOUT`, `JOB`, `MODULES`, `USERNAME`, `PASSWORD`

### The secrets.yml file

```
REDFISH_JOB1_USERNAME: root
REDFISH_JOB1_PASSWORD: root123
```

Login credentials for servers, firewalls and switches can either be added to the secrets.yaml file or passed via environment variables. The environment variables are taking precedence over the entries in secrets.yaml file.

The mapping of job names to environment variables follows a schema: `REDFISH_JOB1_USERNAME` and `REDFISH_JOB1_PASSWORD` would be the variables for example of a job called `redfish-job1`.
A slash gets replaced by underscore and everything gets converted to uppercase.

The order of processing username/password data is

1. secrets.yml
2. env vars
3. fallback to config.yml

### Supported Modules

- Certificate
- Firmware
- Power (incl. PowerSubsystem)
- Sensors
- Thermal (incl. ThermalSubsystem)
- Bios
- Memory
- Processors
- Storage
- Ethernet, Network etc (coming soon)

When you activate `Sensors`, `Thermal` is also activated because they partially share values. The reverse is also true.
