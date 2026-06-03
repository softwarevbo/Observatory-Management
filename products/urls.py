from django.urls import path

from . import views

urlpatterns = [
    # HTML pages
    path("", views.ProductListPageView.as_view(), name="products"),
    path("list/", views.ProductListPageView.as_view(), name="products-list"),
    path("add/", views.ProductCreateView.as_view(), name="add-product"),
    path("detail/<int:pk>/", views.ProductDetailView.as_view(), name="product-detail"),
    path("edit/<int:pk>/", views.ProductEditView.as_view(), name="edit-product"),
    path("delete/<int:pk>/", views.ProductDeleteView.as_view(), name="delete-product"),
    path("categories/", views.CategoryListPageView.as_view(), name="categories"),
    path("categories/add/", views.CategoryCreateView.as_view(), name="add-category"),
    path(
        "categories/edit/<int:pk>/",
        views.CategoryEditView.as_view(),
        name="edit-category",
    ),
    path(
        "categories/delete/<int:pk>/",
        views.CategoryDeleteView.as_view(),
        name="delete-category",
    ),
    # API endpoints (for programmatic access)
    path("api/categories/", views.CategoryListCreate.as_view(), name="categories-api"),
    path("api/products/", views.ProductListCreate.as_view(), name="products-api"),
    # Excel template download
    path(
        "download-excel-template/",
        views.download_excel_template,
        name="download-excel-template",
    ),
]
