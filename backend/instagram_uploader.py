from instagrapi import Client



def login_instagram(username: str, password: str) -> Client:
    cl = Client()
    cl.login(username, password)
    return cl



def upload_image_to_instagram(client: Client, image_path: str, caption: str):
    client.photo_upload(image_path, caption)


if __name__ == "__main__":
    cl = login_instagram("shortstorydaily_", "titikkoma")
    upload_image_to_instagram(cl, "load.jpg", "Ini caption dari AI 🤖")


# # instagram_uploader.py
# from instagrapi import Client
# from instagrapi.exceptions import LoginRequired, ChallengeRequired, TwoFactorRequired # Impor exception yang relevan
# import os
# import time # Untuk jeda jika diperlukan

# SESSION_FILE = "ig_session.json" # Nama file untuk menyimpan data sesi
# # File ini akan dibuat di direktori yang sama dengan instagram_uploader.py (yaitu, di dalam backend/)

# def login_instagram(username: str, password: str) -> Client:
#     cl = Client()
#     cl.delay_range = [1, 3] # Tambahkan jeda acak kecil antar request internal instagrapi

#     if os.path.exists(SESSION_FILE):
#         try:
#             print(f"Mencoba memuat sesi dari {SESSION_FILE}...")
#             cl.load_settings(SESSION_FILE)
#             print(f"Sesi dimuat. Mencoba login dengan sesi untuk username: {username}")
#             # Login masih diperlukan untuk memverifikasi sesi dan mendapatkan data terbaru
#             # Jika sesi valid, login ini akan cepat dan tidak meminta kredensial ulang (biasanya)
#             cl.login(username, password)
#             print("Login dengan sesi berhasil dan sesi terverifikasi.")

#             # Lakukan operasi ringan untuk memastikan sesi benar-benar aktif
#             # Contoh: cl.get_timeline_feed(amount=1)
#             # Atau:
#             # user_id = cl.user_id_from_username(username)
#             # print(f"User ID berhasil didapatkan: {user_id}. Sesi aktif.")

#         except LoginRequired:
#             print("Sesi tidak valid atau kedaluwarsa (LoginRequired). Melakukan login baru...")
#             # Hapus file sesi yang tidak valid agar tidak dicoba lagi
#             if os.path.exists(SESSION_FILE):
#                 os.remove(SESSION_FILE)
#             cl.login(username, password) # Lakukan login standar
#             print("Login baru berhasil.")
#         except ChallengeRequired as e:
#             print(f"ChallengeRequired saat mencoba menggunakan sesi: {e}. Ini berarti Instagram meminta verifikasi.")
#             print("Anda mungkin perlu memasukkan kode verifikasi di terminal jika ini adalah proses interaktif.")
#             print("Menghapus sesi lama dan mencoba login baru yang mungkin memicu input kode.")
#             if os.path.exists(SESSION_FILE):
#                 os.remove(SESSION_FILE)
#             # Pada titik ini, jika challenge terjadi, instagrapi akan mem-print prompt untuk input kode di terminal
#             # di mana server FastAPI (app.py) berjalan.
#             cl.login(username, password)
#             print("Login baru setelah challenge berhasil (atau menunggu input kode).")

#         except TwoFactorRequired as e:
#             print(f"TwoFactorRequired saat mencoba menggunakan sesi: {e}.")
#             print("Akun ini menggunakan 2FA yang mungkin memerlukan input kode dari aplikasi authenticator atau SMS.")
#             print("Menghapus sesi lama dan mencoba login baru yang mungkin memicu input kode 2FA.")
#             if os.path.exists(SESSION_FILE):
#                 os.remove(SESSION_FILE)
#             # Instagrapi akan meminta input kode 2FA di terminal
#             cl.login(username, password)
#             print("Login baru setelah permintaan 2FA berhasil (atau menunggu input kode).")

#         except Exception as e:
#             print(f"Terjadi error tidak terduga saat memuat atau memverifikasi sesi: {e}")
#             print("Mencoba melakukan login baru sebagai fallback.")
#             if os.path.exists(SESSION_FILE):
#                 os.remove(SESSION_FILE) # Hapus sesi bermasalah
#             cl.login(username, password)
#             print("Login baru (fallback) berhasil.")
#     else:
#         print(f"File sesi '{SESSION_FILE}' tidak ditemukan. Melakukan login baru untuk username: {username}")
#         cl.login(username, password)
#         print("Login baru berhasil.")

#     # Selalu simpan/perbarui sesi setelah login berhasil
#     try:
#         print(f"Menyimpan/memperbarui sesi ke {SESSION_FILE}")
#         cl.dump_settings(SESSION_FILE)
#     except Exception as e:
#         print(f"Gagal menyimpan sesi: {e}")
#         # Ini tidak fatal, aplikasi masih bisa berjalan, tapi sesi tidak akan persisten

#     return cl

# def upload_image_to_instagram(client: Client, image_path: str, caption: str):
#     print(f"Mengunggah gambar '{image_path}' dengan caption: '{caption[:70]}...'")
#     try:
#         media = client.photo_upload(image_path, caption[:2200])
#         print(f"Gambar '{image_path}' berhasil diunggah. Media ID: {media.id if media else 'N/A'}")
#     except Exception as e:
#         print(f"Gagal mengunggah gambar '{image_path}': {e}")
#         raise # Re-throw exception agar bisa ditangani oleh pemanggil (app.py)

# if __name__ == "__main__":
#     # Contoh penggunaan untuk testing langsung file ini
#     # Ganti dengan username dan password Anda yang valid
#     test_username = "roy_kiyoshin1"  # Ganti ini
#     test_password = "roy123"  # Ganti ini
#     test_image = "path/ke/gambar/tes.jpg" # Ganti dengan path gambar valid
#     test_caption = "Caption tes dari skrip instagram_uploader.py 🤖"

#     if test_username == "roy_kiyoshin1" or test_password == "roy123":
#         print("Harap ganti USERNAME_ANDA dan PASSWORD_ANDA di bagian __main__ untuk testing.")
#     elif not os.path.exists(test_image):
#         print(f"File gambar tes '{test_image}' tidak ditemukan. Harap sediakan path yang benar.")
#     else:
#         print(f"Memulai tes login untuk {test_username}...")
#         try:
#             cl = login_instagram(test_username, test_password)
#             print(f"Login berhasil. Mencoba mengunggah {test_image}...")
#             upload_image_to_instagram(cl, test_image, test_caption)
#             print("Tes unggah gambar selesai.")
#         except ChallengeRequired:
#             print("Tes dihentikan karena Instagram meminta Challenge (misalnya, input kode verifikasi).")
#             print("Jika ini adalah server, kode harus dimasukkan di terminal server.")
#         except TwoFactorRequired:
#             print("Tes dihentikan karena Instagram meminta kode Two-Factor Authentication.")
#         except LoginRequired:
#             print("Tes gagal: LoginRequired. Periksa username/password.")
#         except Exception as e:
#             print(f"Tes gagal dengan error: {e}")
