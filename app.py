from flask import Flask, request, jsonify, make_response
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta
import os
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal
import uuid
from dotenv import load_dotenv
from extensions import db

load_dotenv()

def create_app():
    app = Flask(__name__)
    # Initialize Flask app
    app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URI', 'sqlite:///ecommerce.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

    # Initialize extensions
    db.init_app(app)
    return app

app = create_app()
from models import db, User, Product, Category, Order, OrderItem, Review, CartItem, Address, ProductImage
migrate = Migrate(app, db)
jwt = JWTManager(app)
# Error handling
@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)

@app.errorhandler(400)
def bad_request(error):
    return make_response(jsonify({'error': 'Bad request'}), 400)

@app.errorhandler(500)
def server_error(error):
    return make_response(jsonify({'error': 'Internal server error'}), 500)

# Authentication routes
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['username', 'email', 'password']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check if username or email already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400
    
    # Create new user
    new_user = User(
        username=data['username'],
        email=data['email'],
        first_name=data.get('first_name', ''),
        last_name=data.get('last_name', '')
    )
    new_user.set_password(data['password'])
    
    db.session.add(new_user)
    db.session.commit()
    
    # Generate token
    access_token = create_access_token(identity=new_user.id)
    
    return jsonify({
        'message': 'User registered successfully',
        'access_token': access_token,
        'user': {
            'id': new_user.id,
            'username': new_user.username,
            'email': new_user.email,
            'first_name': new_user.first_name,
            'last_name': new_user.last_name
        }
    }), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    # Validate required fields
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Missing username or password'}), 400
    
    # Find user by username
    user = User.query.filter_by(username=data['username']).first()
    
    # Check if user exists and password is correct
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    # Generate token
    access_token = create_access_token(identity=user.id)
    
    return jsonify({
        'message': 'Login successful',
        'access_token': access_token,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name
        }
    })

# User routes
@app.route('/users/me', methods=['GET'])
@jwt_required()
def get_user_profile():
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_admin': user.is_admin,
        'created_at': user.created_at.isoformat()
    })

@app.route('/users/me', methods=['PUT'])
@jwt_required()
def update_user_profile():
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    data = request.get_json()
    
    # Update user fields
    if 'first_name' in data:
        user.first_name = data['first_name']
    if 'last_name' in data:
        user.last_name = data['last_name']
    if 'email' in data:
        # Check if email already exists
        if data['email'] != user.email and User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 400
        user.email = data['email']
    if 'password' in data:
        user.set_password(data['password'])
    
    db.session.commit()
    
    return jsonify({
        'message': 'Profile updated successfully',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name
        }
    })

# Product routes
@app.route('/products', methods=['GET'])
def get_products():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    category_id = request.args.get('category_id', type=int)
    
    query = Product.query.filter_by(is_active=True)
    
    # Filter by category if provided
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    # Apply pagination
    pagination = query.paginate(page=page, per_page=per_page)
    products = pagination.items
    
    # Format response
    result = []
    for product in products:
        # Get primary image
        primary_image = ProductImage.query.filter_by(product_id=product.id, is_primary=True).first()
        image_url = primary_image.image_url if primary_image else None
        
        result.append({
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price': str(product.price),
            'stock': product.stock,
            'sku': product.sku,
            'category_id': product.category_id,
            'image_url': image_url,
            'created_at': product.created_at.isoformat()
        })
    
    return jsonify({
        'products': result,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    })

@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Get all product images
    images = []
    for image in product.images:
        images.append({
            'id': image.id,
            'url': image.image_url,
            'alt_text': image.alt_text,
            'is_primary': image.is_primary
        })
    
    # Get product reviews
    reviews = []
    for review in product.reviews:
        reviews.append({
            'id': review.id,
            'rating': review.rating,
            'comment': review.comment,
            'user_id': review.user_id,
            'username': review.user.username,
            'created_at': review.created_at.isoformat()
        })
    
    return jsonify({
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'price': str(product.price),
        'stock': product.stock,
        'sku': product.sku,
        'category_id': product.category_id,
        'category_name': product.category.name if product.category else None,
        'images': images,
        'reviews': reviews,
        'created_at': product.created_at.isoformat(),
        'updated_at': product.updated_at.isoformat()
    })

@app.route('/api/products', methods=['POST'])
@jwt_required()
def create_product():
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    
    # Check if user is admin
    if not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['name', 'price', 'stock', 'category_id']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Generate SKU if not provided
    if 'sku' not in data:
        data['sku'] = f'SKU-{uuid.uuid4().hex[:8].upper()}'
    
    # Create new product
    new_product = Product(
        name=data['name'],
        description=data.get('description', ''),
        price=Decimal(data['price']),
        stock=data['stock'],
        sku=data['sku'],
        category_id=data['category_id']
    )
    
    db.session.add(new_product)
    db.session.commit()
    
    return jsonify({
        'message': 'Product created successfully',
        'product': {
            'id': new_product.id,
            'name': new_product.name,
            'price': str(new_product.price),
            'stock': new_product.stock,
            'sku': new_product.sku
        }
    }), 201

@app.route('/api/products/<int:product_id>', methods=['PUT'])
@jwt_required()
def update_product(product_id):
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    
    # Check if user is admin
    if not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    product = Product.query.get_or_404(product_id)
    data = request.get_json()
    
    # Update product fields
    if 'name' in data:
        product.name = data['name']
    if 'description' in data:
        product.description = data['description']
    if 'price' in data:
        product.price = Decimal(data['price'])
    if 'stock' in data:
        product.stock = data['stock']
    if 'category_id' in data:
        product.category_id = data['category_id']
    if 'is_active' in data:
        product.is_active = data['is_active']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Product updated successfully',
        'product': {
            'id': product.id,
            'name': product.name,
            'price': str(product.price),
            'stock': product.stock,
            'is_active': product.is_active
        }
    })

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
@jwt_required()
def delete_product(product_id):
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    
    # Check if user is admin
    if not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    product = Product.query.get_or_404(product_id)
    
    # Soft delete by setting is_active to False
    product.is_active = False
    db.session.commit()
    
    return jsonify({
        'message': 'Product deleted successfully'
    })

# Category routes
@app.route('/api/categories', methods=['GET'])
def get_categories():
    categories = Category.query.all()
    result = []
    
    for category in categories:
        result.append({
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'product_count': category.products.count()
        })
    
    return jsonify({'categories': result})

@app.route('/api/categories', methods=['POST'])
@jwt_required()
def create_category():
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    
    # Check if user is admin
    if not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    
    # Validate required fields
    if 'name' not in data:
        return jsonify({'error': 'Category name is required'}), 400
    
    # Check if category already exists
    if Category.query.filter_by(name=data['name']).first():
        return jsonify({'error': 'Category already exists'}), 400
    
    # Create new category
    new_category = Category(
        name=data['name'],
        description=data.get('description', '')
    )
    
    db.session.add(new_category)
    db.session.commit()
    
    return jsonify({
        'message': 'Category created successfully',
        'category': {
            'id': new_category.id,
            'name': new_category.name,
            'description': new_category.description
        }
    }), 201

# Cart routes
@app.route('/api/cart', methods=['GET'])
@jwt_required()
def get_cart():
    current_user_id = get_jwt_identity()
    cart_items = CartItem.query.filter_by(user_id=current_user_id).all()
    
    result = []
    total = Decimal('0.00')
    
    for item in cart_items:
        product = item.product
        item_total = product.price * item.quantity
        total += item_total
        
        result.append({
            'id': item.id,
            'product_id': product.id,
            'product_name': product.name,
            'quantity': item.quantity,
            'price': str(product.price),
            'total': str(item_total)
        })
    
    return jsonify({
        'cart_items': result,
        'total': str(total),
        'items_count': len(result)
    })

@app.route('/api/cart', methods=['POST'])
@jwt_required()
def add_to_cart():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    # Validate required fields
    if 'product_id' not in data or 'quantity' not in data:
        return jsonify({'error': 'Product ID and quantity are required'}), 400
    
    product_id = data['product_id']
    quantity = int(data['quantity'])
    
    # Check if product exists and is active
    product = Product.query.filter_by(id=product_id, is_active=True).first()
    if not product:
        return jsonify({'error': 'Product not found or unavailable'}), 404
    
    # Check if quantity is valid
    if quantity <= 0:
        return jsonify({'error': 'Quantity must be greater than zero'}), 400
    
    # Check if product is in stock
    if product.stock < quantity:
        return jsonify({'error': 'Not enough stock available'}), 400
    
    # Check if item already in cart
    cart_item = CartItem.query.filter_by(user_id=current_user_id, product_id=product_id).first()
    
    if cart_item:
        # Update quantity
        cart_item.quantity += quantity
    else:
        # Add new item to cart
        cart_item = CartItem(
            user_id=current_user_id,
            product_id=product_id,
            quantity=quantity
        )
        db.session.add(cart_item)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Product added to cart',
        'cart_item': {
            'id': cart_item.id,
            'product_id': product_id,
            'quantity': cart_item.quantity
        }
    })

@app.route('/api/cart/<int:item_id>', methods=['PUT'])
@jwt_required()
def update_cart_item(item_id):
    current_user_id = get_jwt_identity()
    cart_item = CartItem.query.filter_by(id=item_id, user_id=current_user_id).first()
    
    if not cart_item:
        return jsonify({'error': 'Cart item not found'}), 404
    
    data = request.get_json()
    
    if 'quantity' not in data:
        return jsonify({'error': 'Quantity is required'}), 400
    
    quantity = int(data['quantity'])
    
    # Check if quantity is valid
    if quantity <= 0:
        return jsonify({'error': 'Quantity must be greater than zero'}), 400
    
    # Check if product is in stock
    if cart_item.product.stock < quantity:
        return jsonify({'error': 'Not enough stock available'}), 400
    
    # Update quantity
    cart_item.quantity = quantity
    db.session.commit()
    
    return jsonify({
        'message': 'Cart item updated',
        'cart_item': {
            'id': cart_item.id,
            'product_id': cart_item.product_id,
            'quantity': cart_item.quantity
        }
    })

@app.route('/api/cart/<int:item_id>', methods=['DELETE'])
@jwt_required()
def remove_from_cart(item_id):
    current_user_id = get_jwt_identity()
    cart_item = CartItem.query.filter_by(id=item_id, user_id=current_user_id).first()
    
    if not cart_item:
        return jsonify({'error': 'Cart item not found'}), 404
    
    db.session.delete(cart_item)
    db.session.commit()
    
    return jsonify({
        'message': 'Item removed from cart'
    })

# Order routes
@app.route('/api/orders', methods=['POST'])
@jwt_required()
def create_order():
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    data = request.get_json()
    
    # Validate required fields
    if 'shipping_address_id' not in data:
        return jsonify({'error': 'Shipping address is required'}), 400
    
    # Check if address belongs to user
    shipping_address = Address.query.filter_by(id=data['shipping_address_id'], user_id=current_user_id).first()
    if not shipping_address:
        return jsonify({'error': 'Invalid shipping address'}), 400
    
    # Get billing address
    billing_address_id = data.get('billing_address_id', data['shipping_address_id'])
    billing_address = Address.query.filter_by(id=billing_address_id, user_id=current_user_id).first()
    if not billing_address:
        return jsonify({'error': 'Invalid billing address'}), 400
    
    # Get cart items
    cart_items = CartItem.query.filter_by(user_id=current_user_id).all()
    if not cart_items:
        return jsonify({'error': 'Cart is empty'}), 400
    
    # Create order
    order_number = f'ORD-{uuid.uuid4().hex[:8].upper()}'
    total_amount = Decimal('0.00')
    
    # Create order
    new_order = Order(
        order_number=order_number,
        status='pending',
        total_amount=total_amount,  # Will be updated later
        user_id=current_user_id,
        shipping_address_id=shipping_address.id,
        billing_address_id=billing_address.id
    )
    
    db.session.add(new_order)
    db.session.flush()  # Get order ID without committing
    
    # Create order items and update stock
    for cart_item in cart_items:
        product = cart_item.product
        
        # Check if product is still available and has enough stock
        if not product.is_active or product.stock < cart_item.quantity:
            db.session.rollback()
            return jsonify({
                'error': f'Product {product.name} is not available or not enough in stock'
            }), 400
        
        # Create order item
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=product.id,
            quantity=cart_item.quantity,
            price=product.price
        )
        
        # Update stock
        product.stock -= cart_item.quantity
        
        # Update total amount
        item_total = product.price * cart_item.quantity
        total_amount += item_total
        
        db.session.add(order_item)
    
    # Update order total
    new_order.total_amount = total_amount
    
    # Clear cart
    for cart_item in cart_items:
        db.session.delete(cart_item)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Order created successfully',
        'order': {
            'id': new_order.id,
            'order_number': new_order.order_number,
            'status': new_order.status,
            'total_amount': str(new_order.total_amount),
            'created_at': new_order.created_at.isoformat()
        }
    }), 201

@app.route('/api/orders', methods=['GET'])
@jwt_required()
def get_user_orders():
    current_user_id = get_jwt_identity()
    orders = Order.query.filter_by(user_id=current_user_id).order_by(Order.created_at.desc()).all()
    
    result = []
    for order in orders:
        result.append({
            'id': order.id,
            'order_number': order.order_number,
            'status': order.status,
            'total_amount': str(order.total_amount),
            'created_at': order.created_at.isoformat(),
            'items_count': order.order_items.count()
        })
    
    return jsonify({
        'orders': result
    })

@app.route('/api/orders/<int:order_id>', methods=['GET'])
@jwt_required()
def get_order_details(order_id):
    current_user_id = get_jwt_identity()
    order = Order.query.filter_by(id=order_id, user_id=current_user_id).first()
    
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    # Get order items
    items = []
    for item in order.order_items:
        product = item.product
        items.append({
            'id': item.id,
            'product_id': product.id,
            'product_name': product.name,
            'quantity': item.quantity,
            'price': str(item.price),
            'total': str(item.price * item.quantity)
        })
    
    # Get shipping address
    shipping_address = order.shipping_address
    shipping = {
        'street': shipping_address.street,
        'city': shipping_address.city,
        'state': shipping_address.state,
        'country': shipping_address.country,
        'zip_code': shipping_address.zip_code
    }
    
    # Get billing address
    billing_address = order.billing_address
    billing = {
        'street': billing_address.street,
        'city': billing_address.city,
        'state': billing_address.state,
        'country': billing_address.country,
        'zip_code': billing_address.zip_code
    }
    
    return jsonify({
        'id': order.id,
        'order_number': order.order_number,
        'status': order.status,
        'total_amount': str(order.total_amount),
        'created_at': order.created_at.isoformat(),
        'updated_at': order.updated_at.isoformat(),
        'items': items,
        'shipping_address': shipping,
        'billing_address': billing
    })

# Reviews routes
@app.route('/api/products/<int:product_id>/reviews', methods=['POST'])
@jwt_required()
def create_review(product_id):
    current_user_id = get_jwt_identity()
    product = Product.query.get_or_404(product_id)
    data = request.get_json()
    
    # Validate required fields
    if 'rating' not in data:
        return jsonify({'error': 'Rating is required'}), 400
    
    rating = int(data['rating'])
    
    # Validate rating
    if rating < 1 or rating > 5:
        return jsonify({'error': 'Rating must be between 1 and 5'}), 400
    
    # Check if user already reviewed this product
    existing_review = Review.query.filter_by(user_id=current_user_id, product_id=product_id).first()
    if existing_review:
        return jsonify({'error': 'You have already reviewed this product'}), 400
    
    # Create review
    new_review = Review(
        user_id=current_user_id,
        product_id=product_id,
        rating=rating,
        comment=data.get('comment', '')
    )
    
    db.session.add(new_review)
    db.session.commit()
    
    return jsonify({
        'message': 'Review created successfully',
        'review': {
            'id': new_review.id,
            'rating': new_review.rating,
            'comment': new_review.comment,
            'created_at': new_review.created_at.isoformat()
        }
    }), 201

# Address routes
@app.route('/api/addresses', methods=['GET'])
@jwt_required()
def get_user_addresses():
    current_user_id = get_jwt_identity()
    addresses = Address.query.filter_by(user_id=current_user_id).all()
    
    result = []
    for address in addresses:
        result.append({
            'id': address.id,
            'street': address.street,
            'city': address.city,
            'state': address.state,
            'country': address.country,
            'zip_code': address.zip_code,
            'is_default': address.is_default,
            'address_type': address.address_type
        })
    
    return jsonify({
        'addresses': result
    })

@app.route('/api/addresses', methods=['POST'])
@jwt_required()
def create_address():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['street', 'city', 'country', 'zip_code']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Create address
    new_address = Address(
        user_id=current_user_id,
        street=data['street'],
        city=data['city'],
        state=data.get('state', ''),
        country=data['country'],
        zip_code=data['zip_code'],
        is_default=data.get('is_default', False),
        address_type=data.get('address_type', '')
    )
    
    # If this is the first address or is set as default, update other addresses
    if new_address.is_default or Address.query.filter_by(user_id=current_user_id).count() == 0:
        new_address.is_default = True
        Address.query.filter_by(user_id=current_user_id).update({'is_default': False})
    
    db.session.add(new_address)
    db.session.commit()
    
    return jsonify({
        'message': 'Address created successfully',
        'address': {
            'id': new_address.id,
            'street': new_address.street,
            'city': new_address.city,
            'state': new_address.state,
            'country': new_address.country,
            'zip_code': new_address.zip_code,
            'is_default': new_address.is_default,
            'address_type': new_address.address_type
        }
    }), 201

# Run app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)