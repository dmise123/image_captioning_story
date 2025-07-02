
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import httpx 
from typing import List
import os



OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL_ID = os.getenv("OLLAMA_MODEL_ID", "gemma3:latest") 
STORY_SEPARATOR_TOKEN = "[SEPARATOR]" # Definisikan token separator

app = FastAPI(
    title="Story Generator API",
    description="API to generate stories from image captions using Ollama, with segment separation."
)

class StoryGenerationRequest(BaseModel):
    captions: List[str] = Field(..., min_items=1, max_items=10)
    # Tidak perlu lagi info jumlah caption, kita bisa cek dari len(captions)

class StoryGenerationResponse(BaseModel):
    story: str # Ini akan menjadi cerita penuh, mungkin dengan separator
    model_used: str = Field(OLLAMA_MODEL_ID)
    segment_count: int # Jumlah segmen yang diharapkan (sama dengan jumlah caption)

async def query_ollama_for_story(captions: List[str]) -> str:
    num_captions = len(captions)
    if num_captions == 0: # Tambahkan pemeriksaan eksplisit
        print("ERROR (Story API): query_ollama_for_story called with an empty captions list.")
        raise HTTPException(status_code=400, detail="Cannot generate story from empty captions.")

    prompt_header = "You are a creative storyteller. Based on the following descriptions from a sequence of images, write a coherent and engaging short story that connects them all into a single narrative.\n\n"
    
    # --- DEBUG: Periksa isi captions ---
    print(f"DEBUG (Story API): Captions received in query_ollama_for_story: {captions}")

    numbered_captions_str_list = [f"Image {i+1} Description: {caption}" for i, caption in enumerate(captions)]
    
    # --- DEBUG: Periksa numbered_captions_str_list ---
    print(f"DEBUG (Story API): Formatted numbered captions: {numbered_captions_str_list}")

    joined_numbered_captions = "\n".join(numbered_captions_str_list)

    # --- DEBUG: Periksa hasil join ---
    print(f"DEBUG (Story API): Joined numbered captions string:\n'''{joined_numbered_captions}'''")


    if num_captions > 1:
        prompt_instruction = (
            f"The story should have {num_captions} distinct parts, each corresponding to one of the image descriptions. (max length is 3 sentences) "
            f"Clearly separate each part of the story (that corresponds to an image description) with the exact token: {STORY_SEPARATOR_TOKEN}\n"
            f"For example, if there are 3 image descriptions, the output should be: "
            f"[Story part for Image 1] {STORY_SEPARATOR_TOKEN} [Story part for Image 2] {STORY_SEPARATOR_TOKEN} [Story part for Image 3]\n"
            "Ensure the story flows logically from one part to the next, even with the separators.\n\n"
        )
        full_prompt_content = prompt_header + prompt_instruction + joined_numbered_captions + "\n\nCombined Story:"
    else:
        full_prompt_content = prompt_header + joined_numbered_captions + "\n\nStory:"

    payload = {
        "model": OLLAMA_MODEL_ID,
        "prompt": full_prompt_content,
        "stream": False,
    }

    target_ollama_url = f"{OLLAMA_API_URL}/api/generate"
    
    # --- DEBUG: Tampilkan prompt lengkap yang akan dikirim ke Ollama ---
    print(f"DEBUG (Story API): FINAL PROMPT being sent to Ollama at {target_ollama_url} with model {OLLAMA_MODEL_ID}:\n---------------- PROMPT START ----------------\n{full_prompt_content}\n---------------- PROMPT END ----------------")

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(target_ollama_url, json=payload)
            # ... (sisa kode error handling dan parsing respons tetap sama) ...
            response.raise_for_status()
            response_data = response.json()
            generated_text = response_data.get("response", "").strip()

            if not generated_text:
                print("Ollama returned an empty response.")
                raise HTTPException(status_code=500, detail="Ollama returned an empty story.")
            return generated_text

    except httpx.HTTPStatusError as e:
        error_detail = f"Ollama API error: {e.response.status_code} - Response: {e.response.text[:500]}" # Tampilkan sebagian respons error
        print(f"ERROR (Story API): {error_detail}")
        if e.response.status_code == 404: # Bisa jadi model tidak ditemukan juga
             raise HTTPException(status_code=502, detail=f"Ollama service error: 404 Not Found. Check model '{OLLAMA_MODEL_ID}' or API path '{target_ollama_url}'. Ollama response: {e.response.text[:200]}")
        raise HTTPException(status_code=502, detail=f"Error from Ollama service: {e.response.status_code}")

@app.post("/generate-story/", response_model=StoryGenerationResponse)
async def generate_story_endpoint(request: StoryGenerationRequest):
    if not request.captions:
        raise HTTPException(status_code=400, detail="No captions provided.")
    
    num_captions = len(request.captions)
    print(f"DEBUG (Story API): Received {num_captions} captions for story generation.")

    try:
        story_text = await query_ollama_for_story(request.captions)
        return StoryGenerationResponse(story=story_text, model_used=OLLAMA_MODEL_ID, segment_count=num_captions)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate story due to an internal server error.")

@app.get("/")
async def root():
    return {"message": "Story Generator API with segment support is running."}