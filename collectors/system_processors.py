from collectors._collector import Collector

class Handler(Collector):
    def process(self, name, url):
        processor_collection = self.session.fetch(url)

        if not processor_collection:
            return False

        metricFamily = self.session.getMetricBuilder().createMetricFamily("processor_health", "processor health")

        for processor in processor_collection["Members"]:
            processor_data = self.session.fetch(processor["@odata.id"])

            if not processor_data:
                continue

            proc_status = self.extractHealthStatus(processor_data)

            current_labels = {
                "cpu_name": self.extractStringData(processor_data, "Socket", "unknown"),
                "cpu_manufacturer": self.extractStringData(processor_data, "Manufacturer", "unknown"),
                "cpu_type": self.extractStringData(processor_data, "ProcessorType", "unknown"),
                "cpu_model": self.extractStringData(processor_data, "Model", "unknown"),
                "cpu_cores": self.extractStringData(processor_data, "TotalCores", "unknown"),
                "cpu_threads": self.extractStringData(processor_data, "TotalThreads", "unknown"),
            }

            metricFamily.addMetricSample(value=proc_status, labels=current_labels)

        return True
