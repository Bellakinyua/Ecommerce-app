from django.shortcuts import render

# Create your views here.
from django.shortcuts import render
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login
from django.contrib.auth.views import LogoutView
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.conf import settings
from django.urls import reverse
from decimal import Decimal
import uuid
import requests
from .models import Product, Category, Order, OrderItem
from .forms import SignUpForm
from . import payment as payments



def home(request):
    featured_products = Product.objects.all()[:12]  # get first 12 products
    return render(request, 'products/home.html', {'featured_products': featured_products})

def about(request):
    return render(request, 'products/about.html')


def product_list(request):
    products = Product.objects.filter(is_active=True)
    categories = Category.objects.all()
    q = request.GET.get('q')
    if q:
        products = products.filter(name_icontains=q) | products.filter(description_icontains=q)
    return render(request, 'products/product_list.html', {'products': products, 'categories': categories})

from django.shortcuts import render, get_object_or_404
from .models import Product

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    return render(request, 'products/product_detail.html', {'product': product})

def add_to_cart(request, product_id):
    cart = request.session.get('cart', {})
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    request.session['cart'] = cart
    return redirect('view_cart')

def remove_from_cart(request, product_id):
    cart = request.session.get('cart', {})
    cart.pop(str(product_id), None)
    request.session['cart'] = cart
    return redirect('view_cart')


def update_cart(request):
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        for key, val in request.POST.items():
            if key.startswith('qty_'):
                pid = key.split('_', 1)[1]
                try:
                    qty = int(val)
                    if qty > 0:
                        cart[pid] = qty
                    else:
                        cart.pop(pid, None)
                except ValueError:
                    continue
        request.session['cart'] = cart
    return redirect('view_cart')


def view_cart(request):
    cart = request.session.get('cart', {})
    items = []
    total = Decimal('0.00')
    for pid, qty in cart.items():
        try:
            product = Product.objects.get(pk=int(pid))
        except Product.DoesNotExist:
            continue
        line = product.price * qty
        total += line
        items.append({'product': product, 'quantity': qty, 'line_total': line})
    return render(request, 'products/cart.html', {'items': items, 'total': total})




from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib import messages
from django import forms
from .forms import SignUpForm


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created successfully! You can now log in.')
            return redirect('login')  # <-- make sure 'login' exists in your urls.py
        else:
            messages.error(request, 'There was an error with your signup. Please check the form.')
    else:
        form = SignUpForm()
    
    return render(request, 'products/register.html', {'form': form})



@login_required

def order_history(request):
    orders = request.user.orders.order_by('-created_at')
    return render(request, 'products/order_history.html', {'orders': orders})

def order_success(request):
    """Display success page after successful payment"""
    return render(request, 'products/order_success.html')
def verify_payment(request):
    """Verify payment via Paystack"""
    
    reference = request.GET.get('reference')  
    order_id = request.GET.get('order_id')    
    
    if not reference or not order_id:
        messages.error(request, "Payment verification failed: missing reference or order ID.")
        return redirect('home')
    
    url = f'https://api.paystack.co/transaction/verify/{reference}'
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        res_data = response.json()
        
        if res_data['status'] and res_data['data']['status'] == 'success':
            # Payment successful
            order = Order.objects.get(id=order_id)
            order.status = 'Paid'
            order.save()
            
            messages.success(request, "Payment verified successfully!")
            return redirect('order_success')
        else:
            messages.error(request, "Payment verification failed.")
            return redirect('home')
    
    except Order.DoesNotExist:
        messages.error(request, "Order not found.")
        return redirect('home')
    
    except Exception as e:
        messages.error(request, f"Error verifying payment: {str(e)}")
        return redirect('home')

def checkout(request):
    """Handle checkout and Paystack initialization"""
    cart = request.session.get('cart', {})
    items, total_price = [], 0

    if cart:
        products = Product.objects.filter(id__in=[int(pid) for pid in cart.keys()])
        for product in products:
            quantity = cart.get(str(product.id), 0)
            subtotal = product.price * quantity
            total_price += subtotal
            items.append({
                'product': product,
                'quantity': quantity,
                'subtotal': subtotal,
            })

    if request.method == 'POST':
        if total_price < 50:
            messages.error(request, "Total amount too low to process payment.")
            return redirect('checkout')

        email = request.user.email or 'customer@example.com'
        amount = int(total_price * 100)

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "email": email,
            "amount": amount,
            "callback_url": request.build_absolute_uri(reverse('verify_payment')),
        }

        try:
            response = requests.post("https://api.paystack.co/transaction/initialize", json=data, headers=headers)
            res_data = response.json()
            print("PAYSTACK RESPONSE:", res_data)  # ✅ Debugging output

            if res_data.get('status'):
                return redirect(res_data['data']['authorization_url'])
            else:
                messages.error(request, f"Paystack error: {res_data.get('message', 'Unknown error')}")
        except Exception as e:
            print("Paystack Error:", e)
            messages.error(request, "Payment initialization failed due to a server error.")

    context = {
        'items': items,
        'total_price': total_price,
        'paystack_public_key': settings.PAYSTACK_PUBLIC_KEY,
    }
    return render(request, 'products/checkout.html', context)
