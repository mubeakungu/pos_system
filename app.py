import os
from flask import Flask, render_template_string, request, jsonify

# Template for the POS system
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Simple POS System</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #f3f4f6;
            color: #1f2937;
        }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">

    <div class="bg-white shadow-xl rounded-lg p-8 w-full max-w-4xl flex flex-col md:flex-row space-y-8 md:space-y-0 md:space-x-8">

        <!-- Product List Section -->
        <div class="flex-1">
            <h2 class="text-2xl font-bold mb-6 text-gray-800">Products</h2>
            <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4" id="product-list">
                {% for product in PRODUCTS %}
                <div class="bg-gray-100 rounded-lg p-4 cursor-pointer hover:bg-blue-200 transition-colors duration-200 ease-in-out" onclick="addToCart('{{ product.name }}', {{ product.price }})">
                    <p class="font-semibold text-gray-800">{{ product.name }}</p>
                    <p class="text-gray-600">${{ "%.2f"|format(product.price|float) }}</p>
                </div>
                {% endfor %}
            </div>
        </div>

        <!-- Cart Section -->
        <div class="w-full md:w-96 flex flex-col justify-between bg-gray-50 rounded-lg p-6">
            <div>
                <h2 class="text-2xl font-bold mb-4 text-gray-800">Cart</h2>
                <div id="cart-items" class="space-y-4">
                    <!-- Cart items will be added here by JavaScript -->
                    <div id="empty-cart-message" class="text-center text-gray-500 italic">Cart is empty.</div>
                </div>
            </div>

            <div class="mt-8 pt-4 border-t border-gray-300">
                <div class="flex justify-between items-center text-lg font-semibold text-gray-800">
                    <span>Subtotal:</span>
                    <span id="subtotal-amount">$0.00</span>
                </div>
                <div class="flex justify-between items-center text-lg font-semibold text-gray-800">
                    <span>Tax (8%):</span>
                    <span id="tax-amount">$0.00</span>
                </div>
                <div class="flex justify-between items-center text-2xl font-bold text-gray-900 mt-2">
                    <span>Total:</span>
                    <span id="total-amount">$0.00</span>
                </div>
                <button onclick="checkout()" class="w-full mt-4 bg-green-500 text-white font-bold py-3 rounded-lg hover:bg-green-600 transition-colors duration-200 ease-in-out">
                    Checkout
                </button>
            </div>
        </div>

    </div>

    <script>
        let cart = {};

        const subtotalEl = document.getElementById('subtotal-amount');
        const taxEl = document.getElementById('tax-amount');
        const totalEl = document.getElementById('total-amount');
        const cartItemsEl = document.getElementById('cart-items');
        const emptyCartMessageEl = document.getElementById('empty-cart-message');

        function updateTotals() {
            let subtotal = 0;
            for (const item in cart) {
                subtotal += cart[item].price * cart[item].quantity;
            }
            const tax = subtotal * 0.08;
            const total = subtotal + tax;

            subtotalEl.textContent = `$${subtotal.toFixed(2)}`;
            taxEl.textContent = `$${tax.toFixed(2)}`;
            totalEl.textContent = `$${total.toFixed(2)}`;
        }

        function renderCart() {
            cartItemsEl.innerHTML = '';
            let cartIsEmpty = true;
            for (const item in cart) {
                cartIsEmpty = false;
                const cartItem = document.createElement('div');
                cartItem.className = 'flex justify-between items-center bg-white p-3 rounded-lg shadow-sm';
                cartItem.innerHTML = `
                    <div class="flex-1">
                        <p class="font-semibold text-gray-800">${item}</p>
                        <p class="text-sm text-gray-600">$${cart[item].price.toFixed(2)} x ${cart[item].quantity}</p>
                    </div>
                    <p class="font-bold text-gray-800">$${(cart[item].price * cart[item].quantity).toFixed(2)}</p>
                `;
                cartItemsEl.appendChild(cartItem);
            }
            
            if (cartIsEmpty) {
                emptyCartMessageEl.style.display = 'block';
            } else {
                emptyCartMessageEl.style.display = 'none';
            }

            updateTotals();
        }

        function addToCart(name, price) {
            if (cart[name]) {
                cart[name].quantity++;
            } else {
                cart[name] = { price: price, quantity: 1 };
            }
            renderCart();
        }
        
        function checkout() {
            if (Object.keys(cart).length === 0) {
                alert("Your cart is empty. Please add items to check out.");
                return;
            }
            
            const receipt = Object.entries(cart).map(([name, item]) => {
                const total = (item.price * item.quantity).toFixed(2);
                return `${item.quantity} x ${name} @ $${item.price.toFixed(2)} = $${total}`;
            }).join('\\n');

            alert("Checkout complete!\\n\\nReceipt:\\n" + receipt);
            
            // Clear the cart after successful checkout
            cart = {};
            renderCart();
        }

        // Initial render
        renderCart();

    </script>
</body>
</html>
"""

app = Flask(__name__)

PRODUCTS = [
    {"name": "Coffee", "price": 2.50},
    {"name": "Muffin", "price": 3.00},
    {"name": "Espresso", "price": 3.50},
    {"name": "Croissant", "price": 2.75},
    {"name": "Latte", "price": 4.00},
    {"name": "Tea", "price": 2.00},
    {"name": "Bagel", "price": 3.25},
    {"name": "Juice", "price": 3.50},
]

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE, PRODUCTS=PRODUCTS)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
# This block is for local development only. Gunicorn handles this in production.
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
