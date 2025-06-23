from instagrapi import Client

# Fungsi login ke akun Instagram


def login_instagram(username: str, password: str) -> Client:
    cl = Client()
    cl.login(username, password)
    return cl

# Fungsi untuk upload gambar ke Instagram


def upload_image_to_instagram(client: Client, image_path: str, caption: str):
    client.photo_upload(image_path, caption)


if __name__ == "__main__":
    cl = login_instagram("roy_kiyoshin", "roy123")
    upload_image_to_instagram(cl, "load.jpg", "Ini caption dari AI 🤖")
