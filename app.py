from flask import Flask, render_template_string, request, jsonify

# Create the Flask application object
# Gunicorn looks for this 'app' object to run the application
app = Flask(__name__)

# Basic product data
PRODUCTS = {
    '1': {'name': 'Coffee', 'price': 3.50},
    '2': {'name': 'Tea', 'price': 2.75},
    '3': {'name': 'Muffin', 'price': 2.25},
    '4': {'name': 'Scone', 'price': 3.00}
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Simple POS System</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { font-family: 'Inter', sans-serif; }
    </style>
</head>
<body class="bg-gray-100 flex items-center justify-center min-h-screen p-4">
    <div class="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl">
        <h1 class="text-3xl font-bold text-center text-gray-800 mb-6">Simple POS</h1>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <!-- Product List -->
            <div class="products-list bg-gray-50 rounded-lg p-4 shadow-inner">
                <h2 class="text-xl font-semibold mb-4 text-gray-700">Products</h2>
                <div id="product-list" class="space-y-3">
                    <!-- Products will be rendered here by JS -->
                </div>
            </div>
            
            <!-- Shopping Cart -->
            <div class="shopping-cart bg-gray-50 rounded-lg p-4 shadow-inner">
                <h2 class="text-xl font-semibold mb-4 text-gray-700">Cart</h2>
                <div id="cart-items" class="space-y-2">
                    <!-- Cart items will be rendered here by JS -->
                    <p id="empty-cart-message" class="text-gray-500">Cart is empty.</p>
                </div>
                <div class="mt-4 pt-4 border-t border-gray-200">
                    <div class="flex justify-between items-center text-lg font-bold text-gray-800">
                        <span>Total:</span>
                        <span id="cart-total">$0.00</span>
                    </div>
                </div>
                <div class="mt-6 flex flex-col space-y-2">
                    <button onclick="checkout()" class="w-full bg-indigo-600 text-white font-semibold py-3 px-4 rounded-lg shadow-md hover:bg-indigo-700 transition-colors">
                        Checkout
                    </button>
                    <button onclick="clearCart()" class="w-full bg-gray-400 text-white font-semibold py-3 px-4 rounded-lg shadow-md hover:bg-gray-500 transition-colors">
                        Clear Cart
                    </button>
                </div>
                <div id="message-box" class="mt-4 p-3 rounded-lg text-sm text-center hidden"></div>
            </div>
        </div>
    </div>

    <script>
        const products = {{ PRODUCTS | tojson }};
        let cart = {};

        function showMessage(message, type) {
            const messageBox = document.getElementById('message-box');
            messageBox.textContent = message;
            messageBox.className = 'mt-4 p-3 rounded-lg text-sm text-center'; // Reset classes
            if (type === 'success') {
                messageBox.classList.add('bg-green-100', 'text-green-800', 'border', 'border-green-400');
            } else if (type === 'error') {
                messageBox.classList.add('bg-red-100', 'text-red-800', 'border', 'border-red-400');
            }
            messageBox.classList.remove('hidden');
        }

        function renderProducts() {
            const productList = document.getElementById('product-list');
            productList.innerHTML = '';
            for (const id in products) {
                const product = products[id];
                const productElement = document.createElement('div');
                productElement.className = 'flex justify-between items-center bg-white rounded-md p-3 shadow-sm hover:shadow-md transition-shadow';
                productElement.innerHTML = `
                    <span class="text-gray-900 font-medium">{{ product['name'] }}</span>
                    <span class="text-gray-600">${{ product['price'] | tofixed(2) }}</span>
                    <button onclick="addToCart('${id}')" class="bg-indigo-500 text-white text-sm px-3 py-1 rounded-md hover:bg-indigo-600 transition-colors">Add</button>
                `;
                productList.appendChild(productElement);
            }
        }

        function renderCart() {
            const cartItems = document.getElementById('cart-items');
            const emptyMessage = document.getElementById('empty-cart-message');
            cartItems.innerHTML = '';
            let total = 0;

            if (Object.keys(cart).length === 0) {
                emptyMessage.style.display = 'block';
            } else {
                emptyMessage.style.display = 'none';
                for (const id in cart) {
                    const item = cart[id];
                    total += item.price;
                    const itemElement = document.createElement('div');
                    itemElement.className = 'flex justify-between items-center bg-white rounded-md p-2 shadow-sm';
                    itemElement.innerHTML = `
                        <span class="text-gray-900">{{ item['name'] }}</span>
                        <span class="text-gray-600">${{ item['price'] | tofixed(2) }}</span>
                    `;
                    cartItems.appendChild(itemElement);
                }
            }

            document.getElementById('cart-total').textContent = `$${total.toFixed(2)}`;
        }

        function addToCart(productId) {
            const product = products[productId];
            if (product) {
                const newItem = {
                    name: product.name,
                    price: product.price,
                    id: productId
                };
                cart[Date.now()] = newItem; // Use a unique key for each item
                renderCart();
            }
        }

        function clearCart() {
            cart = {};
            renderCart();
            showMessage('Cart cleared!', 'success');
        }

        function checkout() {
            if (Object.keys(cart).length === 0) {
                showMessage('Cart is empty. Please add items to checkout.', 'error');
                return;
            }

            // In a real application, you would send this to a backend for processing
            showMessage('Checkout successful! Your order is being processed.', 'success');
            setTimeout(() => {
                clearCart();
            }, 3000);
        }

        document.addEventListener('DOMContentLoaded', () => {
            renderProducts();
            renderCart();
        });

        // Custom Jinja filter for toFixed(2)
        // This is a workaround for not having a built-in filter
        Object.defineProperty(Number.prototype, 'tofixed', {
            value: function(fixed) {
                return this.toFixed(fixed);
            },
            configurable: true
        });

    </script>
</body>
</html>
"""

@app.route('/')
def home():
    """Renders the main POS application page."""
    return render_template_string(HTML_TEMPLATE, PRODUCTS=PRODUCTS)

# This block is for local development only. Gunicorn handles this in production.
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
