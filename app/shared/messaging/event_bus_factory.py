"""
Lean EventBus factory with improved configuration and CDI integration.
"""

import os
import yaml
from typing import Dict, Any, Optional

from app.shared.annotations import ApplicationScoped, LoggerBinding


class EventBusConfig:
    """Simple configuration for EventBus."""
    
    def __init__(self, config_data: Dict[str, Any]):
        self.messaging = config_data.get('messaging', {}).get('eventbus', {})
        self.redis = config_data.get('redis', {})
        self.kafka = config_data.get('kafka', {})
        
        # Set defaults
        self.transport = self.messaging.get('transport', 'memory').lower()
        self.redis_host = self.redis.get('host', '127.0.0.1')
        self.redis_port = int(self.redis.get('port', 6379))
        self.redis_db = int(self.redis.get('db', 0))
        
        self.kafka_servers = self.kafka.get('bootstrap_servers', '127.0.0.1:9092')
        self.kafka_topic = self.kafka.get('topic', 'default-topic')
        self.kafka_group = self.kafka.get('group_id', 'default-group')
        self.kafka_dlq = self.kafka.get('dlq_topic', 'default-dlq')
    
    @classmethod
    def load(cls) -> 'EventBusConfig':
        """Load configuration from file."""
        config = {}
        
        # Try YAML first
        if os.path.exists('messaging.eventbus.yml'):
            with open('messaging.eventbus.yml', 'r') as f:
                config = yaml.safe_load(f) or {}
        
        # Try properties
        elif os.path.exists('messaging.eventbus.properties'):
            import configparser
            parser = configparser.ConfigParser()
            parser.read('messaging.eventbus.properties')
            config = {section: dict(parser.items(section)) for section in parser.sections()}
        
        return cls(config)


@ApplicationScoped
class EventBusFactory:
    """Simplified EventBus factory with CDI integration."""
    
    def __init__(self, logger=None):
        from app.shared.logger.john_wick_logger import create_logger
        self.logger = logger or create_logger("EventBusFactory")
        self._event_bus = None
        self._config = EventBusConfig.load()
    
    def create_event_bus(self):
        """Create and return EventBus instance."""
        if self._event_bus:
            return self._event_bus
        
        self.logger.info(f"Creating EventBus with transport: {self._config.transport}")
        
        if self._config.transport == 'redis':
            self._event_bus = self._create_redis_bus()
        elif self._config.transport == 'kafka':
            self._event_bus = self._create_kafka_bus()
        else:
            self._event_bus = self._create_memory_bus()
        
        return self._event_bus
    
    def _create_memory_bus(self):
        """Create in-memory EventBus."""
        from app.shared.messaging.transports.in_process_eventbus import InProcessEventBus
        self.logger.info("Using InProcessEventBus")
        return InProcessEventBus(logger=self.logger)
    
    def _create_redis_bus(self):
        """Create Redis EventBus."""
        from app.shared.messaging.transports.redis_bus import RedisEventBus
        redis_url = f"redis://{self._config.redis_host}:{self._config.redis_port}/{self._config.redis_db}"
        self.logger.info(f"Using RedisEventBus with URL: {redis_url}")
        return RedisEventBus(redis_url=redis_url, logger=self.logger)
    
    def _create_kafka_bus(self):
        """Create Kafka EventBus."""
        from app.shared.messaging.transports.kafka_bus import KafkaEventBus
        from app.shared.clients import KafkaClient
        
        kafka_client = KafkaClient(
            bootstrap_servers=self._config.kafka_servers,
            group_id=self._config.kafka_group,
            topics=[self._config.kafka_topic],
            dlq_topic=self._config.kafka_dlq
        )
        
        self.logger.info(f"Using KafkaEventBus with servers: {self._config.kafka_servers}")
        return KafkaEventBus(kafka_client=kafka_client, logger=self.logger)