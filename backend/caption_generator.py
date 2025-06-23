import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import json
import pickle
import os
import argparse

# --- Definisi Model (HARUS SAMA PERSIS dengan di notebook training) ---


class BahdanauAttention(tf.keras.Model):
    def __init__(self, units):
        super(BahdanauAttention, self).__init__()
        self.units = units  # Simpan units untuk referensi jika perlu
        self.W1 = tf.keras.layers.Dense(units)
        self.W2 = tf.keras.layers.Dense(units)
        self.V = tf.keras.layers.Dense(1)

    def call(self, features, hidden):
        # features shape: (batch_size, num_attention_features, cnn_embedding_dim) -> e.g., (1, 64, 256)
        # hidden shape SEHARUSNYA: (batch_size, self.units) -> e.g., (1, 512)

        # WORKAROUND: Periksa dan perbaiki bentuk 'hidden' jika ia adalah rank-1 tensor
        if tf.rank(hidden) == 1:
            # Dapatkan batch_size dari tensor 'features'
            current_batch_size = tf.shape(features)[0]
            # tf.print("Warning: Reshaping hidden in BahdanauAttention from rank 1. Original shape:", tf.shape(hidden),
            #          "Target batch_size:", current_batch_size, "Target units:", self.units)
            # Bentuk ulang 'hidden' menjadi (current_batch_size, self.units)
            hidden = tf.reshape(hidden, [current_batch_size, self.units])
            # Anda mungkin ingin memastikan bentuknya setelah reshape jika perlu debug lebih lanjut
            # hidden = tf.ensure_shape(hidden, [None, self.units])

        # hidden_with_time_axis shape == (batch_size, 1, self.units)
        hidden_with_time_axis = tf.expand_dims(hidden, 1)

        # self.W1(features) hasilnya (batch_size, num_attention_features, self.units)
        # self.W2(hidden_with_time_axis) hasilnya (batch_size, 1, self.units)
        # Penjumlahan menggunakan broadcasting: (batch_size, num_attention_features, self.units)
        score = tf.nn.tanh(self.W1(features) + self.W2(hidden_with_time_axis))

        # attention_weights shape == (batch_size, num_attention_features, 1)
        attention_weights = tf.nn.softmax(self.V(score), axis=1)

        # context_vector shape after sum == (batch_size, self.units)
        context_vector = attention_weights * features
        context_vector = tf.reduce_sum(context_vector, axis=1)

        return context_vector, attention_weights


class CNN_Encoder(tf.keras.Model):
    def __init__(self, embedding_dim):
        super(CNN_Encoder, self).__init__()
        self.fc = tf.keras.layers.Dense(embedding_dim)

    def call(self, x, training=False):  # Tambahkan parameter training jika ada di definisi asli
        x = self.fc(x)
        x = tf.nn.relu(x)
        return x


class RNN_Decoder(tf.keras.Model):
    def __init__(self, embedding_dim, units, vocab_size):
        super(RNN_Decoder, self).__init__()
        self.units = units
        self.embedding = tf.keras.layers.Embedding(vocab_size, embedding_dim)
        self.gru = tf.keras.layers.GRU(self.units,
                                       return_sequences=True,
                                       return_state=True,
                                       recurrent_initializer='glorot_uniform')
        self.fc1 = tf.keras.layers.Dense(self.units)
        self.fc2 = tf.keras.layers.Dense(vocab_size)
        self.attention = BahdanauAttention(self.units)

    def call(self, x, features, hidden, training=False):  # Tambahkan parameter training
        context_vector, attention_weights = self.attention(features, hidden)
        x = self.embedding(x)
        x = tf.concat([tf.expand_dims(context_vector, 1), x], axis=-1)
        # Pastikan training=training diteruskan
        output, state = self.gru(x, training=training)
        x = self.fc1(output)
        x = tf.reshape(x, (-1, x.shape[2]))
        x = self.fc2(x)
        return x, state, attention_weights

    def reset_state(self, batch_size):
        return tf.zeros((batch_size, self.units))
# --- Akhir Definisi Model ---


def load_image_preprocess(image_path):
    """Memuat dan memproses gambar seperti pada training."""
    img = tf.io.read_file(image_path)
    img = tf.image.decode_jpeg(img, channels=3)
    img = tf.image.resize(img, (299, 299))
    img = tf.keras.applications.inception_v3.preprocess_input(img)
    return img, image_path


def generate_caption(image_path, inception_model, cnn_encoder, rnn_decoder, tokenizer, model_config):
    """Menghasilkan caption untuk gambar."""
    max_length = model_config['max_length']
    # e.g., 64
    attention_features_shape = model_config['attention_features_shape']

    attention_plot = np.zeros((max_length, attention_features_shape))
    hidden = rnn_decoder.reset_state(batch_size=1)

    temp_input = tf.expand_dims(load_image_preprocess(
        image_path)[0], 0)  # (1, 299, 299, 3)
    img_tensor_val = inception_model(temp_input)  # (1, 8, 8, 2048)
    img_tensor_val = tf.reshape(
        img_tensor_val, (img_tensor_val.shape[0], -1, img_tensor_val.shape[3]))  # (1, 64, 2048)

    # (1, 64, embedding_dim)
    features = cnn_encoder(img_tensor_val, training=False)

    dec_input = tf.expand_dims([tokenizer.word_index['<start>']], 0)
    result_caption = []

    for i in range(max_length):
        predictions, hidden, attention_weights = rnn_decoder(
            dec_input, features, hidden, training=False)
        attention_plot[i] = tf.reshape(attention_weights, (-1, )).numpy()
        predicted_id = tf.argmax(predictions[0]).numpy()

        word = tokenizer.index_word.get(
            predicted_id, "<unk>")  # Handle unknown words
        result_caption.append(word)

        if word == '<end>':
            break

        dec_input = tf.expand_dims([predicted_id], 0)

    attention_plot = attention_plot[:len(result_caption), :]
    return ' '.join(result_caption), attention_plot


def generate_caption_simple(image_path, encoder, decoder, tokenizer, inception_model, config):
    caption, _ = generate_caption(
        image_path, inception_model, encoder, decoder, tokenizer, config
    )
    return caption.replace("<start>", "").replace("<end>", "").strip()


def plot_attention(image_path, result_caption, attention_plot):
    """Menampilkan gambar dengan plot attention."""
    temp_image = np.array(Image.open(image_path))
    fig = plt.figure(figsize=(10, 10))
    len_result = len(result_caption.split())

    # Perbaikan: pastikan subplot grid cukup besar
    # Misalnya, jika len_result adalah 5, kita butuh grid 3x2 atau 2x3.
    # Jika len_result adalah 1, grid 1x1.
    # Jika len_result adalah 0 (jarang terjadi), hindari error.
    if len_result == 0:
        print("Warning: Hasil caption kosong, tidak bisa plot attention.")
        return

    cols = int(np.ceil(np.sqrt(len_result)))
    rows = int(np.ceil(len_result / cols))

    for l_idx, word in enumerate(result_caption.split()):
        if l_idx >= attention_plot.shape[0]:  # Pastikan tidak out of bounds
            break
        # Asumsi fitur attention adalah 8x8
        temp_att = np.resize(attention_plot[l_idx], (8, 8))
        ax = fig.add_subplot(rows, cols, l_idx + 1)
        ax.set_title(word)
        img_display = ax.imshow(temp_image)
        ax.imshow(temp_att, cmap='gray', alpha=0.6,
                  extent=img_display.get_extent())
        ax.axis('off')

    plt.tight_layout()
    plt.show()


def load_model_assets(model_dir='image_captioning_model_assets'):
    """Memuat semua aset yang diperlukan untuk caption generation."""
    print(f"Memuat aset dari direktori: {model_dir}")

    if not os.path.exists(model_dir):
        raise FileNotFoundError(
            f"Error: Direktori model '{model_dir}' tidak ditemukan.")

    config_path = os.path.join(model_dir, 'model_config.json')
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Error: File konfigurasi '{config_path}' tidak ditemukan.")
    with open(config_path, 'r') as f:
        config = json.load(f)
    print("Konfigurasi model dimuat.")

    embedding_dim = config['embedding_dim']
    units = config['units']
    vocab_size = config['vocab_size']
    features_shape = config['features_shape']
    attention_features_shape = config['attention_features_shape']

    tokenizer_path = os.path.join(model_dir, 'tokenizer.pickle')
    if not os.path.exists(tokenizer_path):
        raise FileNotFoundError(
            f"Error: File tokenizer '{tokenizer_path}' tidak ditemukan.")
    with open(tokenizer_path, 'rb') as handle:
        tokenizer = pickle.load(handle)
    print("Tokenizer dimuat.")

    encoder = CNN_Encoder(embedding_dim)
    decoder = RNN_Decoder(embedding_dim, units, vocab_size)
    print("Instance model CNN_Encoder dan RNN_Decoder dibuat.")

    inception_model_path = os.path.join(
        model_dir, 'inception_feature_extractor.keras')
    if not os.path.exists(inception_model_path):
        raise FileNotFoundError(
            f"Error: File Inception model '{inception_model_path}' tidak ditemukan.")
    image_features_extract_model = tf.keras.models.load_model(
        inception_model_path, compile=False)
    print("InceptionV3 feature extractor berhasil dimuat.")

    print("Membangun CNN_Encoder...")
    dummy_encoder_input = tf.random.uniform(
        shape=[1, attention_features_shape, features_shape])
    _ = encoder(dummy_encoder_input, training=False)

    print("Membangun RNN_Decoder...")
    dummy_decoder_token_input = tf.zeros(shape=[1, 1], dtype=tf.int32)
    dummy_decoder_features_input = tf.random.uniform(
        shape=[1, attention_features_shape, embedding_dim])
    dummy_hidden_state = decoder.reset_state(batch_size=1)
    _ = decoder(dummy_decoder_token_input, dummy_decoder_features_input,
                dummy_hidden_state, training=False)
    print("Model Encoder dan Decoder dibangun.")

    encoder_weights_path = os.path.join(model_dir, 'cnn_encoder.weights.h5')
    if not os.path.exists(encoder_weights_path):
        raise FileNotFoundError(
            f"Error: File bobot encoder '{encoder_weights_path}' tidak ditemukan.")
    encoder.load_weights(encoder_weights_path)
    print("Bobot CNN_Encoder berhasil dimuat.")

    decoder_weights_path = os.path.join(model_dir, 'rnn_decoder.weights.h5')
    if not os.path.exists(decoder_weights_path):
        raise FileNotFoundError(
            f"Error: File bobot decoder '{decoder_weights_path}' tidak ditemukan.")
    decoder.load_weights(decoder_weights_path)
    print("Bobot RNN_Decoder berhasil dimuat.")

    print("Semua aset model berhasil dimuat.")
    return encoder, decoder, tokenizer, image_features_extract_model, config


def main(args):
    model_dir = args.model_dir
    image_path = args.image_path

    if not os.path.exists(model_dir):
        print(f"Error: Direktori model '{model_dir}' tidak ditemukan.")
        return
    if not os.path.exists(image_path):
        print(f"Error: File gambar '{image_path}' tidak ditemukan.")
        return

    print("Memuat konfigurasi model...")
    with open(os.path.join(model_dir, 'model_config.json'), 'r') as f:
        config = json.load(f)

    embedding_dim = config['embedding_dim']
    units = config['units']
    vocab_size = config['vocab_size']
    features_shape = config['features_shape']  # e.g. 2048 (output Inception)
    # e.g. 64 (8x8)
    attention_features_shape = config['attention_features_shape']

    print("Memuat tokenizer...")
    with open(os.path.join(model_dir, 'tokenizer.pickle'), 'rb') as handle:
        tokenizer = pickle.load(handle)

    print("Membuat instance model CNN_Encoder dan RNN_Decoder...")
    encoder = CNN_Encoder(embedding_dim)
    decoder = RNN_Decoder(embedding_dim, units, vocab_size)

    print("Memuat InceptionV3 feature extractor...")
    inception_model_path = os.path.join(
        model_dir, 'inception_feature_extractor.keras')
    if not os.path.exists(inception_model_path):
        print(
            f"Error: File Inception model '{inception_model_path}' tidak ditemukan.")
        return
    image_features_extract_model = tf.keras.models.load_model(
        inception_model_path)
    print("InceptionV3 feature extractor berhasil dimuat.")

    # "Build" models sebelum memuat bobot (dengan input dummy)
    print("Membangun CNN_Encoder...")
    dummy_encoder_input = tf.random.uniform(
        shape=[1, attention_features_shape, features_shape])
    _ = encoder(dummy_encoder_input, training=False)

    print("Membangun RNN_Decoder...")
    dummy_decoder_token_input = tf.zeros(shape=[1, 1], dtype=tf.int32)
    dummy_decoder_features_input = tf.random.uniform(
        shape=[1, attention_features_shape, embedding_dim])
    dummy_hidden_state = decoder.reset_state(batch_size=1)
    _ = decoder(dummy_decoder_token_input, dummy_decoder_features_input,
                dummy_hidden_state, training=False)

    print("Memuat bobot CNN_Encoder...")
    encoder_weights_path = os.path.join(model_dir, 'cnn_encoder.weights.h5')
    if not os.path.exists(encoder_weights_path):
        print(
            f"Error: File bobot encoder '{encoder_weights_path}' tidak ditemukan.")
        return
    encoder.load_weights(encoder_weights_path)
    print("Bobot CNN_Encoder berhasil dimuat.")

    print("Memuat bobot RNN_Decoder...")
    decoder_weights_path = os.path.join(model_dir, 'rnn_decoder.weights.h5')
    if not os.path.exists(decoder_weights_path):
        print(
            f"Error: File bobot decoder '{decoder_weights_path}' tidak ditemukan.")
        return
    decoder.load_weights(decoder_weights_path)
    print("Bobot RNN_Decoder berhasil dimuat.")

    print(f"\nMenghasilkan caption untuk gambar: {image_path}")
    caption, attention_plot = generate_caption(
        image_path,
        image_features_extract_model,
        encoder,
        decoder,
        tokenizer,
        config
    )

    print("\nPredicted Caption:")
    print(caption)

    if args.show_attention:
        print("\nMenampilkan plot attention...")
        # Hapus <start> dan <end> jika ada untuk plotting
        plot_caption_tokens = [word for word in caption.split() if word not in [
            '<start>', '<end>']]
        plot_attention(image_path, ' '.join(
            plot_caption_tokens), attention_plot)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Image Captioning Prediction Script")
    parser.add_argument('--model_dir', type=str,
                        default='image_captioning_model_assets',
                        help='Direktori tempat model dan tokenizer disimpan.')
    parser.add_argument('--image_path', type=str, required=True,
                        help='Path ke gambar yang akan diberi caption.')
    parser.add_argument('--show_attention', action='store_true',
                        help='Tampilkan plot attention (membutuhkan matplotlib).')

    # Nonaktifkan GPU jika ada masalah, atau biarkan TensorFlow yang memilih
    # os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    # print(f"TensorFlow version: {tf.__version__}")
    # gpus = tf.config.experimental.list_physical_devices('GPU')
    # if gpus:
    #     try:
    #         for gpu in gpus:
    #             tf.config.experimental.set_memory_growth(gpu, True)
    #         print(len(gpus), "Physical GPUs")
    #     except RuntimeError as e:
    #         print(e)

    parsed_args = parser.parse_args()
    main(parsed_args)
