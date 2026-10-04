import stripe
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from xhtml2pdf import pisa
import json
import datetime
from .models import * 
from .utils import cookieCart, cartData, guestOrder

stripe.api_key = settings.STRIPE_SECRET_KEY

def home(request):
	data = cartData(request)
	cartItems = data['cartItems']

	featured_products = Product.objects.all()[:3]
	
	context = {'products': featured_products, 'cartItems': cartItems}
	return render(request, 'shop/home.html', context)

def shop(request):
	data = cartData(request)
	cartItems = data['cartItems']
	order = data['order']
	items = data['items']

	products = Product.objects.all()
	context = {'products':products, 'cartItems':cartItems}
	return render(request, 'shop/shop.html', context)

def cart(request):
	data = cartData(request)
	cartItems = data['cartItems']
	order = data['order']
	items = data['items']

	context = {'items':items, 'order':order, 'cartItems':cartItems}
	return render(request, 'shop/cart.html', context)

def checkout(request):
	data = cartData(request)
	cartItems = data['cartItems']
	order = data['order']
	items = data['items']

	context = {'items':items, 'order':order, 'cartItems':cartItems}
	return render(request, 'shop/checkout.html', context)

def updateItem(request):
	data = json.loads(request.body)
	productId = data['productId']
	action = data['action']
	print('Action:', action)
	print('Product:', productId)

	customer = request.user.customer
	product = Product.objects.get(id=productId)
	order, created = Order.objects.get_or_create(customer=customer, complete=False)

	orderItem, created = OrderItem.objects.get_or_create(order=order, product=product)

	if action == 'add':
		orderItem.quantity = (orderItem.quantity + 1)
	elif action == 'remove':
		orderItem.quantity = (orderItem.quantity - 1)

	orderItem.save()

	if orderItem.quantity <= 0:
		orderItem.delete()

	return JsonResponse('Item was added', safe=False)

def processOrder(request):
	transaction_id = datetime.datetime.now().timestamp()
	data = json.loads(request.body)

	if request.user.is_authenticated:
		customer = request.user.customer
		order, created = Order.objects.get_or_create(customer=customer, complete=False)

	else:
		customer, order = guestOrder(request, data)

	total = float(data['form']['total'])
	order.transaction_id = transaction_id
	order.save()	

	if order.shipping == True:
		ShippingAddress.objects.create(
		customer=customer,
		order=order,
		address=data['shipping']['address'],
		city=data['shipping']['city'],
		country=data['shipping']['country'],
		zipcode=data['shipping']['zipcode'],
		)

	order_items = order.orderitem_set.all()
	line_items = []

	for item in order_items:
		line_items.append({
			'price_data': {
				'currency': 'kes',  
				'product_data': {
					'name': item.product.name,
				},
				'unit_amount': int(item.product.price * 100),
			},
			'quantity': item.quantity,
		})

	# Creating Stripe Checkout Session
	try:
		checkout_session = stripe.checkout.Session.create(
			payment_method_types=['card'],
			line_items=line_items,
			mode='payment',
			success_url=f"http://127.0.0.1:8000/payment_success/{order.id}/",
			cancel_url="http://127.0.0.1:8000/checkout/",
		)
		return JsonResponse({'session_url': checkout_session.url})
	except Exception as e:
		return JsonResponse({'error': str(e)}, status=400)


def paymentSuccess(request, order_id):
    data = cartData(request)
    cartItems = data['cartItems']

    try:
        order = Order.objects.get(id=order_id, complete=False)
        order.complete = True
        order.save()
    except Order.DoesNotExist:
        order = Order.objects.get(id=order_id)

    context = {'order': order, 'cartItems':cartItems}
    response = render(request, 'shop/payment_success.html', context)
    response.set_cookie('cart', json.dumps({}), path='/')
    return response

def downloadReceipt(request, order_id):
    # generating a receipt 
    try:
        order = Order.objects.get(id=order_id)
        items = order.orderitem_set.all()
        shipping_info = ShippingAddress.objects.filter(order=order).first()
    except Order.DoesNotExist:
        return HttpResponse("Order not found", status=404)

    date_str = order.date_ordered.strftime('%B %d, %Y')
	
    items_html_rows = ""
    for item in items:
        items_html_rows += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">{item.product.name}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right;">KSh {item.product.price:,.2f}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: center;">{item.quantity}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0; text-align: right;">KSh {item.get_total:,.2f}</td>
        </tr>
        """

    shipping_html = "Digital Delivery"
    if shipping_info:
        shipping_html = f"""
            {shipping_info.address}<br>
            {shipping_info.city}, {shipping_info.zipcode}<br>
            {shipping_info.country}
        """

    # template structure for receipt 
    pdf_template_string = f"""<!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
      @page {{
        size: a4;
        margin: 20mm 15mm;
      }}
      body {{
        font-family: Helvetica, Arial, sans-serif;
        color: #334155;
        font-size: 10pt;
      }}
      .brand-title {{ font-size: 22pt; font-weight: bold; color: #0f172a; }}
      .brand-subtitle {{ font-size: 9.5pt; color: #64748b; }}
      .receipt-title {{ font-size: 26pt; color: #1e293b; text-align: right; text-transform: uppercase; }}
      .section-heading {{ font-size: 11pt; font-weight: bold; color: #0f172a; text-transform: uppercase; margin-bottom: 10px; }}
      .status-badge {{ background-color: #dcfce7; color: #166534; padding: 5px; font-weight: bold; text-align: center; width: 60px; }}
    </style>
    </head>
    <body>
      
      <!-- Header Segment -->
      <table style="width: 100%; margin-bottom: 30px;">
        <tr>
          <td style="vertical-align: top;">
            <div class="brand-title">GlobeCart LTD</div>
            <div class="brand-subtitle">123 Biashara Street, Nairobi, Kenya</div>
            <div class="brand-subtitle">support@globecart.com</div>
          </td>
          <td style="text-align: right; vertical-align: top;">
            <div class="receipt-title">Receipt</div>
            <span style="color: #64748b;">Order ID:</span> <strong>#{order.id}</strong><br>
            <span style="color: #64748b;">Date:</span> <strong>{date_str}</strong><br>
            <div class="status-badge">PAID</div>
          </td>
        </tr>
      </table>

      <hr style="border: none; border-top: 1px solid #e2e8f0; margin-bottom: 25px;">

      <!-- Customer Info Segment -->
      <table style="width: 100%; margin-bottom: 30px;">
        <tr>
          <td style="width: 50%; vertical-align: top;">
            <div class="section-heading">Billed To:</div>
            <strong>{order.customer.name if order.customer.name else 'Valued Customer'}</strong><br>
            {order.customer.email}
          </td>
          <td style="width: 50%; vertical-align: top;">
            <div class="section-heading">Shipping Address:</div>
            {shipping_html}
          </td>
        </tr>
      </table>

      <!-- Items Segment -->
      <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
        <thead>
          <tr style="background-color: #0f172a; color: #ffffff;">
            <th style="padding: 10px; text-align: left;">Product Description</th>
            <th style="padding: 10px; text-align: right;">Unit Price</th>
            <th style="padding: 10px; text-align: center;">Qty</th>
            <th style="padding: 10px; text-align: right;">Total Price</th>
          </tr>
        </thead>
        <tbody>
          {items_html_rows}
        </tbody>
      </table>

      <!-- Total Summary Segment -->
      <table style="width: 40%; margin-left: 60%; margin-top: 30px;">
        <tr>
          <td style="padding: 5px 0; font-size: 12pt; font-weight: bold; border-top: 2px solid #0f172a;">Total Paid:</td>
          <td style="padding: 5px 0; font-size: 12pt; font-weight: bold; text-align: right; border-top: 2px solid #0f172a;">KSh {order.get_cart_total:,.2f}</td>
        </tr>
      </table>

    </body>
    </html>
    """

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_order_{order.id}.pdf"'
    
    pisa_status = pisa.CreatePDF(pdf_template_string, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Error creating transaction receipt.', status=500)
        
    return response

def registerPage(request):
    if request.user.is_authenticated:
        return redirect('shop')

    data = cartData(request)
    cartItems = data['cartItems']

    form = UserCreationForm()
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, 'Account was created for ' + username)
            return redirect('login')
            
    context = {'form': form, 'cartItems':cartItems}
    return render(request, 'shop/register.html', context)


def loginPage(request):
    if request.user.is_authenticated:
        return redirect('shop')

    data = cartData(request)
    cartItems = data['cartItems']

    if request.method == 'POST':
        username = request.POST.get('username')
        password =  request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('shop')
        else:
            messages.info(request, 'Username or password is incorrect')

    context = {'cartItems':cartItems}
    return render(request, 'shop/login.html', context)


def logoutUser(request):
    logout(request)
    return redirect('login')

@login_required(login_url='login')
def rateProduct(request, product_id):
	if request.method == 'POST':
		data = json.loads(request.body)
		score = int(data.get('score', 0))

		if 1 <= score <= 5:
			product = Product.objects.get(id=product_id)
			Rating.objects.update_or_create(
				product=product,
				user=request.user,
				defaults={'score': score}
			)
			return JsonResponse({
				'status': 'success',
				'avg_rating': product.average_rating,
				'num_ratings': product.num_ratings
			})
		return JsonResponse({'error': 'Invalid score'}, status=400)
	
	return JsonResponse({'error': 'Invalid request'}, status=400)