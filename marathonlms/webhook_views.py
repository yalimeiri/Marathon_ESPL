import json
import requests
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta
from courses.models import Purchase, CategoryAccess, AccessTier, SiteConfiguration
from django.conf import settings

@csrf_exempt
def telegram_webhook(request):
    if request.method == "POST":
        try:
            payload = json.loads(request.body)
            if "callback_query" in payload:
                callback = payload["callback_query"]
                callback_id = callback["id"]
                data = callback["data"]  # e.g., "approve_12" or "reject_12"
                message = callback["message"]
                chat_id = message["chat"]["id"]
                message_id = message["message_id"]
                
                try:
                    action, purchase_id = data.split("_")
                except ValueError:
                    return HttpResponse("OK")
                
                purchase = Purchase.objects.filter(id=purchase_id).first()
                if not purchase:
                    return HttpResponse("OK")
                
                if purchase.status == 'PENDING':
                    new_status = 'APPROVED' if action == 'approve' else 'REJECTED'
                    purchase.status = new_status
                    purchase.save()
                    
                    if new_status == 'APPROVED':
                        access, _ = CategoryAccess.objects.get_or_create(
                            user=purchase.user, 
                            category=purchase.category
                        )
                        access.access_level = AccessTier.PURCHASED
                        access.expires_at = timezone.now() + timedelta(days=120)  # 4 months
                        access.save()
                    
                    # Update message to remove buttons and show status
                    config = SiteConfiguration.get_solo()
                    bot_token = config.telegram_bot_token or settings.TELEGRAM_BOT_TOKEN
                    edit_url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
                    new_text = message.get("text", "") + f"\n\n[{new_status}]"
                    edit_payload = {
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": new_text
                    }
                    requests.post(edit_url, json=edit_payload, timeout=5)
                
                # Answer the callback query so the button stops loading
                config = SiteConfiguration.get_solo()
                bot_token = config.telegram_bot_token or settings.TELEGRAM_BOT_TOKEN
                answer_url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
                requests.post(answer_url, json={
                    "callback_query_id": callback_id,
                    "text": f"Purchase {purchase_id} {purchase.status}."
                }, timeout=5)
                
        except Exception as e:
            print(f"Telegram Webhook Error: {e}")
            
    return HttpResponse("OK")
