from collectors._collector import Collector

class Handler(Collector):
    def process(self, name, url):
        power_data = self.session.fetch(url)
        if not power_data:
            return False

        healthMetricFamily = self.session.getMetricBuilder().createMetricFamily("power_health", "power health")
        readingMetricFamily = self.session.getMetricBuilder().createMetricFamily("power_reading", "power data")

        if name == "PowerSubsystem":
            if 'PowerSupplies' in power_data and '@odata.id' in power_data.get('PowerSupplies', {}):
                power_supplies = self.session.fetch(power_data.get("PowerSupplies").get("@odata.id"))
                if power_supplies is not None:
                    for power_supply in power_supplies['Members']:
                        psu_data = self.session.fetch(power_supply['@odata.id'])

                        # Check if power_supply data was received (connect_server returns "" on error)
                        if not psu_data or 'Metrics' not in psu_data:
                            continue

                        psu_labels = {
                            "psu_name": self.extractStringData(psu_data, "Name", "unknown"),
                            "psu_manufacturer": self.extractStringData(psu_data, "Manufacturer", "unknown"),
                            "psu_model": self.extractStringData(psu_data, "Model", "unknown")
                        }

                        psu_metrics = self.session.fetch(psu_data['Metrics']['@odata.id'])
                        if not psu_metrics:
                            continue

                        psu_health = self.extractHealthStatus(psu_metrics)
                        healthMetricFamily.addMetricSample(value=psu_health, labels=psu_labels)

                        deprecated_fields = {
                            "PowerInputWatts": "InputPowerWatts",
                            "PowerOutputWatts": "OutputPowerWatts"
                        }
                        for metric in ["PowerInputWatts", "PowerOutputWatts", "InputVoltage"]: # "PowerCapacityWatts", "InputCurrentAmps"]:
                            reading = psu_metrics.get(metric)

                            _metric = metric
                            if _metric not in psu_metrics:
                                if _metric in deprecated_fields:
                                    _metric = deprecated_fields.get(metric)
                                if _metric not in psu_metrics:
                                    continue

                            reading = psu_metrics[_metric].get('Reading')
                            if reading is None:
                                continue

                            current_labels = {'type': metric}
                            current_labels.update(psu_labels)
                            readingMetricFamily.addMetricSample(value=reading, labels=current_labels)
        # deprecated
        elif name == "Power":
            psu_data = power_data.get("PowerSupplies")
            if not psu_data:
                return

            for psu in psu_data:
                psu_health = self.extractHealthStatus(psu)
                psu_labels = {
                    "psu_name": self.extractStringData(psu, "Name", "unknown"),
                    "psu_manufacturer": "unknown",
                    "psu_model": self.extractStringData(psu, "Model", "unknown")
                }

                healthMetricFamily.addMetricSample(value=psu_health, labels=psu_labels)

                deprecated_fields = {
                    "InputVoltage": "LineInputVoltage"
                }
                for metric in ["PowerInputWatts", "PowerOutputWatts", "InputVoltage"]: # "PowerCapacityWatts",
                    reading = psu.get(metric)
                    if reading is None:
                        if metric in deprecated_fields:
                            reading = psu.get(deprecated_fields.get(metric))
                        if reading is None:
                            continue

                    current_labels = {'type': metric}
                    current_labels.update(psu_labels)
                    readingMetricFamily.addMetricSample(value=reading, labels=current_labels)
        return True
