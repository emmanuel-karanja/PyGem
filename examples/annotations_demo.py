"""
PyGem Framework: Comprehensive Annotations Example
Demonstrates all CDI annotations and their practical usage patterns.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import asyncio
from dataclasses import dataclass

from app.shared.annotations import (
    ApplicationScoped, RequestScoped, LoggerBinding, 
    Producer, Consumer, Inject
)
from app.shared.logger.john_wick_logger import create_logger
from app.shared.pygem_simple import PyGem
from fastapi import APIRouter, FastAPI, HTTPException
import uvicorn

# ============================================================================
# DOMAIN MODELS
# ============================================================================

@dataclass
class User:
    """User entity."""
    id: str
    name: str
    email: str
    created_at: datetime

@dataclass
class Order:
    """Order entity."""
    id: str
    user_id: str
    total: float
    status: str = "pending"
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

@dataclass
class Product:
    """Product entity."""
    id: str
    name: str
    price: float
    stock: int

# ============================================================================
# DATA ACCESS LAYER - RequestScoped services
# ============================================================================

@RequestScoped
@LoggerBinding()
class UserRepository:
    """User data access with request scope."""
    
    def __init__(self, logger):
        self.logger = logger
        self._users: Dict[str, User] = {}
        self._counter = 0
    
    async def save(self, user: User) -> User:
        """Save user to storage."""
        self.logger.info("Saving user", extra={
            "user_id": user.id,
            "email": user.email
        })
        self._users[user.id] = user
        return user
    
    async def find_by_id(self, user_id: str) -> Optional[User]:
        """Find user by ID."""
        self.logger.debug("Finding user", extra={"user_id": user_id})
        return self._users.get(user_id)
    
    async def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email."""
        self.logger.debug("Finding user by email", extra={"email": email})
        for user in self._users.values():
            if user.email == email:
                return user
        return None

@RequestScoped
@LoggerBinding()
class OrderRepository:
    """Order data access with request scope."""
    
    def __init__(self, logger):
        self.logger = logger
        self._orders: Dict[str, Order] = {}
    
    async def save(self, order: Order) -> Order:
        """Save order to storage."""
        self.logger.info("Saving order", extra={
            "order_id": order.id,
            "user_id": order.user_id,
            "total": order.total
        })
        self._orders[order.id] = order
        return order
    
    async def find_by_id(self, order_id: str) -> Optional[Order]:
        """Find order by ID."""
        return self._orders.get(order_id)
    
    async def find_by_user(self, user_id: str) -> List[Order]:
        """Find orders by user ID."""
        return [order for order in self._orders.values() if order.user_id == user_id]

@RequestScoped
@LoggerBinding()
class ProductRepository:
    """Product data access with request scope."""
    
    def __init__(self, logger):
        self.logger = logger
        self._products: Dict[str, Product] = {}
    
    async def save(self, product: Product) -> Product:
        """Save product to storage."""
        self.logger.info("Saving product", extra={
            "product_id": product.id,
            "name": product.name,
            "price": product.price
        })
        self._products[product.id] = product
        return product
    
    async def find_by_id(self, product_id: str) -> Optional[Product]:
        """Find product by ID."""
        return self._products.get(product_id)
    
    async def update_stock(self, product_id: str, quantity: int) -> bool:
        """Update product stock."""
        product = self._products.get(product_id)
        if product and product.stock >= quantity:
            product.stock -= quantity
            self.logger.info("Stock updated", extra={
                "product_id": product_id,
                "new_stock": product.stock,
                "quantity_sold": quantity
            })
            return True
        return False

# ============================================================================
# BUSINESS LOGIC LAYER - ApplicationScoped services
# ============================================================================

@ApplicationScoped
@LoggerBinding()
class UserService:
    """User business logic service."""
    
    def __init__(self, logger, event_bus):
        self.logger = logger
        self.event_bus = event_bus
    
    async def create_user(self, name: str, email: str) -> User:
        """Create a new user."""
        user_id = f"user_{datetime.now().timestamp()}"
        user = User(
            id=user_id,
            name=name,
            email=email,
            created_at=datetime.utcnow()
        )
        
        # Use injected repository
        user_repo = Inject(UserRepository)
        saved_user = await user_repo.save(user)
        
        self.logger.info("User created successfully", extra={
            "user_id": saved_user.id,
            "name": saved_user.name
        })
        
        # Publish user created event
        await self.event_bus.publish("user.created", {
            "user_id": saved_user.id,
            "name": saved_user.name,
            "email": saved_user.email,
            "created_at": saved_user.created_at.isoformat()
        })
        
        return saved_user

@ApplicationScoped
@LoggerBinding()
class ProductService:
    """Product business logic service."""
    
    def __init__(self, logger, event_bus):
        self.logger = logger
        self.event_bus = event_bus
    
    async def create_product(self, name: str, price: float, stock: int) -> Product:
        """Create a new product."""
        product_id = f"product_{datetime.now().timestamp()}"
        product = Product(
            id=product_id,
            name=name,
            price=price,
            stock=stock
        )
        
        product_repo = Inject(ProductRepository)
        saved_product = await product_repo.save(product)
        
        self.logger.info("Product created successfully", extra={
            "product_id": saved_product.id,
            "name": saved_product.name,
            "price": saved_product.price
        })
        
        # Publish product created event
        await self.event_bus.publish("product.created", {
            "product_id": saved_product.id,
            "name": saved_product.name,
            "price": saved_product.price,
            "stock": saved_product.stock
        })
        
        return saved_product

@ApplicationScoped
@LoggerBinding()
@Producer("order.events")
class OrderService:
    """Order business logic service with producer annotation."""
    
    def __init__(self, logger):
        self.logger = logger
    
    async def create_order(self, user_id: str, items: List[Dict]) -> Order:
        """Create a new order with multiple items."""
        self.logger.info("Creating order", extra={
            "user_id": user_id,
            "item_count": len(items)
        })
        
        # Calculate total
        total = sum(item['price'] * item['quantity'] for item in items)
        
        # Create order
        order_id = f"order_{datetime.now().timestamp()}"
        order = Order(
            id=order_id,
            user_id=user_id,
            total=total,
            status="pending"
        )
        
        # Save order
        order_repo = Inject(OrderRepository)
        saved_order = await order_repo.save(order)
        
        # Update product stock
        product_repo = Inject(ProductRepository)
        for item in items:
            await product_repo.update_stock(item['product_id'], item['quantity'])
        
        self.logger.info("Order created successfully", extra={
            "order_id": saved_order.id,
            "total": saved_order.total,
            "item_count": len(items)
        })
        
        # Publish order created event
        await self.event_bus.publish("order.created", {
            "order_id": saved_order.id,
            "user_id": saved_order.user_id,
            "total": saved_order.total,
            "items": items,
            "created_at": saved_order.created_at.isoformat()
        })
        
        return saved_order

# ============================================================================
# EVENT HANDLERS - Consumer annotations
# ============================================================================

@ApplicationScoped
@LoggerBinding()
@Consumer("user.created")
class UserEventHandler:
    """Handles user-related events."""
    
    def __init__(self, logger):
        self.logger = logger
    
    async def handle_user_created(self, event_data: Dict):
        """Handle user created event."""
        self.logger.info("Processing user.created event", extra={
            "user_id": event_data.get('user_id'),
            "user_name": event_data.get('name')
        })
        
        # Simulate sending welcome email
        await asyncio.sleep(0.1)
        
        self.logger.info("Welcome notification sent", extra={
            "email": event_data.get('email')
        })

@ApplicationScoped
@LoggerBinding()
@Consumer("order.created")
class OrderEventHandler:
    """Handles order-related events."""
    
    def __init__(self, logger):
        self.logger = logger
    
    async def handle_order_created(self, event_data: Dict):
        """Handle order created event."""
        self.logger.info("Processing order.created event", extra={
            "order_id": event_data.get('order_id'),
            "total": event_data.get('total')
        })
        
        # Simulate order processing
        await asyncio.sleep(0.2)
        
        self.logger.info("Order processing completed", extra={
            "order_id": event_data.get('order_id')
        })

# ============================================================================
# API LAYER - FastAPI endpoints
# ============================================================================

@ApplicationScoped
@LoggerBinding()
class UserController:
    """User API controller."""
    
    def __init__(self, logger):
        self.logger = logger
    
    async def create_user(self, name: str, email: str) -> Dict:
        """Create user endpoint."""
        try:
            user_service = Inject(UserService)
            user = await user_service.create_user(name, email)
            
            self.logger.info("User created via API", extra={
                "user_id": user.id,
                "name": user.name
            })
            
            return {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "created_at": user.created_at.isoformat()
            }
        except Exception as e:
            self.logger.error("Failed to create user", extra={
                "name": name,
                "email": email,
                "error": str(e)
            })
            raise HTTPException(status_code=500, detail="Failed to create user")

@ApplicationScoped
@LoggerBinding()
class ProductController:
    """Product API controller."""
    
    def __init__(self, logger):
        self.logger = logger
    
    async def create_product(self, name: str, price: float, stock: int) -> Dict:
        """Create product endpoint."""
        try:
            product_service = Inject(ProductService)
            product = await product_service.create_product(name, price, stock)
            
            return {
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "stock": product.stock
            }
        except Exception as e:
            self.logger.error("Failed to create product", extra={
                "name": name,
                "price": price,
                "error": str(e)
            })
            raise HTTPException(status_code=500, detail="Failed to create product")

# ============================================================================
# APPLICATION SETUP
# ============================================================================

def create_annotation_demo_app() -> FastAPI:
    """Create FastAPI application with comprehensive annotations demo."""
    
    # Initialize PyGem with all packages
    gem = PyGem(["app.examples.annotations"])
    
    # Create FastAPI app
    app = FastAPI(
        title="PyGem Annotations Demo",
        description="Comprehensive demonstration of CDI annotations and patterns",
        version="1.0.0"
    )
    
    # Create API routers
    user_controller = Inject(UserController)
    product_controller = Inject(ProductController)
    
    # User endpoints
    @app.post("/users", summary="Create user", tags=["users"])
    async def create_user(name: str, email: str):
        return await user_controller.create_user(name, email)
    
    # Product endpoints  
    @app.post("/products", summary="Create product", tags=["products"])
    async def create_product(name: str, price: float, stock: int):
        return await product_controller.create_product(name, price, stock)
    
    # System info endpoint
    @app.get("/info", summary="System information", tags=["system"])
    async def get_system_info():
        user_repo = Inject(UserRepository)
        product_repo = Inject(ProductRepository)
        order_repo = Inject(OrderRepository)
        
        return {
            "system": "PyGem Annotations Demo",
            "annotations": {
                "ApplicationScoped": "Singleton services across application",
                "RequestScoped": "New instance per request/injection",
                "LoggerBinding": "Automatic logger injection",
                "Producer": "Event producer with topic binding",
                "Consumer": "Event consumer with topic subscription",
                "Inject": "Runtime dependency injection"
            },
            "statistics": {
                "beans_registered": len(gem._container._beans),
                "consumers_registered": len(gem._consumer_registry),
                "producers_registered": len(gem._producer_registry)
            }
        }
    
    @app.get("/", summary="Health check", tags=["system"])
    async def health_check():
        logger = create_logger("AnnotationsDemo")
        logger.info("Health check requested")
        
        return {
            "status": "healthy",
            "application": "PyGem Annotations Demo",
            "features": [
                "CDI Annotations",
                "Event-Driven Architecture", 
                "Dependency Injection",
                "Structured Logging",
                "Request/Scoped Lifecycle"
            ]
        }
    
    return app

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("=== PyGem Annotations Demo ===")
    print("Features demonstrated:")
    print("- ApplicationScoped & RequestScoped beans")
    print("- LoggerBinding for automatic logger injection")
    print("- Producer & Consumer event patterns")
    print("- Inject annotation for runtime dependencies")
    print("- Clean structured logging without emojis")
    print("============================")
    
    app = create_annotation_demo_app()
    
    print("Starting server on http://127.0.0.1:8003")
    print("API Documentation: http://127.0.0.1:8003/docs")
    print("System Info: http://127.0.0.1:8003/info")
    print("Health Check: http://127.0.0.1:8003/")
    
    uvicorn.run(app, host="127.0.0.1", port=8003)