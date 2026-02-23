import json
import logging
import random
from typing import Optional, List

logger = logging.getLogger('CTE.Fronting')

class DomainFronter:

    def __init__(self, config_file: str = 'cdn_domains.json', enabled: bool = True):
        self.enabled = enabled
        self.cdn_domains = {}

        if enabled:
            self._load_cdn_domains(config_file)

            total_domains = sum(len(domains) for domains in self.cdn_domains.values())
            logger.info(
                f"✓ Domain Fronting: {len(self.cdn_domains)} CDNs, "
                f"{total_domains} domains"
            )
        else:
            logger.info("Domain Fronting: disabled")

    def _load_cdn_domains(self, config_file: str):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.cdn_domains = config.get('cdn_domains', {})

        except FileNotFoundError:
            logger.warning(f"CDN config {config_file} not found, using defaults")
            self._set_default_domains()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {config_file}: {e}")
            self._set_default_domains()
        except Exception as e:
            logger.error(f"Error loading CDN domains: {e}")
            self._set_default_domains()

    def _set_default_domains(self):
        self.cdn_domains = {
            'cloudflare': ['www.cloudflare.com'],
            'akamai': ['www.akamai.com'],
            'google': ['www.google.com']
        }

    def select_front_domain(
        self,
        cdn_provider: Optional[str] = None,
        real_domain: Optional[str] = None
    ) -> Optional[str]:
        if not self.enabled or not self.cdn_domains:
            return None

        if cdn_provider and cdn_provider in self.cdn_domains:
            provider = cdn_provider
        else:
            provider = random.choice(list(self.cdn_domains.keys()))

        domains = self.cdn_domains.get(provider, [])
        if not domains:
            return None

        front_domain = random.choice(domains)

        if real_domain:
            logger.info(
                f"🎭 Domain Fronting: {real_domain} -> {front_domain} "
                f"(via {provider})"
            )

        return front_domain

    def get_available_cdns(self) -> List[str]:
        return list(self.cdn_domains.keys())

    def get_cdn_domains(self, cdn_provider: str) -> List[str]:
        return self.cdn_domains.get(cdn_provider, [])