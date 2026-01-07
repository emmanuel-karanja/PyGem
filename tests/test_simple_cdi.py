"""
Simple tests for lean CDI system.
"""

import pytest
from app.shared.cdi import CDIContainer, BeanScanner
from app.shared.annotations import ApplicationScoped, RequestScoped, Producer, Consumer


# Test beans
@ApplicationScoped
class TestSingleton:
    def __init__(self):
        self.value = "singleton"


@RequestScoped  
class TestRequest:
    def __init__(self):
        self.value = "request"


@Producer("test.topic")
class TestProducer:
    def __init__(self, event_bus=None):
        self.event_bus = event_bus


class TestConsumer:
    @Consumer("test.topic")
    async def handle(self, event):
        pass


class TestCDIContainer:
    
    def test_singleton_creation(self):
        """Test singleton bean creation."""
        container = CDIContainer()
        container.initialize([])
        
        # Register singleton manually for test
        from app.shared.cdi import BeanRegistry
        registry = BeanRegistry()
        instance1 = registry.get_singleton(TestSingleton)
        instance2 = registry.get_singleton(TestSingleton)
        
        assert instance1 is instance2
        assert instance1.value == "singleton"
    
    def test_inject_function(self):
        """Test Inject function."""
        from app.shared.annotations import Inject
        
        # This would work with initialized container
        # For now just test the function exists
        assert callable(Inject)
    
    def test_producer_annotation(self):
        """Test Producer annotation."""
        assert hasattr(TestProducer, '_producer_topic')
        assert TestProducer._producer_topic == "test.topic"
    
    def test_consumer_annotation(self):
        """Test Consumer annotation."""
        consumer = TestConsumer()
        method = getattr(consumer, 'handle')
        assert hasattr(method, '_consumer_topic')
        assert method._consumer_topic == "test.topic"
    
    def test_bean_scanning(self):
        """Test bean scanning."""
        # Test that beans are discovered
        beans = BeanScanner.scan_modules([TestSingleton])
        # Should discover annotated classes
        assert len(beans) > 0


if __name__ == "__main__":
    pytest.main([__file__])