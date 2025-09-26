from app.shared.annotations import ApplicationScoped, Subscribe


@ApplicationScoped
class NotificationService:
    @Subscribe("order.placed")
    async def on_order_placed(self, event: dict):
        self.logger.info(f"Sending notification for order {event['id']}")
