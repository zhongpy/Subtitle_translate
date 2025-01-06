from flask import Flask, request, jsonify
import logging
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
import os

app = Flask(__name__)

# 配置日志记录
logging.basicConfig(
    filename="backend.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 模型目录和名称
MODEL_NAME = "facebook/nllb-200-3.3B"
MODEL_DIR = "./models/facebook_nllb"

# 全局变量
tokenizer = None
model = None

def download_and_load_model():
    global tokenizer, model
    try:
        if not os.path.exists(MODEL_DIR):
            logger.info("Model not found locally. Downloading...")
            os.makedirs(MODEL_DIR, exist_ok=True)
            tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, cache_dir=MODEL_DIR)
            model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME, cache_dir=MODEL_DIR)
            logger.info("Model downloaded and loaded successfully.")
        else:
            logger.info("Model found locally. Loading...")
            tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
            model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_DIR)
            logger.info("Model loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to download/load model: {e}")
        raise

def translate_batch(texts, src_lang='zh', tgt_lang='en'):
    try:
        inputs = tokenizer(texts, return_tensors="pt", padding=True, truncation=True, max_length=512)
        generation_args = {
            "num_beams": 4,
            "max_length": 512,
            "no_repeat_ngram_size": 3,
            "early_stopping": True,
        }
        src_lang_code = f"{src_lang}_X"
        tgt_lang_code = f"{tgt_lang}_X"

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                forced_bos_token_id=tokenizer.get_lang_id(tgt_lang_code),
                **generation_args
            )
        return [tokenizer.decode(output, skip_special_tokens=True) for output in outputs]
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return [str(e)]

@app.route('/translate', methods=['POST'])
def translate():
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({"error": "Invalid request"}), 400

    texts = data['content']
    if not isinstance(texts, list):
        return jsonify({"error": "Content must be a list of sentences."}), 400

    logger.info(f"Received translation request with {len(texts)} sentences.")
    translated_texts = translate_batch(texts)
    return jsonify({"translated": translated_texts})

if __name__ == '__main__':
    logger.info("Starting translation server...")
    download_and_load_model()
    app.run(host='0.0.0.0', port=5000)
