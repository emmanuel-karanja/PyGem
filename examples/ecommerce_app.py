"""
PyGem Example: Complete E-commerce Application
Demonstrates Quarkus-inspired patterns with CDI, events, and health checks.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.application import PyGemApplication, create_app
from app.shared.annotations import ApplicationScoped, LoggerBinding, Producer, Consumer
from fastapi import APIRouter
from typing import Dict, List
import asyncio
from datetime import datetime


# ============================================================================
# DOMAIN MODELS
# ============================================================================

class User:
    def __init__(self, id: str, name: str, email: str):
        self.id = id
        self.name = name
        self.email = email
        self.created_at = datetime.utcnow()


class Product:
    def __init__(self, id: str, name: str, price: float):
        self.id = id
        self.name = name
        self.price = price


class Order:
    def __init__(self, id: str, user_id: str, items: List[Dict]):
        self.id = id
        self.user_id = user_id
        self.items = items
        self.total = sum(item['price'] for item in items)
        self.status = "PENDING"
        self.created_at = datetime.utcnow()


# ============================================================================
# SERVICES
# ============================================================================

@ApplicationScoped
@LoggerBinding()
class UserRepository:
    """User domain service."""
    
    def __init__(self, logger):
        self.logger = logger
        self._users = {}  # In-memory storage
    
    async def save(self, user: User) -> User:
        self._users[user.id] = user
        self.logger.info(f"Saved user: {user.id}")
        return user
    
    async def find_by_id(self, user_id: str) -> User:
        user = self._users.get(user_id)
        self.logger.debug(f"Found user {user_id}: {user is not None}")
        return user
    
    async def find_all(self) -> List[User]:
        return list(self._users.values())


@ApplicationScoped
@LoggerBinding()
class OrderRepository:
    """Order domain service."""
    
    def __init__(self, logger):
        self.logger = logger
        self._orders = {}  # In-memory storage
    
    async def save(self, order: Order) -> Order:
        self._orders[order.id] = order
        self.logger.info(f"Saved order: {order.id}")
        return order
    
    async def find_by_id(self, order_id: str) -> Order:
        return self._orders.get(order_id)
    
    async def find_by_user(self, user_id: str) -> List[Order]:
        return [order for order in self._orders.values() if order.user_id == user_id]


@ApplicationScoped
@LoggerBinding()
class ProductRepository:
    """Product domain service."""
    
    def __init__(self, logger):
        self.logger = logger
        self._products = {}  # In-memory storage
    
    async def save(self, product: Product) -> Product:
        self._products[product.id] = product
        self.logger.info(f"Saved product: {product.id}")
        return product
    
    async def find_by_id(self, product_id: str) -> Product:
        return self._products.get(product_id)
    
    async def find_all(self) -> List[Product]:
        return list(self._products.values())


# ============================================================================
# APPLICATION SERVICES
# ============================================================================

@ApplicationScoped
@LoggerBinding()
class OrderService:
    """Order management service."""
    
    def __init__(self, 
                 order_repo: OrderRepository,
                 user_repo: UserRepository,
                 product_repo: ProductRepository,
                 logger):
        self.order_repo = order_repo
        self.user_repo = user_repo
        self.product_repo = product_repo
        self.logger = logger
    
    async def create_order(self, order_data: Dict) -> Order:
        """Create a new order."""
        # Validate user exists
        user = await self.user_repo.find_by_id(order_data['user_id'])
        if not user:
            raise ValueError(f"User {order_data['user_id']} not found")
        
        # Validate products and calculate total
        items = []
        total = 0.0
        for item in order_data['items']:
            product = await self.product_repo.find_by_id(item['product_id'])
            if not product:
                raise ValueError(f"Product {item['product_id']} not found")
            
            item_total = product.price * item['quantity']
            total += item_total
            items.append({
                'product_id': item['product_id'],
                'quantity': item['quantity'],
                'price': product.price,
                'total': item_total
            })
        
        order = Order(
            id=order_data.get('id', f"order-{datetime.now().timestamp()}"),
            user_id=order_data['user_id'],
            items=items
        )
        order.total = total
        
        # Save order
        saved_order = await self.order_repo.save(order)
        
        self.logger.info(f"Created order {saved_order.id} total: ${total:.2f}")
        return saved_order


@ApplicationScoped
@LoggerBinding()
class UserService:
    """User management service."""
    
    def __init__(self, user_repo: UserRepository, logger):
        self.user_repo = user_repo
        self.logger = logger
    
    async def create_user(self, user_data: Dict) -> User:
        """Create a new user."""
        user = User(
            id=user_data.get('id', f"user-{datetime.now().timestamp()}"),
            name=user_data['name'],
            email=user_data['email']
        )
        
        saved_user = await self.user_repo.save(user)
        self.logger.info(f"Created user {saved_user.id}")
        return saved_user
    
    async def get_user(self, user_id: str) -> User:
        return await self.user_repo.find_by_id(user_id)
    
    async def list_users(self) -> List[User]:
        return await self.user_repo.find_all()


# ============================================================================
# EVENT SYSTEM
# ============================================================================

@Producer("user.events")
class UserEventPublisher:
    """User event publisher."""
    
    def __init__(self, event_bus):
        self.event_bus = event_bus


@Producer("order.events") 
class OrderEventPublisher:
    """Order event publisher."""
    
    def __init__(self, event_bus):
        self.event_bus = event_bus


class UserEventHandler:
    """User event handler."""
    
    def __init__(self, user_repo: UserRepository, logger):
        self.user_repo = user_repo
        self.logger = logger
    
    @Consumer("user.events")
    async def handle_user_created(self, event: dict, logger):
        """Handle user created event."""
        if event['type'] == 'UserCreated':
            user_data = event['data']
            logger.info(f"Processing UserCreated event for {user_data['name']}")
            
            # Could send welcome email, update analytics, etc.
            await self.send_welcome_notification(user_data)
    
    async def send_welcome_notification(self, user_data: dict):
        """Send welcome notification (simulated)."""
        self.logger.info(f"Welcome notification sent to {user_data['email']}")


class OrderEventHandler:
    """Order event handler."""
    
    def __init__(self, order_repo: OrderRepository, user_repo: UserRepository, logger):
        self.order_repo = order_repo
        self.user_repo = user_repo
        self.logger = logger
    
    @Consumer("order.events")
    async def handle_order_created(self, event: dict, logger):
        """Handle order created event."""
        if event['type'] == 'OrderCreated':
            order_data = event['data']
            logger.info(f"Processing OrderCreated event for {order_data['id']}")
            
            # Update user stats, send confirmation, etc.
            await this.process_order_confirmation(order_data)
    
    async def process_order_confirmation(self, order_data: dict):
        """Process order confirmation (simulated)."""
        user = await self.user_repo.find_by_id(order_data['user_id'])
        if user:
            self.logger.info(f"Order confirmation sent to {user.name}")


# ============================================================================
# API CONTROLLERS
# ============================================================================

users_router = APIRouter(prefix="/users", tags=["users"])

@users_router.post("/", response_model=dict)
async def create_user(user_data: dict):
    """Create a new user."""
    from app.shared.pygem_simple import PyGem
    
    gem = PyGem()
    user_service = gem.get(UserService)
    
    try:
        user = await user_service.create_user(user_data)
        
        # Publish user created event
        event_publisher = gem.get(UserEventPublisher)
        await event_publisher.publish({
            'type': 'UserCreated',
            'data': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'created_at': user.created_at.isoformat()
            }
        })
        
        return {"id": user.id, "name": user.name, "email": user.email}
    except ValueError as e:
        return {"error": str(e)}, 400

@users_router.get("/", response_model=list)
async def list_users():
    """List all users."""
    from app.shared.pygem_simple import PyGem
    
    gem = PyGem()
    user_service = gem.get(UserService)
    users = await user_service.list_users()
    
    return [{"id": user.id, "name": user.name, "email": user.email} for user in users]


@users_router.get("/{user_id}", response_model=dict)
async def get_user(user_id: str):
    """Get user by ID."""
    from app.shared.pygem_simple import PyGem
    
    gem = PyGem()
    user_service = gem.get(UserService)
    user = await user_service.get_user(user_id)
    
    if not user:
        return {"error": "User not found"}, 404
    
    return {"id": user.id, "name": user.name, "email": user.email}


orders_router = APIRouter(prefix="/orders", tags=["orders"])

@orders_router.post("/", response_model=dict)
async def create_order(order_data: dict):
    """Create a new order."""
    from app.shared.pygem_simple import PyGem
    
    gem = PyGem()
    order_service = gem.get(OrderService)
    
    try:
        order = await order_service.create_order(order_data)
        
        # Publish order created event
        event_publisher = gem.get(OrderEventPublisher)
        await event_publisher.publish({
            'type': 'OrderCreated',
            'data': {
                'id': order.id,
                'user_id': order.user_id,
                'total': order.total,
                'status': order.status,
                'created_at': order.created_at.isoformat()
            }
        })
        
        return {
            "id": order.id,
            "user_id": order.user_id,
            "total": order.total,
            "status": order.status,
            "items": order.items
        }
    except ValueError as e:
        return {"error": str(e)}, 400


@orders_router.get("/user/{user_id}", response_model=list)
async def get_user_orders(user_id: str):
    """Get orders for a user."""
    from app.shared.pygem_simple import PyGem
    
    gem = PyGem()
    order_repo = gem.get(OrderRepository)
    orders = await order_repo.find_by_user(user_id)
    
    return [{
        "id": order.id,
        "total": order.total,
        "status": order.status,
        "created_at": order.created_at.isoformat()
    } for order in orders]


# ============================================================================
# APPLICATION CONFIGURATION
# ============================================================================

# Create configuration for this example
config = """
# E-commerce Application Configuration
profile: dev
packages: ["app.examples"]

server:
  host: 0.0.0.0
  port: 8080

messaging:
  transport: memory

logging:
  level: INFO
  format: structured

health:
  enabled: true
  path: /health
"""

import os
with open('pygem.yml', 'w') as f:
    f.write(config)


# ============================================================================
# APPLICATION BOOTSTRAP
# ============================================================================

def create_ecommerce_app() -> PyGemApplication:
    """Create and configure the e-commerce application."""
    from app.health import create_health_router
    
    # Create application with all feature packages
    app = create_app([
        "app.examples",
        "app.health"
    ])
    
    # Add API routes
    app.add_routes(users_router, orders_router, create_health_router())
    
    return app


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        app = create_ecommerce_app()
        print("🚀 Starting PyGem E-commerce Application...")
        print("   Users API: http://localhost:8080/users")
        print("   Orders API: http://localhost:8080/orders") 
        print("   Health:     http://localhost:8080/health")
        print("   Docs:       http://localhost:8080/docs")
        print()
        
        app.run()
        
    finally:
        # Clean up config
        if os.path.exists('pygem.yml'):
            os.remove('pygem.yml')