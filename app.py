import os
import datetime
import json
from collections import defaultdict
import cloudinary
import cloudinary.uploader
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
# New imports for QR Code generation
import qrcode
import base64
from io import BytesIO

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_very_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')

# Handle PostgreSQL URL format and add SSL for Render
if app.config['SQLALCHEMY_DATABASE_URI']:
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)
    if 'sslmode' not in app.config['SQLALCHEMY_DATABASE_URI']:
        app.config['SQLALCHEMY_DATABASE_URI'] += '?sslmode=require'


app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_timeout': 20,
    'max_overflow': 0
}

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
# Initialize Flask-Migrate with the app and db
migrate = Migrate(app, db)

# Cloudinary configuration
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET')
)

# --- Database Models ---
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=0)
    image_url = db.Column(db.String(255), nullable=True)
    public_id = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    items = db.Column(db.Text, nullable=False)
    # New columns to store KRA-related data
    kra_invoice_id = db.Column(db.String(255), nullable=True)
    kra_qr_code_data = db.Column(db.String(512), nullable=True)

# --- User Loader ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Utility Functions ---
def generate_qr_code_b64(data):
    """
    Generates a QR code for the given data and returns it as a base64 encoded string.
    """
    if not data:
        return None
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR code to a BytesIO object
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    
    # Encode to base64
    qr_code_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return qr_code_b64

# --- Routes ---
@app.route('/')
@login_required
def index():
    try:
        all_products = Product.query.all()
        total_sales = db.session.query(db.func.sum(Sale.total_amount)).scalar() or 0
        total_items = 0
        try:
            for sale in Sale.query.all():
                if sale.items:
                    items_data = json.loads(sale.items)
                    total_items += sum(item.get('quantity', 0) for item in items_data)
        except (json.JSONDecodeError, KeyError, TypeError):
            total_items = 0
            
        return render_template('index.html', total_sales=total_sales, total_items=total_items, products=all_products)
    except Exception as e:
        print(f"Error in index route: {e}")
        flash('Error loading dashboard data', 'error')
        return render_template('index.html', total_sales=0, total_items=0, products=[])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            user = User.query.filter_by(username=username).first()
            if user and user.verify_password(password):
                login_user(user)
                flash('Logged in successfully!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password.', 'error')
        except Exception as e:
            print(f"Login error: {e}")
            flash('Login system error. Please try again.', 'error')
    
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
            
        try:
            new_product = Product(name=name, price=price, quantity=quantity, image_url=image_url, public_id=public_id)
            db.session.add(new_product)
            db.session.commit()
            flash('Product added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"Error adding product: {e}")
            flash('Error adding product to database', 'error')
            
        return redirect(url_for('manage_products'))

    try:
        all_products = Product.query.all()
    except Exception as e:
        print(f"Error fetching products: {e}")
        all_products = []
        flash('Error loading products', 'error')
        
    return render_template('products.html', products=all_products)

@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    try:
        product = Product.query.get_or_404(product_id)
    except Exception as e:
        print(f"Error fetching product: {e}")
        flash('Product not found', 'error')
        return redirect(url_for('manage_products'))
        
    if request.method == 'POST':
        try:
            product.name = request.form.get('name')
            product.price = float(request.form.get('price'))
            product.quantity = int(request.form.get('quantity'))
            product.updated_at = datetime.datetime.utcnow()
            image = request.files.get('image')

            if image and image.filename:
                if product.public_id:
                    cloudinary.uploader.destroy(product.public_id)
                upload_result = cloudinary.uploader.upload(image)
                product.image_url = upload_result['secure_url']
                product.public_id = upload_result['public_id']
                
            db.session.commit()
            flash('Product updated successfully!', 'success')
            return redirect(url_for('manage_products'))
        except Exception as e:
            db.session.rollback()
            print(f"Error updating product: {e}")
            flash('Error updating product', 'error')
            
    return render_template('edit_product.html', product=product)

@app.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    try:
        product = Product.query.get_or_404(product_id)
        if product.public_id:
            cloudinary.uploader.destroy(product.public_id)
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting product: {e}")
        flash('Error deleting product', 'error')
        
    return redirect(url_for('manage_products'))

@app.route('/sales', methods=['GET', 'POST'])
@login_required
def process_sales():
    if request.method == 'POST':
        try:
            product_id = request.form.get('product_id')
            quantity = int(request.form.get('quantity', 1))
            
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
        except Exception as e:
            print(f"Error processing sale: {e}")
            flash('Error processing sale', 'error')

    try:
        total = sum(item['subtotal'] for item in session.get('active_transaction', []))
        all_products_list = Product.query.all()
        all_products_dict = {p.id: p for p in all_products_list}
    except Exception as e:
        print(f"Error loading sales data: {e}")
        total = 0
        all_products_dict = {}
        
    return render_template('sales.html', products=all_products_dict, transaction=session.get('active_transaction', []), total=total)

@app.route('/complete_sale', methods=['POST'])
@login_required
def complete_sale():
    if not session.get('active_transaction'):
        flash('Cannot complete an empty sale.', 'error')
        return redirect(url_for('process_sales'))
    
    try:
        active_transaction = session.get('active_transaction', [])
        total_amount = sum(item['subtotal'] for item in active_transaction)
        
        for item in active_transaction:
            product = Product.query.get(item['id'])
            if product:
                product.quantity -= item['quantity']
                db.session.add(product)
        
        items_str = json.dumps(active_transaction)
        
        # In a real KRA integration, you would make an API call here.
        # For now, we'll simulate the data that would be returned.
        kra_invoice_id = f"KRA-INV-{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        kra_qr_code_data = f"https://etims.kra.go.ke/verify?id={kra_invoice_id}"

        new_sale = Sale(
            total_amount=total_amount,
            items=items_str,
            kra_invoice_id=kra_invoice_id,
            kra_qr_code_data=kra_qr_code_data
        )
        db.session.add(new_sale)
        
        db.session.commit()
        
        # Store the ID of the new sale in the session to easily redirect to its receipt
        session['last_sale_id'] = new_sale.id
        session.pop('active_transaction', None)
        
        flash('Sale completed successfully!', 'success')
        return redirect(url_for('view_receipt', sale_id=new_sale.id))
    except Exception as e:
        db.session.rollback()
        print(f"Error completing sale: {e}")
        flash('Error completing sale', 'error')
        
    return redirect(url_for('process_sales'))

@app.route('/remove_item_from_sale/<int:item_id>', methods=['POST'])
@login_required
def remove_item_from_sale(item_id):
    active_transaction = session.get('active_transaction', [])
    updated_transaction = [item for item in active_transaction if item['id'] != item_id]
    
    if len(active_transaction) > len(updated_transaction):
        flash('Item removed from cart.', 'info')
        session['active_transaction'] = updated_transaction
    else:
        flash('Item not found in cart.', 'error')
    
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
    try:
        completed_sales = []
        for sale in Sale.query.order_by(Sale.timestamp.desc()).all():
            try:
                items_data = json.loads(sale.items)
                item_count = sum(item.get('quantity', 0) for item in items_data)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"Error processing sales history item {sale.id}: {e}")
                item_count = 0
                
            completed_sales.append({
                'id': sale.id,
                'date': sale.timestamp.strftime('%Y-%m-%d %H:%M'),
                'total': sale.total_amount,
                'item_count': item_count
            })

        ongoing_transactions = [{
            'id': 'current',
            'item_count': sum(item['quantity'] for item in session.get('active_transaction', [])),
            'total': sum(item['subtotal'] for item in session.get('active_transaction', []))
        }]

        remaining_products = [
            {'name': p.name, 'quantity': p.quantity}
            for p in Product.query.order_by(Product.name).all()
        ]

        purchase_counts = defaultdict(int)
        for sale in Sale.query.all():
            try:
                items_data = json.loads(sale.items)
                for item in items_data:
                    purchase_counts[item.get('name', '')] += item.get('quantity', 0)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"Error calculating purchase counts for sale {sale.id}: {e}")
                continue
            
        most_purchased_products = sorted(
            [{'name': name, 'count': count} for name, count in purchase_counts.items() if name],
            key=lambda x: x['count'],
            reverse=True
        )
        
    except Exception as e:
        print(f"Error loading sales history: {e}")
        completed_sales = []
        ongoing_transactions = []
        remaining_products = []
        most_purchased_products = []
        flash('Error loading sales history', 'error')
    
    return render_template(
        'sales_history.html',
        completed_sales=completed_sales,
        ongoing_transactions=ongoing_transactions,
        remaining_products=remaining_products,
        most_purchased_products=most_purchased_products
    )

@app.route('/view_receipt/<int:sale_id>')
@login_required
def view_receipt(sale_id):
    try:
        sale = Sale.query.get_or_404(sale_id)
        
        # Parse the items JSON
        items = json.loads(sale.items)
        
        # Get KRA-related data from the Sale model
        kra_invoice_id = sale.kra_invoice_id
        qr_code_data = sale.kra_qr_code_data
        
        # Generate the QR code as a base64 string
        qr_code_b64 = generate_qr_code_b64(qr_code_data)

        # Get clerk username
        clerk_username = current_user.username if current_user.is_authenticated else "N/A"
        
        return render_template(
            'receipt.html',
            sale=sale,
            items=items,
            kra_invoice_id=kra_invoice_id,
            qr_code_b64=qr_code_b64,
            clerk_username=clerk_username
        )
    except Exception as e:
        print(f"Error viewing receipt: {e}")
        flash('Error loading receipt.', 'error')
        return redirect(url_for('sales_history'))


# --- Main App Execution ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
