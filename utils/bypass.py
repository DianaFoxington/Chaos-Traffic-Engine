import json
import ipaddress
import logging
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger('CTE.Bypass')

class BypassManager:

    def __init__(self, config_file='iranian_domains.json'):
        self.domains = set()
        self.ip_ranges = []
        self.download_mime_types = set()

        self._load_config(config_file)

        logger.info(f"Bypass enabled: {len(self.domains)} domains, {len(self.ip_ranges)} IP ranges")

    def _load_config(self, config_file: str):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

                self.domains = set(config.get('domains', []))

                ip_ranges_str = config.get('ip_ranges', [])
                for ip_range in ip_ranges_str:
                    try:
                        self.ip_ranges.append(ipaddress.ip_network(ip_range))
                    except ValueError as e:
                        logger.warning(f"Invalid IP range: {ip_range} - {e}")

                self.download_mime_types = set(config.get('download_mime_types', []))

        except FileNotFoundError:
            logger.warning(f"Config {config_file} not found, using defaults")
            self._set_defaults()
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            self._set_defaults()
        except Exception as e:
            logger.error(f"Error loading bypass config: {e}")
            self._set_defaults()

    def _set_defaults(self):
        self.domains = {'.ir', 'aparat.com', 'digikala.com'}
        self.ip_ranges = []
        self.download_mime_types = {
            'application/octet-stream',
            'application/zip',
            'video/mp4',
            'audio/mpeg'
        }

    def should_bypass_domain(self, hostname: str) -> bool:
        if not hostname:
            return False

        hostname = hostname.lower()

        if hostname in ['localhost', '127.0.0.1', '0.0.0.0', '::1']:
            return True

        if hostname in self.domains:
            return True

        for domain in self.domains:
            if domain.startswith('.') and hostname.endswith(domain):
                return True
            if not domain.startswith('.') and hostname.endswith('.' + domain):
                return True

        return False

    def should_bypass_ip(self, ip_address: str) -> bool:
        if not ip_address:
            return False

        try:
            ip = ipaddress.ip_address(ip_address)

            if ip.is_loopback or ip.is_private:
                return True

            for ip_range in self.ip_ranges:
                if ip in ip_range:
                    return True

            return False
        except ValueError:
            return False

    def should_bypass_mime(self, content_type: str) -> bool:
        if not content_type:
            return False

        mime_type = content_type.split(';')[0].strip().lower()

        return mime_type in self.download_mime_types

    def should_bypass_url(self, url: str, content_type: Optional[str] = None) -> bool:
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname

            if self.should_bypass_domain(hostname):
                logger.debug(f"Bypass Iranian domain: {hostname}")
                return True

            if content_type and self.should_bypass_mime(content_type):
                logger.debug(f"Bypass download file: {content_type}")
                return True

            return False

        except Exception as e:
            logger.debug(f"Error in bypass detection: {e}")
            return False

    def get_bypass_reason(self, url: str, content_type: Optional[str] = None) -> Optional[str]:
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname

            if self.should_bypass_domain(hostname):
                return f"Iranian domain: {hostname}"

            if content_type and self.should_bypass_mime(content_type):
                return f"Download file: {content_type}"

            return None

        except:
            return None