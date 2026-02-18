from re import search

from collectors._collector import Collector


class Handler(Collector):
    def process(self):
        fw_collection = self.session.fetch("/redfish/v1/UpdateService/FirmwareInventory")
        if not fw_collection:
            return False

        metricFamily = self.session.getMetricBuilder().createMetricFamily("firmware", "firmware data")

        for fw_member in fw_collection['Members']:
            fw_member_url = fw_member['@odata.id']

            manufactor = self.session.getManufactor()

            # only look at entries on a Dell server if the device is marked as installed
            if search(".*Dell.*", manufactor) and "Installed" not in fw_member_url:
                continue

            fw_item = self.session.fetch(fw_member_url)
            if not fw_item:
                continue

            item_name = fw_item['Name'].split(",", 1)[0]
            current_labels = {"item_name": item_name}

            if manufactor == 'Lenovo':
                # Lenovo has always Firmware: in front of the names, let's remove it
                item_name = fw_item['Name'].replace('Firmware:','')
                current_labels.update({"item_name": item_name})
                # we need an additional label to distinguish the metrics because
                # the device ID is not in the name in case of Lenovo
                if "Id" in fw_item:
                    current_labels.update({"item_id": fw_item['Id']})

            if "Manufacturer" in fw_item:
                current_labels.update({"item_manufacturer": fw_item['Manufacturer']})

            if "Version" in fw_item:
                version = fw_item['Version']
                if version != "N/A" and version is not None:
                    current_labels.update({"version": version})
                    metricFamily.addMetricSample(value=1, labels=current_labels)

        return True
