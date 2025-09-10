from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import datetime
import os
from collections import defaultdict
import cloudinary
import cloudinary.uploader
import json # Import the json module to handle sale items safely

app = Flask(__name__)
# Use environment variables for production configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_very_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
# This part is a fix for a known issue with some PostgreSQL providers
if app.config['SQLALCHEMY_DATABASE_URI'] and app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize Flask-Migrate here
migrate = Migrate(app, db)

# Cloudinary configuration
# You MUST set these environment variables in your deployment environment
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=0)
    # Changed from image_filename to image_url to store the Cloudinary URL
    image_url = db.Column(db.String(255), nullable=True)
    # Add public_id to allow deleting images from Cloudinary
    public_id = db.Column(db.String(255), nullable=True)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    items = db.Column(db.String(1000), nullable=False)

# Move database initialization outside of __main__ block
with app.app_context():
    db.create_all()
    # Add a default admin user if the database is new
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', password='pass123')
        db.session.add(admin_user)
        db.session.commit()
        print("Default admin user created with username 'admin' and password 'pass123'")

# User Loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
@login_required
def index():
    all_products = Product.query.all()
    total_sales = db.session.query(db.func.sum(Sale.total_amount)).scalar() or 0
    # Safely load items from string before summing
    total_items = sum(item['quantity'] for sale in Sale.query.all() for item in json.loads(sale.items.replace("'", "\"")))
    return render_template('index.html', total_sales=total_sales, total_items=total_items, products=all_products)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        # Simple password check for demonstration
        if user and user.password == password:
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('login.html')

@app.route('/products', methods=['GET', 'POST'])
@login_required
def manage_products():
    if request.method == 'POST':
        name = request.form.get('name')
        price_str = request.form.get('price')
        quantity_str = request.form.get('quantity')
        image = request.files.get('image')
        image_url = None
        public_id = None

        if not name or not price_str or not quantity_str:
            flash('Name, price, and quantity are required.', 'error')
            return redirect(url_for('manage_products'))

        try:
            price = float(price_str)
            quantity = int(quantity_str)
        except (ValueError, TypeError):
            flash('Price and quantity must be valid numbers.', 'error')
            return redirect(url_for('manage_products'))

        if image and image.filename:
            try:
                upload_result = cloudinary.uploader.upload(image)
                image_url = upload_result['secure_url']
                public_id = upload_result['public_id']
            except Exception as e:
                flash(f'Image upload failed: {e}', 'error')
                return redirect(url_for('manage_products'))
            
        new_product = Product(name=name, price=price, quantity=quantity, image_url=image_url, public_id=public_id)
        db.session.add(new_product)
        db.session.commit()
        flash('Product added successfully!', 'success')
        return redirect(url_for('manage_products'))

    all_products = Product.query.all()
    # Pass the list of Product objects directly
    return render_template('products.html', products=all_products)

@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.price = float(request.form.get('price'))
        product.quantity = int(request.form.get('quantity'))
        image = request.files.get('image')

        if image and image.filename:
            # Delete old image from Cloudinary if it exists
            if product.public_id:
                cloudinary.uploader.destroy(product.public_id)
            
            # Save new image to Cloudinary
            try:
                upload_result = cloudinary.uploader.upload(image)
                product.image_url = upload_result['secure_url']
                product.public_id = upload_result['public_id']
            except Exception as e:
                flash(f'Image upload failed: {e}', 'error')
                return redirect(url_for('edit_product', product_id=product_id))
            
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('manage_products'))
    return render_template('edit_product.html', product=product)

@app.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Delete the associated image from Cloudinary
    if product.public_id:
        cloudinary.uploader.destroy(product.public_id)
            
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('manage_products'))

@app.route('/sales', methods=['GET', 'POST'])
@login_required
def process_sales():
    if request.method == 'POST':
        product_id = request.form.get('product_id')
        quantity = int(request.form.get('quantity'))
        
        product = Product.query.get(int(product_id))
        if product:
            if product.quantity < quantity:
                flash(f'Insufficient stock for {product.name}. Only {product.quantity} left.', 'error')
            else:
                item = {
                    'id': product.id,
                    'name': product.name,
                    'price': product.price,
                    'quantity': quantity,
                    'subtotal': product.price * quantity
                }
                active_transaction = session.get('active_transaction', [])
                active_transaction.append(item)
                session['active_transaction'] = active_transaction
                flash(f'{item["name"]} added to cart.', 'success')
        else:
            flash('Product not found.', 'error')

    total = sum(item['subtotal'] for item in session.get('active_transaction', []))
    all_products = Product.query.all()
    # Pass the list of Product objects directly
    return render_template('sales.html', products=all_products, transaction=session.get('active_transaction', []), total=total)

@app.route('/remove_item_from_sale/<int:item_id>', methods=['POST'])
@login_required
def remove_item_from_sale(item_id):
    active_transaction = session.get('active_transaction', [])
    updated_transaction = [item for item in active_transaction if item['id'] != item_id]
    
    # Check if a product was actually removed
    if len(active_transaction) > len(updated_transaction):
        flash('Item removed from cart.', 'info')
        session['active_transaction'] = updated_transaction
    else:
        flash('Item not found in cart.', 'error')
    
    return redirect(url_for('process_sales'))

@app.route('/complete_sale', methods=['POST'])
@login_required
def complete_sale():
    if not session.get('active_transaction'):
        flash('Cannot complete an empty sale.', 'error')
        return redirect(url_for('process_sales'))
    
    total_amount = sum(item['subtotal'] for item in session.get('active_transaction'))
    
    # Update product quantities in the database
    for item in session.get('active_transaction'):
        product = Product.query.get(item['id'])
        if product:
            product.quantity -= item['quantity']
            db.session.add(product) # Re-add to session to track the change
    
    # Store items as a JSON string for easy retrieval
    items_str = json.dumps(session.get('active_transaction'))
    
    new_sale = Sale(total_amount=total_amount, items=items_str)
    db.session.add(new_sale)
    db.session.commit()
    
    # Clear the active transaction
    session['active_transaction'] = []
    
    flash('Sale completed successfully!', 'success')
    return redirect(url_for('process_sales'))

@app.route('/cancel_sale', methods=['POST'])
@login_required
def cancel_sale():
    session['active_transaction'] = []
    flash('Sale cancelled.', 'info')
    return redirect(url_for('process_sales'))

@app.route('/history')
@login_required
def sales_history():
    # Fetch completed sales from the database
    completed_sales = [
        {
            'id': sale.id,
            'date': sale.timestamp.strftime('%Y-%m-%d %H:%M'),
            'total': sale.total_amount,
            # Safely load items from string before summing
            'item_count': sum(item['quantity'] for item in json.loads(sale.items.replace("'", "\"")))
        }
        for sale in Sale.query.order_by(Sale.timestamp.desc()).all()
    ]

    # Get the ongoing transaction from the session
    ongoing_transactions = [
        {
            'id': 'current',
            'item_count': sum(item['quantity'] for item in session.get('active_transaction', [])),
            'total': sum(item['subtotal'] for item in session.get('active_transaction', []))
        }
    ]

    # Fetch remaining products from the database
    remaining_products = [
        {'name': p.name, 'quantity': p.quantity}
        for p in Product.query.order_by(Product.name).all()
    ]

    # Calculate most purchased products
    purchase_counts = defaultdict(int)
    for sale in Sale.query.all():
        for item in json.loads(sale.items.replace("'", "\"")):
            purchase_counts[item['name']] += item['quantity']
    
    most_purchased_products = sorted(
        [{'name': name, 'count': count} for name, count in purchase_counts.items()],
        key=lambda x: x['count'],
        reverse=True
    )
    
    return render_template(
        'sales_history.html',
        completed_sales=completed_sales,
        ongoing_transactions=ongoing_transactions,
        remaining_products=remaining_products,
        most_purchased_products=most_purchased_products
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
