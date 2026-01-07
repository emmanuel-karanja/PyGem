"""
PyGem Bootstrap Configuration
Quarkus-inspired bootstrap and configuration management.
"""

import os
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path


class BootstrapConfig:
    """Central configuration for PyGem framework."""
    
    def __init__(self):
        self.profile = os.getenv("PYGEM_PROFILE", "dev")
        self.config_file = os.getenv("PYGEM_CONFIG", "pygem.yml")
        self.packages = ["app"]
        self.server = {
            "host": "127.0.0.1",
            "port": 8002
        }
        self.messaging = {
            "transport": "memory"
        }
        self.logging = {
            "level": "INFO",
            "format": "structured"
        }
        self.health = {
            "enabled": True,
            "path": "/health"
        }
        
        self.load_config()
    
    def load_config(self):
        """Load configuration from file and environment."""
        config_data = {}
        
        # Load from file
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                config_data = yaml.safe_load(f) or {}
        
        # Override with environment variables
        self._apply_env_overrides(config_data)
        
        # Merge configuration
        self._merge_config(config_data)
    
    def _apply_env_overrides(self, config_data: Dict[str, Any]):
        """Apply environment variable overrides."""
        env_mappings = {
            "PYGEM_PACKAGES": ("packages", lambda v: v.split(",")),
            "PYGEM_SERVER_HOST": ("server.host", str),
            "PYGEM_SERVER_PORT": ("server.port", int),
            "PYGEM_MESSAGING_TRANSPORT": ("messaging.transport", str),
            "PYGEM_LOG_LEVEL": ("logging.level", str),
            "PYGEM_LOG_FORMAT": ("logging.format", str),
        }
        
        for env_var, (path, converter) in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                self._set_nested(config_data, path, converter(value))
    
    def _set_nested(self, config: Dict[str, Any], path: str, value: Any):
        """Set nested configuration value."""
        keys = path.split('.')
        current = config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def _merge_config(self, config_data: Dict[str, Any]):
        """Merge configuration data into current config."""
        if "packages" in config_data:
            self.packages = config_data["packages"]
        
        if "server" in config_data:
            self.server.update(config_data["server"])
        
        if "messaging" in config_data:
            self.messaging.update(config_data["messaging"])
        
        if "logging" in config_data:
            self.logging.update(config_data["logging"])
        
        if "health" in config_data:
            self.health.update(config_data["health"])
    
    def get_server_url(self) -> str:
        """Get full server URL."""
        return f"http://{self.server['host']}:{self.server['port']}"
    
    def is_dev_profile(self) -> bool:
        """Check if running in development profile."""
        return self.profile == "dev"
    
    def is_prod_profile(self) -> bool:
        """Check if running in production profile."""
        return self.profile == "prod"


class Bootstrap:
    """Quarkus-inspired bootstrap for PyGem applications."""
    
    def __init__(self):
        self.config = BootstrapConfig()
        self._bootstrapped = False
    
    def bootstrap(self, packages: Optional[List[str]] = None):
        """Bootstrap the PyGem application."""
        if self._bootstrapped:
            return
        
        print(f"Bootstrapping PyGem application (profile: {self.config.profile})")
        
        # Override packages if provided
        if packages:
            self.config.packages = packages
        
        # Initialize CDI system
        self._initialize_cdi()
        
        # Configure logging
        self._configure_logging()
        
        # Bootstrap messaging
        self._bootstrap_messaging()
        
        # Bootstrap health checks
        self._bootstrap_health()
        
        self._bootstrapped = True
        print("PyGem bootstrapped successfully")
        print(f"   Server: {self.config.get_server_url()}")
        print(f"   Packages: {self.config.packages}")
        print(f"   Messaging: {self.config.messaging['transport']}")
    
    def _initialize_cdi(self):
        """Initialize CDI container."""
        from app.shared.cdi import initialize_cdi
        container = initialize_cdi(self.config.packages)
        print(f"   CDI: Initialized {len(container._beans)} beans")
    
    def _configure_logging(self):
        """Configure application logging."""
        import logging
        
        # Set root logger level
        level = getattr(logging, self.config.logging['level'].upper(), logging.INFO)
        logging.getLogger().setLevel(level)
        
        print(f"   Logging: {self.config.logging['level']} ({self.config.logging['format']})")
    
    def _bootstrap_messaging(self):
        """Bootstrap messaging system."""
        # Create messaging config for EventBusFactory
        messaging_config = {
            'messaging': {
                'eventbus': self.config.messaging
            }
        }
        
        # Write messaging config
        config_file = 'messaging.eventbus.yml'
        with open(config_file, 'w') as f:
            yaml.dump(messaging_config, f, default_flow_style=False)
        
        print(f"   Messaging: {config_file} configured")
    
    def _bootstrap_health(self):
        """Bootstrap health check system."""
        if self.config.health['enabled']:
            print(f"   Health: {self.config.health['path']} enabled")
    
    def get_config(self) -> BootstrapConfig:
        """Get bootstrap configuration."""
        return self.config


# Global bootstrap instance
_bootstrap: Optional[Bootstrap] = None


def get_bootstrap() -> Bootstrap:
    """Get global bootstrap instance."""
    global _bootstrap
    if _bootstrap is None:
        _bootstrap = Bootstrap()
    return _bootstrap