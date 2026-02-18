from collectors._collector import Collector

class Handler(Collector):
    def process(self, name, url):
        memory_collection = self.session.fetch(url)
        if not memory_collection:
            return False

        healthMetricFamily = self.session.getMetricBuilder().createMetricFamily("memory_health", "general memory health")
        correctableMetricFamily = self.session.getMetricBuilder().createMetricFamily("memory_correctable_health", "correctable memory health")
        uncorrectableMetricFamily = self.session.getMetricBuilder().createMetricFamily("memory_uncorrectable_health", "uncorrectable memory health")
        temperatureMetricFamily = self.session.getMetricBuilder().createMetricFamily("memory_temperature_health", "memmory temerature is critical")

        for dimm_url in memory_collection["Members"]:
            dimm_info = self.session.fetch(dimm_url["@odata.id"])
            if not dimm_info:
                continue

            dimm_health = self.extractHealthStatus(dimm_info)

            current_labels = {
                "dimm_name": self.extractStringData(dimm_info, "Name"),
                "dimm_capacity": self.extractStringData(dimm_info, "CapacityMiB"),
                "dimm_speed": self.extractStringData(dimm_info, "OperatingSpeedMhz", "unknown"),
                "dimm_type": self.extractStringData(dimm_info, "MemoryDeviceType"),
                "dimm_manufacturer": self.extractStringData(dimm_info, "Manufacturer", "unknown")
            }
            if "Oem" in dimm_info and "Hpe" in dimm_info["Oem"]:
                current_labels["device_manufacturer"] = self.extractStringData(dimm_info["Oem"]["Hpe"],"VendorName", "unknown")

            healthMetricFamily.addMetricSample(value=dimm_health, labels=current_labels)

            if "Metrics" in dimm_info:
                dimm_metrics = self.session.fetch(dimm_info["Metrics"]["@odata.id"])
                if not dimm_metrics:
                    continue

                health_data = dimm_metrics.get("HealthData", {}).get("AlarmTrips", {})

                if "CorrectableECCError" in health_data:
                    correctableMetricFamily.addMetricSample(value=health_data.get("CorrectableECCError"), labels=current_labels)
                if "UncorrectableECCError" in health_data:
                    uncorrectableMetricFamily.addMetricSample(value=health_data.get("UncorrectableECCError"), labels=current_labels)
                if "Temperature" in health_data:
                    temperatureMetricFamily.addMetricSample(value=health_data.get("Temperature"), labels=current_labels)

        return True
