from collectors._collector import Collector
from collectors import chassis_sensors

class Handler(Collector):
    def process(self, name, url):
        thermal_data = self.session.fetch(url)
        if thermal_data is None:
            return False

        healthMetricFamily = self.session.getMetricBuilder().createMetricFamily("fan_health", "fan health")
        speedMetricFamily = self.session.getMetricBuilder().createMetricFamily("fan_reading", "fan data")

        sensorMetricFamily = chassis_sensors.Handler.getSensorMetricFamily(self.session)

        if name == "ThermalSubsystem":
            if 'Fans' in thermal_data and '@odata.id' in thermal_data.get('Fans', {}):
               fans = self.session.fetch(thermal_data.get("Fans").get("@odata.id"))
               if fans is not None:
                    for fan_url in fans["Members"]:
                        fan_info = self.session.fetch(fan_url["@odata.id"])

                        raw_status = self.extractHealthRawStatus(fan_info)
                        fan_health = self.extractHealthStatus(fan_info)

                        current_labels = {
                            "fan_state": raw_status,
                            "fan_name": self.extractStringData(fan_info, "Name", "unknown")
                        }
                        healthMetricFamily.addMetricSample(value=fan_health, labels=current_labels)

                        if raw_status != "enabled":
                            continue

                        fan_reading = fan_info.get('SpeedPercent').get('SpeedRPM')
                        if fan_reading is not None:
                            current_labels = {
                                "fan_name": self.extractStringData(fan_info, "Name", "unknown"),
                                "fan_unit": "RPM",
                            }
                            speedMetricFamily.addMetricSample(value=fan_reading, labels=current_labels)

            #if 'ThermalMetrics' in thermal_data and '@odata.id' in thermal_data.get('ThermalMetrics', {}):
            #    sensors = self.session.fetch(thermal_data.get("ThermalMetrics").get("@odata.id"))
            #    if sensors is not None:
            #        thermal_metrics = sensors.get('TemperatureReadingsCelsius', {})
            #        for data in thermal_metrics:
            #            reading = data.get('Reading')
            #            if reading is None:
            #                continue

            #            chassis_sensors.Handler.addSensorMetric(
            #                sensorMetricFamily,
            #                None,
            #                self.extractStringData(data, "DeviceName", ""),
            #                "Temperature",
            #                "C",
            #                None,
            #                float(reading)
            #            )

        # deprecated
        elif name == "Thermal":
            fans = thermal_data.get("Fans", [])
            for fan in fans:
                raw_status = self.extractHealthRawStatus(fan)
                fan_health = self.extractHealthStatus(fan)

                current_labels = {
                    "fan_state": raw_status,
                    "fan_name": self.extractStringData(fan, "Name", "unknown")
                }
                healthMetricFamily.addMetricSample(value=fan_health, labels=current_labels)

                if raw_status != "enabled":
                    continue

                fan_reading = fan.get('Reading')
                if fan_reading is not None:
                    current_labels = {
                        "fan_name": self.extractStringData(fan, "Name", "unknown"),
                        "fan_unit": self.extractStringData(fan, "ReadingUnits", "unknown"),
                    }
                    speedMetricFamily.addMetricSample(value=fan_reading, labels=current_labels)

            #sensors = thermal_data.get("Temperatures", [])
            #for sensor in sensors:
            #    raw_status = self.extractHealthRawStatus(sensor)
            #    if raw_status != "enabled":
            #        continue

            #    reading = sensor.get('ReadingCelsius')
            #    if reading is None:
            #        continue

            #    chassis_sensors.Handler.addSensorMetric(
            #        sensorMetricFamily,
            #        self.extractStringData(sensor, "MemberId", "unknown"),
            #        self.extractStringData(sensor, "Name", "unknown"),
            #        "Temperature",
            #        "C",
            #        self.extractStringData(sensor, "PhysicalContext", "unknown"),
            #        float(reading)
            #    )

        return True
















