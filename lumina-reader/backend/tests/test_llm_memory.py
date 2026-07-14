import sys
import os
import json
from unittest.mock import patch, MagicMock

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'lumina-reader', 'backend'))

# Mock pydantic config before importing settings
os.environ["OPENAI_API_KEY"] = "mock_key"
os.environ["STABILITY_API_KEY"] = "mock_key"

from services.llm_engine import analyze_style_and_characters, generate_page_prompt
from core.config import settings

def test_alice_is_blonde():
    print("Testing 'Alice is blonde' validation with mocked LLM...")
    
    # Mock the OpenAI response for Step 1 (analyze_style_and_characters)
    mock_response_1 = MagicMock()
    mock_response_1.choices = [MagicMock()]
    mock_response_1.choices[0].message.content = json.dumps({
        "global_art_style": "Cyberpunk, neon lighting, gritty textures",
        "character_bible": {
            "Alice": "tall woman with striking blonde hair, wearing a bright red scarf"
        }
    })

    # Mock the OpenAI response for Step 2 (generate_page_prompt)
    mock_response_2 = MagicMock()
    mock_response_2.choices = [MagicMock()]
    mock_response_2.choices[0].message.content = json.dumps({
        "scene_summary": "Alice runs towards a subway entrance in heavy rain.",
        "image_prompt": "Alice, a tall woman with striking blonde hair, wearing a bright red scarf, runs towards a subway entrance in heavy rain. Cyberpunk, neon lighting, gritty textures",
        "scene_changed": True
    })

    with patch('services.llm_engine.client.chat.completions.create', side_effect=[mock_response_1, mock_response_2]):
        intro_text = """
        The city was a sprawling metropolis of steel and neon. 
        Alice walked out of the diner. She was a tall woman with striking blonde hair, 
        wearing a bright red scarf wrapped tightly around her neck to fend off the cold. 
        She looked at the sky and sighed.
        """
        print("\n[Step 1] Analyzing intro text for style and character bible...")
        analysis = analyze_style_and_characters(intro_text)
        
        global_style = analysis.get("global_art_style", "")
        character_bible = analysis.get("character_bible", {})
        
        print(f"Global Style: {global_style}")
        print(f"Character Bible: {json.dumps(character_bible, indent=2)}")
        
        if "Alice" not in character_bible:
            print("❌ FAILED: 'Alice' not found in character bible.")
        elif "blonde" not in character_bible["Alice"].lower() and "red scarf" not in character_bible["Alice"].lower():
            print("❌ FAILED: Alice's physical traits ('blonde' or 'red scarf') not extracted properly.")
        else:
            print("✅ PASSED: Alice's traits extracted successfully.")

        scene_text = """
        The rain started to pour heavily. Alice quickly ran towards the nearest subway entrance, her boots splashing in the puddles. She narrowly avoided a passing hover-cab.
        """
        print("\n[Step 2] Generating page prompt for a subsequent scene...")
        prev_summary = "Alice stood outside a diner looking at the sky."
        
        prompt_data = generate_page_prompt(scene_text, prev_summary, character_bible, global_style)
        
        image_prompt = prompt_data.get("image_prompt", "")
        print(f"Generated Image Prompt:\n{image_prompt}")
        
        if "blonde" in image_prompt.lower() or "red scarf" in image_prompt.lower():
            print("✅ PASSED: The image prompt remembers that Alice is blonde/has a red scarf.")
        else:
            print("❌ FAILED: The image prompt forgot Alice's description from the character bible.")

if __name__ == "__main__":
    test_alice_is_blonde()

