from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_sqlalchemy import SQLAlchemy
import datetime
import os
from collections import defaultdict
import cloudinary
import cloudinary.uploader
import cloudinary.api

# -----------------------------------
# Flask Setup
# -----------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_very_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')

# Fix postgres:// issue
if app.config['SQLALCHEMY_DATABASE_URI'] and app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# -----------------------------------
# Cloudinary Setup (ENV Vars required)
# -----------------------------------
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

# -----------------------------------
# Database Models
# -----------------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=0)
    image_url = db.Column(db.String(500), nullable=True)  # Cloudinary URL

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    items = db.Column(db.String(1000), nullable=False)  # JSON string

# -----------------------------------
# Initialize DB
# -----------------------------------
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', password='pass123')
        db.session.add(admin_user)
        db.session.commit()
        print("✅ Default admin user created (admin / pass123)")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -----------------------------------
# Routes
# -----------------------------------

@app.route('/')
@login_required
def index():
    all_products = Product.query.all()
    total_sales = db.session.query(db.func.sum(Sale.total_amount)).scalar() or 0
    total_items = sum(item['quantity'] for sale in Sale.query.all() for item in eval(sale.items))
    return render_template('index.html', total_sales=total_sales, total_items=total_items, products=all_products)

# ---------------- Login ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully!", "info")
    return redirect(url_for('login'))

# ---------------- Products ----------------
@app.route('/products', methods=['GET', 'POST'])
@login_required
def manage_products():
    if request.method == 'POST':
        name = request.form.get('name')
        price_str = request.form.get('price')
        quantity_str = request.form.get('quantity')
        image = request.files.get('image')
        image_url = None

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
            upload_result = cloudinary.uploader.upload(image)
            image_url = upload_result.get("secure_url")

        new_product = Product(name=name, price=price, quantity=quantity, image_url=image_url)
        db.session.add(new_product)
        db.session.commit()
        flash('Product added successfully!', 'success')
        return redirect(url_for('manage_products'))

    all_products = Product.query.all()
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
            upload_result = cloudinary.uploader.upload(image)
            product.image_url = upload_result.get("secure_url")

        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('manage_products'))
    return render_template('edit_product.html', product=product)

@app.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('manage_products'))

# ---------------- Sales ----------------
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

    total = sum(item['subtotal'] for item in session.get('active_transaction', []))
    all_products = Product.query.all()
    return render_template('sales.html', products=all_products, transaction=session.get('active_transaction', []), total=total)

@app.route('/remove_item_from_sale/<int:item_id>', methods=['POST'])
@login_required
def remove_item_from_sale(item_id):
    active_transaction = session.get('active_transaction', [])
    updated_transaction = [item for item in active_transaction if item['id'] != item_id]
    session['active_transaction'] = updated_transaction
    flash('Item removed from cart.', 'info')
    return redirect(url_for('process_sales'))

@app.route('/complete_sale', methods=['POST'])
@login_required
def complete_sale():
    if not session.get('active_transaction'):
        flash('Cannot complete an empty sale.', 'error')
        return redirect(url_for('process_sales'))

    total_amount = sum(item['subtotal'] for item in session.get('active_transaction'))

    for item in session.get('active_transaction'):
        product = Product.query.get(item['id'])
        if product:
            product.quantity -= item['quantity']
            db.session.add(product)

    items_str = str(session.get('active_transaction'))
    new_sale = Sale(total_amount=total_amount, items=items_str)
    db.session.add(new_sale)
    db.session.commit()

    session['active_transaction'] = []
    flash('Sale completed successfully!', 'success')
    return redirect(url_for('process_sales'))

@app.route('/cancel_sale', methods=['POST'])
@login_required
def cancel_sale():
    session['active_transaction'] = []
    flash('Sale cancelled.', 'info')
    return redirect(url_for('process_sales'))

# ---------------- Sales History ----------------
@app.route('/history')
@login_required
def sales_history():
    completed_sales = [
        {
            'id': sale.id,
            'date': sale.timestamp.strftime('%Y-%m-%d %H:%M'),
            'total': sale.total_amount,
            'item_count': sum(item['quantity'] for item in eval(sale.items))
        }
        for sale in Sale.query.order_by(Sale.timestamp.desc()).all()
    ]

    ongoing_transactions = [
        {
            'id': 'current',
            'item_count': sum(item['quantity'] for item in session.get('active_transaction', [])),
            'total': sum(item['subtotal'] for item in session.get('active_transaction', []))
        }
    ]

    remaining_products = [
        {'name': p.name, 'quantity': p.quantity}
        for p in Product.query.order_by(Product.name).all()
    ]

    purchase_counts = defaultdict(int)
    for sale in Sale.query.all():
        for item in eval(sale.items):
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

# -----------------------------------
# Run App
# -----------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

