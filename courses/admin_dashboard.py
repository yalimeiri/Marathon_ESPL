from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from courses.models import Purchase, CategoryAccess, Category
from django.contrib.auth import get_user_model

User = get_user_model()

def dashboard_callback(request, context):
    """
    Computes 6 core metrics and injects them into the admin dashboard context:
    1. Total revenue
    2. Revenue this month
    3. Total enrolled students
    4. Pending Approvals Count
    5. Sales per course
    6. Expiring Next 7 Days
    """
    now = timezone.now()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    in_7_days = now + timedelta(days=7)

    # 1. Total revenue (Sum of category prices for APPROVED purchases)
    approved_purchases = Purchase.objects.filter(status='APPROVED').select_related('category')
    total_revenue = sum(p.category.price for p in approved_purchases)

    # 2. Revenue this month
    monthly_purchases = approved_purchases.filter(created_at__gte=this_month_start)
    monthly_revenue = sum(p.category.price for p in monthly_purchases)

    # 3. Total enrolled students (Purchased or visiting category accesses, distinct by user)
    total_students = CategoryAccess.objects.values('user').distinct().count()

    # 4. Pending Approvals Count
    pending_approvals = Purchase.objects.filter(status='PENDING').count()

    # 5. Sales per course
    # Count of APPROVED purchases per category
    sales_qs = Purchase.objects.filter(status='APPROVED').values('category__name').annotate(
        sales_count=Count('id')
    ).order_by('-sales_count')
    
    sales_per_course = [
        {"name": item['category__name'], "sales": item['sales_count']}
        for item in sales_qs
    ]

    # 6. Expiring Next 7 Days (students whose access runs out within a week)
    expiring_soon = CategoryAccess.objects.filter(
        expires_at__isnull=False,
        expires_at__gte=now,
        expires_at__lte=in_7_days
    ).count()

    # Inject into context for use in our custom admin/index.html template
    context.update({
        "total_revenue": total_revenue,
        "monthly_revenue": monthly_revenue,
        "total_students": total_students,
        "pending_approvals": pending_approvals,
        "sales_per_course": sales_per_course,
        "expiring_soon": expiring_soon,
    })

    return context
