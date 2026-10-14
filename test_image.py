import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

try:
    result = client.models.generate_images(
        model='imagen-3.0-generate-001',
        prompt='A modern smartphone showing a green website interface, professional marketing design.',
        config=dict(
            number_of_images=1,
            output_mime_type="image/jpeg",
            aspect_ratio="1:1"
        )
    )
    for generated_image in result.generated_images:
        print(f"Generated image length: {len(generated_image.image.image_bytes)} bytes")
except Exception as e:
    print(e)
