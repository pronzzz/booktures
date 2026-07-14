import base64
import requests
import os
import uuid
from core.config import settings
import time

def generate_image(prompt: str) -> str:
    """
    Generates an image using Stability AI API.
    Returns the URL/path of the generated image.
    """
    print(f"Generating image for prompt: {prompt}")
    
    # Check for placeholder mode or missing key
    if not settings.STABILITY_API_KEY or "sk-..." in settings.STABILITY_API_KEY:
        print("Warning: Stability API Key missing. Using placeholder.")
        time.sleep(1)
        return f"https://placehold.co/1024x1024?text={prompt[:20].replace(' ', '+')}"

    api_host = os.getenv('API_HOST', 'https://api.stability.ai')
    engine_id = "stable-diffusion-xl-1024-v1-0"
    
    try:
        response = requests.post(
            f"{api_host}/v1/generation/{engine_id}/text-to-image",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {settings.STABILITY_API_KEY}"
            },
            json={
                "text_prompts": [{"text": prompt}],
                "cfg_scale": 7,
                "height": 1024,
                "width": 1024,
                "samples": 1,
                "steps": 30,
            },
            timeout=30
        )

        if response.status_code != 200:
            print(f"Error generating image: {response.text}")
            return f"https://placehold.co/1024x1024?text=Error+Generating+Image"

        data = response.json()
        
        # Save locally
        output_dir = "generated_images"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        for i, image in enumerate(data.get("artifacts", [])):
            filename = f"{uuid.uuid4()}.png"
            file_path = os.path.join(output_dir, filename)
            
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(image["base64"]))
                
            # Return URL accessible via static mount
            # Assuming backend is on localhost:8000
            return f"http://localhost:8000/generated/{filename}"
            
    except Exception as e:
        print(f"Exception during generation: {e}")
        return f"https://placehold.co/1024x1024?text=Generation+Exception"
        
    return f"https://placehold.co/1024x1024?text=Generation+Empty"
