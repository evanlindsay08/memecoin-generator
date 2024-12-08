from aiohttp import web, ClientSession  # type: ignore
import json
import os
from dotenv import load_dotenv  # type: ignore
import requests  # type: ignore
import time

load_dotenv()

routes = web.RouteTableDef()
LEONARDO_API_KEY = os.getenv('LEONARDO_API_KEY')
LEONARDO_BASE_URL = "https://cloud.leonardo.ai/api/rest/v1"

ART_STYLE_PROMPTS = {
    'pixel': """16-bit pixel art style, retro gaming aesthetic, clean pixelated edges,
        reminiscent of classic video games, limited color palette, sharp pixels""",
    
    'anime': """anime art style, manga-inspired, cel-shaded, vibrant colors,
        kawaii aesthetic, clean linework, anime character design""",
    
    '3d': """3D rendered style, volumetric lighting, subsurface scattering,
        realistic textures, ambient occlusion, ray-traced reflections""",
    
    'minimalist': """minimalist design, clean lines, simple shapes,
        limited color palette, negative space, geometric composition""",
    
    'cartoon': """cartoon style, bold outlines, vibrant colors,
        exaggerated features, playful design, smooth shading""",
    
    'realistic': """realistic digital painting, detailed textures,
        professional illustration, photorealistic elements, detailed shading"""
}

@routes.get('/')
async def serve_html(request):
    try:
        with open('index.html', 'r') as f:
            return web.Response(text=f.read(), content_type='text/html')
    except Exception as e:
        return web.Response(text=str(e), status=500)

@routes.get('/ping')
async def ping(request):
    return web.json_response({"status": "ok", "message": "Server is running"})

@routes.post('/api/test')
async def test(request):
    return web.json_response({"status": "success", "message": "Test successful"})

@routes.post('/api/generate')
async def generate(request):
    try:
        data = await request.json()
        idea = data.get('idea')
        generated_name = data.get('generatedName', '')
        is_regeneration = data.get('isRegeneration', False)
        art_style = data.get('artStyle', 'pixel')  # Default to pixel art
        
        if not idea:
            return web.json_response({"error": "No idea provided"}, status=400)

        # Get the art style prompt
        style_prompt = ART_STYLE_PROMPTS.get(art_style, ART_STYLE_PROMPTS['pixel'])

        # Create base prompt
        base_prompt = f"""detailed cryptocurrency mascot logo of a {generated_name or idea},
            {style_prompt},
            centered composition, clean vectorized style,
            suitable for crypto token, professional logo design"""

        headers = {
            'accept': 'application/json',
            'authorization': f'Bearer {LEONARDO_API_KEY}',
            'content-type': 'application/json'
        }

        payload = {
            "height": 512,
            "width": 512,
            "prompt": base_prompt,
            "modelId": "6bef9f1b-29cb-40c7-b9df-32b51c1f67d3",
            "negative_prompt": "text, watermark, logo, words, letters, signature, realistic, photographic, abstract shapes, blurry, low quality",
            "num_images": 1,
            "guidance_scale": 8,
            "init_strength": 0.4
        }

        try:
            print(f"Making request to Leonardo API...")
            print(f"Headers: {headers}")
            print(f"Payload: {payload}")
            
            async with ClientSession() as session:
                async with session.post(
                    f"{LEONARDO_BASE_URL}/generations",
                    headers=headers,
                    json=payload
                ) as response:
                    response_text = await response.text()
                    print(f"Response status: {response.status}")
                    print(f"Response text: {response_text}")
                    
                    if response.status != 200:
                        return web.json_response(
                            {"error": f"Failed to generate image: {response_text}"}, 
                            status=response.status
                        )
                    
                    generation_data = json.loads(response_text)
                    generation_id = generation_data['sdGenerationJob']['generationId']
                    
                    # Poll for results
                    for _ in range(30):
                        async with session.get(
                            f"{LEONARDO_BASE_URL}/generations/{generation_id}",
                            headers=headers
                        ) as check_response:
                            if check_response.status == 200:
                                result = await check_response.json()
                                if result['generations_by_pk']['status'] == 'COMPLETE':
                                    image_url = result['generations_by_pk']['generated_images'][0]['url']
                                    return web.json_response({
                                        "success": True,
                                        "imageUrl": image_url
                                    })
                        await web.asyncio.sleep(1)

                    return web.json_response({"error": "Timeout waiting for image"}, status=500)

        except Exception as api_error:
            print(f"API request error: {str(api_error)}")
            return web.json_response(
                {"error": f"API request failed: {str(api_error)}"}, 
                status=500
            )

    except Exception as e:
        print(f"General error: {str(e)}")
        return web.json_response({"error": str(e)}, status=500)

async def init_app():
    app = web.Application()
    app.add_routes(routes)
    
    # Add CORS middleware
    async def cors_middleware(app, handler):
        async def middleware_handler(request):
            if request.method == 'OPTIONS':
                response = web.Response()
            else:
                response = await handler(request)
                
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return response
        return middleware_handler
    
    app.middlewares.append(cors_middleware)
    return app

if __name__ == '__main__':
    print("Starting server...")
    print(f"Leonardo API Key present: {'Yes' if LEONARDO_API_KEY else 'No'}")
    port = int(os.environ.get('PORT', 8000))
    app = web.run_app(init_app(), port=port, host='0.0.0.0')
