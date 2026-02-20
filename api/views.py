from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
import json
from .route_service import RouteService

@csrf_exempt
@require_http_methods(["POST"])
def calculate_route(request):
    """
    API endpoint to calculate optimal fuel route.
    
    POST /api/route
    Body: {
        "start": "New York, NY",
        "end": "Los Angeles, CA"
    }
    
    Returns: {
        "route": {...},
        "fuel_stops": [...],
        "total_fuel_cost": 123.45
    }
    """
    try:
        data = json.loads(request.body)
        start = data.get('start', '').strip()
        end = data.get('end', '').strip()
        
        if not start or not end:
            return JsonResponse({
                'error': 'Both start and end locations are required'
            }, status=400)
        
        # Calculate route and fuel stops
        route_service = RouteService()
        result = route_service.calculate_optimal_fuel_stops(start, end)
        
        if 'error' in result:
            return JsonResponse(result, status=404)
        
        return JsonResponse(result)
        
    except ValueError as e:
        return JsonResponse({
            'error': str(e)
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'error': f'Internal server error: {str(e)}'
        }, status=500)

@require_http_methods(["GET"])
def index(request):
    """Render the frontend interface."""
    return render(request, 'index.html')

@require_http_methods(["GET"])
def health_check(request):
    """Health check endpoint."""
    return JsonResponse({
        'status': 'ok',
        'service': 'Fuel Route Optimizer API'
    })
