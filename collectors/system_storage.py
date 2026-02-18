from collectors._collector import Collector

class Handler(Collector):
    def process(self, name, url):
        storage_collection = self.session.fetch(url)
        if not storage_collection:
            return False

        controllerMetricFamily = self.session.getMetricBuilder().createMetricFamily("storage_controller_health", "strorage controller health")
        diskMetricFamily = self.session.getMetricBuilder().createMetricFamily("storage_disk_health", "storage disk health")

        for controller in storage_collection["Members"]:
            controller_data = self.session.fetch(controller["@odata.id"])
            if not controller_data:
                continue

            storage_controllers = controller_data.get("StorageControllers", [])
            if storage_controllers:
                controller_details = storage_controllers[0] if isinstance(storage_controllers, list) else list(storage_controllers.values())[0]
                controller_health = self.extractHealthStatus(controller_details)

                current_labels = {
                    "controller_name": self.extractStringData(controller_details, "Name") or self.extractStringData(controller_data, "Name", "unknown"),
                    "controller_manufacturer": self.extractStringData(controller_details, "Manufacturer", "unknown"),
                    "controller_model": self.extractStringData(controller_details, "Model", "unknown"),
                }

                controllerMetricFamily.addMetricSample(value=controller_health, labels=current_labels)

            storage_drives = controller_data.get("Drives", [])
            if storage_drives:
                for disk in storage_drives:
                    disk_data = self.session.fetch(disk["@odata.id"])
                    if not disk_data:
                        continue

                    disk_health = self.extractHealthStatus(disk_data)

                    disk_attributes = {
                        "Name": "disk_name",
                        "MediaType": "disk_type",
                        "Manufacturer": "disk_manufacturer",
                        "Model": "disk_model",
                        "CapacityBytes": "disk_capacity",
                        "Protocol": "disk_protocol",
                    }
                    current_labels = {}
                    for disk_attribute, label_name in disk_attributes.items():
                        if disk_attribute in disk_data:
                            current_labels[label_name] = str(disk_data[disk_attribute])

                    diskMetricFamily.addMetricSample(value=disk_health, labels=current_labels)

        return True
