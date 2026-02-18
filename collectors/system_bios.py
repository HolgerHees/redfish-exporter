import re

from collectors._collector import Collector

class Handler(Collector):
    def __init__(self, session):
        super().__init__(session)

        self.bios_metrics = {}

    def process(self, name, url):
        bios_data = self.session.fetch(url)
        if not bios_data:
            return False

        # Check for pending BIOS changes
        has_pending_changes = 1 if '@Redfish.Settings' in bios_data else 0
        self.session.getMetricBuilder().createMetricFamily("bios_pending_changes", "bios has pending changes").addMetricSample(value=has_pending_changes)

        # Get BIOS attributes
        if 'Attributes' in bios_data:
            attributes = bios_data['Attributes']

            for attr_name, attr_value in attributes.items():
                # Skip vendor-specific device configuration attributes
                # e.g., Broadcom* attributes that are having complex names and create metric names longer than 80 characters
                # Seen on Lenovo ThinkSystem SR675 V3
                if attr_name.startswith('Broadcom'):
                    continue

                metric_name = "system_bios_{}".format(self.camel_to_snake(attr_name))

                # Create metric if it doesn't exist yet
                if metric_name not in self.bios_metrics:
                    self.bios_metrics[metric_name] = self.session.getMetricBuilder().createMetricFamily(metric_name, f"bios setting: {attr_name}")


                current_labels = {
                    "setting_name": attr_name
                }

                # Handle different value types
                if isinstance(attr_value, (int, float)):
                    numeric_value = float(attr_value)
                elif isinstance(attr_value, bool):
                    numeric_value = 1 if attr_value else 0
                elif isinstance(attr_value, str):
                    # Check if string is a boolean-like value
                    if attr_value.lower() == 'enabled':
                        numeric_value = 1
                    elif attr_value.lower() == 'disabled':
                        numeric_value = 0
                    else:
                        # For other string values, store as info metric with value 1
                        current_labels["setting_value"] = str(attr_value)
                        numeric_value = 1
                else:
                    # Skip unsupported types
                    continue

                self.bios_metrics[metric_name].addMetricSample(value=numeric_value, labels=current_labels)

        return True

    def camel_to_snake(self, name):
        """
        Convert camelCase or PascalCase to snake_case.
        Examples: AcPwrRcvry -> ac_pwr_rcvry, BootMode -> boot_mode
        """
        # Insert underscore before uppercase letters that follow lowercase letters or numbers
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        # Insert underscore before uppercase letters that follow lowercase letters
        s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
        return s2.lower()

