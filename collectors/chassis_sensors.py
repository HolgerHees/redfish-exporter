from collectors._collector import Collector

class Handler(Collector):
    def process(self, name, url):
        sensors_data = self.session.fetch(url)
        if sensors_data is None:
            return False

        metricFamily = session.getMetricBuilder().createMetricFamily("sensor_reading", "sensor data")

        for sensor in sensors_data['Members']:
            metric_info = self.session.fetch(sensor['@odata.id'])
            raw_status = self.extractHealthRawStatus(metric_info)
            if raw_status != "enabled":
                continue

            reading = metric_info.get('Reading')
            if reading is None:
                continue

            reading_type = self.extractStringData(metric_info, "ReadingType", "unknown")
            if reading_type.lower() == "rotational":
                continue

            self.addSensorMetric(
                metricFamily,
                self.extractStringData(metric_info, "Id", "unknown"),
                self.extractStringData(metric_info, "Name", "unknown"),
                reading_type,
                self.extractStringData(metric_info, "ReadingUnits", "unknown"),
                self.extractStringData(metric_info, "PhysicalContext", "unknown"),
                #self.extractStringData(metric_info, "ElectricalContext", "unknown"),
                float(reading)
            )

        return True

    def addSensorMetric(metricFamily, id, name, type, unit, context, value):
        current_labels = {
            "sensor_name": name,
            "sensor_type": type,
            "sensor_unit": unit
        }

        if id is not None:
            current_labels["sensor_id"] = id

        if context is not None:
            current_labels["sensor_context"] = id

        #units = metric.get('ReadingUnits')
        #is_counter = units in ["kW.h", "kWh", "Joules"]

        metricFamily.addMetricSample(value=value, labels=current_labels)

