from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import shutil
import os
import tempfile
import httpx
from typing import List 
from pydantic import BaseModel, Field 


from caption_generator import load_model_assets, generate_caption_simple
from instagram_uploader import login_instagram, upload_image_to_instagram


STORY_GENERATOR_API_URL = "https://u1029-story.gpu3.petra.ac.id/generate-story/"
STORY_SEPARATOR_TOKEN = "[SEPARATOR]"

class StoryFromLocalApiResponse(BaseModel):
    story: str
    is_segmented: bool # Untuk memberitahu frontend apakah cerita ini punya segmen
    segment_count: int # Jumlah segmen yang diharapkan

class CaptionsRequest(BaseModel):
    captions: List[str] = Field(
        ...,
        min_items=1,
        max_items=10, 
        description="A list of image captions."
    )

class StoryResponse(BaseModel):
    story: str
    
app = FastAPI(title="Image Captioning, IG & Story API")


origins = [
    "http://localhost:5173",
    "http://localhost:3000",

]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


MODEL_DIR = "image_captioning_model_assets"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH_ABS = os.path.join(BASE_DIR, MODEL_DIR)

try:
    print(f"Mencoba memuat model caption dari: {MODEL_PATH_ABS}")
    encoder, decoder, tokenizer, inception_model, config = load_model_assets(MODEL_PATH_ABS)
    print("Model caption berhasil dimuat saat startup.")
    models_loaded = True
except Exception as e:
    print(f"GAGAL memuat model caption saat startup: {e}")
    encoder, decoder, tokenizer, inception_model, config = [None] * 5
    models_loaded = False


@app.get("/")
async def read_root():
    return {"message": "Selamat datang di API Image Captioning, Instagram & Story!"}

@app.post("/generate-caption/")
async def api_generate_caption(image: UploadFile = File(...)):
    if not models_loaded:
        raise HTTPException(status_code=503, detail="Model caption tidak berhasil dimuat, layanan tidak tersedia.")
    temp_image_path = None 
    try:
        temp_upload_dir = os.path.join(BASE_DIR, "temp_uploads")
        os.makedirs(temp_upload_dir, exist_ok=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(image.filename)[1], dir=temp_upload_dir) as tmp_file:
            shutil.copyfileobj(image.file, tmp_file)
            temp_image_path = tmp_file.name
        print(f"Gambar (caption) disimpan sementara di: {temp_image_path}")
        caption = generate_caption_simple(
            temp_image_path, encoder, decoder, tokenizer, inception_model, config
        )
        return {"filename": image.filename, "caption": caption}
    except Exception as e:
        print(f"Error saat generate caption: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal menghasilkan caption: {str(e)}")
    finally:
        if image and hasattr(image, 'file') and not image.file.closed:
            image.file.close()
        if temp_image_path and os.path.exists(temp_image_path):
            try:
                os.remove(temp_image_path)
                print(f"File temporer (caption) {temp_image_path} dihapus.")
            except Exception as e_del:
                print(f"Gagal menghapus file temporer (caption) {temp_image_path}: {e_del}")

@app.post("/post-to-instagram/")
async def api_post_to_instagram(
    username: str = Form(...),
    password: str = Form(...),
    caption: str = Form(...),
    image: UploadFile = File(...)
):
    temp_image_path = None 
    try:
        temp_upload_dir = os.path.join(BASE_DIR, "temp_uploads")
        os.makedirs(temp_upload_dir, exist_ok=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(image.filename)[1], dir=temp_upload_dir) as tmp_file:
            shutil.copyfileobj(image.file, tmp_file)
            temp_image_path = tmp_file.name
        print(f"Gambar (IG) disimpan sementara di: {temp_image_path}")
        client = login_instagram(username, password)
        upload_image_to_instagram(client, temp_image_path, caption)
        return {"message": "Berhasil diposting ke Instagram!"}
    except Exception as e:
        print(f"Error saat posting ke Instagram: {e}")
        if "login_required" in str(e).lower() or "checkpoint_required" in str(e).lower():
             raise HTTPException(status_code=401, detail="Login Instagram gagal. Periksa username/password atau akun mungkin memerlukan verifikasi.")
        raise HTTPException(status_code=500, detail=f"Gagal posting ke Instagram: {str(e)}")
    finally:
        if image and hasattr(image, 'file') and not image.file.closed:
            image.file.close()
        if temp_image_path and os.path.exists(temp_image_path):
            try:
                os.remove(temp_image_path)
                print(f"File temporer (IG) {temp_image_path} dihapus.")
            except Exception as e_del:
                print(f"Gagal menghapus file temporer (IG) {temp_image_path}: {e_del}")

@app.post("/generate-story-from-captions/", response_model=StoryFromLocalApiResponse) # Ubah response_model
async def api_generate_story_from_captions(request_data: CaptionsRequest):
    captions_to_send = request_data.captions
    if not captions_to_send:
        raise HTTPException(status_code=400, detail="No captions provided to generate story.")

    print(f"DEBUG (Local API): Menerima {len(captions_to_send)} caption, mengirim ke: {STORY_GENERATOR_API_URL}")

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            payload_to_story_api = {"captions": captions_to_send}
            response_from_story_api = await client.post(STORY_GENERATOR_API_URL, json=payload_to_story_api)

            if response_from_story_api.status_code != 200:
                # ... (error handling sama seperti sebelumnya) ...
                raise HTTPException(status_code=response_from_story_api.status_code, detail="Story Generator API error")

            story_api_response_data = response_from_story_api.json()
            generated_story_text = story_api_response_data.get("story")
            segment_count_from_api = story_api_response_data.get("segment_count", 0) # Ambil segment_count

            if not generated_story_text:
                raise HTTPException(status_code=500, detail="Story Generator API returned an empty story.")

            is_story_segmented = len(captions_to_send) > 1 and STORY_SEPARATOR_TOKEN in generated_story_text
            
            return StoryFromLocalApiResponse(
                story=generated_story_text,
                is_segmented=is_story_segmented, # Jika input > 1 caption
                segment_count=segment_count_from_api
            )

    # ... (error handling httpx.RequestError dan Exception umum tetap sama) ...
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail="Story Generator service is unavailable.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate story: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)