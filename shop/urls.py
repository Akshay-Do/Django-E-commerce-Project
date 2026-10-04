from django.urls import path
from django.conf.urls.static import static
from django.conf import settings

from . import views

urlpatterns = [
    path('', views.home, name="home"),
	path('shop/', views.shop, name="shop"),
	path('cart/', views.cart, name="cart"),
	path('checkout/', views.checkout, name="checkout"),
    path('update_item/', views.updateItem, name="update_item"),
    path('process_order/', views.processOrder, name="process_order"),
    path('payment_success/<int:order_id>/', views.paymentSuccess, name="payment_success"),
    path('download_receipt/<int:order_id>/', views.downloadReceipt, name="download_receipt"),
    path('register/', views.registerPage, name="register"),
    path('login/', views.loginPage, name="login"),
    path('logout/', views.logoutUser, name="logout"),
    path('rate_product/<int:product_id>/', views.rateProduct, name="rate_product"),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)