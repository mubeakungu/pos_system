import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here' # You should use a strong, random key in production

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- In-memory Data Stores (for demonstration purposes) ---
# In a real application, you would use a database like PostgreSQL or SQLite.
products = {
    "1": {"name": "Laptop", "price": 1200.00},
    "2": {"name": "Mouse", "price": 25.00},
    "3": {"name": "Keyboard", "price": 75.00},
}

sales_history = []
current_transaction = []

# Dummy user data for demonstration
users = {
    "admin": {"password": "password123"},
    "user1": {"password": "userpass"}
}

class User(UserMixin):
    def __init__(self, id):
        self.id = id
    
    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    """
    Required user loader for Flask-Login.
    Loads a user from the dummy database.
    """
    if user_id in users:
        return User(user_id)
    return None

# --- Helper Functions ---
def get_total_sales():
    """Calculates the total revenue from all completed sales transactions."""
    total = 0.0
    for sale in sales_history:
        total += sale['total']
    return total

def get_total_items_sold():
    """Counts the total number of items sold across all transactions."""
    total = 0
    for sale in sales_history:
        for item in sale['items']:
            total += item['quantity']
    return total

# --- Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login.
    """
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in users and users[username]['password'] == password:
            user = User(username)
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """
    Handles user logout.
    """
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def home():
    """
    Renders the main dashboard page.
    Displays key metrics like total sales and items sold.
    """
    total_sales = get_total_sales()
    total_items = get_total_items_sold()
    return render_template('index.html', total_sales=total_sales, total_items=total_items)

@app.route('/products', methods=['GET', 'POST'])
@login_required
def manage_products():
    """
    Handles displaying and adding new products.
    GET: Renders the products management page with a list of all products.
    POST: Processes the form submission to add a new product to the system.
    """
    if request.method == 'POST':
        product_id = str(len(products) + 1)
        product_name = request.form['name']
        try:
            product_price = float(request.form['price'])
            products[product_id] = {"name": product_name, "price": product_price}
        except ValueError:
            # Handle cases where price is not a valid number
            pass
        return redirect(url_for('manage_products'))
    
    return render_template('products.html', products=products)

@app.route('/sales', methods=['GET', 'POST'])
@login_required
def process_sales():
    """
    Handles the sales transaction process.
    GET: Renders the sales page, showing the current transaction.
    POST: Processes the addition of an item to the current transaction.
    """
    global current_transaction
    
    if request.method == 'POST':
        product_id = request.form['product_id']
        try:
            quantity = int(request.form['quantity'])
            if quantity > 0 and product_id in products:
                product = products[product_id]
                current_transaction.append({
                    "id": product_id,
                    "name": product["name"],
                    "price": product["price"],
                    "quantity": quantity,
                    "subtotal": product["price"] * quantity
                })
        except (ValueError, KeyError):
            # Handle cases where quantity is not a valid number or product doesn't exist
            pass
        return redirect(url_for('process_sales'))
    
    transaction_total = sum(item['subtotal'] for item in current_transaction)
    return render_template('sales.html', products=products, transaction=current_transaction, total=transaction_total)

@app.route('/complete_sale', methods=['POST'])
@login_required
def complete_sale():
    """
    Finalizes the current sales transaction and saves it to history.
    """
    global current_transaction
    if current_transaction:
        sales_history.append({
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "items": current_transaction,
            "total": sum(item['subtotal'] for item in current_transaction)
        })
        current_transaction = []  # Reset the current transaction
    return redirect(url_for('process_sales'))

@app.route('/cancel_sale', methods=['POST'])
@login_required
def cancel_sale():
    """
    Clears the current sales transaction without saving.
    """
    global current_transaction
    current_transaction = []
    return redirect(url_for('process_sales'))

@app.route('/history')
@login_required
def view_history():
    """
    Renders the sales history page.
    """
    return render_template('history.html', sales=sales_history)


# --- Main entry point ---
if __name__ == '__main__':
    app.run(debug=True)

# This block is for local development only. Gunicorn handles this in production.
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
