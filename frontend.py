import os
import re
import requests
import logging
from pathlib import Path
import math

TRANSLATION_SERVER_URL = "http://127.0.0.1:5000/translate"
LOG_DIR = Path("./logs")
TRANSLATED_LOG_PATH = LOG_DIR / "translated.log"

# 配置日志记录
logging.basicConfig(
    filename="frontend.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 创建日志目录
LOG_DIR.mkdir(exist_ok=True)

def extract_subtitles(file_path):
    subtitles = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        if '-->' in line or line.strip().isdigit():
            continue
        subtitles.append(line.strip())
    return subtitles, lines

def generate_translated_srt(original_lines, translated_subtitles, output_path):
    idx = 0
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in original_lines:
            if '-->' in line or line.strip().isdigit():
                f.write(line)
            elif line.strip():
                f.write(translated_subtitles[idx] + '\n')
                idx += 1
            else:
                f.write('\n')
    logger.info(f"Translated file written to: {output_path}")

def batch_translate(texts, batch_size=100):
    num_batches = math.ceil(len(texts) / batch_size)
    translated_texts = []

    for i in range(num_batches):
        batch = texts[i * batch_size:(i + 1) * batch_size]
        logger.info(f"Translating batch {i + 1}/{num_batches}...")
        response = requests.post(TRANSLATION_SERVER_URL, json={"content": batch})

        if response.status_code != 200:
            logger.error(f"Batch translation failed: {response.text}")
            continue

        translated_texts.extend(response.json().get("translated", []))
    return translated_texts

def process_file(file_path, batch_size=100):
    subtitles, original_lines = extract_subtitles(file_path)
    translated_subtitles = batch_translate(subtitles, batch_size)
    output_path = file_path.replace("zh_hans", "en")
    generate_translated_srt(original_lines, translated_subtitles, output_path)

def process_all_files(folder_path, batch_size=100):
    folder_path = Path(folder_path)
    for serial_folder in folder_path.iterdir():
        if serial_folder.is_dir():
            zh_folder = serial_folder / "zh_hans"
            en_folder = serial_folder / "en"
            en_folder.mkdir(exist_ok=True)

            for srt_file in zh_folder.glob("*.srt"):
                process_file(srt_file, batch_size)

if __name__ == "__main__":
    folder_to_process = "AllSerials"
    logger.info(f"Starting batch subtitle processing in folder: {folder_to_process}")
    process_all_files(folder_to_process, batch_size=100)
    logger.info("Batch subtitle processing completed.")
