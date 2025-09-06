import os
from flask import Flask, render_template_string, request, jsonify

# Create the Flask application instance
app = Flask(__name__)

# A simple in-memory "database" for our products.
# In a real application, you would use a proper database like PostgreSQL or SQLite.
PRODUCTS = {
    'sku-001': {'name': 'Laptop', 'price': 1200.00},
    'sku-002': {'name': 'Monitor', 'price': 300.00},
    'sku-003': {'name': 'Keyboard', 'price': 75.00},
    'sku-004': {'name': 'Mouse', 'price': 35.00},
    'sku-005': {'name': 'Webcam', 'price': 50.00},
}

# The HTML template for the POS interface.
# We are embedding this directly in the Python file for simplicity.
POS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Python POS System</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
    </style>
</head>
<body class="bg-gray-100 p-8 flex items-start justify-center min-h-screen">
    <div class="container mx-auto grid grid-cols-1 md:grid-cols-2 gap-8 max-w-7xl">
        <!-- Product Grid -->
        <div class="bg-white rounded-xl shadow-lg p-6">
            <h1 class="text-3xl font-bold text-gray-800 mb-6">Products</h1>
            <div id="product-list" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                <!-- Products will be rendered here by JavaScript -->
            </div>
        </div>

        <!-- Cart and Checkout -->
        <div class="bg-white rounded-xl shadow-lg p-6">
            <h1 class="text-3xl font-bold text-gray-800 mb-6">Cart</h1>
            <div id="cart" class="space-y-4">
                <ul id="cart-items" class="divide-y divide-gray-200">
                    <!-- Cart items will be rendered here -->
                </ul>
            </div>
            
            <div class="mt-8 pt-4 border-t border-gray-200">
                <div class="flex justify-between items-center text-xl font-semibold text-gray-800 mb-4">
                    <span>Total:</span>
                    <span id="total-price">$0.00</span>
                </div>
                <button id="checkout-btn" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-4 rounded-full transition-colors duration-200">
                    Checkout
                </button>
                <div id="message-box" class="mt-4 p-4 text-center text-sm font-medium rounded-lg hidden"></div>
            </div>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const productList = document.getElementById('product-list');
            const cartItemsContainer = document.getElementById('cart-items');
            const totalPriceElement = document.getElementById('total-price');
            const checkoutBtn = document.getElementById('checkout-btn');
            const messageBox = document.getElementById('message-box');

            let cart = {};

            // Function to fetch products from the server
            const fetchProducts = async () => {
                const response = await fetch('/api/products');
                const products = await response.json();
                renderProducts(products);
            };

            // Function to render products on the page
            const renderProducts = (products) => {
                productList.innerHTML = ''; // Clear existing products
                for (const sku in products) {
                    const product = products[sku];
                    const productCard = document.createElement('div');
                    productCard.className = 'bg-gray-50 rounded-lg p-4 cursor-pointer hover:bg-gray-100 transition-colors duration-200';
                    productCard.innerHTML = `
                        <h3 class="font-bold text-gray-900 truncate">${product.name}</h3>
                        <p class="text-gray-600 mt-1">$${product.price.toFixed(2)}</p>
                    `;
                    productCard.addEventListener('click', () => addToCart(sku, product));
                    productList.appendChild(productCard);
                }
            };

            // Function to add a product to the cart
            const addToCart = (sku, product) => {
                if (cart[sku]) {
                    cart[sku].quantity++;
                } else {
                    cart[sku] = { ...product, quantity: 1 };
                }
                renderCart();
            };

            // Function to remove a product from the cart
            const removeFromCart = (sku) => {
                if (cart[sku]) {
                    if (cart[sku].quantity > 1) {
                        cart[sku].quantity--;
                    } else {
                        delete cart[sku];
                    }
                }
                renderCart();
            };

            // Function to render the cart
            const renderCart = () => {
                cartItemsContainer.innerHTML = '';
                let total = 0;
                for (const sku in cart) {
                    const item = cart[sku];
                    const listItem = document.createElement('li');
                    listItem.className = 'py-4 flex justify-between items-center';
                    listItem.innerHTML = `
                        <div>
                            <p class="font-medium text-gray-900">${item.name} <span class="text-sm text-gray-500">x${item.quantity}</span></p>
                            <p class="text-sm text-gray-600">$${(item.price * item.quantity).toFixed(2)}</p>
                        </div>
                        <button class="text-red-500 hover:text-red-700 text-sm font-semibold" onclick="removeFromCart('${sku}')">Remove</button>
                    `;
                    cartItemsContainer.appendChild(listItem);
                    total += item.price * item.quantity;
                }
                totalPriceElement.textContent = `$${total.toFixed(2)}`;
            };

            // Expose removeFromCart to the global scope for the button's onclick
            window.removeFromCart = removeFromCart;

            // Handle the checkout process
            checkoutBtn.addEventListener('click', async () => {
                const items = Object.entries(cart).map(([sku, item]) => ({
                    sku,
                    quantity: item.quantity,
                    price: item.price
                }));

                if (items.length === 0) {
                    showMessage('The cart is empty!', 'bg-yellow-200 text-yellow-800');
                    return;
                }

                try {
                    const response = await fetch('/api/checkout', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ items })
                    });
                    const result = await response.json();
                    if (response.ok) {
                        showMessage(result.message, 'bg-green-200 text-green-800');
                        cart = {}; // Clear the cart on success
                        renderCart();
                    } else {
                        showMessage(result.message, 'bg-red-200 text-red-800');
                    }
                } catch (error) {
                    showMessage('An error occurred. Please try again.', 'bg-red-200 text-red-800');
                }
            });

            const showMessage = (message, styleClass) => {
                messageBox.textContent = message;
                messageBox.className = `mt-4 p-4 text-center text-sm font-medium rounded-lg ${styleClass}`;
                messageBox.classList.remove('hidden');
                setTimeout(() => {
                    messageBox.classList.add('hidden');
                }, 5000);
            };

            // Initial fetch of products
            fetchProducts();
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Renders the main POS page."""
    return render_template_string(POS_TEMPLATE)

@app.route('/api/products')
def get_products():
    """Returns the list of products as JSON."""
    return jsonify(PRODUCTS)

@app.route('/api/checkout', methods=['POST'])
def checkout():
    """Processes a sale transaction."""
    try:
        data = request.json
        if not data or 'items' not in data:
            return jsonify({'message': 'Invalid request'}), 400

        items = data['items']
        total_sale = 0
        for item in items:
            sku = item.get('sku')
            quantity = item.get('quantity', 1)
            if sku not in PRODUCTS:
                return jsonify({'message': f'Product with SKU {sku} not found.'}), 404
            
            product_info = PRODUCTS[sku]
            total_sale += product_info['price'] * quantity
            
        print(f"Processed sale for a total of ${total_sale:.2f}")
        return jsonify({'message': 'Checkout successful!', 'total': total_sale}), 200

    except Exception as e:
        print(f"Error during checkout: {e}")
        return jsonify({'message': 'An internal error occurred.'}), 500

if __name__ == '__main__':
    # Use Gunicorn in production via the start.sh script
    # This is for local development only.
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000), debug=True)
