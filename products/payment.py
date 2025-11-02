
import requests
from django.conf import settings
from django.urls import reverse




def initialize_paystack_payment(amount, email):
    """
    Initializes a Paystack transaction.
    :param amount: Decimal amount
    :param email: Customer email
    :return: JSON response from Paystack API
    """
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "email": email,
        "amount": int(float(amount) * 100),  
        "callback_url": "http://127.0.0.1:8000/paystack/webhook/",
        "currency": "KES",  
    }

    try:
        response = requests.post(
            "https://api.paystack.co/transaction/initialize",
            json=data,
            headers=headers,
            timeout=15,
        )
        return response.json()
    except Exception as e:
        return {"status": False, "message": f"Paystack initialization failed: {str(e)}"}


def create_stripe_checkout_session(order, request):
    """
    Creates a Stripe Checkout Session for payment.
    :param order: Order instance
    :param request: Django request object
    :return: Stripe session URL
    """
    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",  
                        "product_data": {"name": f"Order {order.reference}"},
                        "unit_amount": int(float(order.total) * 100),  
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=request.build_absolute_uri(reverse("order_history")),
            cancel_url=request.build_absolute_uri(reverse("view_cart")),
            metadata={"order_id": order.id},
        )
        return session.url
    except Exception as e:
        print("Stripe session creation failed:", e)
        return request.build_absolute_uri(reverse("view_cart"))