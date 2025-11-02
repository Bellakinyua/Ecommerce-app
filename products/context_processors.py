
def cart_item_count(request):
    cart = request.session.get('cart', {})
    count = sum(cart.values()) if cart else 0
    return {'cart_item_count':count}