import logging
import ssl
import datetime
import OpenSSL

from collectors._collector import Collector

class Handler(Collector):
    def process(self):
        cert = None
        x509 = None
        cert_days_left = 0
        cert_valid = 0
        cert_has_right_hostname = 0
        cert_selfsigned = 0
        current_labels = {
            "issuer": "n/a",
            "subject": "n/a",
            "not_after": "n/a",
        }

        try:
            cert = ssl.get_server_certificate((self.session.getHost(), self.session.getPort()))
            x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cert)

        except OpenSSL.SSL.Error as e:
            logging.debug("Target %s: Certificate Validation Error!", self.session.getTarget())
            logging.debug("Target %s: %s", self.session.getTarget(), e)

        if cert and x509:
            subject = [
                value.decode('utf-8') for name, value in x509.get_subject().get_components()
                if name.decode('utf-8') == 'CN'
            ][0]
            issuer = [
                value.decode('utf-8') for name, value in x509.get_issuer().get_components()
                if name.decode('utf-8') == 'CN'
            ][0]

            not_after_str = x509.get_notAfter().decode('utf-8')

            cert_expiry_date = datetime.datetime.strptime(
                not_after_str, '%Y%m%d%H%M%S%fZ'
            ) if not_after_str else datetime.datetime.now()

            cert_days_left = (cert_expiry_date - datetime.datetime.now()).days

            current_labels.update({
                "issuer": issuer,
                "subject": subject,
                "not_after": cert_expiry_date.strftime("%Y-%m-%d %H:%M:%S"),
            })

            if issuer == subject:
                cert_selfsigned = 1

            if subject == self.session.getHost():
                cert_has_right_hostname = 1

            if cert_days_left > 0:
                if cert_has_right_hostname:
                    cert_valid = 1

        self.session.getMetricBuilder().createMetricFamily("certificate_isvalid", "certificate is valid").addMetricSample(value = cert_valid, labels = current_labels)
        self.session.getMetricBuilder().createMetricFamily("certificate_valid_hostname", "certificate has valid hostname").addMetricSample(value = cert_has_right_hostname, labels = current_labels)
        self.session.getMetricBuilder().createMetricFamily("certificate_valid_days", "certificate valid for days").addMetricSample(value = cert_days_left, labels = current_labels)
        self.session.getMetricBuilder().createMetricFamily("certificate_selfsigned", "certificate is self-signed").addMetricSample(value = cert_selfsigned, labels = current_labels)

        return True
