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


def product_detail(request, slug):
    product = Product.objects.get(slug=slug)
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
def checkout(request):
    cart = request.session.get('cart', {})
    if not cart:
        return redirect('product_list')

    # Create order
    order = Order.objects.create(user=request.user)
    total = Decimal('0.00')
    for pid, qty in cart.items():
        product = Product.objects.get(pk=int(pid))
        OrderItem.objects.create(order=order, product=product, price=product.price, quantity=qty)
        total += product.price * qty

    order.total = total
    order.reference = str(uuid.uuid4())
    order.save()

    # Clear cart
    request.session['cart'] = {}

    # Choose payment method
    method = request.POST.get('payment_method', 'paystack')

    if method == 'stripe':
        session_url = payments.create_stripe_checkout_session(order, request)
        return redirect(session_url)
    else:
        # Initialize Paystack payment
        paystack_response = payments.initialize_paystack_payment(order.total, request.user.email)
        if paystack_response.get('status') and 'data' in paystack_response:
            auth_url = paystack_response['data']['authorization_url']
            return redirect(auth_url)
        else:
            # Payment initialization failed
            return render(request, 'products/payment_error.html', {'error': 'Unable to initialize Paystack payment.'})



from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def paystack_webhook(request):
    # TODO: Verify Paystack signature and update order status
    return HttpResponse(status=200)


@csrf_exempt
def stripe_webhook(request):
    # TODO: Verify Stripe event and update order status
    return HttpResponse(status=200)



@login_required
def order_history(request):
    orders = request.user.orders.order_by('-created_at')
    return render(request, 'products/order_history.html', {'orders':orders})
# Create your views here.
