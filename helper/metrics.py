import math
import logging

from prometheus_client.core import GaugeMetricFamily
from prometheus_client.exposition import generate_latest

class MetricsFamily:
    def __init__(self, name, description, labels = {}):
        self.name = name
        self.labels = labels
        self.gaugeMetricFamily = GaugeMetricFamily("redfish_" + self.name, description, labels=labels)

    def addMetricSample(self, value, labels = {}, name_suffix = None):
        try:
            value = int(value)
        except (ValueError, TypeError):
            return

        labels.update(self.labels)
        self.gaugeMetricFamily.add_sample("redfish_" + self.name + ("_" + name_suffix if name_suffix is not None else ""), value=value, labels=labels)

class Metrics:
    def __init__(self):
        self.metricFamily = []
        self.used = {}
        self.base_label = {}

    def initBaseLabel(self, base_label):
        self.base_label = base_label

    def createMetricFamily(self, name, description, labels = {}):
        labels.update(self.base_label)
        self.metricFamily.append(MetricsFamily(name, description, labels))
        return self.metricFamily[-1]

    def collect(self):
        result = []
        for group in self.metricFamily:
            if len(group.gaugeMetricFamily.samples) == 0:
                continue
            result.append(group.gaugeMetricFamily)
        return result

    def dump(self):
        return generate_latest(self)
