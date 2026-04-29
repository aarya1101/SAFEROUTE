from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
import json

from .models import IPCSection, SafetyGuideline, ChatLog
from .utils import get_chatbot_response

@csrf_exempt
def chat_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            message = data.get("message", "").strip()

            if not message:
                return JsonResponse({"error": "Message cannot be empty"}, status=400)

            # AI se response (dictionary format mein) lena
            ai_data = get_chatbot_response(message)
            
            response_text = ai_data.get("reply", "I am having trouble processing that.")
            severity = ai_data.get("severity", 0.0)
            intent = ai_data.get("intent", "GENERAL")

            # Database mein log karna
            if request.user.is_authenticated:
                ChatLog.objects.create(
                    user=request.user,
                    message=message,
                    intent=intent,
                    response=response_text,
                    severity_score=severity
                )

            return JsonResponse({
                "intent": intent,
                "severity": severity,
                "response": response_text
            })

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)

def chat_page(request):
    return render(request, 'chatbot/chat.html')