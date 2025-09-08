from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_sqlalchemy import SQLAlchemy
import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_very_secret_key' # Change this to a real secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# In-memory data for demonstration
products = {
    "1": {"name": "Apple", "price": 0.5},
    "2": {"name": "Banana", "price": 0.3},
    "3": {"name": "Orange", "price": 0.6},
}

sales_history = []
active_transaction = []

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    items = db.Column(db.String(500), nullable=False) # Store as a string or JSON

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
    return render_template('index.html')

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

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/products', methods=['GET', 'POST'])
@login_required
def manage_products():
    if request.method == 'POST':
        name = request.form.get('name')
        price = float(request.form.get('price'))
        new_product = Product(name=name, price=price)
        db.session.add(new_product)
        db.session.commit()
        flash('Product added successfully!', 'success')
        return redirect(url_for('manage_products'))

    all_products = Product.query.all()
    # Convert query result to a dictionary for easy access in template
    products_dict = {str(p.id): p for p in all_products}
    return render_template('products.html', products=products_dict)

@app.route('/sales', methods=['GET', 'POST'])
@login_required
def process_sales():
    global active_transaction
    
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
            active_transaction.append(item)
            flash(f'{item["name"]} added to cart.', 'success')
        else:
            flash('Product not found.', 'error')

    total = sum(item['subtotal'] for item in active_transaction)
    all_products = Product.query.all()
    products_dict = {str(p.id): p for p in all_products}
    
    return render_template('sales.html', products=products_dict, transaction=active_transaction, total=total)

@app.route('/complete_sale', methods=['POST'])
@login_required
def complete_sale():
    global active_transaction, sales_history
    if not active_transaction:
        flash('Cannot complete an empty sale.', 'error')
        return redirect(url_for('process_sales'))
    
    total_amount = sum(item['subtotal'] for item in active_transaction)
    
    # Store items as a simple string for now
    items_str = ", ".join([f'{item["name"]} x{item["quantity"]}' for item in active_transaction])
    
    new_sale = Sale(total_amount=total_amount, items=items_str)
    db.session.add(new_sale)
    db.session.commit()
    
    # Clear the active transaction
    active_transaction = []
    
    flash('Sale completed successfully!', 'success')
    return redirect(url_for('process_sales'))

@app.route('/cancel_sale', methods=['POST'])
@login_required
def cancel_sale():
    global active_transaction
    active_transaction = []
    flash('Sale cancelled.', 'info')
    return redirect(url_for('process_sales'))

@app.route('/history')
@login_required
def sales_history():
    all_sales = Sale.query.order_by(Sale.timestamp.desc()).all()
    return render_template('history.html', sales=all_sales)

if __name__ == '__main__':
    # This block is now only for local development
    try:
        app.run(debug=True)
    except Exception as e:
        print(f"An error occurred during local application startup: {e}")
