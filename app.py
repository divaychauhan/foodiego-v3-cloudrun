import os
import re
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.engine.url import URL
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

cors_origins = os.getenv("CORS_ORIGINS", "*")
CORS(app, resources={r"/api/*": {"origins": cors_origins}}, supports_credentials=False)

db = SQLAlchemy()
migrate = Migrate()


def get_database_uri():
    instance_connection_name = os.getenv("INSTANCE_CONNECTION_NAME")

    if instance_connection_name:
        db_user = os.getenv("DB_USER", "foodie_user")
        db_pass = os.getenv("DB_PASS")
        db_name = os.getenv("DB_NAME", "foodiego_db")

        if not db_pass:
            raise RuntimeError("DB_PASS environment variable is required for Cloud SQL")

        return URL.create(
            drivername="mysql+pymysql",
            username=db_user,
            password=db_pass,
            database=db_name,
            query={"unix_socket": f"/cloudsql/{instance_connection_name}"},
        ).render_as_string(hide_password=False)

    return os.getenv("DATABASE_URL", "sqlite:///foodiego.db")


app.config["SQLALCHEMY_DATABASE_URI"] = get_database_uri()
db.init_app(app)
migrate.init_app(app, db)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="CUSTOMER")  # CUSTOMER / ADMIN
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "role": self.role,
        }


class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    cuisine = db.Column(db.String(120), nullable=False)
    rating = db.Column(db.Float, default=4.0)
    delivery_time = db.Column(db.String(40), default="30-35 min")
    price_for_two = db.Column(db.Integer, default=400)
    location = db.Column(db.String(120), default="City Center")
    offer = db.Column(db.String(120), default="20% OFF")
    cover_emoji = db.Column(db.String(20), default="🍽️")
    is_open = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    menu_items = db.relationship("MenuItem", backref="restaurant", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "cuisine": self.cuisine,
            "rating": self.rating,
            "delivery_time": self.delivery_time,
            "price_for_two": self.price_for_two,
            "location": self.location,
            "offer": self.offer,
            "cover_emoji": self.cover_emoji,
            "is_open": self.is_open,
        }


class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Float, nullable=False)
    food_type = db.Column(db.String(20), default="Veg")
    food_emoji = db.Column(db.String(20), default="🍽️")
    is_available = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "restaurant_id": self.restaurant_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "price": self.price,
            "food_type": self.food_type,
            "food_emoji": self.food_emoji,
            "is_available": self.is_available,
        }


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(60), default="MOCK_GATEWAY")
    method = db.Column(db.String(50), default="COD")
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default="PENDING")  # PENDING / PAID / FAILED / REFUNDED
    transaction_id = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False)
    payment_id = db.Column(db.Integer, db.ForeignKey("payment.id"), nullable=True)

    customer_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    flat = db.Column(db.String(120), nullable=False)
    area = db.Column(db.String(120), nullable=False)
    city = db.Column(db.String(120), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    landmark = db.Column(db.String(120), nullable=True)

    subtotal = db.Column(db.Float, nullable=False)
    delivery_fee = db.Column(db.Float, default=35)
    platform_fee = db.Column(db.Float, default=5)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default="PLACED")
    payment_method = db.Column(db.String(50), default="COD")
    cancellation_reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship("OrderItem", backref="order", lazy=True)
    payment = db.relationship("Payment", lazy=True)

    def can_cancel(self):
        allowed_status = ["PLACED", "ACCEPTED"]
        within_time = datetime.utcnow() - self.created_at <= timedelta(minutes=10)
        return self.status in allowed_status and within_time


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_item.id"), nullable=False)
    item_name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)


class DeliveryTracking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    driver_name = db.Column(db.String(120), default="Rohit")
    driver_phone = db.Column(db.String(20), default="9999999999")
    latitude = db.Column(db.Float, default=28.6692)
    longitude = db.Column(db.Float, default=77.4538)
    eta_minutes = db.Column(db.Integer, default=30)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------- Auth helpers ----------------

def create_token(user):
    payload = {
        "user_id": user.id,
        "role": user.role,
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def get_current_user():
    user_id = session.get("user_id")

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            user_id = payload.get("user_id")
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    if not user_id:
        return None

    return db.session.get(User, user_id)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Login required"}), 401
        request.current_user = user
        return fn(*args, **kwargs)
    return wrapper


def role_required(role):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Login required"}), 401
            if user.role != role:
                return jsonify({"error": "Access denied"}), 403
            request.current_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ---------------- Validation helpers ----------------

def validate_address(data):
    required = ["flat", "area", "city", "pincode"]
    for field in required:
        if not str(data.get(field, "")).strip():
            return False, f"{field} is required"

    pincode = str(data.get("pincode", "")).strip()
    if not re.fullmatch(r"\d{6}", pincode):
        return False, "Pincode must be 6 digits"

    if len(str(data.get("area", "")).strip()) < 3:
        return False, "Area is too short"

    return True, "valid"


def update_tracking_for_order(order):
    tracking = DeliveryTracking.query.filter_by(order_id=order.id).first()
    if not tracking:
        tracking = DeliveryTracking(order_id=order.id)
        db.session.add(tracking)

    status_map = {
        "PLACED": (28.6692, 77.4538, 35),
        "ACCEPTED": (28.6705, 77.4550, 30),
        "PREPARING": (28.6720, 77.4565, 25),
        "OUT_FOR_DELIVERY": (28.6755, 77.4590, 12),
        "DELIVERED": (28.6780, 77.4620, 0),
        "CANCELLED": (28.6692, 77.4538, 0),
    }

    lat, lng, eta = status_map.get(order.status, status_map["PLACED"])
    tracking.latitude = lat
    tracking.longitude = lng
    tracking.eta_minutes = eta
    tracking.updated_at = datetime.utcnow()
    db.session.commit()
    return tracking


# ---------------- Seed data ----------------

def seed_data():
    if not User.query.filter_by(email="admin@foodiego.com").first():
        admin = User(name="FoodieGo Admin", email="admin@foodiego.com", phone="9000000001", role="ADMIN")
        admin.set_password("Admin@123")
        db.session.add(admin)

    if not User.query.filter_by(email="customer@foodiego.com").first():
        customer = User(name="Demo Customer", email="customer@foodiego.com", phone="9000000002", role="CUSTOMER")
        customer.set_password("Customer@123")
        db.session.add(customer)

    db.session.commit()

    if Restaurant.query.first():
        return

    admin = User.query.filter_by(email="admin@foodiego.com").first()

    restaurants = [
        Restaurant(owner_id=admin.id, name="Spice Junction", cuisine="North Indian, Mughlai", rating=4.6, delivery_time="25-30 min", price_for_two=450, location="Raj Nagar", offer="50% OFF up to ₹100", cover_emoji="🍛"),
        Restaurant(owner_id=admin.id, name="Pizza Planet", cuisine="Pizza, Italian, Fast Food", rating=4.4, delivery_time="30-35 min", price_for_two=550, location="City Mall", offer="Buy 1 Get 1 Free", cover_emoji="🍕"),
        Restaurant(owner_id=admin.id, name="Burger House", cuisine="Burger, Fast Food, Beverages", rating=4.2, delivery_time="20-25 min", price_for_two=350, location="Vaishali", offer="₹75 OFF above ₹299", cover_emoji="🍔"),
        Restaurant(owner_id=admin.id, name="Biryani Darbar", cuisine="Biryani, Hyderabadi, Kebab", rating=4.7, delivery_time="35-40 min", price_for_two=600, location="Indirapuram", offer="Flat 30% OFF", cover_emoji="🍗"),
        Restaurant(owner_id=admin.id, name="The Dessert Lab", cuisine="Desserts, Ice Cream, Bakery", rating=4.5, delivery_time="20-30 min", price_for_two=300, location="Sector 62", offer="Free delivery", cover_emoji="🍰"),
        Restaurant(owner_id=admin.id, name="Healthy Bowl Co.", cuisine="Healthy Food, Salads, Bowls", rating=4.3, delivery_time="25-35 min", price_for_two=500, location="Noida Extension", offer="20% OFF", cover_emoji="🥗"),
    ]
    db.session.add_all(restaurants)
    db.session.commit()

    menu_items = [
        MenuItem(restaurant_id=1, name="Paneer Butter Masala", description="Creamy paneer curry with rich tomato gravy.", category="Main Course", price=249, food_type="Veg", food_emoji="🍛"),
        MenuItem(restaurant_id=1, name="Dal Makhani", description="Slow cooked black lentils with butter and cream.", category="Main Course", price=199, food_type="Veg", food_emoji="🥣"),
        MenuItem(restaurant_id=1, name="Butter Naan", description="Soft tandoori naan with butter.", category="Breads", price=49, food_type="Veg", food_emoji="🫓"),
        MenuItem(restaurant_id=2, name="Margherita Pizza", description="Classic cheese pizza with tomato sauce.", category="Pizza", price=299, food_type="Veg", food_emoji="🍕"),
        MenuItem(restaurant_id=2, name="Farmhouse Pizza", description="Loaded with capsicum, onion, tomato and corn.", category="Pizza", price=399, food_type="Veg", food_emoji="🍕"),
        MenuItem(restaurant_id=2, name="Cheese Garlic Bread", description="Toasted bread with cheese and garlic butter.", category="Sides", price=159, food_type="Veg", food_emoji="🥖"),
        MenuItem(restaurant_id=3, name="Classic Veg Burger", description="Crispy patty, lettuce, cheese and signature sauce.", category="Burgers", price=129, food_type="Veg", food_emoji="🍔"),
        MenuItem(restaurant_id=3, name="Double Cheese Burger", description="Loaded cheese burger with double patty.", category="Burgers", price=199, food_type="Veg", food_emoji="🍔"),
        MenuItem(restaurant_id=3, name="French Fries", description="Crispy salted fries.", category="Sides", price=99, food_type="Veg", food_emoji="🍟"),
        MenuItem(restaurant_id=4, name="Veg Biryani", description="Aromatic rice cooked with vegetables and spices.", category="Biryani", price=249, food_type="Veg", food_emoji="🍚"),
        MenuItem(restaurant_id=4, name="Chicken Biryani", description="Hyderabadi style chicken biryani.", category="Biryani", price=329, food_type="Non-Veg", food_emoji="🍗"),
        MenuItem(restaurant_id=5, name="Chocolate Brownie", description="Rich chocolate brownie served warm.", category="Desserts", price=149, food_type="Veg", food_emoji="🍫"),
        MenuItem(restaurant_id=5, name="Red Velvet Pastry", description="Soft red velvet pastry with cream cheese.", category="Desserts", price=179, food_type="Veg", food_emoji="🍰"),
        MenuItem(restaurant_id=6, name="Protein Power Bowl", description="Rice, veggies, paneer, sprouts and dressing.", category="Bowls", price=299, food_type="Veg", food_emoji="🥗"),
        MenuItem(restaurant_id=6, name="Greek Salad", description="Fresh salad with feta, olives and veggies.", category="Salads", price=249, food_type="Veg", food_emoji="🥗"),
    ]
    db.session.add_all(menu_items)
    db.session.commit()


# ---------------- Page ----------------

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "service": "foodiego-v3", "timestamp": datetime.utcnow().isoformat()})


# ---------------- Auth APIs ----------------

@app.post("/api/auth/register")
def register():
    data = request.get_json() or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip()
    password = str(data.get("password", ""))

    if not name or not email or not password:
        return jsonify({"error": "Name, email and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    user = User(name=name, email=email, phone=phone, role="CUSTOMER")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = create_token(user)
    session["user_id"] = user.id
    return jsonify({"message": "Registration successful", "user": user.to_dict(), "token": token}), 201


@app.post("/api/auth/login")
def login():
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401
    if not user.is_active:
        return jsonify({"error": "Account is disabled"}), 403

    token = create_token(user)
    session["user_id"] = user.id
    return jsonify({"message": "Login successful", "user": user.to_dict(), "token": token})


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logout successful"})


@app.get("/api/auth/me")
def me():
    user = get_current_user()
    if not user:
        return jsonify({"user": None})
    return jsonify({"user": user.to_dict()})


# ---------------- Customer APIs ----------------

@app.get("/api/restaurants")
def get_restaurants():
    search = request.args.get("search", "").lower().strip()
    cuisine = request.args.get("cuisine", "").lower().strip()
    restaurants = Restaurant.query.filter_by(is_open=True).all()
    filtered = []
    for restaurant in restaurants:
        match_search = search in restaurant.name.lower() or search in restaurant.cuisine.lower() or search in restaurant.location.lower()
        match_cuisine = cuisine == "" or cuisine in restaurant.cuisine.lower()
        if match_search and match_cuisine:
            filtered.append(restaurant)
    return jsonify([restaurant.to_dict() for restaurant in filtered])


@app.get("/api/cuisines")
def get_cuisines():
    restaurants = Restaurant.query.all()
    cuisine_set = set()
    for restaurant in restaurants:
        for part in restaurant.cuisine.split(","):
            cuisine_set.add(part.strip())
    return jsonify(sorted(cuisine_set))


@app.get("/api/restaurants/<int:restaurant_id>/menu")
def get_menu(restaurant_id):
    restaurant = db.session.get(Restaurant, restaurant_id)
    if not restaurant:
        return jsonify({"error": "Restaurant not found"}), 404
    menu_items = MenuItem.query.filter_by(restaurant_id=restaurant_id, is_available=True).all()
    categories = {}
    for item in menu_items:
        categories.setdefault(item.category, []).append(item.to_dict())
    return jsonify({"restaurant": restaurant.to_dict(), "categories": categories})


@app.post("/api/orders")
@login_required
def create_order():
    user = request.current_user
    data = request.get_json() or {}

    required = ["customer_name", "phone", "restaurant_id", "items", "address", "payment_method"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"{field} is required"}), 400

    valid_address, address_msg = validate_address(data["address"])
    if not valid_address:
        return jsonify({"error": address_msg}), 400

    restaurant = db.session.get(Restaurant, data["restaurant_id"])
    if not restaurant or not restaurant.is_open:
        return jsonify({"error": "Restaurant not available"}), 404

    if not data["items"]:
        return jsonify({"error": "Cart is empty"}), 400

    subtotal = 0
    final_items = []
    for incoming_item in data["items"]:
        menu_item = db.session.get(MenuItem, incoming_item.get("menu_item_id"))
        quantity = int(incoming_item.get("quantity", 1))
        if not menu_item or menu_item.restaurant_id != restaurant.id:
            return jsonify({"error": "Invalid cart item"}), 400
        if quantity <= 0:
            return jsonify({"error": "Quantity must be greater than zero"}), 400
        subtotal += menu_item.price * quantity
        final_items.append({"menu_item_id": menu_item.id, "item_name": menu_item.name, "quantity": quantity, "price": menu_item.price})

    delivery_fee = 0 if subtotal >= 499 else 35
    platform_fee = 5
    total_amount = round(subtotal + delivery_fee + platform_fee, 2)
    payment_method = data.get("payment_method", "COD")

    payment_status = "PENDING" if payment_method in ["UPI", "CARD"] else "COD_PENDING"
    payment = Payment(method=payment_method, amount=total_amount, status=payment_status)
    db.session.add(payment)
    db.session.commit()

    address = data["address"]
    order = Order(
        user_id=user.id,
        restaurant_id=restaurant.id,
        payment_id=payment.id,
        customer_name=data["customer_name"],
        phone=data["phone"],
        flat=address["flat"],
        area=address["area"],
        city=address["city"],
        pincode=address["pincode"],
        landmark=address.get("landmark", ""),
        subtotal=round(subtotal, 2),
        delivery_fee=delivery_fee,
        platform_fee=platform_fee,
        total_amount=total_amount,
        payment_method=payment_method,
        status="PLACED",
    )
    db.session.add(order)
    db.session.commit()

    for item in final_items:
        db.session.add(OrderItem(order_id=order.id, **item))
    db.session.commit()
    update_tracking_for_order(order)

    return jsonify({
        "message": "Order placed successfully",
        "order_id": order.id,
        "status": order.status,
        "restaurant": restaurant.name,
        "subtotal": order.subtotal,
        "delivery_fee": order.delivery_fee,
        "platform_fee": order.platform_fee,
        "total_amount": order.total_amount,
        "payment_id": payment.id,
        "payment_status": payment.status,
        "payment_required": payment_method in ["UPI", "CARD"],
    }), 201


@app.post("/api/payments/<int:payment_id>/confirm")
@login_required
def confirm_payment(payment_id):
    payment = db.session.get(Payment, payment_id)
    if not payment:
        return jsonify({"error": "Payment not found"}), 404

    order = Order.query.filter_by(payment_id=payment.id).first()
    if not order or order.user_id != request.current_user.id:
        return jsonify({"error": "Access denied"}), 403

    if payment.status == "PAID":
        return jsonify({"message": "Payment already confirmed", "payment_status": payment.status})

    payment.status = "PAID"
    payment.transaction_id = f"MOCK-{payment.id}-{int(datetime.utcnow().timestamp())}"
    payment.paid_at = datetime.utcnow()
    order.status = "ACCEPTED"
    db.session.commit()
    update_tracking_for_order(order)

    return jsonify({
        "message": "Payment successful",
        "payment_id": payment.id,
        "transaction_id": payment.transaction_id,
        "payment_status": payment.status,
        "order_status": order.status,
    })


@app.get("/api/orders/<int:order_id>")
@login_required
def get_order(order_id):
    user = request.current_user
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    if user.role != "ADMIN" and order.user_id != user.id:
        return jsonify({"error": "Access denied"}), 403

    restaurant = db.session.get(Restaurant, order.restaurant_id)
    return jsonify({
        "order_id": order.id,
        "restaurant": restaurant.name if restaurant else "Unknown",
        "customer_name": order.customer_name,
        "phone": order.phone,
        "address": {"flat": order.flat, "area": order.area, "city": order.city, "pincode": order.pincode, "landmark": order.landmark},
        "subtotal": order.subtotal,
        "delivery_fee": order.delivery_fee,
        "platform_fee": order.platform_fee,
        "total_amount": order.total_amount,
        "payment_method": order.payment_method,
        "payment_status": order.payment.status if order.payment else "N/A",
        "status": order.status,
        "can_cancel": order.can_cancel(),
        "created_at": order.created_at.strftime("%d %b %Y, %I:%M %p"),
        "items": [{"menu_item_id": item.menu_item_id, "item_name": item.item_name, "quantity": item.quantity, "price": item.price, "line_total": item.quantity * item.price} for item in order.items],
    })


@app.get("/api/orders/<int:order_id>/tracking")
@login_required
def get_tracking(order_id):
    user = request.current_user
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    if user.role != "ADMIN" and order.user_id != user.id:
        return jsonify({"error": "Access denied"}), 403

    tracking = update_tracking_for_order(order)
    statuses = ["PLACED", "ACCEPTED", "PREPARING", "OUT_FOR_DELIVERY", "DELIVERED"]
    return jsonify({
        "order_id": order.id,
        "status": order.status,
        "eta_minutes": tracking.eta_minutes,
        "driver": {"name": tracking.driver_name, "phone": tracking.driver_phone},
        "location": {"latitude": tracking.latitude, "longitude": tracking.longitude},
        "timeline": [{"status": s, "completed": statuses.index(s) <= statuses.index(order.status) if order.status in statuses else False} for s in statuses],
        "updated_at": tracking.updated_at.strftime("%d %b %Y, %I:%M:%S %p"),
    })


@app.post("/api/orders/<int:order_id>/cancel")
@login_required
def cancel_order(order_id):
    user = request.current_user
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    if order.user_id != user.id:
        return jsonify({"error": "Only the customer who placed the order can cancel it"}), 403
    if not order.can_cancel():
        return jsonify({"error": "Order can be cancelled only within 10 minutes and before preparation starts"}), 400

    data = request.get_json() or {}
    order.status = "CANCELLED"
    order.cancellation_reason = data.get("reason", "Cancelled by customer")
    if order.payment and order.payment.status == "PAID":
        order.payment.status = "REFUNDED"
    db.session.commit()
    update_tracking_for_order(order)
    return jsonify({"message": "Order cancelled successfully", "status": order.status})


# ---------------- Admin APIs ----------------

@app.get("/api/admin/restaurants")
@role_required("ADMIN")
def admin_restaurants():
    return jsonify([restaurant.to_dict() for restaurant in Restaurant.query.order_by(Restaurant.id.desc()).all()])


@app.post("/api/admin/restaurants")
@role_required("ADMIN")
def admin_create_restaurant():
    data = request.get_json() or {}
    required = ["name", "cuisine", "location"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    restaurant = Restaurant(
        owner_id=request.current_user.id,
        name=data["name"],
        cuisine=data["cuisine"],
        rating=float(data.get("rating", 4.0)),
        delivery_time=data.get("delivery_time", "30-35 min"),
        price_for_two=int(data.get("price_for_two", 400)),
        location=data["location"],
        offer=data.get("offer", "20% OFF"),
        cover_emoji=data.get("cover_emoji", "🍽️"),
        is_open=bool(data.get("is_open", True)),
    )
    db.session.add(restaurant)
    db.session.commit()
    return jsonify({"message": "Restaurant created", "restaurant": restaurant.to_dict()}), 201


@app.post("/api/admin/menu-items")
@role_required("ADMIN")
def admin_create_menu_item():
    data = request.get_json() or {}
    required = ["restaurant_id", "name", "description", "category", "price"]
    for field in required:
        if field not in data or data[field] == "":
            return jsonify({"error": f"{field} is required"}), 400

    restaurant = db.session.get(Restaurant, data["restaurant_id"])
    if not restaurant:
        return jsonify({"error": "Restaurant not found"}), 404

    item = MenuItem(
        restaurant_id=restaurant.id,
        name=data["name"],
        description=data["description"],
        category=data["category"],
        price=float(data["price"]),
        food_type=data.get("food_type", "Veg"),
        food_emoji=data.get("food_emoji", "🍽️"),
        is_available=bool(data.get("is_available", True)),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({"message": "Menu item created", "item": item.to_dict()}), 201


@app.get("/api/admin/orders")
@role_required("ADMIN")
def admin_orders():
    orders = Order.query.order_by(Order.id.desc()).limit(50).all()
    result = []
    for order in orders:
        restaurant = db.session.get(Restaurant, order.restaurant_id)
        result.append({
            "order_id": order.id,
            "restaurant": restaurant.name if restaurant else "Unknown",
            "customer_name": order.customer_name,
            "phone": order.phone,
            "total_amount": order.total_amount,
            "payment_method": order.payment_method,
            "payment_status": order.payment.status if order.payment else "N/A",
            "status": order.status,
            "created_at": order.created_at.strftime("%d %b %Y, %I:%M %p"),
        })
    return jsonify(result)


@app.patch("/api/admin/orders/<int:order_id>/status")
@role_required("ADMIN")
def admin_update_order_status(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404

    data = request.get_json() or {}
    allowed = ["PLACED", "ACCEPTED", "PREPARING", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED"]
    new_status = data.get("status")
    if new_status not in allowed:
        return jsonify({"error": "Invalid status", "allowed_status": allowed}), 400

    order.status = new_status
    db.session.commit()
    update_tracking_for_order(order)
    return jsonify({"message": "Order status updated", "order_id": order.id, "status": order.status})


if os.getenv("AUTO_CREATE_DB", "true").lower() == "true":
    with app.app_context():
        db.create_all()
        seed_data()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
