from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_sqlalchemy import SQLAlchemy
import datetime
import os

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

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    items = db.Column(db.String(500), nullable=False)

# Move database initialization outside of __main__ block
with app.app_context():
    db.create_all()
    # Add a default admin user if the database is new
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', password='pass123') # Use a more secure password in a real app
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
    
    total_items = 0
    all_sales = Sale.query.all()
    for sale in all_sales:
        # Assuming items are stored as a comma-separated string, e.g., "Apple x2, Banana x1"
        item_list = sale.items.split(', ')
        for item_str in item_list:
            parts = item_str.split(' x')
            if len(parts) == 2 and parts[1].isdigit():
                total_items += int(parts[1])

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
        price = float(request.form.get('price'))
        image = request.files.get('image')
        image_filename = None

        if image and image.filename:
            image_filename = image.filename
            image_path = os.path.join(app.root_path, 'static', 'uploads', image_filename)
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            image.save(image_path)
            
        new_product = Product(name=name, price=price, image_filename=image_filename)
        db.session.add(new_product)
        db.session.commit()
        flash('Product added successfully!', 'success')
        return redirect(url_for('manage_products'))

    all_products = Product.query.all()
    # Convert query result to a dictionary for easy access in template
    products_dict = {str(p.id): p for p in all_products}
    return render_template('products.html', products=products_dict)

@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.price = float(request.form.get('price'))
        image = request.files.get('image')

        if image and image.filename:
            # Delete old image if it exists
            if product.image_filename:
                old_image_path = os.path.join(app.root_path, 'static', 'uploads', product.image_filename)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
            
            # Save new image
            image_filename = image.filename
            image_path = os.path.join(app.root_path, 'static', 'uploads', image_filename)
            image.save(image_path)
            product.image_filename = image_filename
        
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('manage_products'))
    return render_template('edit_product.html', product=product)

@app.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Delete the associated image file if it exists
    if product.image_filename:
        image_path = os.path.join(app.root_path, 'static', 'uploads', product.image_filename)
        if os.path.exists(image_path):
            os.remove(image_path)
            
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
            item = {
                'id': product.id,
                'name': product.name,
                'price': product.price,
                'quantity': quantity,
                'subtotal': product.price * quantity
            }
            # Use a session variable or a database table for the active transaction
            # to handle the state across requests.
            active_transaction = session.get('active_transaction', [])
            active_transaction.append(item)
            session['active_transaction'] = active_transaction
            flash(f'{item["name"]} added to cart.', 'success')
        else:
            flash('Product not found.', 'error')

    total = sum(item['subtotal'] for item in session.get('active_transaction', []))
    all_products = Product.query.all()
    products_dict = {str(p.id): p for p in all_products}
    
    return render_template('sales.html', products=products_dict, transaction=session.get('active_transaction', []), total=total)

@app.route('/complete_sale', methods=['POST'])
@login_required
def complete_sale():
    if not session.get('active_transaction'):
        flash('Cannot complete an empty sale.', 'error')
        return redirect(url_for('process_sales'))
    
    total_amount = sum(item['subtotal'] for item in session.get('active_transaction'))
    
    # Store items as a simple string for now
    items_str = ", ".join([f'{item["name"]} x{item["quantity"]}' for item in session.get('active_transaction')])
    
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
    all_sales = Sale.query.order_by(Sale.timestamp.desc()).all()
    return render_template('history.html', sales=all_sales)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
