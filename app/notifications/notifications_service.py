from app.shared.annotations.core import RequestScoped
from app.shared.annotations.core import ApplicationScoped
from app.shared.annotations.messaging import Consumer
from app.shared.annotations.logging import LoggerBinding
from app.shared.logger.john_wick_logger import JohnWickLogger

@RequestScoped
@LoggerBinding()
class NotificationService:
    def __init__(self,logger:JohnWickLogger=None):
        self.logger=logger

    @Consumer(topic="order.placed")
    async def on_order_placed(self, event: dict):
        self.logger.info(f"Sending notification for order {event['id']}")
