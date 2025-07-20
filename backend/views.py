from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from supabase_client import supabase_anon, supabase_admin
import os

@csrf_exempt
def upload_to_supabase(request):
    if request.method == 'POST':
        file = request.FILES.get('file')
        if not file:
            return JsonResponse({'error': 'No file provided'}, status=400)

        content = file.read()
        filename = file.name

        # 버킷 이름이 media라고 가정
        supabase_anon.storage.from_('media').upload(filename, content)

        # Public URL 생성
        url = f"{os.getenv('SUPABASE_URL')}/storage/v1/object/public/media/{filename}"
        return JsonResponse({'url': url})
    
    return JsonResponse({'error': 'Invalid method'}, status=405)
