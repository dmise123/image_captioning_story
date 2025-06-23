# backend/app.py
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import shutil
import os
import tempfile
import httpx # Tambahkan httpx untuk memanggil API story generator
from typing import List # Tambahkan List
from pydantic import BaseModel, Field # Tambahkan Pydantic

# Impor fungsi dari skrip Anda
from caption_generator import load_model_assets, generate_caption_simple
from instagram_uploader import login_instagram, upload_image_to_instagram

# --- Konfigurasi URL API Story Generator di Server GPU ---
STORY_GENERATOR_API_URL = "https://u1029-story.gpu3.petra.ac.id/generate-story/"
# Anda bisa juga mengambil ini dari environment variable jika ingin lebih fleksibel
# STORY_GENERATOR_API_URL = os.getenv("STORY_GENERATOR_API_URL", "http://u1029-story.gpu3.petra.ac.id/generate-story/")


# --- Pydantic Models untuk endpoint baru ---
class CaptionsRequest(BaseModel):
    captions: List[str] = Field(
        ...,
        min_items=1,
        max_items=10, # Sesuaikan batasan jika perlu
        description="A list of image captions."
    )

class StoryResponse(BaseModel):
    story: str
    # Anda bisa menambahkan field lain jika API story generator mengembalikan lebih banyak info
    # model_used: str

# --- Inisialisasi Aplikasi FastAPI ---
app = FastAPI(title="Image Captioning, IG & Story API")

# --- Konfigurasi CORS ---
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    # Tambahkan URL frontend publik Anda jika ada
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pemuatan Model Caption (dilakukan sekali saat startup) ---
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

# --- Endpoint API yang Sudah Ada ---
@app.get("/")
async def read_root():
    return {"message": "Selamat datang di API Image Captioning, Instagram & Story!"}

@app.post("/generate-caption/")
async def api_generate_caption(image: UploadFile = File(...)):
    if not models_loaded:
        raise HTTPException(status_code=503, detail="Model caption tidak berhasil dimuat, layanan tidak tersedia.")
    temp_image_path = None # Inisialisasi
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
    temp_image_path = None # Inisialisasi
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

# --- ENDPOINT BARU UNTUK GENERATE STORY DARI CAPTIONS ---
@app.post("/generate-story-from-captions/", response_model=StoryResponse)
async def api_generate_story_from_captions(request_data: CaptionsRequest):
    """
    Menerima list caption dan memanggil API Story Generator di server GPU.
    """
    captions_to_send = request_data.captions
    if not captions_to_send:
        raise HTTPException(status_code=400, detail="No captions provided to generate story.")

    print(f"Menerima {len(captions_to_send)} caption untuk story, akan dikirim ke: {STORY_GENERATOR_API_URL}")

    try:
        async with httpx.AsyncClient(timeout=180.0) as client: # Timeout lebih lama untuk story
            # Payload untuk API story generator di GPU server
            payload_to_story_api = {"captions": captions_to_send}
            response_from_story_api = await client.post(STORY_GENERATOR_API_URL, json=payload_to_story_api)

            # Periksa jika API story generator mengembalikan error
            if response_from_story_api.status_code != 200:
                try:
                    error_detail = response_from_story_api.json().get("detail", response_from_story_api.text)
                except: # Jika respons bukan JSON
                    error_detail = response_from_story_api.text
                print(f"Error dari Story Generator API: {response_from_story_api.status_code} - {error_detail}")
                raise HTTPException(
                    status_code=response_from_story_api.status_code, # Gunakan status code dari API eksternal
                    detail=f"Story Generator API error: {error_detail}"
                )

            story_data = response_from_story_api.json()
            generated_story = story_data.get("story")

            if not generated_story:
                raise HTTPException(status_code=500, detail="Story Generator API returned an empty story.")

            return StoryResponse(story=generated_story)

    except httpx.RequestError as e:
        print(f"Tidak bisa terhubung ke Story Generator API di {STORY_GENERATOR_API_URL}: {e}")
        raise HTTPException(status_code=503, detail="Story Generator service is unavailable.")
    except Exception as e:
        print(f"Error tidak terduga saat generate story from captions: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal generate story: {str(e)}")


# --- Untuk Menjalankan Server Lokal (jika file ini dijalankan langsung) ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)